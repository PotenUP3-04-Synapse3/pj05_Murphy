from __future__ import annotations

from typing import Literal

from backend.app.schemas.game_turn import (
    Branch,
    DevBPolicyInput,
    DevBPolicyOutput,
    DialogueDirective,
    ErrorCapture,
    ErrorItem,
    Evaluation,
    InGameFeedback,
    LevelHint,
    OutGameFeedbackSeed,
    ReportItem,
    Scores,
    StateDelta,
)
from backend.app.services.service_b.level_adaptation_controller import (
    FeedbackStrategy,
    LevelAdaptationController,
)
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision, ScenarioStateMachine


class EnglishLevelHintAgent:
    def __init__(
        self,
        *,
        state_machine: ScenarioStateMachine | None = None,
        level_controller: LevelAdaptationController | None = None,
    ) -> None:
        self.state_machine = state_machine or ScenarioStateMachine()
        self.level_controller = level_controller or LevelAdaptationController()

    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        decision = self.state_machine.decide(payload)
        english_level = self.level_controller.english_level(payload)
        needs_hint, hint_level, hint_type, hint_kr = self.level_controller.hint_policy(payload, decision)
        feedback_strategy = self.level_controller.feedback_strategy(decision)
        has_form_issue = self.level_controller.has_form_issue(payload)

        return DevBPolicyOutput(
            contract_version="dev_b_policy.v1",
            node_id=payload.current_node_id,
            evaluation=self._build_evaluation(payload, decision, has_form_issue),
            level_hint=LevelHint(
                english_level=english_level,
                travel_speaking_level=payload.player_profile.travel_speaking_level,
                cefr_estimate=self.level_controller.cefr_estimate(english_level),
                needs_hint=needs_hint,
                hint_level=hint_level,
                hint_type=hint_type,
                hint_kr=hint_kr,
                example_en=payload.node_context.recommended_expression,
                avoid_expression=self._avoid_expression(payload),
                recommended_expression=payload.node_context.recommended_expression,
            ),
            in_game_feedback=self._build_in_game_feedback(payload, decision, feedback_strategy),
            error_capture=self._build_error_capture(payload, decision, has_form_issue),
            out_game_feedback_seed=self._build_out_game_feedback_seed(payload, decision, has_form_issue),
            branch=Branch(
                branch_type=decision.branch_type,
                next_action=decision.next_action,
                next_node_id=decision.next_node_id,
                branch_reason=decision.branch_reason,
                allowed_next_node_checked=True,
            ),
            state_delta=StateDelta(
                patience_delta=decision.patience_delta,
                suspicion_delta=decision.suspicion_delta,
                retry_count_delta=decision.retry_count_delta,
                hint_count_delta=decision.hint_count_delta,
            ),
            dialogue_directive=self._build_dialogue_directive(payload, decision),
            report_item=self._build_report_item(payload, decision, has_form_issue),
        )

    def _build_evaluation(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        has_form_issue: bool,
    ) -> Evaluation:
        score_task_success = 3 if decision.verdict == "SUCCESS" else 0
        if decision.verdict == "PARTIAL":
            score_task_success = 2

        clarity = 3 if decision.verdict == "SUCCESS" and not has_form_issue else 2
        if decision.verdict in {"UNCLEAR", "FAIL"}:
            clarity = 1
        if decision.verdict == "CRITICAL_FAIL":
            clarity = 0

        grammar = 1 if has_form_issue else 2
        if decision.verdict in {"UNCLEAR", "FAIL", "CRITICAL_FAIL"}:
            grammar = min(grammar, 1)

        feedback_tags = self._feedback_tags(payload, decision, has_form_issue)

        return Evaluation(
            verdict=decision.verdict,
            detected_intents=[payload.understanding.intent],
            required_intents_passed=decision.verdict == "SUCCESS",
            filled_slots=payload.understanding.extracted_slots,
            missing_slots=payload.understanding.missing_slots,
            scores=Scores(
                task_success=score_task_success,
                clarity=clarity,
                grammar=grammar,
                vocabulary=2 if decision.verdict != "CRITICAL_FAIL" else 0,
                problem_solving=2 if decision.verdict in {"SUCCESS", "PARTIAL"} else 1,
                politeness=3 if decision.verdict != "CRITICAL_FAIL" else 1,
            ),
            feedback_tags=feedback_tags,
            feedback_note=self._feedback_note(decision, has_form_issue),
        )

    def _build_in_game_feedback(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        feedback_strategy: FeedbackStrategy,
    ) -> InGameFeedback:
        is_success = decision.branch_type in {"success", "final"}
        is_warning = decision.branch_type in {"warning", "bad_end"}
        focus = self.level_controller.feedback_focus(payload)
        timing: Literal["during_dialogue_turn", "after_player_answer", "before_retry"] = (
            "during_dialogue_turn" if is_success else "before_retry"
        )

        return InGameFeedback(
            show=feedback_strategy != "none",
            feedback_strategy=feedback_strategy,
            timing=timing,
            priority=self.level_controller.feedback_priority(decision),
            purpose="warn_user" if is_warning else ("maintain_communication" if is_success else "restore_clarity"),
            focus=focus,
            npc_recast_line_candidate=self._recast_candidate(payload) if is_success else None,
            clarification_prompt_candidate=self._clarification_candidate(payload)
            if decision.branch_type == "clarify"
            else None,
            elicitation_cue_candidate=self._elicitation_candidate(payload) if decision.branch_type == "retry" else None,
            scaffolding_hint=payload.node_context.hint_policy.sentence_pattern
            if decision.branch_type == "hint"
            else None,
            recommended_expression=payload.node_context.recommended_expression,
            display_duration_ms=None,
            blocks_progression=not is_success,
        )

    def _build_error_capture(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        has_form_issue: bool,
    ) -> ErrorCapture:
        should_record = has_form_issue or decision.verdict in {"FAIL", "UNCLEAR", "CRITICAL_FAIL"}
        if not should_record:
            return ErrorCapture(
                should_record=False,
                storage_format="markdown",
                error_items=[],
                markdown_entry=None,
            )

        error_type = (
            "risk_expression"
            if decision.verdict == "CRITICAL_FAIL"
            else self._error_type(payload, has_form_issue)
        )
        severity = (
            "critical"
            if decision.verdict == "CRITICAL_FAIL"
            else ("moderate" if decision.verdict == "FAIL" else "minor")
        )
        focus_on_form_target = self._focus_on_form_target(payload, error_type)
        error_id = f"err_{payload.current_node_id.lower()}_{payload.turn_index:03d}"
        error_item = ErrorItem(
            error_id=error_id,
            node_id=payload.current_node_id,
            turn_index=payload.turn_index,
            npc_question=payload.node_context.npc_question,
            original_utterance=payload.player_text,
            intended_meaning_kr=payload.understanding.meaning_summary_kr,
            error_type=error_type,
            error_scope="global" if decision.verdict in {"FAIL", "UNCLEAR", "CRITICAL_FAIL"} else "local",
            focus_on_form_target=focus_on_form_target,
            suggested_expression=payload.node_context.recommended_expression,
            severity=severity,
            affected_scores=self._affected_scores(error_type),
            should_surface_in_game=decision.branch_type in {"clarify", "hint", "warning", "bad_end"},
            should_surface_out_game=True,
        )

        markdown_entry = "\n".join(
            [
                f"### {payload.current_node_id} - {error_id}",
                f"- Turn: {payload.turn_index}",
                f"- NPC Question: {payload.node_context.npc_question}",
                f"- Original: {payload.player_text}",
                f"- Intended Meaning: {payload.understanding.meaning_summary_kr}",
                f"- Error Type: {error_type}",
                f"- Error Scope: {error_item.error_scope}",
                f"- Focus on Form: {focus_on_form_target}",
                f"- Suggested: {payload.node_context.recommended_expression}",
                f"- Severity: {severity}",
            ]
        )
        return ErrorCapture(
            should_record=True,
            storage_format="markdown",
            error_items=[error_item],
            markdown_entry=markdown_entry,
        )

    def _build_out_game_feedback_seed(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        has_form_issue: bool,
    ) -> OutGameFeedbackSeed:
        should_include = has_form_issue or decision.verdict in {"FAIL", "UNCLEAR", "CRITICAL_FAIL"}
        if not should_include:
            return OutGameFeedbackSeed(
                include_in_final_report=False,
                openkb_query_tags=[],
                focus_on_form_targets=[],
                report_priority="low",
            )

        error_type = (
            "risk_expression"
            if decision.verdict == "CRITICAL_FAIL"
            else self._error_type(payload, has_form_issue)
        )
        focus_on_form_target = self._focus_on_form_target(payload, error_type)
        priority: Literal["low", "medium", "high"] = "high" if decision.verdict == "CRITICAL_FAIL" else "medium"
        return OutGameFeedbackSeed(
            include_in_final_report=True,
            openkb_query_tags=[focus_on_form_target, payload.node_context.npc_question_goal, "sentence_completion"],
            focus_on_form_targets=[focus_on_form_target],
            report_priority=priority,
        )

    def _build_dialogue_directive(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
    ) -> DialogueDirective:
        target_slot = payload.node_context.required_slots[0] if payload.node_context.required_slots else None
        if decision.branch_type in {"success", "final"}:
            purpose = "continue_to_next_question"
            tone_hint = "neutral_official"
        elif decision.branch_type in {"warning", "bad_end"}:
            purpose = "warn_and_control_risk"
            tone_hint = "firm_official"
        else:
            purpose = "support_retry"
            tone_hint = "brief_supportive"

        return DialogueDirective(
            purpose=purpose,
            tone_hint=tone_hint,
            target_slot=target_slot,
            do_not_generate_npc_text=True,
        )

    def _build_report_item(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        has_form_issue: bool,
    ) -> ReportItem:
        if decision.verdict == "SUCCESS":
            summary = "The required immigration answer was understood."
            improvement = (
                "Use a complete sentence for a more natural answer."
                if has_form_issue
                else "Keep answering with concise, clear travel details."
            )
            score_tags = ["task_success_good"]
        elif decision.verdict == "CRITICAL_FAIL":
            summary = "The answer raised immigration risk."
            improvement = "Avoid expressions that imply illegal work, overstay, unknown items, or unsafe intent."
            score_tags = ["risk_expression", "critical_fail"]
        else:
            summary = "The answer needs another attempt."
            improvement = "Answer the officer's exact question with the recommended pattern."
            score_tags = ["retry_needed"]

        if has_form_issue:
            score_tags.append("form_issue")

        return ReportItem(
            summary=summary,
            improvement=improvement,
            example_answer=payload.node_context.recommended_expression,
            score_tags=score_tags,
        )

    def _feedback_tags(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        has_form_issue: bool,
    ) -> list[str]:
        tags: list[str] = []
        if decision.verdict == "SUCCESS":
            tags.extend(["intent_matched", "required_slot_filled"])
        if payload.understanding.missing_slots:
            tags.append("missing_required_slot")
        if has_form_issue:
            tags.append("minor_form_issue")
        if decision.branch_type == "hint":
            tags.append("hint_recommended")
        if decision.verdict == "CRITICAL_FAIL":
            tags.extend(["risk_expression", "critical_fail"])
        if not tags:
            tags.append("needs_retry")
        return tags

    def _feedback_note(self, decision: ScenarioDecision, has_form_issue: bool) -> str:
        if decision.verdict == "SUCCESS" and has_form_issue:
            return "Meaning was clear, but the answer can be more complete."
        if decision.verdict == "SUCCESS":
            return "Required intent and slot were understood."
        if decision.verdict == "CRITICAL_FAIL":
            return "Risk expression requires warning or fail-end handling."
        return "The player needs support to answer the current question."

    def _avoid_expression(self, payload: DevBPolicyInput) -> str | None:
        if payload.node_context.risk_keywords:
            return payload.node_context.risk_keywords[0]
        return None

    def _recast_candidate(self, payload: DevBPolicyInput) -> str:
        return payload.node_context.recommended_expression

    def _clarification_candidate(self, payload: DevBPolicyInput) -> str:
        if payload.node_context.allowed_slot_values:
            slot = next(iter(payload.node_context.allowed_slot_values))
            values = payload.node_context.allowed_slot_values[slot][:3]
            return f"Can you clarify {slot}: {', '.join(values)}?"
        return "Can you clarify your answer?"

    def _elicitation_candidate(self, payload: DevBPolicyInput) -> str:
        return f"Try: {payload.node_context.hint_policy.sentence_pattern}"

    def _error_type(self, payload: DevBPolicyInput, has_form_issue: bool) -> str:
        if has_form_issue:
            return "grammar"
        if payload.understanding.missing_slots:
            return "task_response"
        return "clarity"

    def _focus_on_form_target(self, payload: DevBPolicyInput, error_type: str) -> str:
        if error_type == "grammar":
            return "sentence_completion"
        if error_type == "risk_expression":
            return f"{payload.current_node_id.lower()}_risk_expression"
        if payload.node_context.required_slots:
            return f"{payload.node_context.required_slots[0]}_answer_pattern"
        return "clarity_repair"

    def _affected_scores(self, error_type: str) -> list[str]:
        if error_type == "grammar":
            return ["grammar", "clarity"]
        if error_type == "risk_expression":
            return ["problem_solving", "politeness"]
        if error_type == "task_response":
            return ["task_success", "clarity"]
        return ["clarity"]
