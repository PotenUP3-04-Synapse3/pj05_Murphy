from collections.abc import Generator
import json
import random
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.integrations.dev_a_npc_dialogue_client import DevANpcDialogueClient
from backend.app.main import app
from backend.app.schemas.game_turn import (
    DevADialogueInput,
    DevADialogueOutput,
    IncivilityClassification,
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
    session_id: str | None = None,
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
    if session_id is not None:
        turn_payload["session"]["session_id"] = session_id
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


def _read_openkb_session_records(jsonl_path: Path) -> list[dict[str, Any]]:
    if not jsonl_path.exists():
        return []
    return [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _remove_openkb_session_records(runtime_dir: Path, jsonl_path: Path) -> None:
    for record in _read_openkb_session_records(jsonl_path):
        record_id = record.get("record_id")
        if isinstance(record_id, str):
            markdown_path = runtime_dir / f"{record_id}.md"
            if markdown_path.exists():
                markdown_path.unlink()
    if jsonl_path.exists():
        jsonl_path.unlink()


def _remove_dialogue_history_records(jsonl_path: Path) -> None:
    if jsonl_path.exists():
        jsonl_path.unlink()


def test_orchestrator_connects_stt_understanding_dev_b_dev_a_and_response() -> None:
    response = Orchestrator().run_turn(_preprototype_request())

    assert response.contract_version == "dev_c_unreal_response.v1"
    assert response.request_id == "req_imm_0001"
    assert response.current_node_id == "IMM_002_PURPOSE"
    assert response.next_node_id == "IMM_003_DURATION"
    assert response.next_action == "ADVANCE"
    assert response.npc.speaker == "Officer Hale"
    assert response.npc.text == "How long will you stay in the United States?"
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


def test_orchestrator_allows_incivility_bad_end_branch_outside_normal_next_nodes() -> None:
    response = Orchestrator().run_turn(_preprototype_request(transcript="fuck you"))

    assert response.next_action == "COMPLETE_CHAPTER"
    assert response.next_node_id == "IMM_BAD_END_VERBAL_ABUSE"
    assert response.evaluation.verdict == "FAIL"
    assert "verbal_abuse" in response.evaluation.feedback_tags
    assert response.transition is not None
    assert response.transition.unreal_event == "SHOW_BAD_END_SCOREBOARD"
    assert response.flow.transition_type == "scoreboard"
    assert response.flow.transition_id == "bad_end_scoreboard"
    assert response.flow.show_scoreboard is True


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
    assert response.npc.text == "All right, you're cleared."


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
    session_id = "session_alpha_flight_wrap_up_transition_0001"
    runtime_dir = Path("backend/runtime/openkb/dev_b")
    dev_c_jsonl_path = Path("backend/runtime/openkb/dev_c/dialogue_history") / f"{session_id}.jsonl"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = runtime_dir / f"{session_id}.jsonl"
    _remove_dialogue_history_records(dev_c_jsonl_path)
    
    mock_record = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "dialogue_seed": {
            "scene": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "npc_role": "seatmate_passenger",
            "surface_goal": "TRAVEL_PURPOSE",
            "hidden_assessment_goal": "estimate_user_travel_speaking_level",
            "opening_intent": "ask_purpose",
            "difficulty_profile": "auto",
            "tone_guidance": "neutral",
            "stop_condition": "enough_evidence"
        },
        "evaluation": {"verdict": "SUCCESS"},
        "understanding": {"confidence": 0.9}
    }

    try:
        with jsonl_path.open("w", encoding="utf-8") as f:
            for _ in range(4):
                f.write(json.dumps(mock_record) + "\n")

        turn_payload = _turn_payload()
        turn_payload["request_id"] = "req_alpha_flight_to_imm_0001"
        turn_payload["session"]["chapter_id"] = "CH0_01_FLIGHT_SMALLTALK"
        turn_payload["session"]["scene_id"] = "FLIGHT_SEATMATE_SMALLTALK"
        turn_payload["session"]["current_node_id"] = "FLIGHT_A_001_SEATMATE_SMALLTALK"
        turn_payload["session"]["turn_index"] = 5
        turn_payload["npc"]["npc_id"] = "SEATMATE_A_01"
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
        assert response.game_state is not None
        assert response.game_state.assigned_visit_location
        assert response.game_state.assigned_visit_location_ko
        assert response.game_state.visit_location_difficulty is not None
        assert response.game_state.visit_location_suspicion_reason
    finally:
        if jsonl_path.exists():
            jsonl_path.unlink()
        _remove_dialogue_history_records(dev_c_jsonl_path)


def test_orchestrator_persists_flight_smalltalk_records_for_adaptive_controller(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(random, "random", lambda: 0.9)
    monkeypatch.setattr(random, "choices", lambda pop, weights=None, cum_weights=None, k=1: [pop[0]])
    session_id = "session_flight_smalltalk_openkb_accumulation"
    runtime_dir = Path("backend/runtime/openkb/dev_b")
    dev_c_jsonl_path = Path("backend/runtime/openkb/dev_c/dialogue_history") / f"{session_id}.jsonl"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = runtime_dir / f"{session_id}.jsonl"
    _remove_openkb_session_records(runtime_dir, jsonl_path)
    _remove_dialogue_history_records(dev_c_jsonl_path)

    transcripts = [
        "I like playing computer games.",
        "I want to visit museums and eat pizza.",
        "I might stay with my friend.",
        "I feel a little nervous but ready.",
        "Thanks for the friendly talk.",
    ]

    try:
        response = None
        for turn_index, transcript in enumerate(transcripts, start=1):
            turn_payload = _turn_payload()
            turn_payload["request_id"] = f"req_flight_diag_openkb_{turn_index:04d}"
            turn_payload["session"]["session_id"] = session_id
            turn_payload["session"]["chapter_id"] = "CH0_01_FLIGHT_SMALLTALK"
            turn_payload["session"]["scene_id"] = "FLIGHT_A_001_SEATMATE_SMALLTALK"
            turn_payload["session"]["current_node_id"] = "FLIGHT_A_001_SEATMATE_SMALLTALK"
            turn_payload["session"]["turn_index"] = turn_index
            turn_payload["npc"]["npc_id"] = "SEATMATE_A_01"
            turn_payload["npc"]["npc_role"] = "seatmate"
            turn_payload["npc"]["last_npc_message"] = "Let's chat while we wait to land."
            turn_payload["game_state"]["flags"] = ["flight_level_test_active"]
            turn_payload["game_state"]["completed_intents"] = []
            turn_payload["game_state"]["current_objective"] = "Continue the flight diagnostic small talk"
            turn_payload["previous_node_results"] = []
            turn_payload["client_allowed_next_nodes"] = [
                "FLIGHT_A_001_SEATMATE_SMALLTALK",
                "FLIGHT_999_COMPLETE",
            ]

            response = Orchestrator().run_turn(
                PrePrototypeRequest(
                    turn=UnrealTurnRequest.model_validate(turn_payload),
                    audio=MockAudioInput(
                        mock_wav_path=f"mock://alpha/flight_diag_{turn_index}.wav",
                        transcript=transcript,
                    ),
                )
            )

            records = _read_openkb_session_records(jsonl_path)
            assert len(records) == turn_index
            assert records[-1]["node_id"] == "FLIGHT_A_001_SEATMATE_SMALLTALK"
            assert records[-1]["understanding"]["confidence"] == pytest.approx(response.debug.understanding_confidence)
            assert records[-1]["evaluation"]["verdict"] == response.evaluation.verdict
            assert records[-1]["dialogue_seed"]["surface_goal"]

        assert response is not None
        assert response.next_action == "COMPLETE_CHAPTER"
        assert response.next_node_id == "FLIGHT_999_COMPLETE"
    finally:
        _remove_openkb_session_records(runtime_dir, jsonl_path)
        _remove_dialogue_history_records(dev_c_jsonl_path)


def test_orchestrator_marks_immigration_clearance_as_baggage_scene_transition() -> None:
    builder_payloads: list[dict[str, Any]] = []

    def capture_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Officer Hale",
            "npc_text": "All right, you're cleared.",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "Good.",
            "tts": {
                "audio_url": "/runtime/audio/edge/immigration-cleared.wav",
            },
        }

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
    orchestrator = Orchestrator()
    orchestrator.dev_a_client = DevANpcDialogueClient(
        settings=AppSettings(murphy_npc_dialogue_mode="llm"),
        voice_output_builder=capture_voice_output_builder,
    )

    response = orchestrator.run_turn(request)

    assert response.next_action == "COMPLETE_CHAPTER"
    assert response.next_node_id == "IMM_999_CLEARED"
    assert response.transition is not None
    assert response.transition.entry_node_id == "BAG_001_REPORT_MISSING_AT_DESK"
    assert response.flow.transition_type == "scene_transition"
    assert response.flow.transition_id == "immigration_to_baggage_claim"
    assert response.flow.to_scene_id == "BAGGAGE_MISSING"
    assert response.flow.cinematic_id is None
    assert response.flow.skip_allowed is False
    assert response.game_state is not None
    assert response.game_state.random_customs_item is not None
    assert response.game_state.random_customs_item.item_name
    assert response.game_state.random_customs_item.difficulty is not None
    assert response.game_state.random_customs_item.suspicion_reason
    assert builder_payloads
    assert builder_payloads[0]["dialogue_seed"]["suspicion_scope"] == "none"
    assert builder_payloads[0]["dialogue_seed"]["challenge_context"] is None


def test_orchestrator_attaches_recent_dialogue_history_to_dev_a_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MURPHY_C_LEGACY_HISTORY", "1")
    session_id = "session_dialogue_history_c_bridge"
    runtime_dir = Path("backend/runtime/openkb/dev_b")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = runtime_dir / f"{session_id}.jsonl"
    _remove_openkb_session_records(runtime_dir, jsonl_path)

    builder_payloads: list[dict[str, Any]] = []

    def capture_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Officer Hale",
            "npc_text": "Where exactly are you staying?",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "Good.",
            "tts": {
                "audio_url": "/runtime/audio/edge/history.wav",
            },
        }

    previous_records = [
        {
            "session_id": session_id,
            "turn_index": 1,
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I'm here for tourism.",
            "understanding": {"extracted_slots": {"visit_purpose": "tourism"}},
            "dialogue_seed": {"surface_goal": "ask_stay_duration"},
        },
        {
            "session_id": session_id,
            "turn_index": 2,
            "node_id": "IMM_003_DURATION",
            "player_text": "I will stay for five days.",
            "understanding": {"extracted_slots": {"stay_duration": "five days"}},
            "dialogue_seed": {"surface_goal": "ask_stay_location"},
        },
    ]

    try:
        with jsonl_path.open("w", encoding="utf-8") as file:
            for record in previous_records:
                file.write(json.dumps(record) + "\n")

        turn_payload = _turn_payload()
        turn_payload["request_id"] = "req_dialogue_history_c_bridge_0001"
        turn_payload["session"]["session_id"] = session_id
        turn_payload["session"]["current_node_id"] = "IMM_004_STAY_LOCATION"
        turn_payload["session"]["turn_index"] = 3
        turn_payload["npc"]["last_npc_message"] = "Where are you staying?"
        turn_payload["game_state"]["current_objective"] = "State the stay location"
        turn_payload["game_state"]["assigned_visit_location"] = "Downtown Luxury Hotel"
        turn_payload["game_state"]["assigned_visit_location_ko"] = "다운타운 럭셔리 호텔"
        turn_payload["game_state"]["visit_location_difficulty"] = 7
        turn_payload["game_state"]["visit_location_suspicion_reason"] = "Luxury hotel does not match a tight budget."
        turn_payload["game_state"]["arrival_form"] = {
            "full_name": "Sean Han",
            "address": "123 Main Street, Queens",
            "purpose": "tourism",
            "stay_length": "five days",
            "declared_items": ["red ginseng extract"],
        }
        turn_payload["client_allowed_next_nodes"] = [
            "IMM_005_RETURN_TICKET",
            "IMM_004_RETRY_LOCATION",
            "IMM_EXTRA_003_CLARIFY_LOCATION",
            "END_SECONDARY_INSPECTION",
        ]
        request = PrePrototypeRequest(
            turn=UnrealTurnRequest.model_validate(turn_payload),
            audio=MockAudioInput(
                mock_wav_path="mock://immigration/stay_location_address.wav",
                transcript="I will stay at 123 Main Street in Queens.",
            ),
        )
        orchestrator = Orchestrator()
        orchestrator.dev_a_client = DevANpcDialogueClient(
            settings=AppSettings(murphy_npc_dialogue_mode="llm"),
            voice_output_builder=capture_voice_output_builder,
        )

        response = orchestrator.run_turn(request)

        assert response.next_node_id == "IMM_005_RETURN_TICKET"
        assert builder_payloads
        dialogue_seed = builder_payloads[0]["dialogue_seed"]
        assert dialogue_seed["suspicion_scope"] == "location"
        assert dialogue_seed["challenge_context"]["challenge_type"] == "visit_location"
        assert dialogue_seed["challenge_context"]["assigned_visit_location"] == "Downtown Luxury Hotel"
        assert builder_payloads[0]["game_state"]["arrival_form"] == {
            "full_name": "Sean Han",
            "address": "123 Main Street, Queens",
            "purpose": "tourism",
            "stay_duration": "five days",
            "declared_items": ["red ginseng extract"],
        }
        assert response.game_state is not None
        assert response.game_state.arrival_form is not None
        assert response.game_state.arrival_form.stay_duration == "five days"
        assert dialogue_seed["dialogue_history"] == [
            {
                "node_id": "IMM_002_PURPOSE",
                "player_text_preview": "I'm here for tourism.",
                "npc_text_preview": "ask_stay_duration",
                "filled_slots": {"visit_purpose": "tourism"},
            },
            {
                "node_id": "IMM_003_DURATION",
                "player_text_preview": "I will stay for five days.",
                "npc_text_preview": "ask_stay_location",
                "filled_slots": {"stay_duration": "five days"},
            },
        ]
    finally:
        _remove_openkb_session_records(runtime_dir, jsonl_path)


def test_orchestrator_persists_dev_a_npc_text_for_next_dialogue_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MURPHY_C_LEGACY_HISTORY", "1")
    session_id = "session_dialogue_history_npc_text_sidecar"
    dev_b_runtime_dir = Path("backend/runtime/openkb/dev_b")
    dev_c_runtime_dir = Path("backend/runtime/openkb/dev_c/dialogue_history")
    dev_b_runtime_dir.mkdir(parents=True, exist_ok=True)
    dev_c_runtime_dir.mkdir(parents=True, exist_ok=True)
    dev_b_jsonl_path = dev_b_runtime_dir / f"{session_id}.jsonl"
    dev_c_jsonl_path = dev_c_runtime_dir / f"{session_id}.jsonl"
    _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)
    _remove_dialogue_history_records(dev_c_jsonl_path)

    builder_payloads: list[dict[str, Any]] = []

    def capture_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        npc_text = (
            "How long will you stay?"
            if payload["node_id"] == "IMM_002_PURPOSE"
            else "Please confirm your return ticket."
        )
        return {
            "speaker": "Officer Hale",
            "npc_text": npc_text,
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "Good.",
            "tts": {"audio_url": "/runtime/audio/edge/history-sidecar.wav"},
        }

    try:
        orchestrator = Orchestrator()
        orchestrator.dev_a_client = DevANpcDialogueClient(
            settings=AppSettings(murphy_npc_dialogue_mode="llm"),
            voice_output_builder=capture_voice_output_builder,
        )

        first_turn = _turn_payload()
        first_turn["request_id"] = "req_dialogue_history_sidecar_0001"
        first_turn["session"]["session_id"] = session_id
        first_turn["session"]["turn_index"] = 1
        first_response = orchestrator.run_turn(
            PrePrototypeRequest(
                turn=UnrealTurnRequest.model_validate(first_turn),
                audio=MockAudioInput(
                    mock_wav_path="mock://immigration/purpose_tourism.wav",
                    transcript="I'm here for tourism.",
                ),
            )
        )

        assert first_response.next_action == "ADVANCE"
        assert first_response.npc.text == "How long will you stay?"
        assert dev_c_jsonl_path.exists()

        second_turn = _turn_payload()
        second_turn["request_id"] = "req_dialogue_history_sidecar_0002"
        second_turn["session"]["session_id"] = session_id
        second_turn["session"]["current_node_id"] = "IMM_003_DURATION"
        second_turn["session"]["turn_index"] = 2
        second_turn["npc"]["last_npc_message"] = first_response.npc.text
        second_turn["game_state"]["current_objective"] = "State the stay duration"
        second_turn["game_state"]["completed_intents"] = ["submit_passport", "state_visit_purpose"]
        second_turn["client_allowed_next_nodes"] = [
            "IMM_004_STAY_LOCATION",
            "IMM_003_RETRY_DURATION",
            "IMM_EXTRA_002_CLARIFY_DURATION",
            "END_SECONDARY_INSPECTION",
        ]
        orchestrator.run_turn(
            PrePrototypeRequest(
                turn=UnrealTurnRequest.model_validate(second_turn),
                audio=MockAudioInput(
                    mock_wav_path="mock://immigration/duration_five_days.wav",
                    transcript="I will stay for 5 days.",
                ),
            )
        )

        second_payload = builder_payloads[-1]
        assert second_payload["dialogue_seed"]["dialogue_history"][0]["npc_text_preview"] == (
            "How long will you stay?"
        )
        assert second_payload["dialogue_seed"]["dialogue_history"][0]["filled_slots"] == {
            "visit_purpose": "tourism"
        }
    finally:
        _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)
        _remove_dialogue_history_records(dev_c_jsonl_path)


def test_orchestrator_dialogue_history_window_keeps_last_twelve_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MURPHY_C_LEGACY_HISTORY", "1")
    session_id = "session_dialogue_history_window_twelve"
    dev_b_runtime_dir = Path("backend/runtime/openkb/dev_b")
    dev_c_runtime_dir = Path("backend/runtime/openkb/dev_c/dialogue_history")
    dev_b_runtime_dir.mkdir(parents=True, exist_ok=True)
    dev_c_runtime_dir.mkdir(parents=True, exist_ok=True)
    dev_b_jsonl_path = dev_b_runtime_dir / f"{session_id}.jsonl"
    dev_c_jsonl_path = dev_c_runtime_dir / f"{session_id}.jsonl"
    _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)
    _remove_dialogue_history_records(dev_c_jsonl_path)

    builder_payloads: list[dict[str, Any]] = []

    def capture_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Officer Hale",
            "npc_text": "Continue.",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "Good.",
            "tts": {"audio_url": "/runtime/audio/edge/history-window.wav"},
        }

    try:
        with dev_b_jsonl_path.open("w", encoding="utf-8") as dev_b_file:
            for turn_index in range(1, 15):
                dev_b_file.write(
                    json.dumps(
                        {
                            "session_id": session_id,
                            "request_id": f"req_history_window_{turn_index:04d}",
                            "turn_index": turn_index,
                            "node_id": f"IMM_TEST_{turn_index:03d}",
                            "player_text": f"player turn {turn_index}",
                            "understanding": {
                                "extracted_slots": {f"slot_{turn_index}": f"value_{turn_index}"}
                            },
                            "dialogue_seed": {"surface_goal": f"fallback_goal_{turn_index}"},
                        }
                    )
                    + "\n"
                )

        with dev_c_jsonl_path.open("w", encoding="utf-8") as dev_c_file:
            for turn_index in range(1, 15):
                dev_c_file.write(
                    json.dumps(
                        {
                            "session_id": session_id,
                            "request_id": f"req_history_window_{turn_index:04d}",
                            "turn_index": turn_index,
                            "node_id": f"IMM_TEST_{turn_index:03d}",
                            "npc": {"text": f"npc turn {turn_index}"},
                        }
                    )
                    + "\n"
                )

        turn_payload = _turn_payload()
        turn_payload["request_id"] = "req_history_window_current"
        turn_payload["session"]["session_id"] = session_id
        turn_payload["session"]["current_node_id"] = "IMM_004_STAY_LOCATION"
        turn_payload["session"]["turn_index"] = 15
        turn_payload["npc"]["last_npc_message"] = "Where are you staying?"
        turn_payload["game_state"]["current_objective"] = "State the stay location"
        turn_payload["client_allowed_next_nodes"] = [
            "IMM_005_RETURN_TICKET",
            "IMM_004_RETRY_LOCATION",
            "IMM_EXTRA_003_CLARIFY_LOCATION",
            "END_SECONDARY_INSPECTION",
        ]
        orchestrator = Orchestrator()
        orchestrator.dev_a_client = DevANpcDialogueClient(
            settings=AppSettings(murphy_npc_dialogue_mode="llm"),
            voice_output_builder=capture_voice_output_builder,
        )

        orchestrator.run_turn(
            PrePrototypeRequest(
                turn=UnrealTurnRequest.model_validate(turn_payload),
                audio=MockAudioInput(
                    mock_wav_path="mock://immigration/stay_location_address.wav",
                    transcript="I will stay at 123 Main Street in Queens.",
                ),
            )
        )

        history = builder_payloads[0]["dialogue_seed"]["dialogue_history"]
        assert len(history) == 12
        assert history[0]["node_id"] == "IMM_TEST_003"
        assert history[0]["npc_text_preview"] == "npc turn 3"
        assert history[-1]["node_id"] == "IMM_TEST_014"
        assert history[-1]["npc_text_preview"] == "npc turn 14"
    finally:
        _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)
        _remove_dialogue_history_records(dev_c_jsonl_path)


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
    assert response.npc.text == "How long will you stay in the United States?"


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
    assert "npc_recast_line_candidate" not in builder_payloads[0]["in_game_feedback"]
    assert "recommended_expression" not in builder_payloads[0]["in_game_feedback"]
    assert "recommended_expression" not in builder_payloads[0]["level_hint"]
    assert "recommended_expression" not in builder_payloads[0]["node_context"]
    assert "npc_question" not in builder_payloads[0]["node_context"]
    assert "npc_question_goal" not in builder_payloads[0]["node_context"]
    assert "do_not_generate_npc_text" not in builder_payloads[0]["dialogue_directive"]
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
    assert "npc_recast_line_candidate" not in builder_payloads[0]["in_game_feedback"]
    assert "recommended_expression" not in builder_payloads[0]["in_game_feedback"]
    assert "recommended_expression" not in builder_payloads[0]["level_hint"]
    assert "recommended_expression" not in builder_payloads[0]["node_context"]
    assert "npc_question" not in builder_payloads[0]["node_context"]
    assert "npc_question_goal" not in builder_payloads[0]["node_context"]
    assert "do_not_generate_npc_text" not in builder_payloads[0]["dialogue_directive"]


def test_dev_a_adapter_forwards_incivility_to_voice_builder() -> None:
    builder_payloads: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Officer Miller",
            "npc_text": "Watch your language.",
            "tone": "formal_firm",
            "animation": "officer_warning",
            "feedback_kr": "Language warning.",
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
    understanding = _successful_understanding("state_visit_purpose", "visit_purpose", "tourism").model_copy(
        update={
            "incivility": IncivilityClassification(
                tier=3,
                detected_terms=["fuck"],
                confidence=0.95,
                category="profanity",
                source="rule",
            )
        }
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

    assert builder_payloads[0]["incivility"] == {
        "tier": 3,
        "detected_terms": ["fuck"],
        "confidence": 0.95,
        "category": "profanity",
        "source": "rule",
    }
    assert "recommended_expression" not in builder_payloads[0]["level_hint"]


def test_dev_a_adapter_defaults_missing_incivility_to_tier_zero() -> None:
    builder_payloads: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Officer Miller",
            "npc_text": "Okay. Please continue.",
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
    understanding = _successful_understanding("state_visit_purpose", "visit_purpose", "tourism")
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

    assert builder_payloads[0]["incivility"] == {
        "tier": 0,
        "detected_terms": [],
        "confidence": 0.0,
        "category": "none",
        "source": "none",
    }


def _dev_a_payload_for_request(request: PrePrototypeRequest) -> tuple[DevADialogueOutput, dict[str, Any]]:
    builder_payloads: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        surface_goal = str((payload.get("dialogue_seed") or {}).get("surface_goal") or "")
        generated_text_by_goal = {
            "respond_to_polite_request": "Are you visiting New York for a trip?",
            "travel_purpose_travel": "Are you visiting New York for a trip?",
            "report_missing_bag_at_service_desk": "Do you have your baggage claim tag or ticket?",
            "ask_claim_tag_or_ticket": "Do you have your baggage claim tag or ticket?",
        }
        builder_payloads.append(payload)
        return {
            "speaker": str(payload["npc"]["npc_id"]),
            "npc_text": generated_text_by_goal.get(surface_goal, "Okay."),
            "tone": "friendly_neutral",
            "animation": "dialogue_idle",
            "feedback_kr": "Good.",
            "tts": {
                "audio_url": "/runtime/audio/edge/test.wav",
            },
        }

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

    assert builder_payloads
    return output, builder_payloads[0]


def test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(random, "random", lambda: 0.9)
    monkeypatch.setattr(random, "choices", lambda pop, weights=None, cum_weights=None, k=1: [pop[0]])
    session_id = "session_alpha_flight_seed_0001"
    runtime_dir = Path("backend/runtime/openkb/dev_b")
    jsonl_path = runtime_dir / f"{session_id}.jsonl"
    _remove_openkb_session_records(runtime_dir, jsonl_path)

    try:
        output, payload = _dev_a_payload_for_request(
            _chapter_boundary_request(
                request_id="req_alpha_flight_seed_0001",
                session_id=session_id,
                chapter_id="CH0_01_FLIGHT_SMALLTALK",
                current_node_id="FLIGHT_A_001_SEATMATE_SMALLTALK",
                npc_id="SEATMATE_A_01",
                npc_role="seatmate",
                last_npc_message="Could I borrow your pen for this arrival form?",
                transcript="Sure, here you are.",
                allowed_next_nodes=["FLIGHT_A_001_SEATMATE_SMALLTALK", "FLIGHT_999_COMPLETE"],
            )
        )
    finally:
        _remove_openkb_session_records(runtime_dir, jsonl_path)

    assert output.speaker == "SEATMATE_A_01"
    assert output.text == "Are you visiting New York for a trip?"
    assert payload["npc"]["npc_id"] == "SEATMATE_A_01"
    assert payload["npc"]["npc_role"] == "seatmate"
    assert payload["node_context"]["chapter_id"] == "CH0_01_FLIGHT_SMALLTALK"
    assert "npc_recast_line_candidate" not in payload["in_game_feedback"]
    assert "recommended_expression" not in payload["in_game_feedback"]
    assert "recommended_expression" not in payload["level_hint"]
    assert "recommended_expression" not in payload["node_context"]
    assert "npc_question" not in payload["node_context"]
    assert "npc_question_goal" not in payload["node_context"]
    assert "do_not_generate_npc_text" not in payload["dialogue_directive"]
    assert payload["dialogue_directive"]["purpose"] == "smalltalk_diagnostic"
    assert payload["dialogue_directive"]["target_slot"] is None
    assert payload["node_context"]["required_slots"] == []
    assert payload["dialogue_seed"]["required_slots"] == []
    assert payload["dialogue_seed"]["npc_role"] == "seatmate_passenger"
    assert payload["dialogue_seed"]["surface_goal"] == "travel_purpose_travel"
    assert "advance_to_next_prompt" in payload["dialogue_seed"]["allowed_followup_intents"]
    assert payload["dialogue_seed"]["max_turns"] == 5


def test_dev_a_adapter_allows_flight_rude_refusal_to_continue_smalltalk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(random, "random", lambda: 0.9)
    monkeypatch.setattr(random, "choices", lambda pop, weights=None, cum_weights=None, k=1: [pop[0]])
    builder_payloads: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Arabella",
            "npc_text": "Oh, okay. I can get my own one. By the way, are you traveling for work or fun?",
            "tone": "friendly_neutral",
            "animation": "dialogue_idle",
            "feedback_kr": "Keep the conversation polite.",
            "tts": {
                "audio_url": "/runtime/audio/edge/test.wav",
            },
        }

    session_id = "session_alpha_flight_rude_refusal_continue_0001"
    runtime_dir = Path("backend/runtime/openkb/dev_b")
    dev_c_jsonl_path = Path("backend/runtime/openkb/dev_c/dialogue_history") / f"{session_id}.jsonl"
    jsonl_path = runtime_dir / f"{session_id}.jsonl"
    _remove_openkb_session_records(runtime_dir, jsonl_path)
    _remove_dialogue_history_records(dev_c_jsonl_path)

    try:
        request = _chapter_boundary_request(
            request_id="req_alpha_flight_rude_refusal_continue_0001",
            session_id=session_id,
            chapter_id="CH0_01_FLIGHT_SMALLTALK",
            current_node_id="FLIGHT_A_001_SEATMATE_SMALLTALK",
            npc_id="SEATMATE_A_01",
            npc_role="seatmate",
            last_npc_message="Could I borrow your pen for this arrival form?",
            transcript="Nope. Get yourself your own pen.",
            allowed_next_nodes=["FLIGHT_A_001_SEATMATE_SMALLTALK", "FLIGHT_999_COMPLETE"],
        )
        orchestrator = Orchestrator()
        orchestrator.dev_a_client = DevANpcDialogueClient(
            settings=AppSettings(murphy_npc_dialogue_mode="llm"),
            voice_output_builder=fake_voice_output_builder,
        )

        response = orchestrator.run_turn(request)
    finally:
        _remove_openkb_session_records(runtime_dir, jsonl_path)
        _remove_dialogue_history_records(dev_c_jsonl_path)

    assert response.next_action == "ADVANCE"
    assert response.evaluation.verdict == "SUCCESS"
    assert builder_payloads
    payload = builder_payloads[0]
    assert payload["branch"]["branch_reason"] == "flight_smalltalk_continue"
    assert payload["dialogue_directive"]["purpose"] == "smalltalk_diagnostic"
    assert payload["dialogue_directive"]["topic_switch"] is False
    assert payload["dialogue_seed"]["surface_goal"]
    assert "advance_to_next_prompt" in payload["dialogue_seed"]["allowed_followup_intents"]
    assert response.npc.text == "Oh, okay. I can get my own one. By the way, are you traveling for work or fun?"


def test_orchestrator_forwards_flight_history_and_neutral_slots_to_prevent_pen_loop_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MURPHY_C_LEGACY_HISTORY", "1")
    monkeypatch.setattr(random, "random", lambda: 0.9)
    monkeypatch.setattr(random, "choices", lambda pop, weights=None, cum_weights=None, k=1: [pop[0]])

    session_id = "session_alpha_flight_pen_loop_history_0001"
    dev_b_runtime_dir = Path("backend/runtime/openkb/dev_b")
    dev_c_runtime_dir = Path("backend/runtime/openkb/dev_c/dialogue_history")
    dev_b_jsonl_path = dev_b_runtime_dir / f"{session_id}.jsonl"
    dev_c_jsonl_path = dev_c_runtime_dir / f"{session_id}.jsonl"
    _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)
    _remove_dialogue_history_records(dev_c_jsonl_path)

    builder_payloads: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        npc_text = (
            "Thanks, that's kind. Do you have a spare pen too?"
            if len(builder_payloads) == 1
            else "Sorry about that. Anyway, where are you headed after JFK?"
        )
        return {
            "speaker": "Arabella",
            "npc_text": npc_text,
            "tone": "friendly_neutral",
            "animation": "dialogue_idle",
            "feedback_kr": "Keep the conversation going.",
            "tts": {"audio_url": "/runtime/audio/edge/test.wav"},
        }

    try:
        orchestrator = Orchestrator()
        orchestrator.dev_a_client = DevANpcDialogueClient(
            settings=AppSettings(murphy_npc_dialogue_mode="llm"),
            voice_output_builder=fake_voice_output_builder,
        )

        first_request = _chapter_boundary_request(
            request_id="req_alpha_flight_pen_loop_history_0001",
            session_id=session_id,
            chapter_id="CH0_01_FLIGHT_SMALLTALK",
            current_node_id="FLIGHT_A_001_SEATMATE_SMALLTALK",
            npc_id="SEATMATE_A_01",
            npc_role="seatmate",
            last_npc_message="Could I borrow your pen for this arrival form?",
            transcript="Hi. Sure, here you go. You can have that.",
            allowed_next_nodes=["FLIGHT_A_001_SEATMATE_SMALLTALK", "FLIGHT_999_COMPLETE"],
        )
        first_request.turn.session.turn_index = 1
        first_response = orchestrator.run_turn(first_request)

        second_request = _chapter_boundary_request(
            request_id="req_alpha_flight_pen_loop_history_0002",
            session_id=session_id,
            chapter_id="CH0_01_FLIGHT_SMALLTALK",
            current_node_id="FLIGHT_A_001_SEATMATE_SMALLTALK",
            npc_id="SEATMATE_A_01",
            npc_role="seatmate",
            last_npc_message=first_response.npc.text,
            transcript="Why do you keep asking me about my pen? I already gave it to you.",
            allowed_next_nodes=["FLIGHT_A_001_SEATMATE_SMALLTALK", "FLIGHT_999_COMPLETE"],
        )
        second_request.turn.session.turn_index = 2
        second_response = orchestrator.run_turn(second_request)
    finally:
        _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)
        _remove_dialogue_history_records(dev_c_jsonl_path)

    assert second_response.next_action == "ADVANCE"
    assert len(builder_payloads) == 2
    second_payload = builder_payloads[1]
    assert second_payload["dialogue_directive"]["purpose"] == "smalltalk_diagnostic"
    assert second_payload["dialogue_directive"]["target_slot"] is None
    assert second_payload["node_context"]["required_slots"] == []
    assert second_payload["dialogue_seed"]["required_slots"] == []
    assert second_payload["dialogue_seed"]["dialogue_history"][0]["npc_text_preview"] == (
        "Thanks, that's kind. Do you have a spare pen too?"
    )
    assert "pen" not in second_response.npc.text.lower()


def test_orchestrator_prevents_pen_loop_in_default_memory_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.agents.agent_a.npc_dialogue_agent import reset_graph_singleton_for_testing
    reset_graph_singleton_for_testing()

    monkeypatch.setattr(random, "random", lambda: 0.9)
    monkeypatch.setattr(random, "choices", lambda pop, weights=None, cum_weights=None, k=1: [pop[0]])

    session_id = "session_alpha_flight_pen_loop_memory_0001"
    dev_b_runtime_dir = Path("backend/runtime/openkb/dev_b")
    dev_b_jsonl_path = dev_b_runtime_dir / f"{session_id}.jsonl"
    _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)

    class PenLoopLLMClient:
        model = "fake-model"
        def __init__(self):
            self.call_count = 0

        def generate(self, payload: dict) -> dict:
            self.call_count += 1
            text = "Thanks. Could I borrow your pen for this form?" if self.call_count == 1 else "Sorry about that. Could I borrow your pen for this form?"
            return {
                "speaker": "Arabella",
                "npc_text": text,
                "tts_text": text,
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "joy",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[COHERENT] Pen request.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    try:
        orchestrator = Orchestrator()
        orchestrator.dev_a_client = DevANpcDialogueClient(
            settings=AppSettings(murphy_npc_dialogue_mode="llm"),
            use_llm_dialogue=True,
        )
        monkeypatch.setattr(
            "backend.app.agents.agent_a.npc_dialogue_agent.build_npc_dialogue_llm_client_from_environment",
            lambda: PenLoopLLMClient()
        )

        first_request = _chapter_boundary_request(
            request_id="req_alpha_flight_pen_loop_memory_0001",
            session_id=session_id,
            chapter_id="CH0_01_FLIGHT_SMALLTALK",
            current_node_id="FLIGHT_A_001_SEATMATE_SMALLTALK",
            npc_id="SEATMATE_A_01",
            npc_role="seatmate",
            last_npc_message="Could I borrow your pen for this arrival form?",
            transcript="Hi. Sure, here you go. You can have that.",
            allowed_next_nodes=["FLIGHT_A_001_SEATMATE_SMALLTALK", "FLIGHT_999_COMPLETE"],
        )
        first_request.turn.session.turn_index = 1
        first_response = orchestrator.run_turn(first_request)
        assert "borrow your pen" in first_response.npc.text.lower()

        second_request = _chapter_boundary_request(
            request_id="req_alpha_flight_pen_loop_memory_0002",
            session_id=session_id,
            chapter_id="CH0_01_FLIGHT_SMALLTALK",
            current_node_id="FLIGHT_A_001_SEATMATE_SMALLTALK",
            npc_id="SEATMATE_A_01",
            npc_role="seatmate",
            last_npc_message=first_response.npc.text,
            transcript="Why do you keep asking me about my pen? I already gave it to you.",
            allowed_next_nodes=["FLIGHT_A_001_SEATMATE_SMALLTALK", "FLIGHT_999_COMPLETE"],
        )
        second_request.turn.session.turn_index = 2
        second_response = orchestrator.run_turn(second_request)
    finally:
        _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)

    assert second_response.next_action == "ADVANCE"
    assert "pen" not in second_response.npc.text.lower()


def test_dialogue_history_is_empty_in_default_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure legacy history env variable is unset so that we run in default mode
    monkeypatch.delenv("MURPHY_C_LEGACY_HISTORY", raising=False)

    session_id = "session_alpha_flight_empty_history_0001"
    dev_b_runtime_dir = Path("backend/runtime/openkb/dev_b")
    dev_b_jsonl_path = dev_b_runtime_dir / f"{session_id}.jsonl"
    _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)

    builder_payloads: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Emily",
            "npc_text": "Nice to meet you.",
            "tone": "friendly_neutral",
            "animation": "dialogue_idle",
            "feedback_kr": "Keep the conversation going.",
            "tts": {"audio_url": "/runtime/audio/edge/test.wav"},
        }

    try:
        orchestrator = Orchestrator()
        orchestrator.dev_a_client = DevANpcDialogueClient(
            settings=AppSettings(murphy_npc_dialogue_mode="llm"),
            voice_output_builder=fake_voice_output_builder,
        )

        first_request = _chapter_boundary_request(
            request_id="req_alpha_flight_empty_history_0001",
            session_id=session_id,
            chapter_id="CH0_01_FLIGHT_SMALLTALK",
            current_node_id="FLIGHT_A_001_SEATMATE_SMALLTALK",
            npc_id="SEATMATE_A_01",
            npc_role="seatmate",
            last_npc_message="Could I borrow your pen for this arrival form?",
            transcript="Hi. Sure, here you go.",
            allowed_next_nodes=["FLIGHT_A_001_SEATMATE_SMALLTALK", "FLIGHT_999_COMPLETE"],
        )
        first_request.turn.session.turn_index = 1
        orchestrator.run_turn(first_request)

        second_request = _chapter_boundary_request(
            request_id="req_alpha_flight_empty_history_0002",
            session_id=session_id,
            chapter_id="CH0_01_FLIGHT_SMALLTALK",
            current_node_id="FLIGHT_A_001_SEATMATE_SMALLTALK",
            npc_id="SEATMATE_A_01",
            npc_role="seatmate",
            last_npc_message="Nice to meet you.",
            transcript="Nice to meet you too.",
            allowed_next_nodes=["FLIGHT_A_001_SEATMATE_SMALLTALK", "FLIGHT_999_COMPLETE"],
        )
        second_request.turn.session.turn_index = 2
        orchestrator.run_turn(second_request)
    finally:
        _remove_openkb_session_records(dev_b_runtime_dir, dev_b_jsonl_path)

    assert len(builder_payloads) == 2
    second_payload = builder_payloads[1]
    assert second_payload["dialogue_seed"]["dialogue_history"] == []


def test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata() -> None:
    output, payload = _dev_a_payload_for_request(
        _chapter_boundary_request(
            request_id="req_alpha_bag_seed_0001",
            chapter_id="CH0_04_BAGGAGE_CLAIM",
            current_node_id="BAG_001_REPORT_MISSING_AT_DESK",
            npc_id="BAGGAGE_STAFF",
            npc_role="baggage_service_staff",
            last_npc_message="Hi. How can I help you?",
            transcript="My suitcase didn't arrive. I need help.",
            allowed_next_nodes=["BAG_002_PROVIDE_CLAIM_TAG"],
        )
    )

    assert output.speaker == "BAGGAGE_STAFF"
    assert output.text == "Do you have your baggage claim tag or ticket?"
    assert payload["npc"]["npc_id"] == "BAGGAGE_STAFF"
    assert payload["npc"]["npc_role"] == "baggage_service_staff"
    assert payload["node_context"]["chapter_id"] == "CH0_04_BAGGAGE_CLAIM"
    assert "npc_recast_line_candidate" not in payload["in_game_feedback"]
    assert "recommended_expression" not in payload["in_game_feedback"]
    assert "recommended_expression" not in payload["level_hint"]
    assert "recommended_expression" not in payload["node_context"]
    assert "npc_question" not in payload["node_context"]
    assert "npc_question_goal" not in payload["node_context"]
    assert "do_not_generate_npc_text" not in payload["dialogue_directive"]
    assert payload["dialogue_directive"]["purpose"] == "continue_to_next_question"
    assert payload["dialogue_seed"]["npc_role"] == "baggage_service_agent"
    assert payload["dialogue_seed"]["surface_goal"] == "ask_claim_tag_or_ticket"
    assert "advance_to_next_prompt" in payload["dialogue_seed"]["allowed_followup_intents"]
    assert payload["dialogue_seed"]["max_turns"] == 4


def test_orchestrator_forwards_non_advance_action_purpose_and_surface_goal_to_developer_a() -> None:
    builder_payloads: list[dict[str, Any]] = []

    def fake_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": "Officer Hale",
            "npc_text": "Please answer the stay duration again.",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "Try again.",
            "tts": {"audio_url": "/runtime/audio/edge/non-advance.wav"},
        }

    turn_payload = _turn_payload()
    turn_payload["request_id"] = "req_ab_desync_non_advance_0001"
    turn_payload["session"]["current_node_id"] = "IMM_003_DURATION"
    turn_payload["session"]["turn_index"] = 3
    turn_payload["npc"]["last_npc_message"] = "How long will you stay?"
    turn_payload["game_state"]["current_objective"] = "State the stay duration"
    turn_payload["game_state"]["completed_intents"] = ["submit_passport", "state_visit_purpose"]
    turn_payload["client_allowed_next_nodes"] = [
        "IMM_004_STAY_LOCATION",
        "IMM_003_RETRY_DURATION",
        "IMM_EXTRA_002_CLARIFY_DURATION",
        "END_SECONDARY_INSPECTION",
    ]
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://immigration/duration_unclear.wav",
            transcript="I don't know.",
        ),
    )
    orchestrator = Orchestrator()
    orchestrator.understanding_agent = StaticUnderstandingAgent(
        UnderstandingOutput(
            intent="state_stay_duration",
            intent_success=False,
            confidence=0.55,
            meaning_summary_kr="The player did not clearly state a stay duration.",
            emotion="nervous",
            answer_relevance="partially_related",
            ambiguity_type="unclear_duration",
            risk_delta=0,
            risk_reason="No risk expression was found.",
            risk_tags=[],
            extracted_slots={},
            missing_slots=["stay_duration"],
            needs_clarification=True,
        )
    )
    orchestrator.dev_a_client = DevANpcDialogueClient(
        settings=AppSettings(murphy_npc_dialogue_mode="llm"),
        voice_output_builder=fake_voice_output_builder,
    )

    response = orchestrator.run_turn(request)

    assert response.next_action != "ADVANCE"
    assert builder_payloads
    payload = builder_payloads[0]
    assert payload["branch"]["next_action"] == response.next_action
    assert payload["dialogue_directive"]["purpose"] in {
        "support_retry",
        "provide_hint",
        "warn_and_control_risk",
    }
    assert "do_not_generate_npc_text" not in payload["dialogue_directive"]
    assert payload["dialogue_seed"]["surface_goal"] == "ask_stay_duration"


def test_dev_a_adapter_reports_speaker_mismatch_diagnostic() -> None:
    def mismatched_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {
            "speaker": "Officer Miller",
            "npc_text": "Okay.",
            "tone": "friendly_neutral",
            "animation": "dialogue_idle",
            "feedback_kr": "Good.",
            "tts": {
                "audio_url": "/runtime/audio/edge/test.wav",
            },
        }

    request = _chapter_boundary_request(
        request_id="req_alpha_speaker_mismatch_0001",
        chapter_id="CH0_04_BAGGAGE_CLAIM",
        current_node_id="BAG_001_REPORT_MISSING_AT_DESK",
        npc_id="BAGGAGE_STAFF",
        npc_role="baggage_service_staff",
        last_npc_message="Hi. How can I help you?",
        transcript="My suitcase didn't arrive. I need help.",
        allowed_next_nodes=["BAG_002_PROVIDE_CLAIM_TAG"],
    )
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
        voice_output_builder=mismatched_voice_output_builder,
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

    assert output.diagnostics == [
        {
            "code": "npc_speaker_mismatch",
            "severity": "warning",
            "message": "Developer A returned a speaker that does not match the requested NPC context.",
            "expected_npc_id": "BAGGAGE_STAFF",
            "expected_npc_role": "baggage_service_staff",
            "actual_speaker": "Officer Miller",
        }
    ]


def test_orchestrator_passes_random_customs_item_and_routes_customs_npc_to_developer_a() -> None:
    builder_payloads: list[dict[str, Any]] = []

    def capture_voice_output_builder(
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        builder_payloads.append(payload)
        return {
            "speaker": str(payload["npc"]["npc_id"]),
            "npc_text": "Thank you.",
            "tone": "formal_neutral",
            "animation": "customs_inspection_idle",
            "feedback_kr": "Good.",
            "tts": {
                "audio_url": "/runtime/audio/edge/customs-item.wav",
            },
        }

    turn_payload = _turn_payload()
    turn_payload["request_id"] = "req_alpha_random_customs_item_0001"
    turn_payload["session"]["chapter_id"] = "CH0_04_BAGGAGE_CLAIM"
    turn_payload["session"]["scene_id"] = "JFK_BAGGAGE_CLAIM"
    turn_payload["session"]["current_node_id"] = "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"
    turn_payload["session"]["turn_index"] = 16
    turn_payload["npc"]["npc_id"] = "BAGGAGE_STAFF"
    turn_payload["npc"]["npc_role"] = "baggage_service_staff"
    turn_payload["npc"]["last_npc_message"] = "Can you explain what this item is and why it is in your suitcase?"
    turn_payload["game_state"]["current_objective"] = "Explain the random customs item"
    turn_payload["game_state"]["random_customs_item"] = {
        "item_id": "medicine_red_ginseng_extract",
        "item_name": "red ginseng extract",
        "item_category": "medicine",
        "item_description": "Small bottles of Korean red ginseng extract.",
        "visit_location": "Queens",
        "declared": False,
        "source": "unreal_csv",
    }
    turn_payload["client_allowed_next_nodes"] = [
        "BAG_006_CLARIFY_EXPLAIN_RANDOM_CUSTOMS_ITEM",
        "BAG_006_RETRY_EXPLAIN_RANDOM_CUSTOMS_ITEM",
        "BAG_007_CUSTOMS_CLEARANCE",
        "END_BAGGAGE_REPORT_INCOMPLETE",
    ]
    request = PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path="mock://alpha/customs_item_red_ginseng.wav",
            transcript="It's red ginseng medicine for my health.",
        ),
    )
    orchestrator = Orchestrator()
    orchestrator.dev_a_client = DevANpcDialogueClient(
        settings=AppSettings(murphy_npc_dialogue_mode="llm"),
        voice_output_builder=capture_voice_output_builder,
    )

    response = orchestrator.run_turn(request)

    assert response.next_node_id == "BAG_007_CUSTOMS_CLEARANCE"
    assert builder_payloads
    payload = builder_payloads[0]
    assert payload["npc"]["npc_id"] == "CUSTOMS_OFFICER"
    assert payload["npc"]["npc_role"] == "customs_officer"
    assert payload["random_customs_item"] == {
        "item_id": "medicine_red_ginseng_extract",
        "item_name": "red ginseng extract",
        "item_category": "medicine",
        "item_description": "Small bottles of Korean red ginseng extract.",
        "visit_location": "Queens",
        "declared": False,
        "source": "unreal_csv",
        "difficulty": None,
        "suspicion_reason": None,
    }
    assert payload["dialogue_seed"]["suspicion_scope"] == "declaration"
    assert payload["dialogue_seed"]["challenge_context"]["challenge_type"] == "customs_item"
    assert payload["dialogue_seed"]["challenge_context"]["item_name"] == "red ginseng extract"
    assert payload["understanding"]["extracted_slots"]["customs_item_explanation"] == "medicine"


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


def test_api_reports_realtime_transcript_provider_as_stt_runtime() -> None:
    client = TestClient(app)
    payload = {
        "turn": _turn_payload(),
        "audio": {
            "transcript": "I'm here for tourism.",
            "transcript_provider": "elevenlabs_relay",
            "file_name": "realtime-final-transcript.txt",
            "content_type": "text/plain",
        },
    }

    response = client.post("/api/game/ai/respond", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["stt"]["player_text"] == "I'm here for tourism."
    assert body["stt"]["model"] == "scribe_v2_realtime"
    assert body["stt"]["runtime_used"] == "elevenlabs_relay"
    assert body["debug"]["stt_model"] == "scribe_v2_realtime"
    assert body["debug"]["timing_ms"]["stt_ms"] == 0


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
    assert body["npc"]["text"] == "How long will you stay in the United States?"
    assert body["npc"]["audio_url"].startswith("/runtime/audio/edge/")

    audio_response = client.get(body["npc"]["audio_url"])
    assert audio_response.status_code == 200
    assert audio_response.content.startswith(b"RIFF")


def test_api_prefers_realtime_transcript_embedded_in_multipart_turn_audio() -> None:
    client = TestClient(app)
    turn_payload = _turn_payload()
    turn_payload["audio"]["duration_ms"] = 0
    turn_payload["audio"]["transcript"] = "Hello."
    turn_payload["audio"]["transcript_provider"] = "elevenlabs_relay"

    response = client.post(
        "/api/game/ai/respond",
        files={
            "turn": (
                "imm_002_purpose.json",
                json.dumps(turn_payload),
                "application/json",
            ),
            "audio": (
                "too-short.wav",
                b"RIFF....WAVEfmt ",
                "audio/wav",
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stt"]["player_text"] == "Hello."
    assert body["stt"]["runtime_used"] == "elevenlabs_relay"
    assert body["stt"]["model"] == "scribe_v2_realtime"


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
