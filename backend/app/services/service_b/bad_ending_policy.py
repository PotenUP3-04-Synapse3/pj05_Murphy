from __future__ import annotations

from backend.app.schemas.game_turn import (
    Branch,
    DevBPolicyInput,
    DevBPolicyOutput,
    DialogueDirective,
    DifficultyProfile,
    ErrorCapture,
    Evaluation,
    InGameFeedback,
    LevelHint,
    ReportItem,
    RubricScores,
    Scores,
    StateDelta,
    OutGameFeedbackSeed,
)

_BAD_END_BY_CHAPTER = {
    "CH0_01_FLIGHT_SMALLTALK": "FLIGHT_BAD_END_VERBAL_ABUSE",
    "CH0_03_IMMIGRATION_CHECK": "IMM_BAD_END_VERBAL_ABUSE",
    "CH0_04_BAGGAGE_CLAIM":    "BAG_BAD_END_VERBAL_ABUSE",
}

def _bad_end_node_id_for_chapter(chapter_id: str) -> str:
    return _BAD_END_BY_CHAPTER.get(chapter_id, "IMM_BAD_END_VERBAL_ABUSE")

def build_bad_ending_output(payload: DevBPolicyInput, reason: str) -> DevBPolicyOutput:
    """Build DevBPolicyOutput for bad ending due to verbal abuse."""
    chapter_id = payload.chapter_id
    bad_end_node_id = _bad_end_node_id_for_chapter(chapter_id)
    
    tone_hint = "firm_official"
    if chapter_id == "CH0_01_FLIGHT_SMALLTALK":
        tone_hint = "neutral_passenger"
        
    return DevBPolicyOutput(
        contract_version="dev_b_policy.v1",
        node_id=payload.current_node_id,
        npc_emotion="Anger",
        evaluation=Evaluation(
            verdict="FAIL",
            detected_intents=[],
            required_intents_passed=False,
            filled_slots={},
            missing_slots=[],
            scores=Scores(
                task_success=0,
                clarity=0,
                grammar=0,
                vocabulary=0,
                problem_solving=0,
                politeness=0,
            ),
            feedback_tags=["verbal_abuse", "bad_ending"],
            feedback_note="Player ended interaction due to verbal abuse.",
        ),
        level_hint=LevelHint(
            english_level="beginner",
            travel_speaking_level=payload.player_profile.travel_speaking_level,
            cefr_estimate="A1",
            needs_hint=False,
            hint_level="none",
            hint_type=None,
            hint_kr=None,
            example_en=payload.node_context.recommended_expression,
            avoid_expression=None,
            recommended_expression=payload.node_context.recommended_expression,
        ),
        in_game_feedback=InGameFeedback(
            show=False,
            feedback_strategy="none",
            timing="after_player_answer",
            priority="low",
            purpose="none",
            focus="none",
            npc_recast_line_candidate=None,
            clarification_prompt_candidate=None,
            elicitation_cue_candidate=None,
            scaffolding_hint=None,
            recommended_expression=None,
            display_duration_ms=None,
            blocks_progression=True,
        ),
        error_capture=ErrorCapture(
            should_record=False,
            storage_format="markdown",
            error_items=[],
            markdown_entry=None,
        ),
        out_game_feedback_seed=OutGameFeedbackSeed(
            include_in_final_report=True,
            openkb_query_tags=["verbal_conduct_card"],
            focus_on_form_targets=["verbal_conduct_card"],
            report_priority="high",
        ),
        branch=Branch(
            branch_type="bad_end",
            next_action="COMPLETE_CHAPTER",
            next_node_id=bad_end_node_id,
            branch_reason=reason,
            allowed_next_node_checked=True,
        ),
        state_delta=StateDelta(
            patience_delta=-20,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
        ),
        report_item=ReportItem(
            summary="The interaction was terminated due to inappropriate language.",
            improvement="Always use polite and appropriate language when speaking to airport staff or fellow passengers.",
            example_answer=payload.node_context.recommended_expression,
            score_tags=["verbal_abuse", "bad_ending"],
        ),
        dialogue_directive=DialogueDirective(
            purpose="closing_eviction",
            tone_hint=tone_hint,
            target_slot=None,
            do_not_generate_npc_text=False,
        ),
        rubric_scores=RubricScores(
            comprehension=0,
            fluency=0,
            grammar_accuracy=0,
            vocabulary_range=0,
            clarity=0,
            interaction_problem_solving=0,
            total=0,
        ),
        difficulty_profile=DifficultyProfile(
            travel_speaking_level=payload.player_profile.travel_speaking_level,
            npc_speech_speed="normal",
            question_complexity="standard",
            hint_frequency="low",
            pressure_level="high",
        ),
    )
