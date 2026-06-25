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
    CustomsItemJudgeContext,
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
    hint_count: int = 0,
    completed_intents: list[str] | None = None,
    needs_repeat: bool = False,
    needs_clarification: bool = False,
    previous_fail_count: int = 0,
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
            hint_count=hint_count,
            previous_fail_count=previous_fail_count,
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
        hint_count=1,
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "bad_end"
    assert decision.next_action == "FAIL_END"
    assert decision.next_node_id == "END_SECONDARY_INSPECTION"

def test_retry_limit_exceeded_forces_bad_end() -> None:
    sm = ScenarioStateMachine()
    
    # retry_count is 5, answer is not successful (missing slot)
    payload = _policy_input(
        intent_success=False,
        missing_slots=["visit_purpose"],
        patience=40,
        retry_count=5,
        hint_count=1,
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

def test_needs_repeat_patience_waiver_first_time() -> None:
    sm = ScenarioStateMachine()
    
    # First time needs_repeat, previous_fail_count = 0
    payload = _policy_input(
        intent_success=False,
        needs_repeat=True,
        confidence=0.9,
        previous_fail_count=0,
    )
    decision = sm.decide(payload)
    assert decision.branch_type == "clarify"
    assert decision.patience_delta == 0

def test_needs_repeat_patience_penalty_consecutive() -> None:
    sm = ScenarioStateMachine()
    
    # Consecutive needs_repeat, previous_fail_count = 1
    payload = _policy_input(
        intent_success=False,
        needs_repeat=True,
        confidence=0.9,
        previous_fail_count=1,
    )
    decision = sm.decide(payload)
    assert decision.branch_type == "clarify"
    assert decision.patience_delta == -5

def test_unclear_loop_broken_by_hint_escalation() -> None:
    sm = ScenarioStateMachine()
    
    # If previous_fail_count is 2 (high consecutive failure),
    # even when retry_count is 1 (low), hint should take precedence over unclear.
    payload = _policy_input(
        intent_success=False,
        needs_clarification=True,
        confidence=0.4,
        patience=80,
        retry_count=1,
        previous_fail_count=2,
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "hint"
    assert decision.next_action == "GIVE_HINT"

def test_gold_bar_undeclared_triggers_critical_risk() -> None:
    sm = ScenarioStateMachine()
    from backend.app.schemas.game_turn import RandomCustomsItemContext
    
    # Undeclared gold bar in customs node triggers critical risk
    node_ctx = _node_context("BAG_005_CUSTOMS_HOLD_EXPLANATION")
    payload = _policy_input(
        node_context=node_ctx,
        intent_success=False,
    )
    payload.current_node_id = "BAG_005_CUSTOMS_HOLD_EXPLANATION"
    payload.random_customs_item = RandomCustomsItemContext(
        item_id="ITEM_GOLD_BAR",
        item_name="1kg Gold bar",
        item_category="valuable",
        item_description="Gold bar",
        declared=False,
        difficulty=9,
        suspicion_reason="Smuggling risk",
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "bad_end"
    assert decision.next_action == "FAIL_END"

def test_gold_bar_declared_bypasses_critical_risk() -> None:
    sm = ScenarioStateMachine()
    from backend.app.schemas.game_turn import RandomCustomsItemContext
    
    # Declared gold bar in customs node does NOT trigger critical risk
    node_ctx = _node_context("BAG_005_CUSTOMS_HOLD_EXPLANATION")
    payload = _policy_input(
        node_context=node_ctx,
        intent_success=False,
    )
    payload.current_node_id = "BAG_005_CUSTOMS_HOLD_EXPLANATION"
    payload.random_customs_item = RandomCustomsItemContext(
        item_id="ITEM_GOLD_BAR",
        item_name="1kg Gold bar",
        item_category="valuable",
        item_description="Gold bar",
        declared=True,
        difficulty=9,
        suspicion_reason="Smuggling risk",
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type != "bad_end"

def test_patek_watches_undeclared_triggers_critical_risk() -> None:
    sm = ScenarioStateMachine()
    from backend.app.schemas.game_turn import RandomCustomsItemContext
    
    # Undeclared patek watches in customs node triggers critical risk / bad end
    node_ctx = _node_context("BAG_005_CUSTOMS_HOLD_EXPLANATION")
    payload = _policy_input(
        node_context=node_ctx,
        intent_success=False,
    )
    payload.current_node_id = "BAG_005_CUSTOMS_HOLD_EXPLANATION"
    payload.random_customs_item = RandomCustomsItemContext(
        item_id="ITEM_PATEK_WATCHES",
        item_name="10 Patek Philippe watches",
        item_category="luxury",
        item_description="Luxury watches",
        declared=False,
        difficulty=12,
        suspicion_reason="Smuggling risk",
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type == "bad_end"
    assert decision.next_action == "FAIL_END"

def test_patek_watches_declared_bypasses_critical_risk() -> None:
    sm = ScenarioStateMachine()
    from backend.app.schemas.game_turn import RandomCustomsItemContext
    
    # Declared patek watches in customs node does NOT trigger critical risk
    node_ctx = _node_context("BAG_005_CUSTOMS_HOLD_EXPLANATION")
    payload = _policy_input(
        node_context=node_ctx,
        intent_success=False,
    )
    payload.current_node_id = "BAG_005_CUSTOMS_HOLD_EXPLANATION"
    payload.random_customs_item = RandomCustomsItemContext(
        item_id="ITEM_PATEK_WATCHES",
        item_name="10 Patek Philippe watches",
        item_category="luxury",
        item_description="Luxury watches",
        declared=True,
        difficulty=12,
        suspicion_reason="Smuggling risk",
    )
    
    decision = sm.decide(payload)
    assert decision.branch_type != "bad_end"

def test_customs_rule_gate_rejects_high_difficulty_generic_explanation() -> None:
    sm = ScenarioStateMachine()
    
    # High-difficulty (>= 7) item with generic explanation should trigger REASK / clarify
    node_ctx = _node_context("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM")
    node_ctx.customs_item_context = CustomsItemJudgeContext(
        item_name="wild ginseng root",
        item_category="agriculture",
        difficulty=11,
        suspicion_reason="Ecosystem risk",
        declared=False,
    )
    payload = _policy_input(
        node_context=node_ctx,
        intent_success=True,
    )
    payload.current_node_id = "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"
    payload.player_text = "It is just a gift for my friend."
    
    decision = sm.decide(payload)
    assert decision.verdict == "UNCLEAR"
    assert decision.branch_type == "clarify"
    assert decision.next_action == "REASK"

def test_customs_rule_gate_allows_low_difficulty_generic_explanation() -> None:
    sm = ScenarioStateMachine()
    
    # Low-difficulty (< 7) item with generic explanation should succeed / ADVANCE
    node_ctx = _node_context("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM")
    node_ctx.customs_item_context = CustomsItemJudgeContext(
        item_name="A souvenir snow globe",
        item_category="souvenir",
        difficulty=2,
        suspicion_reason="Liquid restriction",
        declared=False,
    )
    payload = _policy_input(
        node_context=node_ctx,
        intent_success=True,
    )
    payload.current_node_id = "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"
    payload.player_text = "It is just a gift."
    
    decision = sm.decide(payload)
    assert decision.verdict == "SUCCESS"
    assert decision.branch_type == "success"
    assert decision.next_action == "ADVANCE"
