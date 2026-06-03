from backend.app.schemas.game_turn import (
    Branch,
    DevBPolicyInput,
    DevBPolicyOutput,
    DialogueDirective,
    ErrorCapture,
    Evaluation,
    InGameFeedback,
    LevelHint,
    OutGameFeedbackSeed,
    ReportItem,
    Scores,
    StateDelta,
)
from typing import Literal


class DevBPolicyClient:
    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        success = payload.understanding.intent_success and not payload.understanding.missing_slots

        if success:
            verdict: Literal["SUCCESS", "PARTIAL", "UNCLEAR", "FAIL", "CRITICAL_FAIL"] = "SUCCESS"
            branch_type: Literal["success", "retry", "clarify", "hint", "warning", "bad_end", "final"] = "success"
            next_action: Literal["ADVANCE", "REASK", "GIVE_HINT", "WARNING", "FAIL_END", "FINAL_DECISION"] = (
                "ADVANCE"
            )
            next_node_id = payload.node_context.success_next_node
            branch_reason = "Required intent and slot were satisfied."
            feedback_strategy: Literal[
                "recast",
                "clarification_request",
                "elicitation",
                "scaffolding_hint",
                "warning",
                "none",
            ] = "recast"
            hint_level: Literal["none", "low", "medium", "high"] = "none"
            needs_hint = False
        elif payload.understanding.needs_clarification:
            verdict = "UNCLEAR"
            branch_type = "clarify"
            next_action = "REASK"
            next_node_id = payload.node_context.clarify_next_node
            branch_reason = "Visit purpose needs clarification."
            feedback_strategy = "clarification_request"
            hint_level = "medium"
            needs_hint = True
        else:
            verdict = "FAIL"
            branch_type = "retry"
            next_action = "REASK"
            next_node_id = payload.node_context.retry_next_node
            branch_reason = "Required visit purpose was not satisfied."
            feedback_strategy = "scaffolding_hint"
            hint_level = "medium"
            needs_hint = True

        scores = Scores(
            task_success=3 if success else 0,
            clarity=2 if success else 1,
            grammar=2 if success else 1,
            vocabulary=2 if success else 1,
            problem_solving=2 if success else 1,
            politeness=3,
        )

        return DevBPolicyOutput(
            contract_version="dev_b_policy.v1",
            node_id=payload.current_node_id,
            evaluation=Evaluation(
                verdict=verdict,
                detected_intents=[payload.understanding.intent],
                required_intents_passed=success,
                filled_slots=payload.understanding.extracted_slots,
                missing_slots=payload.understanding.missing_slots,
                scores=scores,
                feedback_tags=["intent_matched", "required_slot_filled"] if success else ["needs_retry"],
                feedback_note="Visit purpose was understood." if success else "Visit purpose needs support.",
            ),
            level_hint=LevelHint(
                english_level=payload.player_profile.english_confidence or "beginner",
                travel_speaking_level=payload.player_profile.travel_speaking_level,
                cefr_estimate="A1-A2",
                needs_hint=needs_hint,
                hint_level=hint_level,
                hint_type=None if not needs_hint else "sentence_pattern",
                hint_kr=None if not needs_hint else payload.node_context.base_hint_kr,
                example_en=payload.node_context.recommended_expression,
                avoid_expression="I came to work illegally.",
                recommended_expression=payload.node_context.recommended_expression,
            ),
            in_game_feedback=InGameFeedback(
                show=True,
                feedback_strategy=feedback_strategy,
                timing="during_dialogue_turn",
                priority="low" if success else "medium",
                purpose="maintain_communication" if success else "restore_clarity",
                focus="sentence_naturalness" if success else "visit_purpose",
                npc_recast_line_candidate=(
                    "You're here for tourism. How long will you stay?" if success else None
                ),
                clarification_prompt_candidate=(
                    None if success else "Are you visiting for tourism, business, or transit?"
                ),
                elicitation_cue_candidate=None,
                scaffolding_hint=None if success else payload.node_context.hint_policy.sentence_pattern,
                recommended_expression=payload.node_context.recommended_expression,
                display_duration_ms=None,
                blocks_progression=not success,
            ),
            error_capture=ErrorCapture(
                should_record=False,
                storage_format="markdown",
                error_items=[],
                markdown_entry=None,
            ),
            out_game_feedback_seed=OutGameFeedbackSeed(
                include_in_final_report=False,
                openkb_query_tags=[],
                focus_on_form_targets=[],
                report_priority="low",
            ),
            branch=Branch(
                branch_type=branch_type,
                next_action=next_action,
                next_node_id=next_node_id,
                branch_reason=branch_reason,
                allowed_next_node_checked=True,
            ),
            state_delta=StateDelta(
                patience_delta=0 if success else -5,
                suspicion_delta=payload.understanding.risk_delta,
                retry_count_delta=0 if success else 1,
                hint_count_delta=0 if not needs_hint else 1,
            ),
            dialogue_directive=DialogueDirective(
                purpose="continue_to_next_question" if success else "support_retry",
                tone_hint="neutral",
                target_slot="stay_duration" if success else "visit_purpose",
                do_not_generate_npc_text=False,
            ),
            report_item=ReportItem(
                summary="Visit purpose was understood." if success else "Visit purpose needs retry.",
                improvement="Use a full sentence for a natural immigration answer.",
                example_answer=payload.node_context.recommended_expression,
                score_tags=["task_success_good"] if success else ["retry_needed"],
            ),
        )
