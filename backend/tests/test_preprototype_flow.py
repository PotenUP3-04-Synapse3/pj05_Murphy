import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.schemas.game_turn import MockAudioInput, PrePrototypeRequest, UnrealTurnRequest
from backend.app.services.orchestrator import Orchestrator
from backend.app.services.validator import ValidationError, Validator


SAMPLE_WAV = Path("samples/utterance-20260603-163237.wav")


def _turn_payload() -> dict:
    return {
        "contract_version": "dev_c_unreal_turn.v1",
        "request_id": "req_imm_0001",
        "session": {
            "session_id": "session_001",
            "player_id": "player_001",
            "chapter_id": "CH0_IMMIGRATION",
            "scene_id": "JFK_IMMIGRATION_HALL",
            "current_node_id": "IMM_002_PURPOSE",
            "turn_index": 2,
        },
        "npc": {
            "npc_id": "OFFICER_MILLER",
            "npc_role": "immigration_officer",
            "last_npc_message": "What is the purpose of your visit?",
        },
        "audio": {
            "mime_type": "audio/wav",
            "sample_rate_hz": 16000,
            "channels": 1,
            "duration_ms": 2800,
            "language_hint": "en-US",
        },
        "player_profile": {
            "nickname": "Sean",
            "english_confidence": "beginner",
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
            "inventory": ["passport", "boarding_pass", "return_ticket"],
            "flags": ["arrived_at_jfk", "passport_submitted"],
            "completed_intents": ["submit_passport"],
            "current_objective": "State the visit purpose",
        },
        "previous_node_results": [
            {
                "node_id": "IMM_001_PASSPORT",
                "verdict": "SUCCESS",
                "next_action": "ADVANCE",
            }
        ],
        "client_allowed_next_nodes": [
            "IMM_003_DURATION",
            "IMM_002_RETRY_PURPOSE",
            "IMM_EXTRA_001_CLARIFY_PURPOSE",
            "END_SECONDARY_INSPECTION",
        ],
        "client_context": {
            "platform": "windows",
            "input_device": "microphone",
            "locale": "ko-KR",
            "build_version": "0.1.0",
        },
    }


def _preprototype_request() -> PrePrototypeRequest:
    return PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(_turn_payload()),
        audio=MockAudioInput(
            mock_wav_path="mock://immigration/purpose_tourism.wav",
            transcript="I'm here for tourism.",
        ),
    )


def test_orchestrator_connects_stt_understanding_dev_b_dev_a_and_response() -> None:
    response = Orchestrator().run_turn(_preprototype_request())

    assert response.contract_version == "dev_c_unreal_response.v1"
    assert response.request_id == "req_imm_0001"
    assert response.current_node_id == "IMM_002_PURPOSE"
    assert response.next_node_id == "IMM_003_DURATION"
    assert response.next_action == "ADVANCE"
    assert response.npc.speaker == "Officer Miller"
    assert "tourism" in response.npc.text.lower()
    assert response.evaluation.verdict == "SUCCESS"
    assert response.ui.in_game_feedback.feedback_strategy == "recast"
    assert response.debug.stt_model == "whisper-large-v3-turbo"
    assert response.debug.stt_confidence == pytest.approx(0.87)
    assert response.stt.primary_runtime == "local"
    assert response.stt.fallback_runtime == "api"
    assert response.stt.runtime_used == "local"


def test_api_accepts_mock_unreal_turn_json() -> None:
    client = TestClient(app)
    payload = {
        "turn": _turn_payload(),
        "audio": {
            "mock_wav_path": "mock://immigration/purpose_tourism.wav",
            "transcript": "I'm here for tourism.",
        },
    }

    response = client.post("/api/game/ai/respond", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["next_node_id"] == "IMM_003_DURATION"
    assert body["stt"]["player_text"] == "I'm here for tourism."
    assert body["stt"]["primary_runtime"] == "local"
    assert body["stt"]["fallback_runtime"] == "api"
    assert body["stt"]["runtime_used"] == "local"
    assert body["debug"]["stt_model"] == "whisper-large-v3-turbo"


def test_api_accepts_multipart_turn_json_and_sample_wav() -> None:
    client = TestClient(app)

    with SAMPLE_WAV.open("rb") as audio_file:
        response = client.post(
            "/api/game/ai/respond",
            files={
                "turn": (
                    "imm_002_purpose.json",
                    json.dumps(_turn_payload()),
                    "application/json",
                ),
                "audio": (
                    SAMPLE_WAV.name,
                    audio_file,
                    "audio/wav",
                ),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["stt"]["model"] == "whisper-large-v3-turbo"
    assert body["stt"]["primary_runtime"] == "local"
    assert body["stt"]["fallback_runtime"] == "api"
    assert body["stt"]["runtime_used"] == "local"
    assert body["stt"]["player_text"] == "I'm here for tourism."
    assert body["next_node_id"] == "IMM_003_DURATION"
    assert body["npc"]["text"] == "You're here for tourism. How long will you stay?"


def test_validator_rejects_developer_b_branch_outside_allowed_nodes() -> None:
    request = _preprototype_request()
    node_context = Orchestrator().openkb_service.get_node_context(
        request.turn.session.chapter_id,
        request.turn.session.current_node_id,
    )
    policy_output = Orchestrator().dev_b_client.evaluate_turn(
        Orchestrator().build_dev_b_policy_input(
            request,
            normalized_input=Orchestrator().stt_service.transcribe_wav(
                request.audio,
                request.turn.audio,
            ),
            node_context=node_context,
            understanding=Orchestrator().understanding_agent.analyze_player_text(
                "I'm here for tourism.",
                node_context,
            ),
        )
    )
    policy_output.branch.next_node_id = "END_BAD_HANDCUFF"

    with pytest.raises(ValidationError, match="not in node_context.allowed_next_nodes"):
        Validator().validate_dev_b_policy_output(
            policy_output,
            current_node_id=request.turn.session.current_node_id,
            allowed_next_nodes=node_context.allowed_next_nodes,
            client_allowed_next_nodes=request.turn.client_allowed_next_nodes,
        )
