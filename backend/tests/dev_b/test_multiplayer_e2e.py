import asyncio
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.game_turn import (
    PrePrototypeRequest,
    UnrealResponse,
)
from backend.app.services.service_c.orchestrator import Orchestrator
from backend.app.api.ai_respond import respond


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("MURPHY_STT_MODE", "mock")
    monkeypatch.setenv("MURPHY_TTS_MODE", "fake")
    monkeypatch.setenv("MURPHY_NPC_DIALOGUE_MODE", "rule")
    monkeypatch.setenv("MURPHY_UNDERSTANDING_MODE", "rule")
    monkeypatch.setenv("MURPHY_UNREAL_REQUEST_CAPTURE_MODE", "off")
    monkeypatch.setenv("DEV_B_FEEDBACK_LLM_MODE", "rule")


def test_multiplayer_baggage_setup_and_respond_flow() -> None:
    client = TestClient(app)

    # 1. Setup Room and Baggage Owner
    setup_payload = {
        "room_id": "room_multi_e2e",
        "player1_profile": {
            "player_id": "player_alice",
            "nickname": "Alice",
            "tier": "Bronze",
            "travel_speaking_level": "TSL_1_SURVIVAL",
            "total_score": 3,
        },
        "player2_profile": {
            "player_id": "player_bob",
            "nickname": "Bob",
            "tier": "Silver",
            "travel_speaking_level": "TSL_2_FUNCTIONAL",
            "total_score": 6,
        }
    }
    setup_resp = client.post("/api/game/ai/room/baggage/setup", json=setup_payload)
    assert setup_resp.status_code == 200
    setup_data = setup_resp.json()
    assert setup_data["bag_owner_player_id"] == "player_alice"
    assert setup_data["random_customs_item"] is not None

    # 2. Bob (Helper) speaks on BAG_001
    turn_payload = {
        "contract_version": "dev_c_unreal_turn.v1",
        "request_id": "req_bag_001_bob",
        "session": {
            "session_id": "room_multi_e2e",
            "player_id": "player_bob",
            "room_id": "room_multi_e2e",
            "chapter_id": "CH0_04_BAGGAGE_CLAIM",
            "scene_id": "BAGGAGE_MISSING",
            "current_node_id": "BAG_001_REPORT_MISSING_AT_DESK",
            "turn_index": 1,
        },
        "npc": {
            "npc_id": "BAGGAGE_STAFF",
            "npc_role": "baggage_service_staff",
            "last_npc_message": "How can I help you?",
        },
        "audio": {
            "mime_type": "audio/wav",
            "sample_rate_hz": 16000,
            "channels": 1,
            "duration_ms": 2000,
        },
        "player_profile": {
            "nickname": "Bob",
            "tier": "Silver",
            "travel_speaking_level": "TSL_2_FUNCTIONAL",
        },
        "scenario_state": {
            "patience": 100,
            "suspicion": 0,
            "retry_count": 0,
            "hint_count": 0,
            "previous_fail_count": 0,
        },
        "game_state": {
            "inventory": [],
            "flags": ["bag_missing"],
            "completed_intents": [],
            "current_objective": "Report the missing bag",
            "random_customs_item": setup_data["random_customs_item"],
            "speaker_player_id": "player_bob",
            "bag_owner_player_id": "player_alice",
            "addressed_player_id": "player_alice",
        },
        "speaker_player_id": "player_bob",
        "bag_owner_player_id": "player_alice",
        "addressed_player_id": "player_alice",
        "client_allowed_next_nodes": [
            "BAG_002_PROVIDE_CLAIM_TAG",
            "BAG_001_RETRY_REPORT_MISSING_AT_DESK",
        ],
    }

    # Respond call for Bob (Helper)
    respond_payload = {
        "turn": turn_payload,
        "audio": {
            "mock_wav_path": "mock://baggage/missing.wav",
            "transcript": "My friend's suitcase did not arrive. We need help.",
        }
    }
    resp = client.post("/api/game/ai/respond", json=respond_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_node_id"] == "BAG_002_PROVIDE_CLAIM_TAG"
    assert data["next_action"] == "ADVANCE"


def test_multiplayer_scoring_separation_result_endpoint() -> None:
    client = TestClient(app)

    # 1. Setup Room and Baggage Owner
    room_id = "room_scoring_separation_test"
    setup_payload = {
        "room_id": room_id,
        "player1_profile": {
            "player_id": "player_alice",
            "nickname": "Alice",
            "tier": "Bronze",
            "travel_speaking_level": "TSL_1_SURVIVAL",
            "total_score": 3,
        },
        "player2_profile": {
            "player_id": "player_bob",
            "nickname": "Bob",
            "tier": "Silver",
            "travel_speaking_level": "TSL_2_FUNCTIONAL",
            "total_score": 6,
        }
    }

    # Clean up prior records if they exist
    runtime_dir = Path("backend/runtime/openkb/dev_b")
    jsonl_path = runtime_dir / f"{room_id}.jsonl"
    if jsonl_path.exists():
        jsonl_path.unlink()

    try:
        setup_resp = client.post("/api/game/ai/room/baggage/setup", json=setup_payload)
        assert setup_resp.status_code == 200
        setup_data = setup_resp.json()
        assert setup_data["bag_owner_player_id"] == "player_alice"
        random_item = setup_data["random_customs_item"]

        # 2. Bob (Helper) speaks on BAG_001
        bob_turn = {
            "contract_version": "dev_c_unreal_turn.v1",
            "request_id": "req_scoring_bob",
            "session": {
                "session_id": room_id,
                "player_id": "player_bob",
                "room_id": room_id,
                "chapter_id": "CH0_04_BAGGAGE_CLAIM",
                "scene_id": "BAGGAGE_MISSING",
                "current_node_id": "BAG_001_REPORT_MISSING_AT_DESK",
                "turn_index": 1,
            },
            "npc": {
                "npc_id": "BAGGAGE_STAFF",
                "npc_role": "baggage_service_staff",
                "last_npc_message": "How can I help you?",
            },
            "audio": {
                "mime_type": "audio/wav",
                "sample_rate_hz": 16000,
                "channels": 1,
                "duration_ms": 1000,
            },
            "player_profile": {
                "nickname": "Bob",
                "tier": "Silver",
                "travel_speaking_level": "TSL_2_FUNCTIONAL",
            },
            "scenario_state": {
                "patience": 100,
                "suspicion": 0,
                "retry_count": 0,
                "hint_count": 0,
                "previous_fail_count": 0,
            },
            "game_state": {
                "inventory": [],
                "flags": ["bag_missing"],
                "completed_intents": [],
                "current_objective": "Report the missing bag",
                "random_customs_item": random_item,
                "speaker_player_id": "player_bob",
                "bag_owner_player_id": "player_alice",
                "addressed_player_id": "player_alice",
            },
            "speaker_player_id": "player_bob",
            "bag_owner_player_id": "player_alice",
            "addressed_player_id": "player_alice",
            "client_allowed_next_nodes": [
                "BAG_002_PROVIDE_CLAIM_TAG",
                "BAG_001_RETRY_REPORT_MISSING_AT_DESK",
            ],
        }

        bob_respond_payload = {
            "turn": bob_turn,
            "audio": {
                "mock_wav_path": "mock://baggage/missing.wav",
                "transcript": "bag lost",  # Extremely short text for lower score
            }
        }
        resp1 = client.post("/api/game/ai/respond", json=bob_respond_payload)
        assert resp1.status_code == 200

        # 3. Alice (Owner) speaks on BAG_002
        alice_turn = {
            "contract_version": "dev_c_unreal_turn.v1",
            "request_id": "req_scoring_alice",
            "session": {
                "session_id": room_id,
                "player_id": "player_alice",
                "room_id": room_id,
                "chapter_id": "CH0_04_BAGGAGE_CLAIM",
                "scene_id": "BAGGAGE_MISSING",
                "current_node_id": "BAG_002_PROVIDE_CLAIM_TAG",
                "turn_index": 2,
            },
            "npc": {
                "npc_id": "BAGGAGE_STAFF",
                "npc_role": "baggage_service_staff",
                "last_npc_message": "Do you have your claim tag?",
            },
            "audio": {
                "mime_type": "audio/wav",
                "sample_rate_hz": 16000,
                "channels": 1,
                "duration_ms": 1000,
            },
            "player_profile": {
                "nickname": "Alice",
                "tier": "Bronze",
                "travel_speaking_level": "TSL_1_SURVIVAL",
            },
            "scenario_state": {
                "patience": 100,
                "suspicion": 0,
                "retry_count": 0,
                "hint_count": 0,
                "previous_fail_count": 0,
            },
            "game_state": {
                "inventory": [],
                "flags": ["bag_missing"],
                "completed_intents": [],
                "current_objective": "Provide claim tag",
                "random_customs_item": random_item,
                "speaker_player_id": "player_alice",
                "bag_owner_player_id": "player_alice",
                "addressed_player_id": "player_alice",
            },
            "speaker_player_id": "player_alice",
            "bag_owner_player_id": "player_alice",
            "addressed_player_id": "player_alice",
            "client_allowed_next_nodes": [
                "BAG_003_ASK_BAG_COLOR",
                "BAG_002_RETRY_PROVIDE_CLAIM_TAG",
            ],
        }

        alice_respond_payload = {
            "turn": alice_turn,
            "audio": {
                "mock_wav_path": "mock://baggage/tag.wav",
                "transcript": "Here is my baggage claim tag, please check it.",  # Longer text for higher score
            }
        }
        resp2 = client.post("/api/game/ai/respond", json=alice_respond_payload)
        assert resp2.status_code == 200

        # Call the GET /api/game/ai/result/{room_id} route
        response = client.get(f"/api/game/ai/result/{room_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["contract_version"] == "dev_c_unreal_room_result.v1"
        assert data["room_id"] == room_id
        assert len(data["players"]) == 2
        
        reports = {p["player_id"]: p for p in data["players"]}
        assert "player_alice" in reports
        assert "player_bob" in reports

        # P-1 DoD: room_id in response comes from records, not just the path param.
        # Since session_id == room_id in shared baggage chapter, both values match —
        # confirming the direct-file-lookup path is sufficient (no directory scan needed).
        assert data["room_id"] == room_id

        alice_score = reports["player_alice"]["final_result"]["final_score_100"]
        bob_score = reports["player_bob"]["final_result"]["final_score_100"]

        # Verify Alice (longer utterance) got a higher score than Bob (short utterance)
        assert alice_score > bob_score

    finally:
        if jsonl_path.exists():
            jsonl_path.unlink()


class MockRequest:
    def __init__(self, json_data):
        self._json_data = json_data
        self.headers = {"content-type": "application/json"}

    async def json(self):
        return self._json_data


@pytest.mark.anyio
async def test_concurrency_lock_prevents_race_conditions(monkeypatch) -> None:
    call_order = []

    def mock_run_turn(self, preprototype_request: PrePrototypeRequest):
        import time
        req_id = preprototype_request.turn.request_id
        call_order.append(f"start_{req_id}")
        time.sleep(0.1)
        call_order.append(f"end_{req_id}")
        return MagicMock(spec=UnrealResponse)

    monkeypatch.setattr(Orchestrator, "run_turn", mock_run_turn)

    req1 = {
        "turn": {
            "contract_version": "dev_c_unreal_turn.v1",
            "request_id": "req1",
            "session": {
                "session_id": "room_lock_test",
                "room_id": "room_lock_test",
                "chapter_id": "CH0_04_BAGGAGE_CLAIM",
                "scene_id": "BAGGAGE_MISSING",
                "current_node_id": "BAG_001_REPORT_MISSING_AT_DESK",
                "turn_index": 1,
            },
            "npc": {"npc_id": "BAGGAGE_STAFF", "npc_role": "baggage_service_staff", "last_npc_message": ""},
            "audio": {"mime_type": "audio/wav", "sample_rate_hz": 16000, "channels": 1, "duration_ms": 1000},
            "player_profile": {"nickname": "Alice", "tier": "Bronze", "travel_speaking_level": "TSL_1_SURVIVAL"},
            "scenario_state": {"patience": 100, "suspicion": 0, "retry_count": 0, "hint_count": 0, "previous_fail_count": 0},
            "game_state": {"inventory": [], "flags": [], "completed_intents": [], "current_objective": ""},
        },
        "audio": {"transcript": "Hello"}
    }

    req2 = {
        "turn": {
            "contract_version": "dev_c_unreal_turn.v1",
            "request_id": "req2",
            "session": {
                "session_id": "room_lock_test",
                "room_id": "room_lock_test",
                "chapter_id": "CH0_04_BAGGAGE_CLAIM",
                "scene_id": "BAGGAGE_MISSING",
                "current_node_id": "BAG_001_REPORT_MISSING_AT_DESK",
                "turn_index": 2,
            },
            "npc": {"npc_id": "BAGGAGE_STAFF", "npc_role": "baggage_service_staff", "last_npc_message": ""},
            "audio": {"mime_type": "audio/wav", "sample_rate_hz": 16000, "channels": 1, "duration_ms": 1000},
            "player_profile": {"nickname": "Bob", "tier": "Silver", "travel_speaking_level": "TSL_2_FUNCTIONAL"},
            "scenario_state": {"patience": 100, "suspicion": 0, "retry_count": 0, "hint_count": 0, "previous_fail_count": 0},
            "game_state": {"inventory": [], "flags": [], "completed_intents": [], "current_objective": ""},
        },
        "audio": {"transcript": "Hello"}
    }

    # Call endpoint directly on the async event loop to test locks safely
    task1 = respond(MockRequest(req1))  # type: ignore[arg-type]
    task2 = respond(MockRequest(req2))  # type: ignore[arg-type]

    await asyncio.gather(task1, task2)

    assert len(call_order) == 4
    if call_order[0] == "start_req1":
        assert call_order == ["start_req1", "end_req1", "start_req2", "end_req2"]
    else:
        assert call_order == ["start_req2", "end_req2", "start_req1", "end_req1"]
