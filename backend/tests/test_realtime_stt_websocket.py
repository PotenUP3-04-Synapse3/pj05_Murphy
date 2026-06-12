from fastapi.testclient import TestClient

import backend.app.api.ai_respond as ai_respond_api
from backend.app.main import app


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
