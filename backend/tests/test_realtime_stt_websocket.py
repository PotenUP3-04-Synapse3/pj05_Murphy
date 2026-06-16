import json
from typing import Any, cast

import anyio
from fastapi import WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import backend.app.api.ai_respond as ai_respond_api
from backend.app.main import app
from backend.app.services.service_c.settings_service import get_settings


client = TestClient(app)


def _session_start_event() -> dict[str, object]:
    return {
        "contract_version": "dev_c_realtime_stt.v1",
        "event_type": "session_start",
        "request_id": "req_realtime_0001",
        "session_id": "session_realtime_001",
        "turn_index": 3,
        "sequence": 0,
        "chapter_id": "CH0_IMMIGRATION",
        "scene_id": "JFK_IMMIGRATION_HALL",
        "current_node_id": "IMM_003_DURATION",
        "provider": "stt_provider_websocket",
        "language_hint": "en-US",
    }


def test_realtime_stt_websocket_echoes_partial_transcript_for_unreal_subtitles() -> None:
    with client.websocket_connect("/api/game/ai/stt/stream") as websocket:
        websocket.send_json(_session_start_event())

        started = websocket.receive_json()
        assert started["contract_version"] == "dev_c_realtime_stt.v1"
        assert started["event_type"] == "session_started"
        assert started["request_id"] == "req_realtime_0001"
        assert started["session_id"] == "session_realtime_001"

        websocket.send_json(
            {
                "contract_version": "dev_c_realtime_stt.v1",
                "event_type": "partial_transcript",
                "request_id": "req_realtime_0001",
                "session_id": "session_realtime_001",
                "turn_index": 3,
                "sequence": 1,
                "transcript": "I will stay",
                "confidence": 0.72,
                "language_detected": "en-US",
                "provider": "stt_provider_websocket",
            }
        )

        partial = websocket.receive_json()
        assert partial["event_type"] == "partial_transcript"
        assert partial["request_id"] == "req_realtime_0001"
        assert partial["sequence"] == 1
        assert partial["committed"] is False
        assert partial["subtitle"] == {
            "text": "I will stay",
            "is_final": False,
            "display_mode": "replace",
        }


def test_realtime_stt_websocket_marks_final_transcript_as_committed() -> None:
    with client.websocket_connect("/api/game/ai/stt/stream") as websocket:
        websocket.send_json(_session_start_event())
        websocket.receive_json()

        websocket.send_json(
            {
                "contract_version": "dev_c_realtime_stt.v1",
                "event_type": "final_transcript",
                "request_id": "req_realtime_0001",
                "session_id": "session_realtime_001",
                "turn_index": 3,
                "sequence": 2,
                "transcript": "I will stay for five days.",
                "confidence": 0.91,
                "language_detected": "en-US",
                "provider": "stt_provider_websocket",
            }
        )

        final = websocket.receive_json()
        assert final["event_type"] == "final_transcript"
        assert final["sequence"] == 2
        assert final["committed"] is True
        assert final["target_endpoint"] == "POST /api/game/ai/respond"
        assert final["subtitle"] == {
            "text": "I will stay for five days.",
            "is_final": True,
            "display_mode": "replace",
        }


def test_realtime_stt_websocket_returns_contract_error_for_invalid_event() -> None:
    with client.websocket_connect("/api/game/ai/stt/stream") as websocket:
        websocket.send_json(
            {
                "contract_version": "wrong",
                "event_type": "partial_transcript",
                "request_id": "req_realtime_0001",
                "session_id": "session_realtime_001",
                "turn_index": 3,
                "sequence": 1,
                "transcript": "Hello",
            }
        )

        error = websocket.receive_json()
        assert error["contract_version"] == "dev_c_realtime_stt.v1"
        assert error["event_type"] == "contract_error"
        assert error["request_id"] == "req_realtime_0001"
        assert "contract_version" in error["error_message"]


def test_realtime_stt_websocket_relays_audio_chunks_through_elevenlabs(monkeypatch) -> None:
    class FakeRelay:
        def __init__(self) -> None:
            self.audio_chunks: list[str] = []

        async def start(self, event):
            return [
                {
                    "contract_version": "dev_c_realtime_stt.v1",
                    "event_type": "session_started",
                    "request_id": event.request_id,
                    "session_id": event.session_id,
                    "turn_index": event.turn_index,
                    "sequence": event.sequence,
                    "provider": "elevenlabs_relay",
                }
            ]

        async def send_audio_chunk(self, event):
            self.audio_chunks.append(event.audio_base64)
            return [
                {
                    "contract_version": "dev_c_realtime_stt.v1",
                    "event_type": "partial_transcript",
                    "request_id": event.request_id,
                    "session_id": event.session_id,
                    "turn_index": event.turn_index,
                    "sequence": event.sequence,
                    "provider": "elevenlabs_relay",
                    "subtitle": {
                        "text": "I will stay",
                        "is_final": False,
                        "display_mode": "replace",
                    },
                    "committed": False,
                },
                {
                    "contract_version": "dev_c_realtime_stt.v1",
                    "event_type": "final_transcript",
                    "request_id": event.request_id,
                    "session_id": event.session_id,
                    "turn_index": event.turn_index,
                    "sequence": event.sequence,
                    "provider": "elevenlabs_relay",
                    "subtitle": {
                        "text": "I will stay for five days.",
                        "is_final": True,
                        "display_mode": "replace",
                    },
                    "committed": True,
                    "target_endpoint": "POST /api/game/ai/respond",
                },
            ]

        async def close(self) -> None:
            return None

    fake_relay = FakeRelay()
    monkeypatch.setattr(ai_respond_api, "_build_elevenlabs_realtime_relay", lambda: fake_relay)

    with client.websocket_connect("/api/game/ai/stt/stream") as websocket:
        start_event = _session_start_event()
        start_event["provider"] = "elevenlabs_relay"
        websocket.send_json(start_event)

        started = websocket.receive_json()
        assert started["event_type"] == "session_started"
        assert started["provider"] == "elevenlabs_relay"

        websocket.send_json(
            {
                "contract_version": "dev_c_realtime_stt.v1",
                "event_type": "audio_chunk",
                "request_id": "req_realtime_0001",
                "session_id": "session_realtime_001",
                "turn_index": 3,
                "sequence": 1,
                "provider": "elevenlabs_relay",
                "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
                "commit": True,
                "sample_rate_hz": 16000,
            }
        )

        partial = websocket.receive_json()
        final = websocket.receive_json()
        assert fake_relay.audio_chunks == ["UklGRiQAAABXQVZFZm10IBAAAAABAAEA"]
        assert partial["event_type"] == "partial_transcript"
        assert partial["subtitle"]["text"] == "I will stay"
        assert partial["committed"] is False
        assert final["event_type"] == "final_transcript"
        assert final["subtitle"]["text"] == "I will stay for five days."
        assert final["committed"] is True


def test_realtime_stt_websocket_appends_debug_agent_run_log_for_stt_session(tmp_path, monkeypatch) -> None:
    class FakeRelay:
        async def start(self, event):
            return [
                {
                    "contract_version": "dev_c_realtime_stt.v1",
                    "event_type": "session_started",
                    "request_id": event.request_id,
                    "session_id": event.session_id,
                    "turn_index": event.turn_index,
                    "sequence": event.sequence,
                    "provider": "elevenlabs_relay",
                }
            ]

        async def send_audio_chunk(self, event):
            return [
                {
                    "contract_version": "dev_c_realtime_stt.v1",
                    "event_type": "final_transcript",
                    "request_id": event.request_id,
                    "session_id": event.session_id,
                    "turn_index": event.turn_index,
                    "sequence": event.sequence,
                    "provider": "elevenlabs_relay",
                    "subtitle": {
                        "text": "I will stay for five days.",
                        "is_final": True,
                        "display_mode": "replace",
                    },
                    "committed": True,
                    "target_endpoint": "POST /api/game/ai/respond",
                }
            ]

        async def close(self) -> None:
            return None

    monkeypatch.setattr(ai_respond_api, "_build_elevenlabs_realtime_relay", lambda: FakeRelay())
    monkeypatch.setattr(ai_respond_api, "AGENT_RUN_LOG_ROOT", tmp_path)
    monkeypatch.setenv("MURPHY_STT_DEBUG_LOG_MODE", "debug")
    monkeypatch.setenv("ELEVENLABS_REALTIME_ESTIMATED_COST_PER_MINUTE_USD", "0.006")
    get_settings.cache_clear()

    try:
        with client.websocket_connect("/api/game/ai/stt/stream") as websocket:
            start_event = _session_start_event()
            start_event["provider"] = "elevenlabs_relay"
            websocket.send_json(start_event)
            websocket.receive_json()

            websocket.send_json(
                {
                    "contract_version": "dev_c_realtime_stt.v1",
                    "event_type": "audio_chunk",
                    "request_id": "req_realtime_0001",
                    "session_id": "session_realtime_001",
                    "turn_index": 3,
                    "sequence": 1,
                    "provider": "elevenlabs_relay",
                    "audio_base64": "AQIDBA==",
                    "commit": True,
                    "sample_rate_hz": 16000,
                }
            )
            websocket.receive_json()
    finally:
        get_settings.cache_clear()

    records = [
        json.loads(line)
        for line in (tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    record = records[0]
    assert record["schema_version"] == "unified_agent_run.v1"
    assert record["agent_name"] == "realtime_stt_relay"
    assert record["owner"] == "developer_c"
    assert record["request_id"] == "req_realtime_0001"
    assert record["session_id"] == "session_realtime_001"
    assert record["model"]["model_name"] == "elevenlabs_realtime_stt"
    assert record["model"]["input_tokens"] == 0
    assert record["model"]["output_tokens"] == 0
    assert record["summary"]["output"]["final_transcript"] == "I will stay for five days."
    assert record["metadata"]["debug_scope"] == "developer_c_realtime_stt"
    assert record["metadata"]["audio"]["chunk_count"] == 1
    assert record["metadata"]["audio"]["total_audio_bytes"] == 4
    assert record["metadata"]["cost"]["estimated_cost_usd"] >= 0
    assert "ELEVENLABS_API_KEY" not in json.dumps(record)

    markdown = (tmp_path / "unified_agent_runs.md").read_text(encoding="utf-8")
    assert "## Agent Run: realtime_stt_relay / developer_c" in markdown


def test_realtime_stt_send_events_handles_client_disconnect_without_server_error() -> None:
    class DisconnectingWebSocket:
        def __init__(self) -> None:
            self.sent_payloads: list[dict[str, object]] = []

        async def send_json(self, payload: dict[str, object]) -> None:
            self.sent_payloads.append(payload)
            raise WebSocketDisconnect(code=1006)

    disconnecting_websocket = DisconnectingWebSocket()
    websocket = cast(WebSocket, disconnecting_websocket)
    events: list[dict[str, Any]] = [
        {
            "contract_version": "dev_c_realtime_stt.v1",
            "event_type": "partial_transcript",
            "request_id": "req_realtime_0001",
            "session_id": "session_realtime_001",
            "turn_index": 3,
            "sequence": 1,
            "provider": "elevenlabs_relay",
        }
    ]

    result = anyio.run(
        ai_respond_api._send_realtime_events,
        websocket,
        events,
    )

    assert result is False
    assert disconnecting_websocket.sent_payloads[0]["event_type"] == "partial_transcript"


def test_realtime_stt_stream_handles_client_close_before_first_message() -> None:
    class ClosedBeforeMessageWebSocket:
        def __init__(self) -> None:
            self.accepted = False

        async def accept(self) -> None:
            self.accepted = True

        async def receive_json(self) -> dict[str, object]:
            raise RuntimeError('WebSocket is not connected. Need to call "accept" first.')

    closed_websocket = ClosedBeforeMessageWebSocket()

    result = anyio.run(
        ai_respond_api.realtime_stt_stream,
        cast(WebSocket, closed_websocket),
    )

    assert result is None
    assert closed_websocket.accepted is True
