import json
from pathlib import Path

from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    HintPolicy,
    InputSource,
    NodeContext,
    PlayerProfile,
    ScenarioState,
    UnderstandingOutput,
)
from backend.app.services.service_b.scenario_state_machine import ScenarioStateMachine

SCENARIO_NODE_PATH = Path("backend/app/data/scenario_nodes.json")

def _node_context(node_id: str = "IMM_002_PURPOSE") -> NodeContext:
    node_data = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))
    node = node_data["nodes"][node_id]
    return NodeContext(
        node_id=node["node_id"],
        scenario_id=node_data["scenario_id"],
        chapter_id=node["chapter_id"],
        node_type=node["node_type"],
        transition=node.get("transition"),
        npc_question=node["npc_question"],
        npc_question_goal=node["npc_question_goal"],
        objective_kr=node["objective_kr"],
        required_intents=node["required_intents"],
        required_slots=node["required_slots"],
        optional_slots=node.get("optional_slots", []),
        critical_slots=node.get("critical_slots", []),
        allowed_slot_values=node.get("allowed_slot_values", {}),
        risk_keywords=node.get("risk_keywords", []),
        recommended_expression=node["recommended_expression"],
        base_hint_kr=node["base_hint_kr"],
        hint_policy=HintPolicy(**node["hint_policy"]),
        success_next_node=node["branch_candidates"]["success"],
        retry_next_node=node["branch_candidates"]["retry"],
        clarify_next_node=node["branch_candidates"]["clarify"],
        hint_next_node=node["branch_candidates"]["hint"],
        warning_next_node=node["branch_candidates"]["warning"],
        allowed_next_nodes=node["allowed_next_nodes"],
    )

def _policy_input(
    *,
    node_context: NodeContext | None = None,
    intent_success: bool = True,
    confidence: float = 0.9,
    extracted_slots: dict[str, str] | None = None,
    missing_slots: list[str] | None = None,
    patience: int = 100,
    retry_count: int = 0,
    completed_intents: list[str] | None = None,
    needs_repeat: bool = False,
    needs_clarification: bool = False,
) -> DevBPolicyInput:
    context = node_context or _node_context()
    return DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_test",
        session_id="session_test",
        player_id="player_test",
        chapter_id=context.chapter_id,
        scene_id="JFK_IMMIGRATION_HALL",
        current_node_id=context.node_id,
        turn_index=2,
        player_text="Hello",
        input_source=InputSource(
            input_type="voice",
            stt_confidence=confidence,
            language_detected="en",
            needs_repeat=needs_repeat,
        ),
        player_profile=PlayerProfile(
            nickname="tester",
            english_confidence="beginner",
            tier="Bronze",
            travel_speaking_level="TSL_1_SURVIVAL",
        ),
        scenario_state=ScenarioState(
            patience=patience,
            suspicion=0,
            retry_count=retry_count,
            hint_count=0,
            previous_fail_count=0,
            completed_intents=completed_intents or [],
        ),
        node_context=context,
        understanding=UnderstandingOutput(
            intent="explain_purpose",
            intent_success=intent_success,
            confidence=confidence,
            meaning_summary_kr="의도 설명",
            emotion="Nomal",
            answer_relevance="on_topic",
            ambiguity_type="none",
            risk_delta=0,
            risk_reason="",
            risk_tags=[],
            extracted_slots=extracted_slots or {},
            missing_slots=missing_slots or [],
            needs_clarification=needs_clarification,
        ),
    )

def test_patience_exhausted_forces_bad_end() -> None:
    sm = ScenarioStateMachine()
    
    # Patience is 0, answer is not successful (missing slot)
    payload = _policy_input(
        intent_success=False,
        missing_slots=["visit_purpose"],
        patience=0,
        retry_count=1,
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "bad_end"
    assert decision.next_action == "FAIL_END"
    assert decision.next_node_id == "END_SECONDARY_INSPECTION"

def test_retry_limit_exceeded_forces_bad_end() -> None:
    sm = ScenarioStateMachine()
    
    # retry_count is 3, answer is not successful (missing slot)
    payload = _policy_input(
        intent_success=False,
        missing_slots=["visit_purpose"],
        patience=40,
        retry_count=3,
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "bad_end"
    assert decision.next_action == "FAIL_END"
    assert decision.next_node_id == "END_SECONDARY_INSPECTION"

def test_success_despite_missing_patience_and_retries() -> None:
    sm = ScenarioStateMachine()
    
    # Answer is fully successful, despite patience=0 and retry_count=3
    payload = _policy_input(
        intent_success=True,
        missing_slots=[],
        patience=0,
        retry_count=3,
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "success"
    assert decision.next_action == "ADVANCE"

def test_reorder_hint_before_unclear_when_retries_high() -> None:
    sm = ScenarioStateMachine()
    
    # If retry_count is 2, and needs clarification (unclear),
    # since retry_count >= 2, we evaluate _should_give_hint first (which is True when retry_count >= 2).
    # Thus, it returns hint rather than clarify.
    payload = _policy_input(
        intent_success=False,
        needs_clarification=True,
        confidence=0.4,
        patience=80,
        retry_count=2,
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "hint"
    assert decision.next_action == "GIVE_HINT"

def test_unclear_before_hint_when_retries_low() -> None:
    sm = ScenarioStateMachine()
    
    # If retry_count is 1 (low), and needs clarification (unclear),
    # since retry_count < 2, unclear takes precedence over hint.
    # Thus, it returns clarify.
    payload = _policy_input(
        intent_success=False,
        needs_clarification=True,
        confidence=0.4,
        patience=80,
        retry_count=1,
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "clarify"
    assert decision.next_action == "REASK"

def test_completed_intents_bypasses_missing_slots() -> None:
    sm = ScenarioStateMachine()
    
    # In IMM_002_PURPOSE: required intent is "state_visit_purpose"
    # If "state_visit_purpose" is in completed_intents, but slots are missing (e.g. visit_purpose missing)
    # it should still be marked SUCCESS.
    payload = _policy_input(
        intent_success=True,
        missing_slots=["visit_purpose"],
        completed_intents=["state_visit_purpose"],
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "success"
    assert decision.next_action == "ADVANCE"
