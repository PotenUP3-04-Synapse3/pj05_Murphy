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
        scenario_id=node_data["scenario_id"],
        chapter_id=node["chapter_id"],
        node_type=node["node_type"],
        transition=node.get("transition"),
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
        chapter_id=context.chapter_id,
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
    assert result.npc_emotion == "Nomal"


def test_npc_emotion_uses_shared_external_enum(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(_policy_input())

    assert result.npc_emotion in {
        "Nomal",
        "Joy",
        "Anger",
        "Sadness",
        "Panic",
        "Suspicion",
        "Disgust",
        "Fear",
        "Smirk",
        "Surprise",
        "Pain",
        "Confusion",
        "Boredom",
    }


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
    assert result.npc_emotion == "Confusion"


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
    assert result.npc_emotion == "Suspicion"


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

    assert node_data["contract_version"] == "dev_b_scenario_nodes.v2"
    assert node_data["scenario_id"] == "ALPHA_AIRPORT_ARRIVAL"
    assert [chapter["chapter_id"] for chapter in node_data["chapters"]] == [
        "CH0_01_FLIGHT_SMALLTALK",
        "CH0_02_ARRIVAL_TUTORIAL",
        "CH0_03_IMMIGRATION_CHECK",
        "CH0_04_BAGGAGE_CLAIM",
        "CH0_05_RESULT",
    ]
    assert node_data["chapters"][0]["entry_node_id"] == "FLIGHT_A_001_SEATMATE_SMALLTALK"
    assert node_data["chapters"][0]["entry_node_ids"] == [
        "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "FLIGHT_B_001_DESTINATION_CHAT",
        "FLIGHT_C_001_FORM_HELP_REQUEST",
    ]
    assert set(node_data["nodes"]) == {
        "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "FLIGHT_A_002_TRAVEL_PURPOSE",
        "FLIGHT_A_003_STAY_PLAN",
        "FLIGHT_A_004_CLARIFY_OR_ASK_BACK",
        "FLIGHT_A_005_WRAP_UP",
        "FLIGHT_B_001_DESTINATION_CHAT",
        "FLIGHT_B_002_COMPANION_OR_VISIT",
        "FLIGHT_B_003_STAY_PLACE",
        "FLIGHT_B_004_TRIP_PLANS",
        "FLIGHT_B_005_LANDING_CLOSE",
        "FLIGHT_C_001_FORM_HELP_REQUEST",
        "FLIGHT_C_002_FIRST_TIME_ENTRY",
        "FLIGHT_C_003_ADDRESS_HELP",
        "FLIGHT_C_004_HOTEL_HOSTEL_REPAIR",
        "FLIGHT_C_005_FORM_CLOSE",
        "FLIGHT_999_COMPLETE",
        "IMM_001_PASSPORT",
        "IMM_002_PURPOSE",
        "IMM_003_DURATION",
        "IMM_004_STAY_LOCATION",
        "IMM_005_RETURN_TICKET",
        "IMM_ALPHA_GOLD_BAG_CONTENT_CHECK",
        "IMM_006_DECLARATION_CHECK",
        "IMM_006B_PACKED_BAG_CHECK",
        "IMM_007_FINAL_DECISION",
        "IMM_999_CLEARED",
        "BAG_001_REPORT_MISSING_AT_DESK",
        "BAG_002_PROVIDE_CLAIM_TAG",
        "BAG_003_CONFIRM_SEARCHED_CAROUSEL",
        "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD",
        "BAG_005_CUSTOMS_HOLD_EXPLANATION",
        "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM",
        "BAG_007_CUSTOMS_CLEARANCE",
        "BAG_999_COMPLETE",
        "ALPHA_999_FINAL_SCOREBOARD",
    }
    for node in node_data["nodes"].values():
        allowed_next_nodes = set(node["allowed_next_nodes"])
        assert allowed_next_nodes
        assert node["chapter_id"].startswith("CH0_")
        assert node["node_type"] in {"dialogue", "transition", "result", "ending"}
        assert node["objective_kr"]
        for branch_name in ["retry", "clarify", "warning", "bad_end"]:
            assert branch_name in node["branch_candidates"]
            assert node["branch_candidates"][branch_name] in allowed_next_nodes


def test_flight_smalltalk_node_exists_as_alpha_diagnostic_node() -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")

    assert context.node_id == "FLIGHT_A_001_SEATMATE_SMALLTALK"
    assert context.npc_question_goal == "respond_to_polite_request"
    assert context.required_intents == ["respond_to_seatmate_request"]
    assert context.required_slots == ["polite_response"]
    assert "FLIGHT_A_002_TRAVEL_PURPOSE" in context.allowed_next_nodes


def test_alpha_flight_nodes_form_three_five_turn_diagnostic_routes() -> None:
    expected_routes = [
        [
            ("FLIGHT_A_001_SEATMATE_SMALLTALK", "FLIGHT_A_002_TRAVEL_PURPOSE"),
            ("FLIGHT_A_002_TRAVEL_PURPOSE", "FLIGHT_A_003_STAY_PLAN"),
            ("FLIGHT_A_003_STAY_PLAN", "FLIGHT_A_004_CLARIFY_OR_ASK_BACK"),
            ("FLIGHT_A_004_CLARIFY_OR_ASK_BACK", "FLIGHT_A_005_WRAP_UP"),
            ("FLIGHT_A_005_WRAP_UP", "FLIGHT_999_COMPLETE"),
        ],
        [
            ("FLIGHT_B_001_DESTINATION_CHAT", "FLIGHT_B_002_COMPANION_OR_VISIT"),
            ("FLIGHT_B_002_COMPANION_OR_VISIT", "FLIGHT_B_003_STAY_PLACE"),
            ("FLIGHT_B_003_STAY_PLACE", "FLIGHT_B_004_TRIP_PLANS"),
            ("FLIGHT_B_004_TRIP_PLANS", "FLIGHT_B_005_LANDING_CLOSE"),
            ("FLIGHT_B_005_LANDING_CLOSE", "FLIGHT_999_COMPLETE"),
        ],
        [
            ("FLIGHT_C_001_FORM_HELP_REQUEST", "FLIGHT_C_002_FIRST_TIME_ENTRY"),
            ("FLIGHT_C_002_FIRST_TIME_ENTRY", "FLIGHT_C_003_ADDRESS_HELP"),
            ("FLIGHT_C_003_ADDRESS_HELP", "FLIGHT_C_004_HOTEL_HOSTEL_REPAIR"),
            ("FLIGHT_C_004_HOTEL_HOSTEL_REPAIR", "FLIGHT_C_005_FORM_CLOSE"),
            ("FLIGHT_C_005_FORM_CLOSE", "FLIGHT_999_COMPLETE"),
        ],
    ]

    for route in expected_routes:
        assert len(route) == 5
        for node_id, next_node_id in route:
            context = _node_context(node_id)
            assert context.chapter_id == "CH0_01_FLIGHT_SMALLTALK"
            assert context.node_type == "dialogue"
            assert context.success_next_node == next_node_id
            assert context.retry_next_node == next_node_id
            assert context.clarify_next_node == next_node_id
            assert context.hint_next_node == next_node_id
            assert context.warning_next_node == next_node_id
            assert set(context.allowed_next_nodes) == {next_node_id}


def test_alpha_flight_route_a_uses_labeled_node_ids() -> None:
    node_data = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))
    legacy_route_a_node_ids = {
        "FLIGHT_001_SEATMATE_SMALLTALK",
        "FLIGHT_002_TRAVEL_PURPOSE",
        "FLIGHT_003_STAY_PLAN",
        "FLIGHT_004_CLARIFY_OR_ASK_BACK",
        "FLIGHT_005_WRAP_UP",
    }

    assert not legacy_route_a_node_ids & set(node_data["nodes"])
    assert node_data["chapters"][0]["entry_node_id"] == "FLIGHT_A_001_SEATMATE_SMALLTALK"


def test_baggage_route_requires_customs_hold_item_explanation_and_alpha_scoreboard() -> None:
    bag_notice = _node_context("BAG_001_REPORT_MISSING_AT_DESK")
    customs_item = _node_context("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM")
    customs_clearance = _node_context("BAG_007_CUSTOMS_CLEARANCE")
    baggage_complete = _node_context("BAG_999_COMPLETE")
    final_scoreboard = _node_context("ALPHA_999_FINAL_SCOREBOARD")

    assert bag_notice.success_next_node == "BAG_002_PROVIDE_CLAIM_TAG"
    assert bag_notice.required_intents == ["report_missing_bag_at_service_desk"]
    assert bag_notice.required_slots == ["missing_bag_statement"]
    assert customs_item.required_intents == ["explain_random_customs_item"]
    assert customs_item.required_slots == ["customs_item_explanation"]
    assert customs_clearance.success_next_node == "BAG_999_COMPLETE"
    assert baggage_complete.node_type == "transition"
    assert baggage_complete.transition is not None
    assert baggage_complete.transition.unreal_event == "SHOW_ALPHA_SCOREBOARD"
    assert baggage_complete.transition.entry_node_id == "ALPHA_999_FINAL_SCOREBOARD"
    assert final_scoreboard.success_next_node == "END_ALPHA_SCENARIO"
    assert "END_ALPHA_SCENARIO" in final_scoreboard.allowed_next_nodes


def test_alpha_boundary_transition_nodes_define_unreal_events() -> None:
    flight_complete = _node_context("FLIGHT_999_COMPLETE")
    immigration_cleared = _node_context("IMM_999_CLEARED")
    baggage_complete = _node_context("BAG_999_COMPLETE")

    assert flight_complete.node_type == "transition"
    assert flight_complete.chapter_id == "CH0_01_FLIGHT_SMALLTALK"
    assert flight_complete.transition is not None
    assert flight_complete.transition.completed_chapter_id == "CH0_01_FLIGHT_SMALLTALK"
    assert flight_complete.transition.next_chapter_id == "CH0_02_ARRIVAL_TUTORIAL"
    assert flight_complete.transition.entry_node_id is None
    assert flight_complete.transition.unreal_event == "START_AIRPORT_ARRIVAL_TUTORIAL"
    assert flight_complete.transition.requires_player_input is False

    assert immigration_cleared.node_type == "transition"
    assert immigration_cleared.transition is not None
    assert immigration_cleared.transition.completed_chapter_id == "CH0_03_IMMIGRATION_CHECK"
    assert immigration_cleared.transition.next_chapter_id == "CH0_04_BAGGAGE_CLAIM"
    assert immigration_cleared.transition.entry_node_id == "BAG_001_REPORT_MISSING_AT_DESK"
    assert immigration_cleared.transition.unreal_event == "ENTER_BAGGAGE_CLAIM"

    assert baggage_complete.node_type == "transition"
    assert baggage_complete.transition is not None
    assert baggage_complete.transition.completed_chapter_id == "CH0_04_BAGGAGE_CLAIM"
    assert baggage_complete.transition.next_chapter_id == "CH0_05_RESULT"
    assert baggage_complete.transition.entry_node_id == "ALPHA_999_FINAL_SCOREBOARD"
    assert baggage_complete.transition.unreal_event == "SHOW_ALPHA_SCOREBOARD"


def test_flight_smalltalk_creates_deferred_out_game_feedback_seed(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="Sure, here you are.",
            intent_success=True,
            confidence=0.88,
            extracted_slots={"polite_response": "offered_help"},
            missing_slots=[],
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.out_game_feedback_seed.include_in_final_report is True
    assert result.out_game_feedback_seed.focus_on_form_targets == ["smalltalk_response_clarity"]
    assert "deferred_out_game_feedback" in result.out_game_feedback_seed.openkb_query_tags
    assert result.branch.next_node_id in context.allowed_next_nodes
    assert result.branch.next_node_id == "FLIGHT_A_002_TRAVEL_PURPOSE"
    assert result.dialogue_seed is not None
    assert result.dialogue_seed.max_turns == 5


def test_flight_diagnostic_retry_still_moves_to_next_evidence_node(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_003_STAY_PLAN")

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="Maybe.",
            intent_success=False,
            confidence=0.66,
            extracted_slots={},
            missing_slots=["stay_plan"],
            tier="Silver",
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.evaluation.verdict == "FAIL"
    assert result.branch.branch_type == "retry"
    assert result.branch.next_node_id == "FLIGHT_A_004_CLARIFY_OR_ASK_BACK"


def test_alpha_final_scoreboard_is_only_dev_b_final_branch(tmp_path: Path) -> None:
    imm_final_context = _node_context("IMM_007_FINAL_DECISION")
    alpha_final_context = _node_context("ALPHA_999_FINAL_SCOREBOARD")

    imm_result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=imm_final_context,
            player_text="Thank you, officer.",
            intent_success=True,
            confidence=0.92,
            extracted_slots={"immigration_transition_acknowledgement": "acknowledged"},
            missing_slots=[],
            client_allowed_next_nodes=imm_final_context.allowed_next_nodes,
        )
    )
    alpha_result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=alpha_final_context,
            player_text="Thank you.",
            intent_success=True,
            confidence=0.92,
            extracted_slots={"final_recommendation": "PASS"},
            missing_slots=[],
            client_allowed_next_nodes=alpha_final_context.allowed_next_nodes,
        )
    )

    assert imm_result.branch.branch_type == "success"
    assert imm_result.branch.next_action == "COMPLETE_CHAPTER"
    assert imm_result.branch.next_node_id == "IMM_999_CLEARED"
    assert alpha_result.branch.branch_type == "final"
    assert alpha_result.branch.next_action == "FINAL_DECISION"
    assert alpha_result.branch.next_node_id == "END_ALPHA_SCENARIO"


def test_report_item_and_feedback_tags_are_returned(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(_policy_input())

    assert result.report_item.summary
    assert result.report_item.improvement
    assert result.report_item.example_answer
    assert result.evaluation.feedback_tags


def test_report_seed_summary_contains_ui_assembly_metadata(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            player_text="Travel. New York.",
            intent_success=True,
            confidence=0.72,
            extracted_slots={"visit_purpose": "tourism"},
            missing_slots=[],
            english_confidence="beginner",
        )
    )

    assert result.report_seed_summary is not None
    assert result.report_seed_summary.estimated_level == "beginner"
    assert result.report_seed_summary.tier == "Bronze"
    assert result.report_seed_summary.scenario_result == "passed"
    assert 0 <= result.report_seed_summary.overall_score_candidate <= 100
    assert result.report_seed_summary.category_scores.task_success >= 0
    assert result.report_seed_summary.strengths
    assert result.report_seed_summary.critical_breakdowns
    assert result.report_seed_summary.corrected_examples
    assert result.report_seed_summary.reusable_sentence_patterns
    assert result.report_seed_summary.next_practice_goal
    assert result.report_seed_summary.feedback_focus
    assert result.report_seed_summary.ui_priority_order[0] == "scenario_result"
    assert "Bronze" in result.report_seed_summary.display_policy_by_tier


def test_dialogue_seed_contains_generation_metadata_without_final_npc_text(tmp_path: Path) -> None:
    payload = _policy_input()

    result = _agent(tmp_path).evaluate_turn(payload)

    assert result.dialogue_seed is not None
    assert result.dialogue_seed.scene == payload.scene_id
    assert result.dialogue_seed.npc_role == "immigration_officer"
    assert result.dialogue_seed.surface_goal == payload.node_context.npc_question_goal
    assert result.dialogue_seed.hidden_assessment_goal == "estimate_user_travel_speaking_level"
    assert payload.node_context.required_slots[0] in result.dialogue_seed.required_slots
    assert payload.node_context.required_slots[0] in result.dialogue_seed.assessment_targets
    assert result.dialogue_seed.max_turns == 4
    assert result.dialogue_seed.difficulty_profile == "auto"
    assert result.dialogue_seed.feedback_focus
    assert result.dialogue_seed.tone_guidance == "neutral_official"
    assert result.dialogue_seed.allowed_followup_intents
    assert result.dialogue_seed.stop_condition

    forbidden_keys = {"npc_text", "npc_utterance", "final_dialogue_line"}
    assert forbidden_keys.isdisjoint(_all_keys(result.model_dump()))


@pytest.mark.parametrize(
    ("node_id", "slot_name", "slot_value", "success_next_node"),
    [
        ("FLIGHT_A_001_SEATMATE_SMALLTALK", "polite_response", "offered_help", "FLIGHT_A_002_TRAVEL_PURPOSE"),
        ("FLIGHT_A_002_TRAVEL_PURPOSE", "travel_purpose", "tourism", "FLIGHT_A_003_STAY_PLAN"),
        ("FLIGHT_A_003_STAY_PLAN", "stay_plan", "five_days", "FLIGHT_A_004_CLARIFY_OR_ASK_BACK"),
        ("FLIGHT_A_004_CLARIFY_OR_ASK_BACK", "interaction_repair", "asked_clarification", "FLIGHT_A_005_WRAP_UP"),
        ("FLIGHT_A_005_WRAP_UP", "smalltalk_closing", "polite_closing", "FLIGHT_999_COMPLETE"),
        ("IMM_001_PASSPORT", "passport_submission_status", "submitted", "IMM_002_PURPOSE"),
        ("IMM_002_PURPOSE", "visit_purpose", "tourism", "IMM_003_DURATION"),
        ("IMM_003_DURATION", "stay_duration", "days", "IMM_004_STAY_LOCATION"),
        ("IMM_004_STAY_LOCATION", "stay_location", "hotel", "IMM_005_RETURN_TICKET"),
        ("IMM_006_DECLARATION_CHECK", "item_purpose", "personal_recreation", "IMM_006B_PACKED_BAG_CHECK"),
        ("IMM_006B_PACKED_BAG_CHECK", "packed_by_self", "yes_self_packed", "IMM_007_FINAL_DECISION"),
        ("IMM_ALPHA_GOLD_BAG_CONTENT_CHECK", "bag_contents_summary", "mixed_personal_items", "IMM_006_DECLARATION_CHECK"),
        ("IMM_007_FINAL_DECISION", "immigration_transition_acknowledgement", "acknowledged", "IMM_999_CLEARED"),
        ("BAG_001_REPORT_MISSING_AT_DESK", "missing_bag_statement", "bag_not_arrived", "BAG_002_PROVIDE_CLAIM_TAG"),
        ("BAG_002_PROVIDE_CLAIM_TAG", "claim_tag_status", "has_claim_tag", "BAG_003_CONFIRM_SEARCHED_CAROUSEL"),
        ("BAG_003_CONFIRM_SEARCHED_CAROUSEL", "carousel_search_confirmation", "searched_carefully", "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD"),
        ("BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD", "customs_hold_redirect_acknowledgement", "will_go_to_customs_hold", "BAG_005_CUSTOMS_HOLD_EXPLANATION"),
        ("BAG_005_CUSTOMS_HOLD_EXPLANATION", "customs_hold_acknowledgement", "will_unlock_and_check", "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"),
        ("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM", "customs_item_explanation", "personal_item", "BAG_007_CUSTOMS_CLEARANCE"),
        ("BAG_007_CUSTOMS_CLEARANCE", "customs_clearance_acknowledgement", "acknowledged_clearance", "BAG_999_COMPLETE"),
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
    expected_action = "COMPLETE_CHAPTER" if success_next_node.endswith("_999_COMPLETE") or success_next_node == "IMM_999_CLEARED" else "ADVANCE"
    assert result.branch.next_action == expected_action
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
        ("IMM_007_FINAL_DECISION", "immigration_transition_acknowledgement", "IMM_007_RETRY_FINAL_DECISION"),
        ("BAG_001_REPORT_MISSING_AT_DESK", "missing_bag_statement", "BAG_001_RETRY_REPORT_MISSING_AT_DESK"),
        ("BAG_002_PROVIDE_CLAIM_TAG", "claim_tag_status", "BAG_002_RETRY_PROVIDE_CLAIM_TAG"),
        ("BAG_003_CONFIRM_SEARCHED_CAROUSEL", "carousel_search_confirmation", "BAG_003_RETRY_CONFIRM_SEARCHED_CAROUSEL"),
        ("BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD", "customs_hold_redirect_acknowledgement", "BAG_004_RETRY_STAFF_REDIRECT_TO_CUSTOMS_HOLD"),
        ("BAG_005_CUSTOMS_HOLD_EXPLANATION", "customs_hold_acknowledgement", "BAG_005_RETRY_CUSTOMS_HOLD_EXPLANATION"),
        ("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM", "customs_item_explanation", "BAG_006_RETRY_EXPLAIN_RANDOM_CUSTOMS_ITEM"),
        ("BAG_007_CUSTOMS_CLEARANCE", "customs_clearance_acknowledgement", "BAG_007_RETRY_CUSTOMS_CLEARANCE"),
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
    assert result.report_seed_summary is not None
    assert result.dialogue_seed is not None
    assert record["report_seed_summary"]["estimated_level"] == result.report_seed_summary.estimated_level
    assert record["dialogue_seed"]["scene"] == result.dialogue_seed.scene


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
    invalid = result.model_copy(update={"level_hint": result.level_hint.model_copy(update={"hint_kr": "遺덊븘?뷀븳 ?뚰듃"})})

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
            "hint_kr": "諛⑸Ц 紐⑹쟻??吏㏐쾶 留먰븯硫??⑸땲?? ?? tourism.",
            "feedback_note": "?살? ?듯뻽吏留??꾩쟾??臾몄옣?쇰줈 留먰븯硫????먯뿰?ㅻ읇?듬땲??",
            "report_summary": "?낃뎅?ъ궗 紐⑹쟻 ?듬?? ?댄빐?섏뿀?듬땲??",
            "report_improvement": "I am here for tourism泥섎읆 二쇱뼱? ?숈궗瑜??ｌ뼱 留먰빐蹂댁꽭??",
            "example_answer": "I'm here for tourism.",
            "focus_on_form_explanation_kr": "吏㏃? ?⑥뼱 ?듬?蹂대떎 I'm here for ... ?⑦꽩???덉쟾?⑸땲??",
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
            "hint_kr": "諛⑸Ц 紐⑹쟻??吏㏐쾶 留먰븯硫??⑸땲?? ?? tourism.",
            "feedback_note": "?살? ?듯뻽吏留??꾩쟾??臾몄옣?쇰줈 留먰븯硫????먯뿰?ㅻ읇?듬땲??",
            "report_summary": "?낃뎅?ъ궗 紐⑹쟻 ?듬?? ?댄빐?섏뿀?듬땲??",
            "report_improvement": "I am here for tourism泥섎읆 二쇱뼱? ?숈궗瑜??ｌ뼱 留먰빐蹂댁꽭??",
            "example_answer": "I'm here for tourism.",
            "focus_on_form_explanation_kr": "吏㏃? ?⑥뼱 ?듬?蹂대떎 I'm here for ... ?⑦꽩???덉쟾?⑸땲??",
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


class _ForbiddenDialogueFeedbackLLMClient:
    model = "fake-forbidden-dialogue-model"

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "hint_kr": "諛⑸Ц 紐⑹쟻??吏㏐쾶 留먰븯硫??⑸땲?? ?? tourism.",
            "feedback_note": "?살? ?듯뻽吏留??꾩쟾??臾몄옣?쇰줈 留먰븯硫????먯뿰?ㅻ읇?듬땲??",
            "report_summary": "?낃뎅?ъ궗 紐⑹쟻 ?듬?? ?댄빐?섏뿀?듬땲??",
            "report_improvement": "I am here for tourism泥섎읆 二쇱뼱? ?숈궗瑜??ｌ뼱 留먰빐蹂댁꽭??",
            "example_answer": "I'm here for tourism.",
            "focus_on_form_explanation_kr": "吏㏃? ?⑥뼱 ?듬?蹂대떎 I'm here for ... ?⑦꽩???덉쟾?⑸땲??",
            "rubric_scores": {
                "comprehension": 2,
                "fluency": 1,
                "grammar_accuracy": 1,
                "vocabulary_range": 1,
                "clarity": 2,
                "interaction_problem_solving": 2,
            },
            "npc_utterance": "Final NPC line must not come from Developer B.",
            "final_dialogue_line": "This should force fallback.",
        }


class _UsageFeedbackLLMClient:
    model = "fake-usage-model"

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "hint_kr": "諛⑸Ц 紐⑹쟻??吏㏐쾶 留먰븯硫??⑸땲?? ?? tourism.",
            "feedback_note": "?살? ?듯뻽吏留??꾩쟾??臾몄옣?쇰줈 留먰븯硫????먯뿰?ㅻ읇?듬땲??",
            "report_summary": "?낃뎅?ъ궗 紐⑹쟻 ?듬?? ?댄빐?섏뿀?듬땲??",
            "report_improvement": "I am here for tourism泥섎읆 二쇱뼱? ?숈궗瑜??ｌ뼱 留먰빐蹂댁꽭??",
            "example_answer": "I'm here for tourism.",
            "focus_on_form_explanation_kr": "吏㏃? ?⑥뼱 ?듬?蹂대떎 I'm here for ... ?⑦꽩???덉쟾?⑸땲??",
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

    assert result.level_hint.hint_kr == "諛⑸Ц 紐⑹쟻??吏㏐쾶 留먰븯硫??⑸땲?? ?? tourism."
    assert result.evaluation.feedback_note == "?살? ?듯뻽吏留??꾩쟾??臾몄옣?쇰줈 留먰븯硫????먯뿰?ㅻ읇?듬땲??"
    assert result.report_item.summary == "?낃뎅?ъ궗 紐⑹쟻 ?듬?? ?댄빐?섏뿀?듬땲??"
    assert result.report_item.improvement == "I am here for tourism泥섎읆 二쇱뼱? ?숈궗瑜??ｌ뼱 留먰빐蹂댁꽭??"
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


def test_forbidden_llm_dialogue_keys_force_fallback_without_changing_policy(tmp_path: Path) -> None:
    payload = _policy_input(
        player_text="I don't know.",
        intent_success=False,
        confidence=0.6,
        extracted_slots={},
        missing_slots=["visit_purpose"],
        retry_count=2,
        previous_fail_count=2,
    )

    result = _llm_agent(tmp_path, _ForbiddenDialogueFeedbackLLMClient()).evaluate_turn(payload)

    assert result.branch.next_node_id == "IMM_002_RETRY_PURPOSE"
    assert result.evaluation.verdict == "FAIL"
    assert result.state_delta.retry_count_delta == 1
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
    context = _node_context("BAG_001_REPORT_MISSING_AT_DESK")

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="My bag no come.",
            intent_success=True,
            confidence=0.72,
            extracted_slots={"missing_bag_statement": "bag_not_arrived"},
            missing_slots=[],
            tier="Bronze",
            english_confidence="beginner",
        )
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.error_capture.should_record is True
    assert result.out_game_feedback_seed.include_in_final_report is True
    assert result.out_game_feedback_seed.focus_on_form_targets == ["problem_statement"]


def test_gold_baggage_customs_item_detail_retries_and_records_seed(tmp_path: Path) -> None:
    context = _node_context("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM")

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="Just a suitcase.",
            intent_success=False,
            confidence=0.7,
            extracted_slots={},
            missing_slots=["customs_item_explanation"],
            tier="Gold",
            english_confidence="advanced",
        )
    )

    assert result.evaluation.verdict == "FAIL"
    assert result.branch.branch_type == "retry"
    assert result.level_hint.needs_hint is False
    assert result.out_game_feedback_seed.include_in_final_report is True
    assert result.out_game_feedback_seed.focus_on_form_targets == ["customs_item_explanation"]


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


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_all_keys(child))
        return keys
    if isinstance(value, list):
        list_keys: set[str] = set()
        for child in value:
            list_keys.update(_all_keys(child))
        return list_keys
    return set()
