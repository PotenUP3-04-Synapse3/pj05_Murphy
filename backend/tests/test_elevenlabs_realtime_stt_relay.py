import asyncio
import base64
import json
import wave
from io import BytesIO
from typing import Any

from backend.app.schemas.game_turn import RealtimeTranscriptClientEvent
from backend.app.services.service_c.elevenlabs_realtime_stt_relay import (
    ElevenLabsRealtimeRelayError,
    ElevenLabsRealtimeSttRelay,
)
from backend.app.services.service_c.settings_service import AppSettings


class FakeProviderConnection:
    def __init__(self, incoming: list[dict[str, Any]]) -> None:
        self.incoming = list(incoming)
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    async def recv(self) -> str:
        if self.incoming:
            return json.dumps(self.incoming.pop(0))

        await asyncio.sleep(10)
        return "{}"

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def close(self) -> None:
        self.closed = True


class FakeProviderConnector:
    def __init__(self, connection: FakeProviderConnection) -> None:
        self.connection = connection
        self.uri: str | None = None
        self.headers: dict[str, str] | None = None

    async def __call__(self, uri: str, *, additional_headers: dict[str, str]) -> FakeProviderConnection:
        self.uri = uri
        self.headers = additional_headers
        return self.connection


class FakeLocalBatchSttFallback:
    def __init__(self, transcript: str = "Local fallback transcript.") -> None:
        self.transcript = transcript
        self.calls: list[dict[str, Any]] = []

    def transcribe_wav(self, audio, audio_metadata):
        self.calls.append(
            {
                "file_name": audio.file_name,
                "content_type": audio.content_type,
                "audio_bytes": audio.audio_bytes,
                "audio_metadata": audio_metadata,
            }
        )
        return self.transcript


class FailingLocalBatchSttFallback:
    def transcribe_wav(self, audio, audio_metadata):
        raise RuntimeError("local stt unavailable")


class FailingProviderConnection(FakeProviderConnection):
    async def send(self, payload: str) -> None:
        raise OSError("provider send failed")


def _session_start_event() -> RealtimeTranscriptClientEvent:
    return RealtimeTranscriptClientEvent(
        contract_version="dev_c_realtime_stt.v1",
        event_type="session_start",
        request_id="req_relay_0001",
        session_id="session_relay_001",
        turn_index=4,
        sequence=0,
        provider="elevenlabs_relay",
        language_hint="en",
    )


def _audio_chunk_event() -> RealtimeTranscriptClientEvent:
    return RealtimeTranscriptClientEvent(
        contract_version="dev_c_realtime_stt.v1",
        event_type="audio_chunk",
        request_id="req_relay_0001",
        session_id="session_relay_001",
        turn_index=4,
        sequence=1,
        provider="elevenlabs_relay",
        audio_base64="UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
        commit=True,
        sample_rate_hz=16000,
        previous_text="",
    )


def _audio_chunk_event_from_pcm(
    *,
    pcm_bytes: bytes,
    sequence: int = 1,
    commit: bool = True,
) -> RealtimeTranscriptClientEvent:
    return RealtimeTranscriptClientEvent(
        contract_version="dev_c_realtime_stt.v1",
        event_type="audio_chunk",
        request_id="req_relay_0001",
        session_id="session_relay_001",
        turn_index=4,
        sequence=sequence,
        provider="elevenlabs_relay",
        audio_base64=base64.b64encode(pcm_bytes).decode("ascii"),
        commit=commit,
        sample_rate_hz=16000,
        previous_text="",
    )


def test_elevenlabs_relay_connects_with_server_side_api_key_and_maps_session_started() -> None:
    connection = FakeProviderConnection(
        incoming=[
            {
                "message_type": "session_started",
                "session_id": "provider_session_001",
            }
        ]
    )
    connector = FakeProviderConnector(connection)
    relay = ElevenLabsRealtimeSttRelay(
        settings=AppSettings(
            elevenlabs_api_key="xi-secret-test",
            elevenlabs_realtime_stt_endpoint="wss://example.test/v1/speech-to-text/realtime",
        ),
        websocket_connect=connector,
    )

    events = asyncio.run(relay.start(_session_start_event()))

    assert connector.uri is not None
    assert connector.uri.startswith("wss://example.test/v1/speech-to-text/realtime?")
    assert "model_id=scribe_v2_realtime" in connector.uri
    assert "audio_format=pcm_16000" in connector.uri
    assert "commit_strategy=manual" in connector.uri
    assert connector.headers == {"xi-api-key": "xi-secret-test"}
    assert events[0].event_type == "session_started"
    assert events[0].provider == "elevenlabs_relay"
    assert "xi-secret-test" not in events[0].model_dump_json()


def test_elevenlabs_relay_sends_audio_chunk_and_maps_partial_and_committed_transcripts() -> None:
    connection = FakeProviderConnection(
        incoming=[
            {"message_type": "session_started", "session_id": "provider_session_001"},
            {"message_type": "partial_transcript", "text": "I will stay"},
            {"message_type": "committed_transcript", "text": "I will stay for five days."},
        ]
    )
    relay = ElevenLabsRealtimeSttRelay(
        settings=AppSettings(elevenlabs_api_key="xi-secret-test"),
        websocket_connect=FakeProviderConnector(connection),
    )
    asyncio.run(relay.start(_session_start_event()))

    events = asyncio.run(relay.send_audio_chunk(_audio_chunk_event()))

    assert connection.sent == [
        {
            "message_type": "input_audio_chunk",
            "audio_base_64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
            "commit": True,
            "sample_rate": 16000,
        }
    ]
    assert events[0].event_type == "partial_transcript"
    assert events[0].subtitle is not None
    assert events[0].subtitle.text == "I will stay"
    assert events[0].committed is False
    assert events[1].event_type == "final_transcript"
    assert events[1].subtitle is not None
    assert events[1].subtitle.text == "I will stay for five days."
    assert events[1].committed is True
    assert events[1].target_endpoint == "POST /api/game/ai/respond"


def test_elevenlabs_relay_sends_previous_text_only_on_first_audio_chunk_when_present() -> None:
    connection = FakeProviderConnection(
        incoming=[
            {"message_type": "session_started", "session_id": "provider_session_001"},
            {"message_type": "partial_transcript", "text": "I will"},
            {"message_type": "partial_transcript", "text": "I will stay"},
        ]
    )
    relay = ElevenLabsRealtimeSttRelay(
        settings=AppSettings(
            elevenlabs_api_key="xi-secret-test",
            elevenlabs_realtime_receive_timeout_s=0.01,
        ),
        websocket_connect=FakeProviderConnector(connection),
    )
    asyncio.run(relay.start(_session_start_event()))

    first_chunk = _audio_chunk_event_from_pcm(pcm_bytes=b"\x01\x02" * 1600, sequence=1, commit=False)
    first_chunk.previous_text = "Officer asked how long I will stay."
    second_chunk = _audio_chunk_event_from_pcm(pcm_bytes=b"\x03\x04" * 1600, sequence=2, commit=False)
    second_chunk.previous_text = "Officer asked how long I will stay."

    asyncio.run(relay.send_audio_chunk(first_chunk))
    asyncio.run(relay.send_audio_chunk(second_chunk))

    assert connection.sent[0]["previous_text"] == "Officer asked how long I will stay."
    assert "previous_text" not in connection.sent[1]


def test_elevenlabs_relay_omits_blank_previous_text_from_audio_chunk_payload() -> None:
    connection = FakeProviderConnection(
        incoming=[
            {"message_type": "session_started", "session_id": "provider_session_001"},
            {"message_type": "committed_transcript", "text": "I will stay for five days."},
        ]
    )
    relay = ElevenLabsRealtimeSttRelay(
        settings=AppSettings(elevenlabs_api_key="xi-secret-test"),
        websocket_connect=FakeProviderConnector(connection),
    )
    asyncio.run(relay.start(_session_start_event()))

    asyncio.run(relay.send_audio_chunk(_audio_chunk_event()))

    assert "previous_text" not in connection.sent[0]


def test_elevenlabs_relay_uses_local_batch_fallback_on_committed_chunk_without_provider_final() -> None:
    connection = FakeProviderConnection(
        incoming=[
            {"message_type": "session_started", "session_id": "provider_session_001"},
        ]
    )
    local_fallback = FakeLocalBatchSttFallback("I will stay for five days.")
    relay = ElevenLabsRealtimeSttRelay(
        settings=AppSettings(
            elevenlabs_api_key="xi-secret-test",
            elevenlabs_realtime_receive_timeout_s=0.01,
        ),
        websocket_connect=FakeProviderConnector(connection),
        local_batch_fallback=local_fallback,
    )
    asyncio.run(relay.start(_session_start_event()))

    events = asyncio.run(relay.send_audio_chunk(_audio_chunk_event_from_pcm(pcm_bytes=b"\x01\x02" * 1600)))

    assert local_fallback.calls
    fallback_call = local_fallback.calls[0]
    assert fallback_call["content_type"] == "audio/wav"
    assert fallback_call["file_name"] == "realtime_fallback.wav"
    assert fallback_call["audio_bytes"].startswith(b"RIFF")
    with wave.open(BytesIO(fallback_call["audio_bytes"]), "rb") as wav_file:
        assert wav_file.getframerate() == 16000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
    assert events[-1].event_type == "final_transcript"
    assert events[-1].provider == "local_batch_fallback"
    assert events[-1].subtitle is not None
    assert events[-1].subtitle.text == "I will stay for five days."
    assert events[-1].committed is True
    assert events[-1].target_endpoint == "POST /api/game/ai/respond"


def test_elevenlabs_relay_returns_provider_error_when_local_batch_fallback_fails() -> None:
    connection = FakeProviderConnection(
        incoming=[
            {"message_type": "session_started", "session_id": "provider_session_001"},
        ]
    )
    relay = ElevenLabsRealtimeSttRelay(
        settings=AppSettings(
            elevenlabs_api_key="xi-secret-test",
            elevenlabs_realtime_receive_timeout_s=0.01,
        ),
        websocket_connect=FakeProviderConnector(connection),
        local_batch_fallback=FailingLocalBatchSttFallback(),
    )
    asyncio.run(relay.start(_session_start_event()))

    events = asyncio.run(relay.send_audio_chunk(_audio_chunk_event_from_pcm(pcm_bytes=b"\x01\x02" * 1600)))

    assert events[-1].event_type == "provider_error"
    assert events[-1].provider == "local_batch_fallback"
    assert events[-1].error_message is not None
    assert "local batch fallback failed" in events[-1].error_message


def test_elevenlabs_relay_uses_local_batch_fallback_when_provider_send_fails_on_commit() -> None:
    connection = FailingProviderConnection(
        incoming=[
            {"message_type": "session_started", "session_id": "provider_session_001"},
        ]
    )
    local_fallback = FakeLocalBatchSttFallback("Recovered locally.")
    relay = ElevenLabsRealtimeSttRelay(
        settings=AppSettings(elevenlabs_api_key="xi-secret-test"),
        websocket_connect=FakeProviderConnector(connection),
        local_batch_fallback=local_fallback,
    )
    asyncio.run(relay.start(_session_start_event()))

    events = asyncio.run(relay.send_audio_chunk(_audio_chunk_event_from_pcm(pcm_bytes=b"\x03\x04" * 1600)))

    assert local_fallback.calls
    assert events[-1].event_type == "final_transcript"
    assert events[-1].provider == "local_batch_fallback"
    assert events[-1].subtitle is not None
    assert events[-1].subtitle.text == "Recovered locally."


def test_elevenlabs_relay_raises_provider_error_when_send_fails_before_commit() -> None:
    connection = FailingProviderConnection(
        incoming=[
            {"message_type": "session_started", "session_id": "provider_session_001"},
        ]
    )
    relay = ElevenLabsRealtimeSttRelay(
        settings=AppSettings(elevenlabs_api_key="xi-secret-test"),
        websocket_connect=FakeProviderConnector(connection),
        local_batch_fallback=FakeLocalBatchSttFallback(),
    )
    asyncio.run(relay.start(_session_start_event()))

    try:
        asyncio.run(relay.send_audio_chunk(_audio_chunk_event_from_pcm(pcm_bytes=b"\x03\x04" * 1600, commit=False)))
    except ElevenLabsRealtimeRelayError as exc:
        assert "audio send failed" in str(exc)
    else:
        raise AssertionError("Expected ElevenLabsRealtimeRelayError")
