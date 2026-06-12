from typing import Any

from fastapi.testclient import TestClient
import pytest

from backend.app.api import ai_respond
from backend.app.main import app
from backend.app.schemas.game_turn import (
    DevADialogueOutput,
    DevBPolicyOutput,
    FinalResult,
    InputSource,
    MockAudioInput,
    NormalizedInput,
    PrePrototypeRequest,
    RecordedErrorSummary,
    UnrealTurnRequest,
    UnderstandingOutput,
)
from backend.app.services.service_c.response_builder import ResponseBuilder
from backend.app.services.service_c.validator import ValidationError, Validator


def _turn_payload() -> dict[str, Any]:
    return {
        "contract_version": "dev_c_unreal_turn.v1",
        "request_id": "req_final_result",
        "session": {
            "session_id": "session_final_result",
            "player_id": "player_final_result",
            "chapter_id": "CH0_03_IMMIGRATION_CHECK",
            "scene_id": "JFK_IMMIGRATION_HALL",
            "current_node_id": "IMM_007_FINAL_DECISION",
            "turn_index": 8,
        },
        "npc": {
            "npc_id": "OFFICER_MILLER",
            "npc_role": "immigration_officer",
            "last_npc_message": "All right, you're cleared to enter. Enjoy your stay.",
        },
        "audio": {
            "mime_type": "audio/wav",
            "sample_rate_hz": 16000,
            "channels": 1,
            "duration_ms": 1800,
            "language_hint": "en-US",
        },
        "player_profile": {
            "nickname": "Sean",
            "english_confidence": "beginner",
            "tier": "Bronze",
            "travel_speaking_level": "TSL_1_SURVIVAL",
        },
        "scenario_state": {
            "patience": 90,
            "suspicion": 0,
            "retry_count": 0,
            "hint_count": 0,
            "previous_fail_count": 0,
        },
        "game_state": {
            "inventory": ["passport", "boarding_pass", "return_ticket"],
            "flags": ["arrived_at_jfk"],
            "completed_intents": ["submit_passport"],
            "current_objective": "Receive final result",
        },
        "previous_node_results": [],
        "client_allowed_next_nodes": ["END_PASS", "END_SECONDARY_INSPECTION"],
        "client_context": {"platform": "windows"},
    }


def _request() -> PrePrototypeRequest:
    return PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(_turn_payload()),
        audio=MockAudioInput(transcript="Thank you."),
    )


def _normalized_input() -> NormalizedInput:
    return NormalizedInput(
        player_text="Thank you.",
        input_source=InputSource(
            input_type="voice",
            stt_confidence=0.91,
            language_detected="en-US",
            needs_repeat=False,
        ),
        stt_model="whisper-large-v3-turbo",
        stt_primary_runtime="local",
        stt_fallback_runtime="api",
        stt_runtime_used="local",
    )


def _understanding() -> UnderstandingOutput:
    return UnderstandingOutput(
        intent="summarize_final_result",
        intent_success=True,
        confidence=0.95,
        meaning_summary_kr="The traveler acknowledged the final result.",
        emotion="calm",
        answer_relevance="on_topic",
        ambiguity_type="none",
        risk_delta=0,
        risk_reason="No risk expression was found.",
        risk_tags=[],
        extracted_slots={"final_recommendation": "PASS"},
        missing_slots=[],
        needs_clarification=False,
    )


def _final_result(score: int = 87) -> dict[str, Any]:
    return {
        "final_recommendation": "PASS",
        "rank": "Silver Pass",
        "final_score_100": score,
        "reason_tags": ["score_at_least_80"],
        "quantitative_scores": {
            "overall": score,
            "comprehension": 90,
            "fluency": 80,
            "grammar_accuracy": 80,
            "vocabulary_range": 90,
            "clarity": 90,
            "interaction_problem_solving": 90,
            "scoring_policy": "simple_average",
        },
        "report_summary": {
            "overall": "You passed the immigration check.",
            "best_node": "IMM_003_DURATION",
            "weakest_node": "IMM_002_PURPOSE",
            "main_improvement": "Keep answers concise and polite.",
            "focus_on_form_targets": [],
            "included_node_count": 6,
        },
    }


def _dev_b_output(final_result: dict[str, Any] | None = None) -> DevBPolicyOutput:
    payload: dict[str, Any] = {
        "contract_version": "dev_b_policy.v1",
        "node_id": "IMM_007_FINAL_DECISION",
        "evaluation": {
            "verdict": "SUCCESS",
            "detected_intents": ["summarize_final_result"],
            "required_intents_passed": True,
            "filled_slots": {"final_recommendation": "PASS"},
            "missing_slots": [],
            "scores": {
                "task_success": 3,
                "clarity": 3,
                "grammar": 2,
                "vocabulary": 2,
                "problem_solving": 2,
                "politeness": 3,
            },
            "feedback_tags": ["intent_matched"],
            "feedback_note": "The final result is ready.",
        },
        "level_hint": {
            "english_level": "beginner",
            "travel_speaking_level": "TSL_1_SURVIVAL",
            "cefr_estimate": "A1",
            "needs_hint": False,
            "hint_level": "none",
            "hint_type": None,
            "hint_kr": None,
            "example_en": "Thank you, officer.",
            "avoid_expression": None,
            "recommended_expression": "Thank you, officer.",
        },
        "in_game_feedback": {
            "show": False,
            "feedback_strategy": "none",
            "timing": "during_dialogue_turn",
            "priority": "low",
            "purpose": "maintain_communication",
            "focus": "summarize_final_result",
            "npc_recast_line_candidate": None,
            "clarification_prompt_candidate": None,
            "elicitation_cue_candidate": None,
            "scaffolding_hint": None,
            "recommended_expression": "Thank you, officer.",
            "display_duration_ms": None,
            "blocks_progression": False,
        },
        "error_capture": {
            "should_record": False,
            "storage_format": "markdown",
            "error_items": [],
            "markdown_entry": None,
        },
        "out_game_feedback_seed": {
            "include_in_final_report": False,
            "openkb_query_tags": [],
            "focus_on_form_targets": [],
            "report_priority": "low",
        },
        "branch": {
            "branch_type": "final",
            "next_action": "FINAL_DECISION",
            "next_node_id": "END_PASS",
            "branch_reason": "Final result is ready.",
            "allowed_next_node_checked": True,
        },
        "state_delta": {
            "patience_delta": 0,
            "suspicion_delta": 0,
            "retry_count_delta": 0,
            "hint_count_delta": 0,
        },
        "report_item": {
            "summary": "The traveler completed the immigration check.",
            "improvement": "Keep answers concise and polite.",
            "example_answer": "Thank you, officer.",
            "score_tags": ["task_success_good"],
        },
    }
    if final_result is not None:
        payload["final_result"] = final_result
    return DevBPolicyOutput.model_validate(payload)


def test_response_builder_includes_dev_b_final_result_for_unreal_report() -> None:
    response = ResponseBuilder().build_unreal_response(
        request=_request(),
        normalized_input=_normalized_input(),
        understanding=_understanding(),
        dev_b_output=_dev_b_output(final_result=_final_result()),
        dev_a_output=DevADialogueOutput(
            contract_version="dev_a_dialogue.v1",
            speaker="Officer Miller",
            text="All right, you're cleared to enter. Enjoy your stay.",
            tone="formal_neutral",
            animation="officer_check_passport",
            audio_url="/runtime/audio/kokoro/final.wav",
        ),
        logging_summary=RecordedErrorSummary(
            recorded=False,
            storage_format="markdown",
            error_log_markdown_path=None,
            recorded_error_count=0,
        ),
    )

    assert response.report.final_result is not None
    assert response.report.final_result.final_score_100 == 87
    assert response.report.final_result.final_recommendation == "PASS"


def test_validator_rejects_inconsistent_final_result_overall_score() -> None:
    policy_output = _dev_b_output(final_result=_final_result())
    assert policy_output.final_result is not None
    policy_output.final_result.quantitative_scores.overall = 86

    with pytest.raises(ValidationError, match="final_result.final_score_100"):
        Validator().validate_dev_b_policy_output(
            policy_output,
            current_node_id="IMM_007_FINAL_DECISION",
            allowed_next_nodes=["END_PASS", "END_SECONDARY_INSPECTION"],
            client_allowed_next_nodes=["END_PASS", "END_SECONDARY_INSPECTION"],
        )


def test_result_endpoint_returns_unreal_result_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDevBPolicyClient:
        def final_result_for_session(self, session_id: str) -> FinalResult:
            assert session_id == "session_final_result"
            return FinalResult.model_validate(_final_result())

    monkeypatch.setattr(ai_respond, "DevBPolicyClient", FakeDevBPolicyClient)
    client = TestClient(app)

    response = client.get("/api/game/ai/result/session_final_result")

    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "dev_c_unreal_result.v1"
    assert body["session_id"] == "session_final_result"
    assert body["final_result"]["final_score_100"] == 87
