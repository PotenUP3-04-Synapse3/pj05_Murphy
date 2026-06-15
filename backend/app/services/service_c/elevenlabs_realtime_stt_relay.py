"""Relay Unreal audio chunks to ElevenLabs realtime STT.

Beginner guide:
Unreal connects to Developer C, not directly to ElevenLabs.  This class opens
the server-side ElevenLabs WebSocket using the backend API key, forwards base64
PCM chunks, converts provider messages into Developer C subtitle events, and
uses local batch STT as a final-transcript fallback when a committed provider
final is missing.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import wave
from io import BytesIO
from typing import Any, Awaitable, Callable, Protocol, cast
from urllib.parse import urlencode

import websockets
from websockets.exceptions import WebSocketException

from backend.app.schemas.game_turn import (
    AudioMetadata,
    MockAudioInput,
    RealtimeSubtitlePayload,
    RealtimeTranscriptClientEvent,
    RealtimeTranscriptServerEvent,
)
from backend.app.services.service_c.settings_service import AppSettings, get_settings
from backend.app.services.service_c.stt_service import LocalWhisperLargeV3TurboRuntime, SttRuntime


class ElevenLabsRealtimeRelayError(RuntimeError):
    pass


class ProviderWebSocket(Protocol):
    async def recv(self) -> str: ...

    async def send(self, payload: str) -> None: ...

    async def close(self) -> None: ...


WebSocketConnect = Callable[..., Awaitable[ProviderWebSocket]]


class ElevenLabsRealtimeSttRelay:
    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        websocket_connect: WebSocketConnect | None = None,
        local_batch_fallback: SttRuntime | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.websocket_connect = websocket_connect or cast(WebSocketConnect, websockets.connect)
        self.local_batch_fallback = local_batch_fallback or LocalWhisperLargeV3TurboRuntime(settings=self.settings)
        self.connection: ProviderWebSocket | None = None
        self._audio_chunks: list[bytes] = []
        self._sample_rate_hz = 16000
        self._sent_audio_chunk_count = 0

    async def start(self, event: RealtimeTranscriptClientEvent) -> list[RealtimeTranscriptServerEvent]:
        if not self.settings.elevenlabs_api_key:
            raise ElevenLabsRealtimeRelayError("ELEVENLABS_API_KEY is required for ElevenLabs realtime STT relay.")

        self._audio_chunks = []
        self._sample_rate_hz = event.sample_rate_hz or 16000
        self._sent_audio_chunk_count = 0

        try:
            self.connection = await self.websocket_connect(
                self._build_realtime_url(event),
                additional_headers={"xi-api-key": self.settings.elevenlabs_api_key},
            )
        except (OSError, TimeoutError, WebSocketException) as exc:
            raise ElevenLabsRealtimeRelayError(f"ElevenLabs realtime STT connection failed: {exc}") from exc

        return await self._drain_provider_events(event, max_events=1)

    async def send_audio_chunk(self, event: RealtimeTranscriptClientEvent) -> list[RealtimeTranscriptServerEvent]:
        if self.connection is None:
            raise ElevenLabsRealtimeRelayError("ElevenLabs realtime STT relay is not connected.")

        audio_chunk = _decode_audio_chunk(event)
        self._audio_chunks.append(audio_chunk)
        self._sample_rate_hz = event.sample_rate_hz or self._sample_rate_hz

        provider_payload: dict[str, Any] = {
            "message_type": "input_audio_chunk",
            "audio_base_64": event.audio_base64,
            "commit": event.commit,
            "sample_rate": event.sample_rate_hz or 16000,
        }
        if self._sent_audio_chunk_count == 0 and event.previous_text and event.previous_text.strip():
            provider_payload["previous_text"] = event.previous_text

        try:
            await self.connection.send(json.dumps(provider_payload))
            self._sent_audio_chunk_count += 1
        except (OSError, TimeoutError, WebSocketException) as exc:
            if event.commit:
                return [
                    self._local_batch_fallback_or_error_event(
                        event,
                        reason=f"ElevenLabs realtime STT audio send failed: {exc}",
                    )
                ]
            raise ElevenLabsRealtimeRelayError(f"ElevenLabs realtime STT audio send failed: {exc}") from exc

        events = await self._drain_provider_events(
            event,
            timeout_s=self.settings.elevenlabs_realtime_commit_timeout_s
            if event.commit
            else self.settings.elevenlabs_realtime_receive_timeout_s,
            stop_after_final=event.commit,
        )
        if event.commit and not _has_final_transcript(events):
            events.append(self._local_batch_fallback_or_error_event(event, reason="provider_final_transcript_missing"))

        return events

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
        self._audio_chunks = []
        self._sent_audio_chunk_count = 0

    def _build_realtime_url(self, event: RealtimeTranscriptClientEvent) -> str:
        query: dict[str, str] = {
            "model_id": self.settings.elevenlabs_realtime_stt_model,
            "audio_format": self.settings.elevenlabs_realtime_audio_format,
            "commit_strategy": self.settings.elevenlabs_realtime_commit_strategy,
        }
        language_code = _elevenlabs_language_code(event.language_hint)
        if language_code:
            query["language_code"] = language_code

        return f"{self.settings.elevenlabs_realtime_stt_endpoint}?{urlencode(query)}"

    def _local_batch_fallback_or_error_event(
        self,
        context_event: RealtimeTranscriptClientEvent,
        *,
        reason: str,
    ) -> RealtimeTranscriptServerEvent:
        try:
            return self._local_batch_fallback_event(context_event, reason=reason)
        except Exception as exc:
            return RealtimeTranscriptServerEvent(
                event_type="provider_error",
                request_id=context_event.request_id,
                session_id=context_event.session_id,
                turn_index=context_event.turn_index,
                sequence=context_event.sequence,
                provider="local_batch_fallback",
                error_message=f"{reason}; local batch fallback failed: {exc}",
            )

    def _local_batch_fallback_event(
        self,
        context_event: RealtimeTranscriptClientEvent,
        *,
        reason: str,
    ) -> RealtimeTranscriptServerEvent:
        wav_bytes = _pcm_chunks_to_wav(
            self._audio_chunks,
            sample_rate_hz=self._sample_rate_hz,
        )
        audio_metadata = AudioMetadata(
            mime_type="audio/wav",
            sample_rate_hz=self._sample_rate_hz,
            channels=1,
            duration_ms=_audio_duration_ms(
                audio_bytes=sum(len(chunk) for chunk in self._audio_chunks),
                sample_rate_hz=self._sample_rate_hz,
            ),
            language_hint=context_event.language_hint,
        )
        transcript = self.local_batch_fallback.transcribe_wav(
            MockAudioInput(
                mock_wav_path="samples/realtime_fallback.wav",
                file_name="realtime_fallback.wav",
                content_type="audio/wav",
                audio_bytes=wav_bytes,
            ),
            audio_metadata,
        )
        return RealtimeTranscriptServerEvent(
            event_type="final_transcript",
            request_id=context_event.request_id,
            session_id=context_event.session_id,
            turn_index=context_event.turn_index,
            sequence=context_event.sequence,
            provider="local_batch_fallback",
            subtitle=RealtimeSubtitlePayload(text=transcript, is_final=True),
            committed=True,
            target_endpoint="POST /api/game/ai/respond",
            error_message=reason,
        )

    async def _drain_provider_events(
        self,
        context_event: RealtimeTranscriptClientEvent,
        *,
        max_events: int | None = None,
        timeout_s: float | None = None,
        stop_after_final: bool = False,
    ) -> list[RealtimeTranscriptServerEvent]:
        if self.connection is None:
            return []

        events: list[RealtimeTranscriptServerEvent] = []
        event_timeout_s = timeout_s or self.settings.elevenlabs_realtime_receive_timeout_s
        while max_events is None or len(events) < max_events:
            try:
                raw_payload = await asyncio.wait_for(
                    self.connection.recv(),
                    timeout=event_timeout_s,
                )
            except TimeoutError:
                break
            except (OSError, WebSocketException) as exc:
                events.append(
                    _provider_error_event(
                        context_event,
                        error_message=f"ElevenLabs realtime STT receive failed: {exc}",
                    )
                )
                break

            try:
                provider_payload = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                events.append(
                    _provider_error_event(
                        context_event,
                        error_message=f"ElevenLabs realtime STT returned non-JSON message: {exc.msg}",
                    )
                )
                continue

            event = _provider_payload_to_event(context_event, provider_payload)
            events.append(event)
            if stop_after_final and event.event_type == "final_transcript":
                break

        return events


def _provider_payload_to_event(
    context_event: RealtimeTranscriptClientEvent,
    provider_payload: dict[str, Any],
) -> RealtimeTranscriptServerEvent:
    message_type = provider_payload.get("message_type")
    text = str(provider_payload.get("text") or "").strip()

    if message_type == "session_started":
        return RealtimeTranscriptServerEvent(
            event_type="session_started",
            request_id=context_event.request_id,
            session_id=context_event.session_id,
            turn_index=context_event.turn_index,
            sequence=context_event.sequence,
            provider="elevenlabs_relay",
        )

    if message_type == "partial_transcript":
        return RealtimeTranscriptServerEvent(
            event_type="partial_transcript",
            request_id=context_event.request_id,
            session_id=context_event.session_id,
            turn_index=context_event.turn_index,
            sequence=context_event.sequence,
            provider="elevenlabs_relay",
            subtitle=RealtimeSubtitlePayload(text=text, is_final=False),
            committed=False,
        )

    if message_type in {"committed_transcript", "committed_transcript_with_timestamps"}:
        return RealtimeTranscriptServerEvent(
            event_type="final_transcript",
            request_id=context_event.request_id,
            session_id=context_event.session_id,
            turn_index=context_event.turn_index,
            sequence=context_event.sequence,
            provider="elevenlabs_relay",
            subtitle=RealtimeSubtitlePayload(text=text, is_final=True),
            committed=True,
            target_endpoint="POST /api/game/ai/respond",
        )

    return _provider_error_event(
        context_event,
        error_message=f"Unsupported ElevenLabs realtime STT message_type: {message_type}",
    )


def _provider_error_event(
    context_event: RealtimeTranscriptClientEvent,
    *,
    error_message: str,
) -> RealtimeTranscriptServerEvent:
    return RealtimeTranscriptServerEvent(
        event_type="provider_error",
        request_id=context_event.request_id,
        session_id=context_event.session_id,
        turn_index=context_event.turn_index,
        sequence=context_event.sequence,
        provider="elevenlabs_relay",
        error_message=error_message,
    )


def _decode_audio_chunk(event: RealtimeTranscriptClientEvent) -> bytes:
    if event.audio_base64 is None:
        raise ElevenLabsRealtimeRelayError("audio_base64 is required for realtime STT audio chunks.")

    try:
        return base64.b64decode(event.audio_base64, validate=True)
    except binascii.Error as exc:
        raise ElevenLabsRealtimeRelayError("audio_base64 must be valid base64 for realtime STT audio chunks.") from exc


def _has_final_transcript(events: list[RealtimeTranscriptServerEvent]) -> bool:
    return any(event.event_type == "final_transcript" for event in events)


def _pcm_chunks_to_wav(
    chunks: list[bytes],
    *,
    sample_rate_hz: int,
    channels: int = 1,
    sample_width_bytes: int = 2,
) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate_hz)
        wav_file.writeframes(b"".join(chunks))

    return buffer.getvalue()


def _audio_duration_ms(
    *,
    audio_bytes: int,
    sample_rate_hz: int,
    channels: int = 1,
    sample_width_bytes: int = 2,
) -> int:
    bytes_per_second = sample_rate_hz * channels * sample_width_bytes
    if bytes_per_second <= 0:
        return 0

    return round((audio_bytes / bytes_per_second) * 1000)


def _elevenlabs_language_code(language_hint: str | None) -> str | None:
    if not language_hint:
        return None

    return language_hint.split("-", maxsplit=1)[0].lower()
