import json
from pathlib import Path
from typing import Literal

import pytest

from backend.app.agents.agent_b.english_level_hint_agent import EnglishLevelHintAgent
from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    HintPolicy,
    InputSource,
    NodeContext,
    PlayerProfile,
    PreviousNodeResult,
    ScenarioState,
    UnderstandingOutput,
)


SCENARIO_NODE_PATH = Path("backend/app/data/scenario_nodes.json")


def _node_context(node_id: str = "IMM_002_PURPOSE") -> NodeContext:
    node_data = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))
    node = node_data["nodes"][node_id]
    return NodeContext(
        node_id=node["node_id"],
        chapter_id=node["chapter_id"],
        npc_question=node["npc_question"],
        npc_question_goal=node["npc_question_goal"],
        required_intents=node["required_intents"],
        required_slots=node["required_slots"],
        optional_slots=node["optional_slots"],
        critical_slots=node["critical_slots"],
        allowed_slot_values=node["allowed_slot_values"],
        risk_keywords=node["risk_keywords"],
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
    player_text: str = "I'm here for tourism.",
    node_context: NodeContext | None = None,
    intent_success: bool = True,
    confidence: float = 0.92,
    answer_relevance: Literal["on_topic", "partially_related", "off_topic"] = "on_topic",
    ambiguity_type: str = "none",
    risk_delta: int = 0,
    risk_tags: list[str] | None = None,
    extracted_slots: dict[str, str] | None = None,
    missing_slots: list[str] | None = None,
    needs_clarification: bool = False,
    retry_count: int = 0,
    hint_count: int = 0,
    previous_fail_count: int = 0,
    tier: Literal["Bronze", "Silver", "Gold"] = "Bronze",
    english_confidence: Literal["beginner", "intermediate", "advanced"] = "beginner",
    client_allowed_next_nodes: list[str] | None = None,
) -> DevBPolicyInput:
    context = node_context or _node_context()
    slots = extracted_slots if extracted_slots is not None else {"visit_purpose": "tourism"}
    missing = missing_slots if missing_slots is not None else []
    allowed = client_allowed_next_nodes if client_allowed_next_nodes is not None else context.allowed_next_nodes

    return DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_dev_b_test",
        session_id="session_dev_b_test",
        player_id="player_dev_b_test",
        chapter_id="CH0_IMMIGRATION",
        scene_id="JFK_IMMIGRATION_HALL",
        current_node_id=context.node_id,
        turn_index=2,
        player_text=player_text,
        input_source=InputSource(
            input_type="voice",
            stt_confidence=0.9,
            language_detected="en-US",
            needs_repeat=False,
        ),
        player_profile=PlayerProfile(
            nickname="Sean",
            english_confidence=english_confidence,
            tier=tier,
            travel_speaking_level="TSL_1_SURVIVAL",
        ),
        scenario_state=ScenarioState(
            patience=100,
            suspicion=0,
            retry_count=retry_count,
            hint_count=hint_count,
            previous_fail_count=previous_fail_count,
            completed_intents=["submit_passport"],
        ),
        node_context=context,
        understanding=UnderstandingOutput(
            intent=context.required_intents[0],
            intent_success=intent_success,
            confidence=confidence,
            meaning_summary_kr="Player answered the current immigration question.",
            emotion="neutral",
            answer_relevance=answer_relevance,
            ambiguity_type=ambiguity_type,
            risk_delta=risk_delta,
            risk_reason="No risk." if risk_delta == 0 else "Risk expression detected.",
            risk_tags=risk_tags or [],
            extracted_slots=slots,
            missing_slots=missing,
            needs_clarification=needs_clarification,
        ),
        previous_node_results=[
            PreviousNodeResult(
                node_id="IMM_001_PASSPORT",
                verdict="SUCCESS",
                next_action="ADVANCE",
                feedback_tags=["passport_submitted"],
            )
        ],
        client_allowed_next_nodes=allowed,
    )


def test_clear_purpose_answer_advances_to_duration() -> None:
    payload = _policy_input()
    result = EnglishLevelHintAgent().evaluate_turn(payload)

    assert result.contract_version == "dev_b_policy.v1"
    assert result.node_id == "IMM_002_PURPOSE"
    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.branch_type == "success"
    assert result.branch.next_action == "ADVANCE"
    assert result.branch.next_node_id == "IMM_003_DURATION"
    assert result.branch.next_node_id in payload.node_context.allowed_next_nodes
    assert result.dialogue_directive is not None
    assert result.dialogue_directive.do_not_generate_npc_text is True


@pytest.mark.parametrize("player_text", ["Travel. New York.", "I go travel five days"])
def test_broken_english_records_error_without_immediate_fail(player_text: str) -> None:
    result = EnglishLevelHintAgent().evaluate_turn(
        _policy_input(
            player_text=player_text,
            intent_success=True,
            confidence=0.72,
            extracted_slots={"visit_purpose": "tourism"},
            missing_slots=[],
            english_confidence="beginner",
        )
    )

    assert result.evaluation.verdict in {"SUCCESS", "PARTIAL"}
    assert result.level_hint.english_level in {"beginner", "intermediate"}
    assert result.error_capture.should_record is True
    assert result.error_capture.storage_format == "markdown"
    assert result.error_capture.error_items
    assert result.out_game_feedback_seed.include_in_final_report is True
    assert result.branch.branch_type != "bad_end"


def test_first_unclear_answer_clarifies_or_retries() -> None:
    result = EnglishLevelHintAgent().evaluate_turn(
        _policy_input(
            player_text="Yes.",
            intent_success=False,
            confidence=0.45,
            extracted_slots={},
            missing_slots=["visit_purpose"],
            needs_clarification=True,
        )
    )

    assert result.evaluation.verdict == "UNCLEAR"
    assert result.branch.branch_type == "clarify"
    assert result.branch.next_action == "REASK"
    assert result.in_game_feedback.feedback_strategy == "clarification_request"


def test_repeated_failure_uses_hint_branch() -> None:
    result = EnglishLevelHintAgent().evaluate_turn(
        _policy_input(
            player_text="I don't know.",
            intent_success=False,
            confidence=0.6,
            extracted_slots={},
            missing_slots=["visit_purpose"],
            retry_count=2,
            previous_fail_count=2,
        )
    )

    assert result.evaluation.verdict == "FAIL"
    assert result.branch.branch_type == "hint"
    assert result.branch.next_action == "GIVE_HINT"
    assert result.level_hint.needs_hint is True
    assert result.level_hint.hint_level in {"medium", "high"}


def test_risky_answer_warns_or_goes_to_bad_end() -> None:
    result = EnglishLevelHintAgent().evaluate_turn(
        _policy_input(
            player_text="I came to work illegally and stay forever.",
            intent_success=False,
            confidence=0.9,
            risk_delta=85,
            risk_tags=["illegal_work_intent", "overstay_intent"],
            extracted_slots={"illegal_work_intent": "true"},
            missing_slots=["visit_purpose"],
            retry_count=2,
        )
    )

    assert result.evaluation.verdict == "CRITICAL_FAIL"
    assert result.branch.branch_type in {"warning", "bad_end"}
    assert result.branch.next_action in {"WARNING", "FAIL_END"}
    assert result.state_delta.suspicion_delta > 0


def test_branch_next_node_stays_within_allowed_next_nodes() -> None:
    payload = _policy_input(client_allowed_next_nodes=["IMM_003_DURATION"])

    result = EnglishLevelHintAgent().evaluate_turn(payload)

    assert result.branch.next_node_id in payload.node_context.allowed_next_nodes
    assert result.branch.next_node_id in payload.client_allowed_next_nodes
    assert result.branch.allowed_next_node_checked is True


def test_empty_allowed_next_nodes_raises_value_error() -> None:
    context = _node_context()
    invalid_context = context.model_copy(update={"allowed_next_nodes": []})

    with pytest.raises(ValueError, match="allowed_next_nodes"):
        EnglishLevelHintAgent().evaluate_turn(_policy_input(node_context=invalid_context))


def test_all_chapter_zero_nodes_define_branch_candidates_and_allowed_next_nodes() -> None:
    node_data = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))

    assert set(node_data["nodes"]) == {
        "IMM_001_PASSPORT",
        "IMM_002_PURPOSE",
        "IMM_003_DURATION",
        "IMM_004_STAY_LOCATION",
        "IMM_005_RETURN_TICKET",
        "IMM_006_DECLARATION_CHECK",
        "IMM_006B_PACKED_BAG_CHECK",
        "IMM_007_FINAL_DECISION",
    }
    for node in node_data["nodes"].values():
        allowed_next_nodes = set(node["allowed_next_nodes"])
        assert allowed_next_nodes
        for branch_name in ["retry", "clarify", "warning", "bad_end"]:
            assert branch_name in node["branch_candidates"]
            assert node["branch_candidates"][branch_name] in allowed_next_nodes


def test_report_item_and_feedback_tags_are_returned() -> None:
    result = EnglishLevelHintAgent().evaluate_turn(_policy_input())

    assert result.report_item.summary
    assert result.report_item.improvement
    assert result.report_item.example_answer
    assert result.evaluation.feedback_tags
