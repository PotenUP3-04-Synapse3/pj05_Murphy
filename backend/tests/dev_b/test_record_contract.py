from pathlib import Path

from backend.app.schemas.game_turn import PolicyTurnFeedbackRecord
from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    DevBPolicyOutput,
    Evaluation,
    LevelHint,
    ErrorCapture,
    OutGameFeedbackSeed,
    Branch,
    StateDelta,
    InputSource,
    PlayerProfile,
    ScenarioState,
    UnderstandingOutput,
    RubricScores,
    ReportItem,
    Scores,
    InGameFeedback,
)


def test_record_contract_schema_defaults() -> None:
    # Test that minimum fields can be parsed (with default fallbacks)
    partial_data = {
        "node_id": "IMM_002_PURPOSE",
        "player_text": "I am here for tourism.",
        "understanding": {"meaning_summary_kr": "관광 목적"},
        "evaluation": {"verdict": "SUCCESS"},
    }

    record = PolicyTurnFeedbackRecord.model_validate(partial_data)
    assert record.node_id == "IMM_002_PURPOSE"
    assert record.player_text == "I am here for tourism."
    assert record.namespace == "dev_b"
    assert record.record_schema_version == "dev_b_openkb_record.v2"
    assert record.record_kind == "policy_turn_feedback"
    assert isinstance(record.input_source, dict)
    assert isinstance(record.state_delta, dict)
    assert record.speaker_player_id is None


def test_record_contract_writer_output_validation() -> None:
    # Load real node context using OpenKBService
    node_context = OpenKBService().get_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_002_PURPOSE")

    # Construct policy input and output payload matching actual writer inputs
    payload = DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_test_contract_123",
        session_id="session_test_contract",
        player_id="player_alice",
        room_id="room_test_contract",
        chapter_id="CH0_03_IMMIGRATION_CHECK",
        scene_id="IMM_INTERVIEW",
        current_node_id="IMM_002_PURPOSE",
        turn_index=2,
        player_text="Tourism",
        input_source=InputSource(
            input_type="voice",
            stt_confidence=1.0,
            language_detected="en-US",
            needs_repeat=False,
        ),
        player_profile=PlayerProfile(
            nickname="Alice",
            english_confidence="beginner",
            tier="Bronze",
            travel_speaking_level="TSL_1_SURVIVAL",
        ),
        scenario_state=ScenarioState(
            patience=100,
            suspicion=0,
            retry_count=0,
            hint_count=0,
            previous_fail_count=0,
            completed_intents=[],
        ),
        understanding=UnderstandingOutput(
            intent="state_purpose",
            intent_success=True,
            confidence=0.9,
            meaning_summary_kr="관광",
            emotion="calm",
            answer_relevance="on_topic",
            ambiguity_type="none",
            risk_delta=0,
            risk_reason="No risk.",
            risk_tags=[],
            extracted_slots={"visit_purpose": "tourism"},
            missing_slots=[],
            needs_clarification=False,
        ),
        speaker_player_id="player_alice",
        bag_owner_player_id="player_alice",
        addressed_player_id="player_alice",
        node_context=node_context,
    )

    output = DevBPolicyOutput(
        contract_version="dev_b_policy.v1",
        node_id="IMM_002_PURPOSE",
        evaluation=Evaluation(
            verdict="SUCCESS",
            detected_intents=["state_purpose"],
            required_intents_passed=True,
            filled_slots={"visit_purpose": "tourism"},
            missing_slots=[],
            scores=Scores(task_success=100, clarity=100, grammar=100, vocabulary=100, problem_solving=100, politeness=100),
            feedback_tags=[],
            feedback_note="Good job."
        ),
        level_hint=LevelHint(
            english_level="beginner",
            travel_speaking_level="TSL_1_SURVIVAL",
            needs_hint=False,
            hint_level="none",
            hint_type="none",
            hint_kr=None,
            example_en="I am here for tourism.",
            recommended_expression="I am here for tourism.",
        ),
        in_game_feedback=InGameFeedback(
            show=False,
            feedback_strategy="none",
            timing="during_dialogue_turn",
            priority="low",
            purpose="none",
            focus="none",
            npc_recast_line_candidate=None,
            clarification_prompt_candidate=None,
            elicitation_cue_candidate=None,
            scaffolding_hint=None,
            blocks_progression=False,
        ),
        error_capture=ErrorCapture(
            should_record=False,
            storage_format="markdown",
            error_items=[],
            markdown_entry=None,
        ),
        out_game_feedback_seed=OutGameFeedbackSeed(
            include_in_final_report=True,
            openkb_query_tags=[],
            focus_on_form_targets=[],
            report_priority="low",
        ),
        report_item=ReportItem(
            summary="Valid purpose",
            improvement="None",
            example_answer="Tourism",
            score_tags=[],
        ),
        rubric_scores=RubricScores(
            comprehension=2,
            fluency=2,
            grammar_accuracy=2,
            vocabulary_range=2,
            clarity=2,
            interaction_problem_solving=2,
            total=12,
        ),
        branch=Branch(
            branch_type="success",
            next_action="ADVANCE",
            next_node_id="IMM_003_DURATION",
            branch_reason="test",
            allowed_next_node_checked=True,
        ),
        state_delta=StateDelta(
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
        ),
    )

    writer = OpenKBFeedbackWriter(runtime_root=Path("backend/runtime/openkb/dev_b"))
    built_dict = writer._build_record(payload, output)

    # Validate that writer builds a dict that fully conforms to PolicyTurnFeedbackRecord
    record = PolicyTurnFeedbackRecord.model_validate(built_dict)
    assert record.request_id == "req_test_contract_123"
    assert record.session_id == "session_test_contract"
    assert record.player_id == "player_alice"
    assert record.room_id == "room_test_contract"
    assert record.speaker_player_id == "player_alice"
    assert record.bag_owner_player_id == "player_alice"
    assert record.addressed_player_id == "player_alice"
    assert record.evaluation["verdict"] == "SUCCESS"
    assert record.rubric_scores is not None
    assert record.rubric_scores["total"] == 12

    # P-4: auto key-set contract — writer output keys must cover all PolicyTurnFeedbackRecord fields.
    # If a new field is added to PolicyTurnFeedbackRecord without updating _build_record, this fails.
    schema_fields = set(PolicyTurnFeedbackRecord.model_fields.keys())
    writer_keys = set(built_dict.keys())
    missing_from_writer = schema_fields - writer_keys
    assert not missing_from_writer, (
        f"Writer._build_record is missing PolicyTurnFeedbackRecord fields: {missing_from_writer}. "
        "Add them to _build_record or give them a sentinel default in the schema."
    )


def test_record_contract_keyset_detection_works() -> None:
    """Verify that the key-set mechanism correctly detects missing fields.

    This test shows the inverse: if a writer dict is missing schema fields,
    the superset check raises — confirming the guard is active.
    """
    schema_fields = set(PolicyTurnFeedbackRecord.model_fields.keys())
    # Simulate a writer that only writes a subset of fields
    incomplete_writer_dict = {"node_id": "TEST", "player_text": "hello"}
    missing = schema_fields - set(incomplete_writer_dict.keys())
    assert missing, (
        "Expected to detect schema fields absent from a partial writer output, "
        f"but got no missing fields. schema_fields={schema_fields}"
    )
