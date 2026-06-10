from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import (
    FlightSmallTalkDiagnosticPolicy,
)


def test_smalltalk_requires_three_player_turns_before_normal_exit() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=2)

    assert decision.scene_id == "FLIGHT_001_SEATMATE_SMALLTALK"
    assert decision.diagnostic_only is True
    assert decision.minimum_turns_met is False
    assert decision.required_more_turns == 1
    assert decision.skip_eligible is False
    assert decision.should_emit_out_game_feedback_seed is True
    assert decision.should_show_out_game_feedback_now is False


def test_smalltalk_allows_normal_exit_after_three_player_turns() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=3)

    assert decision.minimum_turns_met is True
    assert decision.required_more_turns == 0
    assert decision.skip_eligible is False
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

    assert policy.fallback_question(0) == "Is this your first time flying to New York?"
    assert policy.fallback_question(1) == "What are you most excited to do after you land?"
    assert policy.fallback_question(4) == "Do you usually like window seats or aisle seats?"
