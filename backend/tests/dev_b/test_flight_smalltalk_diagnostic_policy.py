import json
from pathlib import Path
import pytest

from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import (
    FlightSmallTalkDiagnosticPolicy,
)
from backend.tests.dev_b.test_developer_b_policy_engine import _policy_input, _node_context, _agent


def test_smalltalk_requires_three_player_turns_before_normal_exit() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=2)

    assert decision.scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK"
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
    assert decision.skip_eligible is True
    assert decision.should_emit_out_game_feedback_seed is True
    assert decision.should_show_out_game_feedback_now is False


def test_smalltalk_skip_becomes_eligible_after_three_player_turns() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=3)

    assert decision.minimum_turns_met is True
    assert decision.required_more_turns == 0
    assert decision.skip_eligible is True
    assert decision.should_emit_out_game_feedback_seed is True
    assert decision.should_show_out_game_feedback_now is False





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
    assert result.branch.next_node_id == "FLIGHT_A_001_SEATMATE_SMALLTALK"
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
    assert result.branch.next_node_id == "FLIGHT_A_001_SEATMATE_SMALLTALK"


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


def test_steering_zero_never_forces_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Set steering parameter to 0
    from backend.app.services.service_b import flight_smalltalk_diagnostic_policy
    monkeypatch.setattr(flight_smalltalk_diagnostic_policy, "STEERING", 0.0)

    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(node_context=context, player_text="Sure")
    
    policy = FlightSmallTalkDiagnosticPolicy(runtime_root=tmp_path / "openkb" / "dev_b")
    decision = policy.decide_conversational(payload)
    
    assert decision.selected_probe is not None
    # Instead of deterministic first probe, it does a weighted choice on unmeasured competencies.
    # We assert that the chosen probe is one of the valid configured probes.
    probe_ids = {p["probe_id"] for p in policy.probes}
    assert decision.selected_probe["probe_id"] in probe_ids


def test_probe_selection_prefers_coherent_topic(tmp_path: Path) -> None:
    # Setup some history to set topic tag
    runtime_root = tmp_path / "openkb" / "dev_b"
    runtime_root.mkdir(parents=True, exist_ok=True)
    
    # Write a past record with travel_purpose probe
    history_record = {
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
        "evaluation": {"verdict": "SUCCESS"}
    }
    
    jsonl_path = runtime_root / "session_dev_b_test.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(history_record) + "\n")
        
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(node_context=context, player_text="New York.")
    
    policy = FlightSmallTalkDiagnosticPolicy(runtime_root=runtime_root)
    decision = policy.decide_conversational(payload)
    
    # Since topic is "travel", the selected probe should have a coherent topic tag "travel".
    assert decision.selected_probe is not None
    assert decision.selected_probe["topic_tag"] == "travel" or "travel" in decision.selected_probe["coherent_topics"]


def test_termination_bounded_by_turns_and_confidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.services.service_b import flight_smalltalk_diagnostic_policy
    monkeypatch.setattr(flight_smalltalk_diagnostic_policy, "MIN_TURNS", 3)
    monkeypatch.setattr(flight_smalltalk_diagnostic_policy, "MAX_TURNS", 5)

    runtime_root = tmp_path / "openkb" / "dev_b"
    runtime_root.mkdir(parents=True, exist_ok=True)
    jsonl_path = runtime_root / "session_dev_b_test.jsonl"
    
    # 1. 2 turns -> MIN_TURNS not met yet
    history_record = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "dialogue_seed": {"scene": "FLIGHT_A_001_SEATMATE_SMALLTALK", "npc_role": "seatmate", "surface_goal": "TRAVEL_PURPOSE", "hidden_assessment_goal": "a", "opening_intent": "a", "difficulty_profile": "a", "tone_guidance": "a", "stop_condition": "a"},
        "evaluation": {"verdict": "SUCCESS"},
        "understanding": {"confidence": 0.9}
    }
    
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(history_record) + "\n")
        
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(node_context=context, player_text="Yes", confidence=0.9)
    policy = FlightSmallTalkDiagnosticPolicy(runtime_root=runtime_root)
    decision = policy.decide_conversational(payload)
    
    assert decision.next_node_id == "FLIGHT_A_001_SEATMATE_SMALLTALK"
    assert decision.next_action == "ADVANCE"
    
    # 2. 4 turns, with enough confidence (covering distinct competencies) -> should terminate
    history_record1 = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "dialogue_seed": {"scene": "FLIGHT_A_001_SEATMATE_SMALLTALK", "npc_role": "seatmate", "surface_goal": "TRAVEL_PURPOSE"},
        "evaluation": {"verdict": "SUCCESS"},
        "understanding": {"confidence": 0.9}
    }
    history_record2 = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "dialogue_seed": {"scene": "FLIGHT_A_001_SEATMATE_SMALLTALK", "npc_role": "seatmate", "surface_goal": "STAY_PLAN"},
        "evaluation": {"verdict": "SUCCESS"},
        "understanding": {"confidence": 0.9}
    }
    history_record3 = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "dialogue_seed": {"scene": "FLIGHT_A_001_SEATMATE_SMALLTALK", "npc_role": "seatmate", "surface_goal": "CLARIFY_OR_ASK_BACK"},
        "evaluation": {"verdict": "SUCCESS"},
        "understanding": {"confidence": 0.9}
    }
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(history_record1) + "\n")
        f.write(json.dumps(history_record2) + "\n")
        f.write(json.dumps(history_record3) + "\n")
        
    decision2 = policy.decide_conversational(payload)
    assert decision2.next_node_id == "FLIGHT_999_COMPLETE"
    assert decision2.next_action == "COMPLETE_CHAPTER"
