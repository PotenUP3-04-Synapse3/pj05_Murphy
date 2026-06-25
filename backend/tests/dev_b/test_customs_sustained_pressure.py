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
    RandomCustomsItemContext,
)
from backend.app.services.service_b.scenario_state_machine import ScenarioStateMachine
from backend.app.data.challenge_tables import CUSTOMS_ITEMS, CustomsItemEntry

SCENARIO_NODE_PATH = Path("backend/app/data/scenario_nodes.json")
CHAPTER_ID = "CH0_04_BAGGAGE_CLAIM"
NODE_ID = "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"

INSUFFICIENT_ANSWERS_POOL = [
    "It's a gift for my friend.",
    "It's just a personal item.",
    "I bought it as a souvenir.",
    "It's something I brought from home.",
    "It's mine, nothing special.",
    "I just have it for myself, honestly.",
]


def _node_context() -> NodeContext:
    node_data = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))
    node = node_data["nodes"][NODE_ID]
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
    item: CustomsItemEntry,
    answer: str,
    intent_success: bool = True,
    confidence: float = 0.9,
    patience: int = 100,
    retry_count: int = 0,
    hint_count: int = 0,
    suspicion: int = 0,
    previous_fail_count: int = 0,
    declared: bool = False,
    needs_clarification: bool = False,
    missing_slots: list[str] | None = None,
) -> DevBPolicyInput:
    context = _node_context()
    context.customs_item_context = CustomsItemJudgeContext(
        item_name=item.name_en,
        item_category=item.item_category,
        difficulty=item.difficulty,
        suspicion_reason=item.suspicion_reason,
        declared=declared,
    )

    return DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_test",
        session_id="session_test",
        player_id="player_test",
        chapter_id=context.chapter_id,
        scene_id="JFK_BAGGAGE_CLAIM",
        current_node_id=context.node_id,
        turn_index=2,
        player_text=answer,
        input_source=InputSource(
            input_type="voice",
            stt_confidence=1.0,
            language_detected="en-US",
            needs_repeat=False,
        ),
        player_profile=PlayerProfile(
            nickname="tester",
            english_confidence="beginner",
            tier="Silver",
            travel_speaking_level="TSL_2_FUNCTIONAL",
        ),
        scenario_state=ScenarioState(
            patience=patience,
            suspicion=suspicion,
            retry_count=retry_count,
            hint_count=hint_count,
            previous_fail_count=previous_fail_count,
            completed_intents=[],
        ),
        node_context=context,
        understanding=UnderstandingOutput(
            intent="explain_baggage",
            intent_success=intent_success,
            confidence=confidence,
            meaning_summary_kr="수하물 설명",
            emotion="Normal",
            answer_relevance="on_topic",
            ambiguity_type="none",
            risk_delta=0,
            risk_reason="",
            risk_tags=[],
            extracted_slots={},
            missing_slots=missing_slots or [],
            needs_clarification=needs_clarification,
        ),
        random_customs_item=RandomCustomsItemContext(
            item_id=item.item_id,
            item_name=item.name_en,
            item_category=item.item_category,
            item_description=item.suspicion_reason,
            declared=declared,
            difficulty=item.difficulty,
            suspicion_reason=item.suspicion_reason,
        ),
    )


def test_high_difficulty_item_never_passes_on_consecutive_insufficient() -> None:
    sm = ScenarioStateMachine()

    high_diff_items = [item for item in CUSTOMS_ITEMS if item.difficulty >= 7]
    assert len(high_diff_items) > 0, "No high-difficulty items found in challenge tables"

    for item in high_diff_items:
        patience = 30
        suspicion = 0
        retry_count = 0
        hint_count = 0
        previous_fail_count = 0

        declared_status = item.item_category in {"valuable", "luxury"}
        reached_terminal = False
        for turn_idx in range(1, 9):
            answer = INSUFFICIENT_ANSWERS_POOL[(turn_idx - 1) % len(INSUFFICIENT_ANSWERS_POOL)]
            payload = _policy_input(
                item=item,
                answer=answer,
                intent_success=True,
                patience=patience,
                suspicion=suspicion,
                retry_count=retry_count,
                hint_count=hint_count,
                previous_fail_count=previous_fail_count,
                declared=declared_status,
            )
            decision = sm.decide(payload)

            assert decision.branch_type != "success", (
                f"Item {item.item_id} leaked success on Turn {turn_idx} with answer: '{answer}'"
            )

            patience = max(0, patience + decision.patience_delta)
            suspicion = max(0, suspicion + decision.suspicion_delta)
            retry_count = retry_count + decision.retry_count_delta
            hint_count = hint_count + decision.hint_count_delta
            previous_fail_count = previous_fail_count + 1

            if decision.branch_type in {"bad_end", "final"} or patience <= 0:
                reached_terminal = True
                break

        assert reached_terminal or previous_fail_count == 8


def test_low_difficulty_item_passes_generic() -> None:
    sm = ScenarioStateMachine()

    low_diff_items = [
        item for item in CUSTOMS_ITEMS
        if item.difficulty < 7 and item.item_category not in {"valuable", "luxury"}
    ]
    assert len(low_diff_items) > 0

    for item in low_diff_items:
        answer = INSUFFICIENT_ANSWERS_POOL[0]
        payload = _policy_input(
            item=item,
            answer=answer,
            intent_success=True,
            patience=30,
            declared=False,
        )
        decision = sm.decide(payload)

        assert decision.branch_type == "success", (
            f"Low diff item {item.item_id} failed to pass on Turn 1 with answer: '{answer}'"
        )


def test_sufficient_answer_escapes_pressure() -> None:
    sm = ScenarioStateMachine()

    high_diff_items = [item for item in CUSTOMS_ITEMS if item.difficulty >= 7]

    for item in high_diff_items:
        declared_status = item.item_category in {"valuable", "luxury"}
        answer_1 = INSUFFICIENT_ANSWERS_POOL[0]
        payload_1 = _policy_input(
            item=item,
            answer=answer_1,
            intent_success=True,
            patience=30,
            declared=declared_status,
        )
        decision_1 = sm.decide(payload_1)

        assert decision_1.branch_type != "success"

        patience_2 = max(0, 30 + decision_1.patience_delta)
        suspicion_2 = max(0, 0 + decision_1.suspicion_delta)
        retry_count_2 = 0 + decision_1.retry_count_delta
        hint_count_2 = 0 + decision_1.hint_count_delta
        previous_fail_count_2 = 1

        answer_2 = f"This is my personal item, it is {item.name_en.lower()}."
        payload_2 = _policy_input(
            item=item,
            answer=answer_2,
            intent_success=True,
            patience=patience_2,
            suspicion=suspicion_2,
            retry_count=retry_count_2,
            hint_count=hint_count_2,
            previous_fail_count=previous_fail_count_2,
            declared=declared_status,
        )
        decision_2 = sm.decide(payload_2)

        assert decision_2.branch_type == "success", (
            f"Item {item.item_id} failed to escape pressure on Turn 2 with sufficient answer: '{answer_2}'"
        )


def test_undeclared_valuable_luxury_item_triggers_critical_fail() -> None:
    sm = ScenarioStateMachine()

    valuable_luxury_items = [
        item for item in CUSTOMS_ITEMS
        if item.item_category in {"valuable", "luxury"}
    ]
    assert len(valuable_luxury_items) > 0

    for item in valuable_luxury_items:
        answer = "It is just a personal item."
        payload = _policy_input(
            item=item,
            answer=answer,
            intent_success=True,
            patience=30,
            declared=False,
        )
        decision = sm.decide(payload)

        assert decision.branch_type == "bad_end", (
            f"Undeclared item {item.item_id} did not trigger bad_end. Got: {decision.branch_type}"
        )
        assert decision.verdict == "CRITICAL_FAIL"
