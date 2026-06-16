from pathlib import Path
from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import (
    FlightSmallTalkDiagnosticPolicy,
)
from backend.tests.dev_b.test_developer_b_policy_engine import _policy_input, _node_context, _agent


def test_smalltalk_requires_five_player_turns_before_normal_exit() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=4)

    assert decision.scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK"
    assert decision.diagnostic_only is True
    assert decision.minimum_turns_met is False
    assert decision.required_more_turns == 1
    assert decision.skip_eligible is False
    assert decision.should_emit_out_game_feedback_seed is True
    assert decision.should_show_out_game_feedback_now is False


def test_smalltalk_allows_normal_exit_after_five_player_turns() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=5)

    assert decision.minimum_turns_met is True
    assert decision.required_more_turns == 0
    assert decision.skip_eligible is True
    assert decision.should_emit_out_game_feedback_seed is True
    assert decision.should_show_out_game_feedback_now is False


def test_smalltalk_skip_becomes_eligible_after_five_player_turns() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=5)

    assert decision.minimum_turns_met is True
    assert decision.required_more_turns == 0
    assert decision.skip_eligible is True
    assert decision.should_emit_out_game_feedback_seed is True
    assert decision.should_show_out_game_feedback_now is False


def test_smalltalk_fallback_questions_are_available_when_flow_stalls() -> None:
    policy = FlightSmallTalkDiagnosticPolicy()

    assert policy.fallback_question(0) == "Could I borrow your pen for this form?"
    assert policy.fallback_question(1) == "Are you visiting New York for a trip?"
    assert policy.fallback_question(4) == "Looks like we're landing soon. Are you ready for immigration?"


def test_flight_smalltalk_offtopic_does_not_reask(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="I like playing computer games.",
        intent_success=False,
        answer_relevance="off_topic",
        confidence=0.8,
    )

    result = _agent(tmp_path).evaluate_turn(payload)

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.branch_type == "success"
    assert result.branch.next_action == "ADVANCE"
    assert result.branch.next_node_id == "FLIGHT_A_002_TRAVEL_PURPOSE"
    assert result.state_delta.patience_delta == 0
    assert result.state_delta.retry_count_delta == 0


def test_flight_smalltalk_missing_slot_still_advances(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="Hello",
        intent_success=False,
        missing_slots=["polite_response"],
        confidence=0.8,
    )

    result = _agent(tmp_path).evaluate_turn(payload)

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.branch_type == "success"
    assert result.branch.next_action == "ADVANCE"
    assert result.branch.next_node_id == "FLIGHT_A_002_TRAVEL_PURPOSE"


def test_flight_smalltalk_no_penalty_delta(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="Sure",
        intent_success=True,
    )

    result = _agent(tmp_path).evaluate_turn(payload)

    assert result.state_delta.patience_delta == 0
    assert result.state_delta.suspicion_delta == 0
    assert result.state_delta.retry_count_delta == 0
    assert result.state_delta.hint_count_delta == 0


def test_flight_smalltalk_low_confidence_clarifies_softly(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")

    # 1. low confidence
    payload = _policy_input(
        node_context=context,
        player_text="Uh",
        confidence=0.2,
    )
    result = _agent(tmp_path).evaluate_turn(payload)

    assert result.evaluation.verdict == "UNCLEAR"
    assert result.branch.branch_type == "clarify"
    assert result.branch.next_action == "REASK"
    assert result.state_delta.patience_delta == 0
    assert result.state_delta.retry_count_delta == 0

    # 2. needs repeat
    payload2 = _policy_input(
        node_context=context,
        player_text="Pardon?",
        confidence=0.9,
    )
    payload2.input_source.needs_repeat = True
    result2 = _agent(tmp_path).evaluate_turn(payload2)

    assert result2.evaluation.verdict == "UNCLEAR"
    assert result2.branch.branch_type == "clarify"
    assert result2.state_delta.patience_delta == 0
    assert result2.state_delta.retry_count_delta == 0


def test_flight_smalltalk_critical_risk_still_guarded(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="I want to work illegally in the US.",
        intent_success=False,
        risk_delta=30,
        risk_tags=["illegal_work_intent"],
    )

    result = _agent(tmp_path).evaluate_turn(payload)

    assert result.evaluation.verdict == "CRITICAL_FAIL"
    assert result.branch.branch_type in {"warning", "bad_end"}
    assert result.state_delta.patience_delta == -20
    assert result.state_delta.suspicion_delta >= 20


def test_flight_smalltalk_feedback_is_out_game_only(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="Sure",
    )

    result = _agent(tmp_path).evaluate_turn(payload)

    assert result.in_game_feedback.show is False
    assert result.in_game_feedback.feedback_strategy == "none"
    assert result.in_game_feedback.blocks_progression is False
    assert result.out_game_feedback_seed.include_in_final_report is True
    assert "smalltalk_response_clarity" in result.out_game_feedback_seed.focus_on_form_targets
