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
    UnderstandingOutput,
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


class StaticUnderstandingAgent(UnderstandingAgent):
    def __init__(self, output: UnderstandingOutput) -> None:
        self.output = output
        self.last_trace = {"mode": "test_static"}

    def analyze_player_text(self, player_text: str, node_context: object) -> UnderstandingOutput:
        return self.output


def _successful_understanding(intent: str, slot: str, value: str) -> UnderstandingOutput:
    return UnderstandingOutput(
        intent=intent,
        intent_success=True,
        confidence=0.94,
        meaning_summary_kr="The player satisfied the chapter boundary node.",
        emotion="calm",
        answer_relevance="on_topic",
        ambiguity_type="none",
        risk_delta=0,
        risk_reason="No risk expression was found.",
        risk_tags=[],
        extracted_slots={slot: value},
        missing_slots=[],
        needs_clarification=False,
    )


@pytest.fixture(autouse=True)
def _use_deterministic_runtime_modes(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("MURPHY_STT_MODE", "mock")
    monkeypatch.setenv("MURPHY_TTS_MODE", "fake")
    monkeypatch.setenv("MURPHY_NPC_DIALOGUE_MODE", "rule")
    monkeypatch.setenv("MURPHY_UNDERSTANDING_MODE", "rule")
    monkeypatch.setenv("MURPHY_UNREAL_REQUEST_CAPTURE_MODE", "off")
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
            "chapter_id": "CH0_03_IMMIGRATION_CHECK",
            "scene_id": "JFK_IMMIGRATION_HALL",
            "current_node_id": "IMM_002_PURPOSE",
            "turn_index": 2,
        },
        "npc": {
            "npc_id": "miller",
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


def _chapter_boundary_request(
    *,
    request_id: str,
    chapter_id: str,
    current_node_id: str,
    npc_id: str,
    npc_role: str,
    last_npc_message: str,
    transcript: str,
    allowed_next_nodes: list[str],
) -> PrePrototypeRequest:
    turn_payload = _turn_payload()
    turn_payload["request_id"] = request_id
    turn_payload["session"]["chapter_id"] = chapter_id
    turn_payload["session"]["current_node_id"] = current_node_id
    turn_payload["session"]["turn_index"] = 9
    turn_payload["npc"]["npc_id"] = npc_id
    turn_payload["npc"]["npc_role"] = npc_role
    turn_payload["npc"]["last_npc_message"] = last_npc_message
    turn_payload["game_state"]["current_objective"] = "Complete the current Alpha chapter"
    turn_payload["client_allowed_next_nodes"] = allowed_next_nodes
    return PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path=f"mock://alpha/{current_node_id.lower()}.wav",
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
    assert response.npc.speaker == "Officer Hale"
    assert "tourism" in response.npc.text.lower()
    assert response.npc.text.startswith("All right.")
    assert response.npc.emotion == "Nomal"
    assert response.evaluation.verdict == "SUCCESS"
    assert response.ui.in_game_feedback.feedback_strategy == "recast"
    assert response.debug.stt_model == "whisper-large-v3-turbo"
    assert response.debug.stt_confidence == pytest.approx(0.87)
    assert response.stt.primary_runtime == "local"
    assert response.stt.fallback_runtime == "api"
    assert response.stt.runtime_used == "local"
    assert response.interaction.initiator == "npc"
    assert response.interaction.interaction_type == "quest"
    assert response.interaction.time_limit_s is None
    assert response.debug.timing_ms.total_ms >= response.debug.timing_ms.stt_ms
    assert response.debug.timing_ms.developer_b_ms >= 0
    assert response.debug.timing_ms.developer_a_ms >= 0


def test_orchestrator_accepts_player_initiated_quest_interaction_context() -> None:
    turn_payload = _turn_payload()
    turn_payload["interaction"] = {
        "initiator": "player",
        "interaction_type": "quest",
        "quest_id": "QUEST_BAGGAGE_DECLARATION_CHECK",
        "interaction_id": "airport_counter_user_opener_001",
        "time_limit_s": 30,
        "first_contact": True,
        "npc_can_initiate": False,
        "player_can_initiate": True,
    }
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://airport/player_opener.wav",
            transcript="Excuse me, can you help me with my declaration form?",
        ),
    )

    response = Orchestrator().run_turn(request)

    assert response.interaction.initiator == "player"
    assert response.interaction.interaction_type == "quest"
    assert response.interaction.quest_id == "QUEST_BAGGAGE_DECLARATION_CHECK"
    assert response.interaction.interaction_id == "airport_counter_user_opener_001"
    assert response.interaction.time_limit_s == 30
    assert response.interaction.first_contact is True
    assert response.interaction.npc_can_initiate is False
    assert response.interaction.player_can_initiate is True
    assert "dev_c_interaction_context.v1" in response.debug.contract_versions


def test_openkb_loads_immigration_chapter_duration_node_from_scenario_nodes() -> None:
    node_context = OpenKBService().get_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_003_DURATION")

    assert node_context.node_id == "IMM_003_DURATION"
    assert node_context.scenario_id == "ALPHA_AIRPORT_ARRIVAL"
    assert node_context.chapter_id == "CH0_03_IMMIGRATION_CHECK"
    assert node_context.node_type == "dialogue"
    assert node_context.npc_question == "How long will you be staying?"
    assert node_context.objective_kr == "체류 기간 말하기"
    assert node_context.success_next_node == "IMM_004_STAY_LOCATION"
    assert "IMM_003_RETRY_DURATION" in node_context.allowed_next_nodes


def test_openkb_rejects_wrong_chapter_for_existing_node() -> None:
    with pytest.raises(ValueError, match="Node chapter mismatch"):
        OpenKBService().get_node_context("CH0_01_FLIGHT_SMALLTALK", "IMM_003_DURATION")


def test_openkb_loads_transition_node_metadata() -> None:
    node_context = OpenKBService().get_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_999_CLEARED")

    assert node_context.node_type == "transition"
    assert node_context.transition is not None
    assert node_context.transition.status == "chapter_complete"
    assert node_context.transition.completed_chapter_id == "CH0_03_IMMIGRATION_CHECK"
    assert node_context.transition.next_chapter_id == "CH0_04_BAGGAGE_CLAIM"
    assert node_context.transition.entry_node_id == "BAG_001_REPORT_MISSING_AT_DESK"
    assert node_context.transition.unreal_event == "ENTER_BAGGAGE_CLAIM"
    assert node_context.transition.requires_player_input is False


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


def test_orchestrator_advances_stay_duration_answer_to_location_node() -> None:
    turn_payload = _turn_payload()
    turn_payload["request_id"] = "req_imm_duration_0001"
    turn_payload["session"]["current_node_id"] = "IMM_003_DURATION"
    turn_payload["session"]["turn_index"] = 3
    turn_payload["npc"]["last_npc_message"] = "How long will you be staying?"
    turn_payload["game_state"]["current_objective"] = "State the stay duration"
    turn_payload["game_state"]["completed_intents"] = ["submit_passport", "state_visit_purpose"]
    turn_payload["previous_node_results"].append(
        {
            "node_id": "IMM_002_PURPOSE",
            "verdict": "SUCCESS",
            "next_action": "ADVANCE",
        }
    )
    turn_payload["client_allowed_next_nodes"] = [
        "IMM_004_STAY_LOCATION",
        "IMM_003_RETRY_DURATION",
        "IMM_EXTRA_002_CLARIFY_DURATION",
        "END_SECONDARY_INSPECTION",
    ]
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://immigration/stay_duration_five_days.wav",
            transcript="I will stay for 5 days.",
        ),
    )

    response = Orchestrator().run_turn(request)

    assert response.stt.player_text == "I will stay for 5 days."
    assert response.next_action == "ADVANCE"
    assert response.next_node_id == "IMM_004_STAY_LOCATION"
    assert response.evaluation.verdict == "SUCCESS"
    assert response.evaluation.feedback_tags == ["intent_matched", "required_slot_filled"]


def test_orchestrator_treats_immigration_final_decision_as_baggage_transition() -> None:
    turn_payload = _turn_payload()
    turn_payload["request_id"] = "req_alpha_imm_to_bag_0001"
    turn_payload["session"]["scene_id"] = "IMMIGRATION_ALPHA"
    turn_payload["session"]["current_node_id"] = "IMM_007_FINAL_DECISION"
    turn_payload["session"]["turn_index"] = 8
    turn_payload["npc"]["last_npc_message"] = "All right, you're cleared to enter. Enjoy your stay."
    turn_payload["game_state"]["current_objective"] = "Move to baggage claim"
    turn_payload["game_state"]["completed_intents"] = [
        "submit_passport",
        "state_visit_purpose",
        "state_stay_duration",
        "confirm_packed_by_self",
    ]
    turn_payload["previous_node_results"].append(
        {
            "node_id": "IMM_006B_PACKED_BAG_CHECK",
            "verdict": "SUCCESS",
            "next_action": "ADVANCE",
        }
    )
    turn_payload["client_allowed_next_nodes"] = [
        "IMM_999_CLEARED",
        "IMM_007_RETRY_FINAL_DECISION",
        "IMM_EXTRA_007_CLARIFY_FINAL_DECISION",
        "END_SECONDARY_INSPECTION",
    ]
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://alpha/immigration_clearance_ack.wav",
            transcript="Thank you, officer.",
        ),
    )

    response = Orchestrator().run_turn(request)

    assert response.next_action == "COMPLETE_CHAPTER"
    assert response.next_node_id == "IMM_999_CLEARED"
    assert response.transition is not None
    assert response.transition.unreal_event == "ENTER_BAGGAGE_CLAIM"
    assert response.transition.entry_node_id == "BAG_001_REPORT_MISSING_AT_DESK"
    assert response.report.final_result is None
    assert "thank" in response.npc.text.lower()


def test_orchestrator_advances_baggage_report_to_claim_tag_node() -> None:
    turn_payload = _turn_payload()
    turn_payload["request_id"] = "req_alpha_bag_notice_0001"
    turn_payload["session"]["chapter_id"] = "CH0_04_BAGGAGE_CLAIM"
    turn_payload["session"]["scene_id"] = "BAGGAGE_MISSING"
    turn_payload["session"]["current_node_id"] = "BAG_001_REPORT_MISSING_AT_DESK"
    turn_payload["session"]["turn_index"] = 9
    turn_payload["npc"]["npc_id"] = "BAGGAGE_STAFF"
    turn_payload["npc"]["npc_role"] = "baggage_service_staff"
    turn_payload["npc"]["last_npc_message"] = (
        "The carousel has stopped, and your suitcase still isn't here. What do you need to do?"
    )
    turn_payload["game_state"]["current_objective"] = "Report the missing bag"
    turn_payload["game_state"]["flags"] = ["arrived_at_jfk", "immigration_cleared", "bag_missing"]
    turn_payload["previous_node_results"].append(
        {
            "node_id": "IMM_999_CLEARED",
            "verdict": "SUCCESS",
            "next_action": "COMPLETE_CHAPTER",
        }
    )
    turn_payload["client_allowed_next_nodes"] = [
        "BAG_002_PROVIDE_CLAIM_TAG",
        "BAG_001_RETRY_REPORT_MISSING_AT_DESK",
        "BAG_001_CLARIFY_REPORT_MISSING_AT_DESK",
        "END_BAGGAGE_REPORT_INCOMPLETE",
    ]
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://alpha/baggage_notice_missing.wav",
            transcript="My suitcase didn't arrive. I need to ask for help.",
        ),
    )

    response = Orchestrator().run_turn(request)

    assert response.next_action == "ADVANCE"
    assert response.next_node_id == "BAG_002_PROVIDE_CLAIM_TAG"
    assert response.evaluation.verdict == "SUCCESS"


def test_orchestrator_attaches_final_result_only_on_alpha_scoreboard_node() -> None:
    turn_payload = _turn_payload()
    turn_payload["request_id"] = "req_alpha_scoreboard_0001"
    turn_payload["session"]["chapter_id"] = "CH0_05_RESULT"
    turn_payload["session"]["scene_id"] = "ALPHA_SCOREBOARD"
    turn_payload["session"]["current_node_id"] = "ALPHA_999_FINAL_SCOREBOARD"
    turn_payload["session"]["turn_index"] = 16
    turn_payload["npc"]["last_npc_message"] = (
        "Your airport arrival scenario is complete. Let's review your result."
    )
    turn_payload["game_state"]["current_objective"] = "Review the Alpha result"
    turn_payload["game_state"]["flags"] = [
        "arrived_at_jfk",
        "immigration_cleared",
        "baggage_report_completed",
    ]
    turn_payload["previous_node_results"] = [
        {
            "node_id": "FLIGHT_001_SEATMATE_SMALLTALK",
            "verdict": "SUCCESS",
            "next_action": "ADVANCE",
        },
        {
            "node_id": "IMM_007_FINAL_DECISION",
            "verdict": "SUCCESS",
            "next_action": "ADVANCE",
        },
        {
            "node_id": "BAG_999_COMPLETE",
            "verdict": "SUCCESS",
            "next_action": "COMPLETE_CHAPTER",
        },
    ]
    turn_payload["client_allowed_next_nodes"] = ["END_ALPHA_SCENARIO"]
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://alpha/final_scoreboard_ack.wav",
            transcript="Thank you. Let's review the result.",
        ),
    )

    response = Orchestrator().run_turn(request)

    assert response.next_action == "FINAL_DECISION"
    assert response.next_node_id == "END_ALPHA_SCENARIO"
    assert response.report.final_result is not None
    assert 0 <= response.report.final_result.final_score_100 <= 100


def test_orchestrator_marks_flight_wrap_up_as_arrival_cutscene_transition() -> None:
    turn_payload = _turn_payload()
    turn_payload["request_id"] = "req_alpha_flight_to_imm_0001"
    turn_payload["session"]["chapter_id"] = "CH0_01_FLIGHT_SMALLTALK"
    turn_payload["session"]["scene_id"] = "FLIGHT_SEATMATE_SMALLTALK"
    turn_payload["session"]["current_node_id"] = "FLIGHT_A_005_WRAP_UP"
    turn_payload["session"]["turn_index"] = 5
    turn_payload["npc"]["npc_id"] = "SEATMATE_EMILY"
    turn_payload["npc"]["npc_role"] = "seatmate"
    turn_payload["npc"]["last_npc_message"] = (
        "Looks like we're landing soon. Are you ready for immigration?"
    )
    turn_payload["game_state"]["current_objective"] = "Finish the flight small talk"
    turn_payload["game_state"]["flags"] = ["flight_level_test_active"]
    turn_payload["client_allowed_next_nodes"] = ["FLIGHT_999_COMPLETE"]
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://alpha/flight_wrap_up_ready.wav",
            transcript="I think I'm ready. Thanks for talking with me.",
        ),
    )

    response = Orchestrator().run_turn(request)

    assert response.next_action == "COMPLETE_CHAPTER"
    assert response.next_node_id == "FLIGHT_999_COMPLETE"
    assert response.transition is not None
    assert response.transition.unreal_event == "START_AIRPORT_ARRIVAL_TUTORIAL"
    assert response.flow.transition_type == "cutscene"
    assert response.flow.transition_id == "flight_to_arrival_tutorial"
    assert response.flow.to_scene_id == "ARRIVAL_TUTORIAL"
    assert response.flow.cinematic_id == "CIN_FLIGHT_ARRIVAL_JFK"
    assert response.flow.skip_allowed is True
    assert response.flow.show_scoreboard is False


def test_orchestrator_marks_immigration_clearance_as_baggage_scene_transition() -> None:
    turn_payload = _turn_payload()
    turn_payload["request_id"] = "req_alpha_imm_to_bag_flow_0001"
    turn_payload["session"]["scene_id"] = "IMMIGRATION_ALPHA"
    turn_payload["session"]["current_node_id"] = "IMM_007_FINAL_DECISION"
    turn_payload["session"]["turn_index"] = 8
    turn_payload["npc"]["last_npc_message"] = "All right, you're cleared to enter. Enjoy your stay."
    turn_payload["game_state"]["current_objective"] = "Move to baggage claim"
    turn_payload["client_allowed_next_nodes"] = ["IMM_999_CLEARED"]
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://alpha/immigration_clearance_ack.wav",
            transcript="Thank you, officer.",
        ),
    )

    response = Orchestrator().run_turn(request)

    assert response.next_action == "COMPLETE_CHAPTER"
    assert response.next_node_id == "IMM_999_CLEARED"
    assert response.transition is not None
    assert response.transition.entry_node_id == "BAG_001_REPORT_MISSING_AT_DESK"
    assert response.flow.transition_type == "scene_transition"
    assert response.flow.transition_id == "immigration_to_baggage_claim"
    assert response.flow.to_scene_id == "BAGGAGE_MISSING"
    assert response.flow.cinematic_id is None
    assert response.flow.skip_allowed is False


def test_orchestrator_marks_alpha_final_branch_as_scoreboard_flow() -> None:
    turn_payload = _turn_payload()
    turn_payload["request_id"] = "req_alpha_scoreboard_flow_0001"
    turn_payload["session"]["chapter_id"] = "CH0_05_RESULT"
    turn_payload["session"]["scene_id"] = "ALPHA_SCOREBOARD"
    turn_payload["session"]["current_node_id"] = "ALPHA_999_FINAL_SCOREBOARD"
    turn_payload["session"]["turn_index"] = 16
    turn_payload["npc"]["last_npc_message"] = (
        "Your airport arrival scenario is complete. Let's review your result."
    )
    turn_payload["game_state"]["current_objective"] = "Review the Alpha result"
    turn_payload["game_state"]["flags"] = [
        "arrived_at_jfk",
        "immigration_cleared",
        "baggage_report_completed",
    ]
    turn_payload["client_allowed_next_nodes"] = ["END_ALPHA_SCENARIO"]
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://alpha/final_scoreboard_ack.wav",
            transcript="Thank you. Let's review the result.",
        ),
    )

    response = Orchestrator().run_turn(request)

    assert response.next_action == "FINAL_DECISION"
    assert response.flow.transition_type == "scoreboard"
    assert response.flow.transition_id == "alpha_final_scoreboard"
    assert response.flow.to_scene_id == "ALPHA_SCOREBOARD"
    assert response.flow.show_scoreboard is True
    assert response.flow.skip_allowed is False
    assert "dev_c_unreal_flow.v1" in response.debug.contract_versions


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
    assert response.npc.text != "All right. Let's continue."
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
            "npc_text": "You're here for tourism. How long will you be staying?",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "Good.",
            "tts": {
                "audio_url": "/runtime/audio/edge/real-demo.wav",
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

    assert output.audio_url == "/runtime/audio/edge/real-demo.wav"
    assert builder_calls[0]["use_real_tts"] is True
    assert builder_calls[0]["use_llm_dialogue"] is True


def test_dev_a_adapter_uses_next_question_seed_without_generic_recast_in_llm_mode() -> None:
    builder_payloads: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Officer Miller",
            "npc_text": "How long will you stay?",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "Good.",
            "tts": {"audio_url": "/runtime/audio/edge/test.wav"},
        }

    request = _preprototype_request(transcript="I'm here to visit my uncle.")
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
        settings=AppSettings(murphy_npc_dialogue_mode="llm"),
        voice_output_builder=fake_voice_output_builder,
    )

    client.generate_dialogue(
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

    assert builder_payloads
    assert builder_payloads[0]["in_game_feedback"]["npc_recast_line_candidate"] == "How long will you be staying?"
    assert builder_payloads[0]["in_game_feedback"]["recommended_expression"] is None
    assert builder_payloads[0]["level_hint"]["recommended_expression"] is None
    assert builder_payloads[0]["node_context"]["recommended_expression"] is None
    assert builder_payloads[0]["player_text"] == "I'm here to visit my uncle."


def test_dev_a_adapter_forwards_npc_context_to_voice_builder() -> None:
    builder_payloads: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Officer Miller",
            "npc_text": "You're here for tourism. How long will you stay?",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "Good.",
            "tts": {
                "audio_url": "/runtime/audio/edge/test.wav",
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
    client = DevANpcDialogueClient(voice_output_builder=fake_voice_output_builder)

    client.generate_dialogue(
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

    assert builder_payloads[0]["npc"] == {
        "npc_id": "miller",
        "npc_role": "immigration_officer",
        "last_npc_message": "What is the purpose of your visit?",
        "emotion": dev_b_output.npc_emotion,
    }


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
    assert body["npc"]["audio_url"].startswith("/runtime/audio/edge/")

    audio_response = client.get(body["npc"]["audio_url"])
    assert audio_response.status_code == 200
    assert audio_response.content.startswith(b"RIFF")


def test_api_captures_unreal_multipart_request_when_debug_mode_is_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MURPHY_UNREAL_REQUEST_CAPTURE_MODE", "debug")
    monkeypatch.setenv("MURPHY_UNREAL_REQUEST_CAPTURE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(app)

    with SAMPLE_WAV.open("rb") as audio_file:
        original_audio = audio_file.read()
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
                original_audio,
                "audio/wav",
            ),
        },
    )

    assert response.status_code == 200
    capture_dirs = list(tmp_path.iterdir())
    assert len(capture_dirs) == 1
    capture_dir = capture_dirs[0]
    captured_turn = json.loads((capture_dir / "turn.json").read_text(encoding="utf-8"))
    captured_metadata = json.loads((capture_dir / "metadata.json").read_text(encoding="utf-8"))
    assert (capture_dir / "audio.wav").read_bytes() == original_audio
    assert captured_turn["request_id"] == "req_imm_0001"
    assert captured_metadata["request_id"] == "req_imm_0001"
    assert captured_metadata["audio_filename"] == SAMPLE_WAV.name
    assert captured_metadata["audio_bytes"] == len(original_audio)
    assert captured_metadata["content_type"].startswith("multipart/form-data")


def test_api_captures_malformed_unreal_turn_json_before_returning_422(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MURPHY_UNREAL_REQUEST_CAPTURE_MODE", "debug")
    monkeypatch.setenv("MURPHY_UNREAL_REQUEST_CAPTURE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(app, raise_server_exceptions=False)

    with SAMPLE_WAV.open("rb") as audio_file:
        original_audio = audio_file.read()
    response = client.post(
        "/api/game/ai/respond",
        files={
            "turn": (
                "bad_turn.json",
                '{"request_id": "req_bad_json"',
                "application/json",
            ),
            "audio": (
                SAMPLE_WAV.name,
                original_audio,
                "audio/wav",
            ),
        },
    )

    assert response.status_code == 422
    capture_dir = next(tmp_path.iterdir())
    assert (capture_dir / "turn.json").read_text(encoding="utf-8") == '{"request_id": "req_bad_json"'
    assert (capture_dir / "audio.wav").read_bytes() == original_audio


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
