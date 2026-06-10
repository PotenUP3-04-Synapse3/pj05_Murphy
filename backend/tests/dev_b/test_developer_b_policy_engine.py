import json
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from backend.app.agents.agent_b.feedback_hint_llm_client import FeedbackHintLLMClient
from backend.app.agents.agent_b.english_level_hint_agent import EnglishLevelHintAgent, _validate_b_policy_output
from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    HintPolicy,
    InputSource,
    NodeContext,
    OpenKBWriteResult,
    PlayerProfile,
    PreviousNodeResult,
    RubricScores,
    ScenarioState,
    UnderstandingOutput,
)
from backend.app.services.service_b.feedback_hint_generator import FeedbackHintGenerator
from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision
from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyController


SCENARIO_NODE_PATH = Path("backend/app/data/scenario_nodes.json")


@pytest.fixture(autouse=True)
def _use_rule_feedback_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEV_B_FEEDBACK_LLM_MODE", "rule")


def _agent(tmp_path: Path) -> EnglishLevelHintAgent:
    return EnglishLevelHintAgent(openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"))


def _llm_agent(tmp_path: Path, llm_client: FeedbackHintLLMClient, mode: str = "llm") -> EnglishLevelHintAgent:
    return EnglishLevelHintAgent(
        feedback_generator=FeedbackHintGenerator(mode=mode, llm_client=llm_client),
        openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"),
    )


def _node_context(node_id: str = "IMM_002_PURPOSE") -> NodeContext:
    node_data = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))
    node = node_data["nodes"][node_id]
    return NodeContext(
        node_id=node["node_id"],
        chapter_id=node["chapter_id"],
        npc_question=node["npc_question"],
        npc_question_goal=node["npc_question_goal"],
        objective_kr=node["objective_kr"],
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


def test_clear_purpose_answer_advances_to_duration(tmp_path: Path) -> None:
    payload = _policy_input()
    result = _agent(tmp_path).evaluate_turn(payload)

    assert result.contract_version == "dev_b_policy.v1"
    assert result.node_id == "IMM_002_PURPOSE"
    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.branch_type == "success"
    assert result.branch.next_action == "ADVANCE"
    assert result.branch.next_node_id == "IMM_003_DURATION"
    assert result.branch.next_node_id in payload.node_context.allowed_next_nodes
    assert result.dialogue_directive is not None
    assert result.dialogue_directive.do_not_generate_npc_text is True
    assert result.openkb_write is not None
    assert result.openkb_write.attempted is True


@pytest.mark.parametrize("player_text", ["Travel. New York.", "I go travel five days"])
def test_broken_english_records_error_without_immediate_fail(player_text: str, tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(
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


def test_first_unclear_answer_clarifies_or_retries(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(
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


def test_repeated_failure_uses_hint_branch(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(
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


def test_risky_answer_warns_or_goes_to_bad_end(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(
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


def test_branch_next_node_stays_within_allowed_next_nodes(tmp_path: Path) -> None:
    payload = _policy_input(client_allowed_next_nodes=["IMM_003_DURATION"])

    result = _agent(tmp_path).evaluate_turn(payload)

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
        "FLIGHT_001_SEATMATE_SMALLTALK",
        "IMM_001_PASSPORT",
        "IMM_002_PURPOSE",
        "IMM_003_DURATION",
        "IMM_004_STAY_LOCATION",
        "IMM_005_RETURN_TICKET",
        "IMM_ALPHA_GOLD_BAG_CONTENT_CHECK",
        "IMM_006_DECLARATION_CHECK",
        "IMM_006B_PACKED_BAG_CHECK",
        "IMM_007_FINAL_DECISION",
        "BAG_002_FIND_STAFF",
        "BAG_003_REPORT_MISSING_BAG",
        "BAG_004_DESCRIBE_BAG",
        "BAG_005_PROVIDE_FLIGHT_OR_TAG",
        "BAG_006_CONTACT_AND_DELIVERY",
        "BAG_007_RESOLUTION",
    }
    for node in node_data["nodes"].values():
        allowed_next_nodes = set(node["allowed_next_nodes"])
        assert allowed_next_nodes
        assert node["objective_kr"]
        for branch_name in ["retry", "clarify", "warning", "bad_end"]:
            assert branch_name in node["branch_candidates"]
            assert node["branch_candidates"][branch_name] in allowed_next_nodes


def test_flight_smalltalk_node_exists_as_alpha_diagnostic_node() -> None:
    context = _node_context("FLIGHT_001_SEATMATE_SMALLTALK")

    assert context.node_id == "FLIGHT_001_SEATMATE_SMALLTALK"
    assert context.npc_question_goal == "friendly_seatmate_smalltalk"
    assert context.required_intents == ["respond_to_smalltalk"]
    assert context.required_slots == ["smalltalk_response"]
    assert "FLIGHT_001_SEATMATE_SMALLTALK" in context.allowed_next_nodes
    assert "IMM_001_PASSPORT" in context.allowed_next_nodes


def test_flight_smalltalk_creates_deferred_out_game_feedback_seed(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_001_SEATMATE_SMALLTALK")
    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="I go New York. First time.",
            intent_success=True,
            confidence=0.88,
            extracted_slots={"smalltalk_response": "answered"},
            missing_slots=[],
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.out_game_feedback_seed.include_in_final_report is True
    assert result.out_game_feedback_seed.focus_on_form_targets == ["smalltalk_response_clarity"]
    assert "deferred_out_game_feedback" in result.out_game_feedback_seed.openkb_query_tags
    assert result.branch.next_node_id in context.allowed_next_nodes


def test_report_item_and_feedback_tags_are_returned(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(_policy_input())

    assert result.report_item.summary
    assert result.report_item.improvement
    assert result.report_item.example_answer
    assert result.evaluation.feedback_tags


@pytest.mark.parametrize(
    ("node_id", "slot_name", "slot_value", "success_next_node"),
    [
        ("IMM_001_PASSPORT", "passport_submission_status", "submitted", "IMM_002_PURPOSE"),
        ("IMM_002_PURPOSE", "visit_purpose", "tourism", "IMM_003_DURATION"),
        ("IMM_003_DURATION", "stay_duration", "days", "IMM_004_STAY_LOCATION"),
        ("IMM_004_STAY_LOCATION", "stay_location", "hotel", "IMM_005_RETURN_TICKET"),
        ("IMM_006_DECLARATION_CHECK", "item_purpose", "personal_recreation", "IMM_006B_PACKED_BAG_CHECK"),
        ("IMM_006B_PACKED_BAG_CHECK", "packed_by_self", "yes_self_packed", "IMM_007_FINAL_DECISION"),
        ("IMM_ALPHA_GOLD_BAG_CONTENT_CHECK", "bag_contents_summary", "mixed_personal_items", "IMM_006_DECLARATION_CHECK"),
        ("BAG_002_FIND_STAFF", "missing_bag_status", "not_arrived", "BAG_003_REPORT_MISSING_BAG"),
        ("BAG_003_REPORT_MISSING_BAG", "missing_bag_report", "checked_bag_missing", "BAG_004_DESCRIBE_BAG"),
        ("BAG_004_DESCRIBE_BAG", "bag_description", "black_medium_suitcase", "BAG_005_PROVIDE_FLIGHT_OR_TAG"),
        ("BAG_005_PROVIDE_FLIGHT_OR_TAG", "baggage_tag_or_flight_info", "has_baggage_tag", "BAG_006_CONTACT_AND_DELIVERY"),
        ("BAG_006_CONTACT_AND_DELIVERY", "delivery_contact", "hotel_address", "BAG_007_RESOLUTION"),
        ("BAG_007_RESOLUTION", "resolution_acknowledgement", "acknowledged_reference_number", "END_BAGGAGE_REPORT_FILED"),
    ],
)
def test_chapter_zero_success_nodes_advance(
    node_id: str,
    slot_name: str,
    slot_value: str,
    success_next_node: str,
    tmp_path: Path,
) -> None:
    context = _node_context(node_id)

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text=context.recommended_expression,
            intent_success=True,
            confidence=0.92,
            extracted_slots={slot_name: slot_value},
            missing_slots=[],
            tier="Silver",
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.next_action == "ADVANCE"
    assert result.branch.next_node_id == success_next_node
    assert result.branch.next_node_id in context.allowed_next_nodes


@pytest.mark.parametrize(
    ("node_id", "missing_slot", "retry_next_node"),
    [
        ("IMM_001_PASSPORT", "passport_submission_status", "IMM_001_RETRY_PASSPORT"),
        ("IMM_002_PURPOSE", "visit_purpose", "IMM_002_RETRY_PURPOSE"),
        ("IMM_003_DURATION", "stay_duration", "IMM_003_RETRY_DURATION"),
        ("IMM_004_STAY_LOCATION", "stay_location", "IMM_004_RETRY_LOCATION"),
        ("IMM_005_RETURN_TICKET", "return_ticket_status", "IMM_005_RETRY_RETURN_TICKET"),
        ("IMM_006_DECLARATION_CHECK", "item_purpose", "IMM_006_RETRY_DECLARATION"),
        ("IMM_006B_PACKED_BAG_CHECK", "packed_by_self", "IMM_006B_RETRY_PACKED_BAG"),
        ("IMM_ALPHA_GOLD_BAG_CONTENT_CHECK", "bag_contents_summary", "IMM_ALPHA_GOLD_RETRY_BAG_CONTENT_CHECK"),
        ("BAG_002_FIND_STAFF", "missing_bag_status", "BAG_002_RETRY_FIND_STAFF"),
        ("BAG_003_REPORT_MISSING_BAG", "missing_bag_report", "BAG_003_RETRY_REPORT_MISSING_BAG"),
        ("BAG_004_DESCRIBE_BAG", "bag_description", "BAG_004_RETRY_DESCRIBE_BAG"),
        ("BAG_005_PROVIDE_FLIGHT_OR_TAG", "baggage_tag_or_flight_info", "BAG_005_RETRY_PROVIDE_FLIGHT_OR_TAG"),
        ("BAG_006_CONTACT_AND_DELIVERY", "delivery_contact", "BAG_006_RETRY_CONTACT_AND_DELIVERY"),
        ("BAG_007_RESOLUTION", "resolution_acknowledgement", "BAG_007_RETRY_RESOLUTION"),
    ],
)
def test_chapter_zero_missing_slot_retries(
    node_id: str,
    missing_slot: str,
    retry_next_node: str,
    tmp_path: Path,
) -> None:
    context = _node_context(node_id)

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="I am not sure.",
            intent_success=False,
            confidence=0.65,
            extracted_slots={},
            missing_slots=[missing_slot],
            tier="Silver",
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.evaluation.verdict == "FAIL"
    assert result.branch.branch_type == "retry"
    assert result.branch.next_action == "REASK"
    assert result.branch.next_node_id == retry_next_node


def test_openkb_write_creates_jsonl_and_markdown_for_error_turn(tmp_path: Path) -> None:
    payload = _policy_input(
        player_text="Travel. New York.",
        intent_success=True,
        confidence=0.72,
        extracted_slots={"visit_purpose": "tourism"},
        missing_slots=[],
        english_confidence="beginner",
    )

    result = _agent(tmp_path).evaluate_turn(payload)

    assert result.openkb_write is not None
    assert result.openkb_write.succeeded is True
    assert result.openkb_write.namespace == "dev_b"
    assert result.openkb_write.record_id
    assert result.openkb_write.jsonl_path is not None
    assert result.openkb_write.markdown_path is not None

    jsonl_path = Path(result.openkb_write.jsonl_path)
    markdown_path = Path(result.openkb_write.markdown_path)
    assert jsonl_path.exists()
    assert markdown_path.exists()

    record = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["record_schema_version"] == "dev_b_openkb_record.v2"
    assert record["record_kind"] == "policy_turn_feedback"
    assert record["record_id"] == result.openkb_write.record_id
    assert record["scene_id"] == payload.scene_id
    assert record["node_id"] == payload.current_node_id
    assert record["turn_index"] == payload.turn_index
    assert record["error_capture"]["should_record"] is True
    assert record["out_game_feedback_seed"]["include_in_final_report"] is True
    assert record["focus_on_form_targets"] == result.out_game_feedback_seed.focus_on_form_targets
    assert record["report_item"]["example_answer"] == result.report_item.example_answer
    assert record["rubric_scores"] == result.rubric_scores.model_dump() if result.rubric_scores else None
    assert record["difficulty_profile"] == result.difficulty_profile.model_dump() if result.difficulty_profile else None
    assert record["feedback_generation"] == result.feedback_generation.model_dump() if result.feedback_generation else None
    assert record["branch"] == result.branch.model_dump()
    assert record["state_delta"] == result.state_delta.model_dump()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Developer B OpenKB Record" in markdown
    assert "- Record Schema: dev_b_openkb_record.v2" in markdown
    assert "- Record Kind: policy_turn_feedback" in markdown


def test_openkb_write_records_success_turn_summary(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(_policy_input())

    assert result.openkb_write is not None
    assert result.openkb_write.succeeded is True
    assert result.openkb_write.jsonl_path is not None

    record = json.loads(Path(result.openkb_write.jsonl_path).read_text(encoding="utf-8").splitlines()[0])
    assert record["error_capture"]["should_record"] is False
    assert record["out_game_feedback_seed"]["report_priority"] == "low"
    assert record["report_item"]["summary"] == result.report_item.summary


def test_bronze_return_ticket_success_uses_baseline_immigration_route(tmp_path: Path) -> None:
    context = _node_context("IMM_005_RETURN_TICKET")

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="Yes, return ticket.",
            intent_success=True,
            confidence=0.8,
            extracted_slots={"return_ticket_status": "has_return_ticket"},
            missing_slots=[],
            tier="Bronze",
            english_confidence="beginner",
        )
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.next_node_id == "IMM_006_DECLARATION_CHECK"
    assert result.branch.next_node_id != "IMM_ALPHA_GOLD_BAG_CONTENT_CHECK"


def test_gold_return_ticket_success_routes_to_alpha_bag_content_challenge(tmp_path: Path) -> None:
    context = _node_context("IMM_005_RETURN_TICKET")

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="Yes, I do. My return flight is next Friday.",
            intent_success=True,
            confidence=0.95,
            extracted_slots={"return_ticket_status": "has_return_ticket"},
            missing_slots=[],
            tier="Gold",
            english_confidence="advanced",
        )
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.branch_type == "success"
    assert result.branch.next_node_id == "IMM_ALPHA_GOLD_BAG_CONTENT_CHECK"
    assert result.difficulty_profile is not None
    assert result.difficulty_profile.npc_speech_speed == "natural"
    assert result.difficulty_profile.question_complexity == "complex"
    assert result.difficulty_profile.pressure_level == "high"


def test_gold_challenge_node_success_returns_to_declaration_route(tmp_path: Path) -> None:
    context = _node_context("IMM_ALPHA_GOLD_BAG_CONTENT_CHECK")

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="I packed clothes, toiletries, and my laptop. I have nothing else to declare.",
            intent_success=True,
            confidence=0.94,
            extracted_slots={"bag_contents_summary": "mixed_personal_items"},
            missing_slots=[],
            tier="Gold",
            english_confidence="advanced",
        )
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.next_node_id == "IMM_006_DECLARATION_CHECK"


def test_gold_missing_return_ticket_slot_retries_without_bronze_hint(tmp_path: Path) -> None:
    context = _node_context("IMM_005_RETURN_TICKET")

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="I think so.",
            intent_success=False,
            confidence=0.68,
            extracted_slots={},
            missing_slots=["return_ticket_status"],
            tier="Gold",
            english_confidence="advanced",
        )
    )

    assert result.evaluation.verdict == "FAIL"
    assert result.branch.branch_type == "retry"
    assert result.level_hint.needs_hint is False
    assert result.out_game_feedback_seed.include_in_final_report is True
    assert result.out_game_feedback_seed.focus_on_form_targets == ["return_ticket_statement"]


def test_clean_immigration_success_does_not_create_final_report_seed(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(_policy_input(player_text="I'm here for tourism."))

    assert result.error_capture.should_record is False
    assert result.out_game_feedback_seed.include_in_final_report is False
    assert result.out_game_feedback_seed.focus_on_form_targets == []


class _InvalidBranchStateMachine:
    def decide(self, payload: DevBPolicyInput) -> ScenarioDecision:
        return ScenarioDecision(
            verdict="SUCCESS",
            branch_type="success",
            next_action="ADVANCE",
            next_node_id="IMM_NOT_ALLOWED",
            branch_reason="Invalid test branch.",
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
        )


def test_dev_b_output_self_check_rejects_branch_outside_allowed_nodes() -> None:
    with pytest.raises(ValueError, match="outside node_context.allowed_next_nodes"):
        EnglishLevelHintAgent(state_machine=cast(Any, _InvalidBranchStateMachine())).evaluate_turn(_policy_input())


def test_dev_b_output_self_check_rejects_hint_payload_when_hint_not_needed(tmp_path: Path) -> None:
    payload = _policy_input()
    result = _agent(tmp_path).evaluate_turn(payload)
    invalid = result.model_copy(update={"level_hint": result.level_hint.model_copy(update={"hint_kr": "불필요한 힌트"})})

    with pytest.raises(ValueError, match="hint payload"):
        _validate_b_policy_output(payload, invalid)


def test_dev_b_output_self_check_rejects_recast_without_candidate(tmp_path: Path) -> None:
    payload = _policy_input()
    result = _agent(tmp_path).evaluate_turn(payload)
    invalid = result.model_copy(
        update={"in_game_feedback": result.in_game_feedback.model_copy(update={"npc_recast_line_candidate": None})}
    )

    with pytest.raises(ValueError, match="recast feedback"):
        _validate_b_policy_output(payload, invalid)


def test_dev_b_output_self_check_rejects_empty_final_report_seed(tmp_path: Path) -> None:
    payload = _policy_input(
        player_text="I am not sure.",
        intent_success=False,
        confidence=0.65,
        extracted_slots={},
        missing_slots=["visit_purpose"],
        tier="Silver",
    )
    result = _agent(tmp_path).evaluate_turn(payload)
    invalid = result.model_copy(
        update={
            "out_game_feedback_seed": result.out_game_feedback_seed.model_copy(
                update={"include_in_final_report": True, "focus_on_form_targets": []}
            )
        }
    )

    with pytest.raises(ValueError, match="final-report seed"):
        _validate_b_policy_output(payload, invalid)


def test_dev_b_output_self_check_rejects_invalid_rubric_total(tmp_path: Path) -> None:
    payload = _policy_input()
    result = _agent(tmp_path).evaluate_turn(payload)
    invalid_scores = RubricScores.model_construct(
        comprehension=2,
        fluency=2,
        grammar_accuracy=2,
        vocabulary_range=2,
        clarity=2,
        interaction_problem_solving=2,
        total=13,
    )
    invalid = result.model_copy(update={"rubric_scores": invalid_scores})

    with pytest.raises(ValueError, match="rubric_scores.total"):
        _validate_b_policy_output(payload, invalid)


def test_openkb_write_is_idempotent_for_same_turn(tmp_path: Path) -> None:
    payload = _policy_input(player_text="Travel. New York.")
    agent = _agent(tmp_path)

    first = agent.evaluate_turn(payload)
    second = agent.evaluate_turn(payload)

    assert first.openkb_write is not None
    assert second.openkb_write is not None
    assert first.openkb_write.record_id == second.openkb_write.record_id
    assert first.openkb_write.jsonl_path is not None
    lines = Path(first.openkb_write.jsonl_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


class _FailingOpenKBWriter:
    namespace = "dev_b"

    def write_policy_output(self, payload: DevBPolicyInput, output: object) -> OpenKBWriteResult:
        raise RuntimeError("simulated write failure")

    def failure_result(self, error: Exception) -> OpenKBWriteResult:
        return OpenKBWriteResult(
            attempted=True,
            succeeded=False,
            namespace=self.namespace,
            error_message=str(error),
        )


def test_openkb_write_failure_does_not_change_policy_decision() -> None:
    payload = _policy_input()
    result = EnglishLevelHintAgent(openkb_writer=_FailingOpenKBWriter()).evaluate_turn(payload)

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.branch_type == "success"
    assert result.state_delta.retry_count_delta == 0
    assert result.openkb_write is not None
    assert result.openkb_write.attempted is True
    assert result.openkb_write.succeeded is False
    assert result.openkb_write.error_message == "simulated write failure"


class _FakeFeedbackLLMClient:
    model = "fake-dev-b-model"

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "hint_kr": "방문 목적을 짧게 말하면 됩니다. 예: tourism.",
            "feedback_note": "뜻은 통했지만 완전한 문장으로 말하면 더 자연스럽습니다.",
            "report_summary": "입국심사 목적 답변은 이해되었습니다.",
            "report_improvement": "I am here for tourism처럼 주어와 동사를 넣어 말해보세요.",
            "example_answer": "I'm here for tourism.",
            "focus_on_form_explanation_kr": "짧은 단어 답변보다 I'm here for ... 패턴이 안전합니다.",
            "rubric_scores": {
                "comprehension": 2,
                "fluency": 1,
                "grammar_accuracy": 1,
                "vocabulary_range": 1,
                "clarity": 2,
                "interaction_problem_solving": 2,
            },
        }


class _FailingFeedbackLLMClient:
    model = "fake-failing-model"

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("simulated llm failure")


class _ForbiddenFeedbackLLMClient:
    model = "fake-forbidden-model"

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "hint_kr": "방문 목적을 짧게 말하면 됩니다. 예: tourism.",
            "feedback_note": "뜻은 통했지만 완전한 문장으로 말하면 더 자연스럽습니다.",
            "report_summary": "입국심사 목적 답변은 이해되었습니다.",
            "report_improvement": "I am here for tourism처럼 주어와 동사를 넣어 말해보세요.",
            "example_answer": "I'm here for tourism.",
            "focus_on_form_explanation_kr": "짧은 단어 답변보다 I'm here for ... 패턴이 안전합니다.",
            "rubric_scores": {
                "comprehension": 2,
                "fluency": 1,
                "grammar_accuracy": 1,
                "vocabulary_range": 1,
                "clarity": 2,
                "interaction_problem_solving": 2,
            },
            "branch": {"next_node_id": "END_SECONDARY_INSPECTION"},
            "state_delta": {"suspicion_delta": 99},
            "verdict": "CRITICAL_FAIL",
        }


class _UsageFeedbackLLMClient:
    model = "fake-usage-model"

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "hint_kr": "방문 목적을 짧게 말하면 됩니다. 예: tourism.",
            "feedback_note": "뜻은 통했지만 완전한 문장으로 말하면 더 자연스럽습니다.",
            "report_summary": "입국심사 목적 답변은 이해되었습니다.",
            "report_improvement": "I am here for tourism처럼 주어와 동사를 넣어 말해보세요.",
            "example_answer": "I'm here for tourism.",
            "focus_on_form_explanation_kr": "짧은 단어 답변보다 I'm here for ... 패턴이 안전합니다.",
            "__llm_usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
        }


def test_fake_llm_feedback_updates_hint_note_and_report_without_changing_branch(tmp_path: Path) -> None:
    payload = _policy_input(
        player_text="I don't know.",
        intent_success=False,
        confidence=0.6,
        extracted_slots={},
        missing_slots=["visit_purpose"],
        retry_count=2,
        previous_fail_count=2,
        english_confidence="beginner",
    )

    result = _llm_agent(tmp_path, _FakeFeedbackLLMClient()).evaluate_turn(payload)

    assert result.level_hint.hint_kr == "방문 목적을 짧게 말하면 됩니다. 예: tourism."
    assert result.evaluation.feedback_note == "뜻은 통했지만 완전한 문장으로 말하면 더 자연스럽습니다."
    assert result.report_item.summary == "입국심사 목적 답변은 이해되었습니다."
    assert result.report_item.improvement == "I am here for tourism처럼 주어와 동사를 넣어 말해보세요."
    assert result.report_item.example_answer == "I'm here for tourism."
    assert result.branch.next_node_id == "IMM_002_RETRY_PURPOSE"
    assert result.evaluation.verdict == "FAIL"
    assert result.state_delta.suspicion_delta == 0
    assert result.feedback_generation is not None
    assert result.feedback_generation.mode == "llm"
    assert result.feedback_generation.used_llm is True


def test_forbidden_llm_authority_keys_force_fallback_without_changing_policy(tmp_path: Path) -> None:
    payload = _policy_input(
        player_text="I don't know.",
        intent_success=False,
        confidence=0.6,
        extracted_slots={},
        missing_slots=["visit_purpose"],
        retry_count=2,
        previous_fail_count=2,
    )

    result = _llm_agent(tmp_path, _ForbiddenFeedbackLLMClient()).evaluate_turn(payload)

    assert result.branch.next_node_id == "IMM_002_RETRY_PURPOSE"
    assert result.evaluation.verdict == "FAIL"
    assert result.state_delta.suspicion_delta == 0
    assert result.feedback_generation is not None
    assert result.feedback_generation.mode == "fallback"
    assert result.feedback_generation.used_llm is False
    assert "forbidden keys" in (result.feedback_generation.fallback_reason or "")


def test_llm_usage_is_not_exposed_on_public_dev_b_policy_output(tmp_path: Path) -> None:
    payload = _policy_input(
        player_text="I don't know.",
        intent_success=False,
        confidence=0.6,
        extracted_slots={},
        missing_slots=["visit_purpose"],
        retry_count=2,
        previous_fail_count=2,
    )

    result = _llm_agent(tmp_path, _UsageFeedbackLLMClient()).evaluate_turn(payload)

    assert result.feedback_generation is not None
    assert result.feedback_generation.mode == "llm"
    assert "__llm_usage" not in result.model_dump()


def test_bronze_baggage_broken_english_creates_problem_statement_seed(tmp_path: Path) -> None:
    context = _node_context("BAG_003_REPORT_MISSING_BAG")

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="My bag no come.",
            intent_success=True,
            confidence=0.72,
            extracted_slots={"missing_bag_report": "checked_bag_missing"},
            missing_slots=[],
            tier="Bronze",
            english_confidence="beginner",
        )
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.error_capture.should_record is True
    assert result.out_game_feedback_seed.include_in_final_report is True
    assert result.out_game_feedback_seed.focus_on_form_targets == ["problem_statement"]


def test_gold_baggage_missing_detail_retries_and_records_seed(tmp_path: Path) -> None:
    context = _node_context("BAG_004_DESCRIBE_BAG")

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="Just a suitcase.",
            intent_success=False,
            confidence=0.7,
            extracted_slots={},
            missing_slots=["bag_description"],
            tier="Gold",
            english_confidence="advanced",
        )
    )

    assert result.evaluation.verdict == "FAIL"
    assert result.branch.branch_type == "retry"
    assert result.level_hint.needs_hint is False
    assert result.out_game_feedback_seed.include_in_final_report is True
    assert result.out_game_feedback_seed.focus_on_form_targets == ["bag_description"]


def test_llm_failure_uses_fallback_generation_without_changing_policy(tmp_path: Path) -> None:
    payload = _policy_input(
        player_text="I don't know.",
        intent_success=False,
        confidence=0.6,
        extracted_slots={},
        missing_slots=["visit_purpose"],
        retry_count=2,
        previous_fail_count=2,
    )

    result = _llm_agent(tmp_path, _FailingFeedbackLLMClient()).evaluate_turn(payload)

    assert result.branch.next_node_id == "IMM_002_RETRY_PURPOSE"
    assert result.evaluation.verdict == "FAIL"
    assert result.feedback_generation is not None
    assert result.feedback_generation.mode == "fallback"
    assert result.feedback_generation.used_llm is False
    assert result.feedback_generation.fallback_reason == "simulated llm failure"
    assert result.report_item.summary


@pytest.mark.parametrize(
    ("scores", "expected_tsl"),
    [
        ([0, 0, 1, 1, 0, 1], "TSL_1_SURVIVAL"),
        ([1, 1, 1, 1, 1, 1], "TSL_2_FUNCTIONAL"),
        ([2, 1, 1, 2, 2, 1], "TSL_3_INDEPENDENT"),
        ([2, 2, 2, 2, 2, 2], "TSL_4_STRATEGIC"),
    ],
)
def test_tier_difficulty_controller_maps_rubric_total_to_tsl(
    scores: list[int],
    expected_tsl: str,
) -> None:
    result = TierDifficultyController().from_score_values(*scores)

    assert result.rubric_scores.total == sum(scores)
    assert result.difficulty_profile.travel_speaking_level == expected_tsl


def test_difficulty_profile_changes_by_tier_and_tsl() -> None:
    controller = TierDifficultyController()

    bronze = controller.from_score_values(0, 0, 1, 0, 1, 0, tier="Bronze")
    gold = controller.from_score_values(2, 2, 2, 2, 2, 2, tier="Gold")

    assert bronze.difficulty_profile.npc_speech_speed == "slow"
    assert bronze.difficulty_profile.hint_frequency == "high"
    assert bronze.difficulty_profile.pressure_level == "low"
    assert gold.difficulty_profile.npc_speech_speed == "natural"
    assert gold.difficulty_profile.hint_frequency == "low"
    assert gold.difficulty_profile.pressure_level == "high"


def test_openkb_record_includes_feedback_generation_and_difficulty(tmp_path: Path) -> None:
    payload = _policy_input(player_text="Travel. New York.")

    result = _llm_agent(tmp_path, _FakeFeedbackLLMClient()).evaluate_turn(payload)

    assert result.openkb_write is not None
    assert result.openkb_write.jsonl_path is not None
    assert result.rubric_scores is not None
    assert result.difficulty_profile is not None
    record = json.loads(Path(result.openkb_write.jsonl_path).read_text(encoding="utf-8").splitlines()[0])
    assert record["feedback_generation"]["mode"] == "llm"
    assert record["rubric_scores"]["total"] == result.rubric_scores.total
    assert record["difficulty_profile"]["travel_speaking_level"] == result.difficulty_profile.travel_speaking_level
