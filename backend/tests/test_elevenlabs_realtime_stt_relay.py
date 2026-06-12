import asyncio
import json
from typing import Any

from backend.app.schemas.game_turn import RealtimeTranscriptClientEvent
from backend.app.services.service_c.elevenlabs_realtime_stt_relay import ElevenLabsRealtimeSttRelay
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
            "previous_text": "",
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
