from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Protocol, cast
from urllib.parse import urlencode

import websockets
from websockets.exceptions import WebSocketException

from backend.app.schemas.game_turn import (
    RealtimeSubtitlePayload,
    RealtimeTranscriptClientEvent,
    RealtimeTranscriptServerEvent,
)
from backend.app.services.service_c.settings_service import AppSettings, get_settings


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
    ) -> None:
        self.settings = settings or get_settings()
        self.websocket_connect = websocket_connect or cast(WebSocketConnect, websockets.connect)
        self.connection: ProviderWebSocket | None = None

    async def start(self, event: RealtimeTranscriptClientEvent) -> list[RealtimeTranscriptServerEvent]:
        if not self.settings.elevenlabs_api_key:
            raise ElevenLabsRealtimeRelayError("ELEVENLABS_API_KEY is required for ElevenLabs realtime STT relay.")

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

        try:
            await self.connection.send(
                json.dumps(
                    {
                        "message_type": "input_audio_chunk",
                        "audio_base_64": event.audio_base64,
                        "commit": event.commit,
                        "sample_rate": event.sample_rate_hz or 16000,
                        "previous_text": event.previous_text or "",
                    }
                )
            )
        except (OSError, TimeoutError, WebSocketException) as exc:
            raise ElevenLabsRealtimeRelayError(f"ElevenLabs realtime STT audio send failed: {exc}") from exc

        return await self._drain_provider_events(event)

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

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

    async def _drain_provider_events(
        self,
        context_event: RealtimeTranscriptClientEvent,
        *,
        max_events: int | None = None,
    ) -> list[RealtimeTranscriptServerEvent]:
        if self.connection is None:
            return []

        events: list[RealtimeTranscriptServerEvent] = []
        while max_events is None or len(events) < max_events:
            try:
                raw_payload = await asyncio.wait_for(
                    self.connection.recv(),
                    timeout=self.settings.elevenlabs_realtime_receive_timeout_s,
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

            events.append(_provider_payload_to_event(context_event, provider_payload))

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


def _elevenlabs_language_code(language_hint: str | None) -> str | None:
    if not language_hint:
        return None

    return language_hint.split("-", maxsplit=1)[0].lower()
