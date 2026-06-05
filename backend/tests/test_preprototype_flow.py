from collections.abc import Generator
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.integrations.dev_a_npc_dialogue_client import DevANpcDialogueClient
from backend.app.main import app
from backend.app.schemas.game_turn import (
    DevADialogueInput,
    MockAudioInput,
    PrePrototypeRequest,
    UnrealTurnRequest,
)
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.services.service_c.orchestrator import Orchestrator
from backend.app.services.service_c.settings_service import AppSettings, get_settings
from backend.app.services.service_c.validator import ValidationError, Validator


SAMPLE_WAV = Path("samples/utterance-20260603-163237.wav")


class MissingVisitPurposeLLMClient:
    model = "fake-understanding-model"

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": "state_visit_purpose",
            "intent_success": False,
            "confidence": 0.92,
            "meaning_summary_kr": "The visit purpose is unclear.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "unclear_purpose",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "extracted_slots": {},
            "missing_slots": ["visit_purpose"],
            "needs_clarification": True,
            "__llm_usage": {"input_tokens": 753, "output_tokens": 153, "total_tokens": 906},
        }


@pytest.fixture(autouse=True)
def _use_deterministic_runtime_modes(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("MURPHY_STT_MODE", "mock")
    monkeypatch.setenv("MURPHY_TTS_MODE", "fake")
    monkeypatch.setenv("MURPHY_NPC_DIALOGUE_MODE", "rule")
    monkeypatch.setenv("MURPHY_UNDERSTANDING_MODE", "rule")
    monkeypatch.setenv("DEV_B_FEEDBACK_LLM_MODE", "rule")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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


def _preprototype_request(transcript: str = "I'm here for tourism.") -> PrePrototypeRequest:
    return PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(_turn_payload()),
        audio=MockAudioInput(
            mock_wav_path="mock://immigration/purpose_tourism.wav",
            transcript=transcript,
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


def test_openkb_loads_chapter_zero_duration_node_from_scenario_nodes() -> None:
    node_context = OpenKBService().get_node_context("CH0_IMMIGRATION", "IMM_003_DURATION")

    assert node_context.node_id == "IMM_003_DURATION"
    assert node_context.npc_question == "How long will you stay?"
    assert node_context.objective_kr == "체류 기간 말하기"
    assert node_context.success_next_node == "IMM_004_STAY_LOCATION"
    assert "IMM_003_RETRY_DURATION" in node_context.allowed_next_nodes


def test_orchestrator_uses_real_developer_b_policy_for_form_issue_capture() -> None:
    response = Orchestrator().run_turn(_preprototype_request(transcript="Travel. New York."))

    assert response.next_node_id == "IMM_003_DURATION"
    assert response.report.recorded_error_count == 1
    assert "minor_form_issue" in response.evaluation.feedback_tags


def test_orchestrator_advances_family_visit_purpose_to_duration_node() -> None:
    response = Orchestrator().run_turn(_preprototype_request(transcript="I'm here to visit my uncle."))

    assert response.stt.player_text == "I'm here to visit my uncle."
    assert response.next_action == "ADVANCE"
    assert response.next_node_id == "IMM_003_DURATION"
    assert response.debug.understanding_confidence == pytest.approx(0.94)


def test_orchestrator_uses_repaired_llm_visit_purpose_before_developer_a_dialogue() -> None:
    orchestrator = Orchestrator()
    orchestrator.understanding_agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=MissingVisitPurposeLLMClient(),
    )

    response = orchestrator.run_turn(_preprototype_request(transcript="I'm here to visit my uncle."))

    assert response.next_action == "ADVANCE"
    assert response.next_node_id == "IMM_003_DURATION"
    assert response.evaluation.verdict == "SUCCESS"
    assert response.debug.understanding_confidence == pytest.approx(0.94)
    assert response.npc.text != "Okay. Please continue."
    assert "how long" in response.npc.text.lower()


def test_dev_a_adapter_uses_real_tts_and_llm_modes_from_settings() -> None:
    builder_calls: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_calls.append(kwargs)
        return {
            "speaker": "Officer Miller",
            "npc_text": "You're here for tourism. How long will you stay?",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "Good.",
            "tts": {
                "audio_url": "/runtime/audio/kokoro/real-demo.wav",
            },
        }

    request = _preprototype_request()
    orchestrator = Orchestrator()
    node_context = orchestrator.openkb_service.get_node_context(
        request.turn.session.chapter_id,
        request.turn.session.current_node_id,
    )
    normalized_input = orchestrator.stt_service.transcribe_wav(request.audio, request.turn.audio)
    understanding = orchestrator.understanding_agent.analyze_player_text(
        normalized_input.player_text,
        node_context,
    )
    dev_b_output = orchestrator.dev_b_client.evaluate_turn(
        orchestrator.build_dev_b_policy_input(
            request,
            normalized_input=normalized_input,
            node_context=node_context,
            understanding=understanding,
        )
    )
    client = DevANpcDialogueClient(
        settings=AppSettings(
            murphy_tts_mode="real",
            murphy_npc_dialogue_mode="llm",
        ),
        voice_output_builder=fake_voice_output_builder,
    )

    output = client.generate_dialogue(
        DevADialogueInput(
            contract_version="dev_a_dialogue.v1",
            request_id=request.turn.request_id,
            session_id=request.turn.session.session_id,
            current_node_id=request.turn.session.current_node_id,
            player_text=normalized_input.player_text,
            npc=request.turn.npc,
            node_context=node_context,
            understanding=understanding,
            developer_b_policy=dev_b_output,
        )
    )

    assert output.audio_url == "/runtime/audio/kokoro/real-demo.wav"
    assert builder_calls[0]["use_real_tts"] is True
    assert builder_calls[0]["use_llm_dialogue"] is True


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
    assert "how long" in body["npc"]["text"].lower()
    assert body["npc"]["audio_url"].startswith("/runtime/audio/kokoro/")

    audio_response = client.get(body["npc"]["audio_url"])
    assert audio_response.status_code == 200
    assert audio_response.content.startswith(b"RIFF")


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


def test_validator_rejects_developer_b_hint_payload_when_hint_is_not_needed() -> None:
    request = _preprototype_request()
    orchestrator = Orchestrator()
    node_context = orchestrator.openkb_service.get_node_context(
        request.turn.session.chapter_id,
        request.turn.session.current_node_id,
    )
    normalized_input = orchestrator.stt_service.transcribe_wav(request.audio, request.turn.audio)
    understanding = orchestrator.understanding_agent.analyze_player_text(
        normalized_input.player_text,
        node_context,
    )
    policy_output = orchestrator.dev_b_client.evaluate_turn(
        orchestrator.build_dev_b_policy_input(
            request,
            normalized_input=normalized_input,
            node_context=node_context,
            understanding=understanding,
        )
    )
    policy_output.level_hint.hint_type = "sentence_pattern"

    with pytest.raises(ValidationError, match="hint_type must be null"):
        Validator().validate_dev_b_policy_output(
            policy_output,
            current_node_id=request.turn.session.current_node_id,
            allowed_next_nodes=node_context.allowed_next_nodes,
            client_allowed_next_nodes=request.turn.client_allowed_next_nodes,
        )


def test_validator_requires_npc_audio_url_for_preprototype_response() -> None:
    response = Orchestrator().run_turn(_preprototype_request())
    response.npc.audio_url = None

    with pytest.raises(ValidationError, match="npc.audio_url"):
        Validator().validate_unreal_response(response)
