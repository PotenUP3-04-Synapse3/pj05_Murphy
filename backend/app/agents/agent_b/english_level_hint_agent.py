from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal, Protocol

from backend.app.schemas.game_turn import (
    Branch,
    DevBPolicyInput,
    DevBPolicyOutput,
    DialogueDirective,
    DialogueSeed,
    ErrorCapture,
    ErrorItem,
    Evaluation,
    InGameFeedback,
    LevelHint,
    NpcEmotion,
    OpenKBWriteResult,
    OutGameFeedbackSeed,
    ReportSeedCategoryScores,
    ReportSeedCorrectedExample,
    ReportSeedCriticalBreakdown,
    ReportSeedStrength,
    ReportSeedSummary,
    ReportItem,
    Scores,
    StateDelta,
)
from backend.app.services.service_b.level_adaptation_controller import (
    FeedbackStrategy,
    LevelAdaptationController,
)
from backend.app.services.service_b.feedback_hint_generator import FeedbackHintGenerator
from backend.app.services.service_b.developer_b_agent_run_logger import DeveloperBAgentRunLogger
from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision, ScenarioStateMachine
from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyController


class OpenKBPolicyWriter(Protocol):
    def write_policy_output(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> OpenKBWriteResult: ...

    def failure_result(self, error: Exception) -> OpenKBWriteResult: ...


class EnglishLevelHintAgent:
    def __init__(
        self,
        *,
        state_machine: ScenarioStateMachine | None = None,
        level_controller: LevelAdaptationController | None = None,
        tier_controller: TierDifficultyController | None = None,
        feedback_generator: FeedbackHintGenerator | None = None,
        openkb_writer: OpenKBPolicyWriter | None = None,
        agent_run_root: Path | None = None,
        agent_run_logger: DeveloperBAgentRunLogger | None = None,
    ) -> None:
        self.state_machine = state_machine or ScenarioStateMachine()
        self.level_controller = level_controller or LevelAdaptationController()
        self.tier_controller = tier_controller or TierDifficultyController()
        self.feedback_generator = feedback_generator or FeedbackHintGenerator()
        self.openkb_writer = openkb_writer or OpenKBFeedbackWriter()
        self.agent_run_logger = agent_run_logger or DeveloperBAgentRunLogger(agent_run_root)

    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        agent_run = self.agent_run_logger.start_run(payload)
        input_summary = _policy_input_summary(payload)
        self.agent_run_logger.record_event(
            agent_run,
            event="agent_start",
            status="started",
            data_loaded=input_summary,
        )
        self.agent_run_logger.record_data_flow(
            agent_run,
            from_node="dev_b_policy_input",
            to_node="scenario_state_machine",
            payload_summary=input_summary,
        )

        try:
            decision = self.state_machine.decide(payload)
            self.agent_run_logger.record_event(
                agent_run,
                event="tool_call",
                status="completed",
                tool_name="scenario_state_machine.decide",
                input_summary=input_summary,
                output_summary=_decision_summary(decision),
            )

            english_level = self.level_controller.english_level(payload)
            self.agent_run_logger.record_event(
                agent_run,
                event="tool_call",
                status="completed",
                tool_name="level_adaptation_controller.english_level",
                output_summary={"english_level": english_level},
            )

            needs_hint, hint_level, hint_type, hint_kr = self.level_controller.hint_policy(payload, decision)
            self.agent_run_logger.record_event(
                agent_run,
                event="tool_call",
                status="completed",
                tool_name="level_adaptation_controller.hint_policy",
                output_summary={
                    "needs_hint": needs_hint,
                    "hint_level": hint_level,
                    "hint_type": hint_type,
                },
            )

            feedback_strategy = self.level_controller.feedback_strategy(decision)
            self.agent_run_logger.record_event(
                agent_run,
                event="tool_call",
                status="completed",
                tool_name="level_adaptation_controller.feedback_strategy",
                output_summary={"feedback_strategy": feedback_strategy},
            )

            has_form_issue = self.level_controller.has_form_issue(payload)
            self.agent_run_logger.record_event(
                agent_run,
                event="tool_call",
                status="completed",
                tool_name="level_adaptation_controller.has_form_issue",
                output_summary={"has_form_issue": has_form_issue},
            )

            tier_result = self.tier_controller.evaluate(payload, decision, has_form_issue=has_form_issue)
            self.agent_run_logger.record_event(
                agent_run,
                event="tool_call",
                status="completed",
                tool_name="tier_difficulty_controller.evaluate",
                output_summary={
                    "rubric_total": tier_result.rubric_scores.total,
                    "travel_speaking_level": tier_result.difficulty_profile.travel_speaking_level,
                },
            )

            output = DevBPolicyOutput(
                contract_version="dev_b_policy.v1",
                node_id=payload.current_node_id,
                npc_emotion=self._build_npc_emotion(payload, decision),
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
                rubric_scores=tier_result.rubric_scores,
                difficulty_profile=tier_result.difficulty_profile,
            )
            feedback_generation = self.feedback_generator.generate(
                payload=payload,
                decision=decision,
                base_output=output,
                tier_result=tier_result,
                focus_on_form_explanation_kr=self._focus_on_form_explanation(payload, output),
            )
            self.agent_run_logger.record_event(
                agent_run,
                event="tool_call",
                status="completed",
                tool_name="feedback_hint_generator.generate",
                output_summary=_feedback_generation_summary(feedback_generation),
            )
            if feedback_generation.rubric_scores is not None:
                tier_result = self.tier_controller.from_rubric_scores(
                    feedback_generation.rubric_scores,
                    tier=payload.player_profile.tier,
                )
            output = output.model_copy(
                update={
                    "evaluation": output.evaluation.model_copy(
                        update={"feedback_note": feedback_generation.feedback_note}
                    ),
                    "level_hint": output.level_hint.model_copy(update={"hint_kr": feedback_generation.hint_kr}),
                    "report_item": output.report_item.model_copy(
                        update={
                            "summary": feedback_generation.report_summary,
                            "improvement": feedback_generation.report_improvement,
                            "example_answer": feedback_generation.example_answer,
                        }
                    ),
                    "rubric_scores": tier_result.rubric_scores,
                    "difficulty_profile": tier_result.difficulty_profile,
                    "feedback_generation": feedback_generation.trace,
                }
            )
            output = output.model_copy(
                update={
                    "report_seed_summary": self._build_report_seed_summary(payload, output),
                    "dialogue_seed": self._build_dialogue_seed(payload, output),
                }
            )
            _validate_b_policy_output(payload, output)
            try:
                openkb_write = self.openkb_writer.write_policy_output(payload, output)
            except Exception as exc:
                openkb_write = self.openkb_writer.failure_result(exc)
            openkb_status = "completed" if openkb_write.succeeded else "failed"
            self.agent_run_logger.record_event(
                agent_run,
                event="tool_call",
                status=openkb_status,
                tool_name="openkb_feedback_writer.write_policy_output",
                output_summary=_openkb_write_summary(openkb_write),
            )

            output = output.model_copy(update={"openkb_write": openkb_write})
            output_summary = _policy_output_summary(output)
            self.agent_run_logger.record_data_flow(
                agent_run,
                from_node="openkb_feedback_writer",
                to_node="dev_b_policy_output",
                payload_summary=output_summary,
            )
            self.agent_run_logger.record_event(
                agent_run,
                event="agent_end",
                status="completed",
                output_summary=output_summary,
            )
            self.agent_run_logger.complete_and_append(
                agent_run,
                status="completed",
                summary={
                    "input": input_summary,
                    "output": output_summary,
                    "fallback_used": _feedback_fallback_used(output),
                    "audio_url": None,
                },
                model_name=_model_name(output),
            )
            return output
        except Exception as exc:
            error_summary = {"error": str(exc), "error_type": exc.__class__.__name__}
            self.agent_run_logger.record_event(
                agent_run,
                event="agent_end",
                status="failed",
                error=str(exc),
            )
            self.agent_run_logger.fail_and_append(
                agent_run,
                error=exc,
                summary={
                    "input": input_summary,
                    "output": error_summary,
                    "fallback_used": False,
                    "audio_url": None,
                },
            )
            raise

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
        if payload.current_node_id.startswith("FLIGHT_"):
            return OutGameFeedbackSeed(
                include_in_final_report=True,
                openkb_query_tags=[
                    "smalltalk_response_clarity",
                    "diagnostic_level_sample",
                    "deferred_out_game_feedback",
                ],
                focus_on_form_targets=["smalltalk_response_clarity"],
                report_priority="low",
            )

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

    def _build_report_seed_summary(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> ReportSeedSummary:
        category_scores = ReportSeedCategoryScores(
            task_success=_score_candidate(output.evaluation.scores.task_success),
            clarity=_score_candidate(output.evaluation.scores.clarity),
            grammar=_score_candidate(output.evaluation.scores.grammar),
            vocabulary=_score_candidate(output.evaluation.scores.vocabulary),
            politeness=_score_candidate(output.evaluation.scores.politeness),
            problem_solving=_score_candidate(output.evaluation.scores.problem_solving),
        )
        category_values = [
            category_scores.task_success,
            category_scores.clarity,
            category_scores.grammar,
            category_scores.vocabulary,
            category_scores.politeness,
            category_scores.problem_solving,
        ]
        return ReportSeedSummary(
            estimated_level=output.level_hint.english_level,
            tier=payload.player_profile.tier,
            scenario_result=self._scenario_result_candidate(output),
            overall_score_candidate=_average_score_candidate(category_values),
            category_scores=category_scores,
            strengths=self._report_seed_strengths(payload, output),
            critical_breakdowns=self._report_seed_critical_breakdowns(payload, output),
            corrected_examples=self._report_seed_corrected_examples(payload, output),
            reusable_sentence_patterns=_unique_non_empty(
                [
                    payload.node_context.hint_policy.sentence_pattern,
                    payload.node_context.recommended_expression,
                ]
            ),
            next_practice_goal=output.report_item.improvement,
            feedback_focus=_unique_non_empty(
                [
                    output.in_game_feedback.focus,
                    *output.out_game_feedback_seed.focus_on_form_targets,
                    *output.evaluation.feedback_tags,
                ]
            ),
            ui_priority_order=[
                "scenario_result",
                "overall_score_candidate",
                "category_scores",
                "strengths",
                "critical_breakdowns",
                "corrected_examples",
                "next_practice_goal",
            ],
            display_policy_by_tier={
                "Bronze": "show simple correction and reusable sentence patterns first",
                "Silver": "show correction, reason, and one grammar explanation",
                "Gold": "show naturalness, politeness, and contextual nuance",
            },
        )

    def _report_seed_strengths(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> list[ReportSeedStrength]:
        strengths: list[ReportSeedStrength] = []
        if output.evaluation.verdict in {"SUCCESS", "PARTIAL"}:
            strengths.append(
                ReportSeedStrength(
                    title="Core answer understood",
                    evidence=output.report_item.summary,
                    ui_priority=1,
                )
            )
        if output.evaluation.filled_slots:
            strengths.append(
                ReportSeedStrength(
                    title="Required information provided",
                    evidence=", ".join(sorted(output.evaluation.filled_slots)),
                    ui_priority=len(strengths) + 1,
                )
            )
        if not strengths:
            strengths.append(
                ReportSeedStrength(
                    title="Retry target identified",
                    evidence=payload.node_context.npc_question_goal,
                    ui_priority=1,
                )
            )
        return strengths[:3]

    def _report_seed_critical_breakdowns(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> list[ReportSeedCriticalBreakdown]:
        breakdowns: list[ReportSeedCriticalBreakdown] = []
        for index, item in enumerate(output.error_capture.error_items[:3], start=1):
            issue_type = _report_issue_type(item.error_type)
            breakdowns.append(
                ReportSeedCriticalBreakdown(
                    user_utterance=item.original_utterance,
                    issue_type=issue_type,
                    why_it_matters=_why_issue_matters(issue_type),
                    better_version=item.suggested_expression,
                    reusable_pattern=payload.node_context.hint_policy.sentence_pattern,
                    ui_priority=index,
                )
            )
        return breakdowns

    def _report_seed_corrected_examples(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> list[ReportSeedCorrectedExample]:
        examples: list[ReportSeedCorrectedExample] = []
        for item in output.error_capture.error_items[:3]:
            examples.append(
                ReportSeedCorrectedExample(
                    original=item.original_utterance,
                    corrected=item.suggested_expression,
                    brief_explanation=output.report_item.improvement,
                    pattern=payload.node_context.hint_policy.sentence_pattern,
                )
            )
        return examples

    def _scenario_result_candidate(
        self,
        output: DevBPolicyOutput,
    ) -> Literal["passed", "conditional_pass", "failed"]:
        if output.evaluation.verdict == "CRITICAL_FAIL" or output.branch.branch_type == "bad_end":
            return "failed"
        if output.evaluation.verdict == "SUCCESS":
            return "passed"
        return "conditional_pass"

    def _build_dialogue_seed(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> DialogueSeed:
        return DialogueSeed(
            scene=payload.scene_id,
            npc_role=self._npc_role(payload),
            surface_goal=payload.node_context.npc_question_goal,
            hidden_assessment_goal="estimate_user_travel_speaking_level",
            opening_intent=self._opening_intent(payload),
            assessment_targets=_unique_non_empty(
                [
                    *payload.node_context.required_intents,
                    *payload.node_context.required_slots,
                    *payload.node_context.critical_slots,
                ]
            ),
            required_slots=payload.node_context.required_slots,
            max_turns=5 if payload.current_node_id.startswith("FLIGHT_") else 4,
            difficulty_profile="auto",
            feedback_focus=_unique_non_empty(
                [
                    output.in_game_feedback.focus,
                    *payload.node_context.required_slots,
                    *output.out_game_feedback_seed.focus_on_form_targets,
                ]
            ),
            tone_guidance=output.dialogue_directive.tone_hint if output.dialogue_directive else "neutral",
            allowed_followup_intents=self._allowed_followup_intents(payload, output),
            stop_condition=(
                "enough_evidence_for_level_estimation"
                if payload.current_node_id.startswith("FLIGHT_")
                else "required_slots_filled_or_retry_policy_triggered"
            ),
        )

    def _npc_role(self, payload: DevBPolicyInput) -> str:
        if payload.current_node_id.startswith("FLIGHT_"):
            return "seatmate_passenger"
        if payload.current_node_id.startswith("BAG_"):
            return "baggage_service_agent"
        return "immigration_officer"

    def _opening_intent(self, payload: DevBPolicyInput) -> str:
        if payload.node_context.required_slots:
            return f"ask_{payload.node_context.required_slots[0]}"
        if payload.node_context.required_intents:
            return payload.node_context.required_intents[0]
        return payload.node_context.npc_question_goal

    def _allowed_followup_intents(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> list[str]:
        intents = [f"ask_{slot}" for slot in payload.node_context.required_slots]
        if output.branch.branch_type in {"success", "final"}:
            intents.extend(["advance_to_next_prompt", "offer_reassurance"])
        elif output.branch.branch_type == "clarify":
            intents.append("ask_clarification")
        elif output.branch.branch_type in {"warning", "bad_end"}:
            intents.append("warn_about_risk")
        else:
            intents.extend(["prompt_retry", "offer_reassurance"])
        return _unique_non_empty(intents)

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

    def _build_npc_emotion(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
    ) -> NpcEmotion:
        if decision.verdict == "CRITICAL_FAIL" or decision.branch_type in {"warning", "bad_end"}:
            return "Suspicion"
        if decision.branch_type in {"clarify", "retry", "hint"} or payload.understanding.needs_clarification:
            return "Confusion"
        return "Nomal"

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
        if payload.current_node_id.startswith("FLIGHT_"):
            return "smalltalk_response_clarity"
        if error_type == "risk_expression":
            return f"{payload.current_node_id.lower()}_risk_expression"
        if payload.current_node_id.startswith("BAG_"):
            node_target = _immigration_focus_target(payload.current_node_id)
            if node_target:
                return node_target
        if error_type == "grammar":
            return "sentence_completion"
        node_target = _immigration_focus_target(payload.current_node_id)
        if node_target:
            return node_target
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

    def _focus_on_form_explanation(self, payload: DevBPolicyInput, output: DevBPolicyOutput) -> str:
        targets = output.out_game_feedback_seed.focus_on_form_targets
        if targets:
            return f"Focus on {', '.join(targets)} using: {payload.node_context.recommended_expression}"
        return f"Use a concise immigration answer such as: {payload.node_context.recommended_expression}"


def _policy_input_summary(payload: DevBPolicyInput) -> dict[str, Any]:
    return {
        "request_id": payload.request_id,
        "session_id": payload.session_id,
        "turn_index": payload.turn_index,
        "node_id": payload.current_node_id,
        "player_text_preview": _preview(payload.player_text),
        "tier": payload.player_profile.tier,
        "travel_speaking_level": payload.player_profile.travel_speaking_level,
        "retry_count": payload.scenario_state.retry_count,
        "suspicion": payload.scenario_state.suspicion,
    }


def _score_candidate(score: int) -> int:
    return max(0, min(100, round(score / 3 * 100)))


def _average_score_candidate(scores: list[int]) -> int:
    if not scores:
        return 0
    return round(sum(scores) / len(scores))


def _unique_non_empty(values: Iterable[str | None]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique_values.append(text)
    return unique_values


def _report_issue_type(
    error_type: str,
) -> Literal["grammar", "clarity", "vocabulary", "task", "politeness", "problem_solving"]:
    if error_type == "grammar":
        return "grammar"
    if error_type == "vocabulary":
        return "vocabulary"
    if error_type == "politeness":
        return "politeness"
    if error_type == "problem_solving":
        return "problem_solving"
    if error_type == "clarity":
        return "clarity"
    if error_type == "task_response":
        return "task"
    if error_type == "risk_expression":
        return "problem_solving"
    return "clarity"


def _why_issue_matters(
    issue_type: Literal["grammar", "clarity", "vocabulary", "task", "politeness", "problem_solving"],
) -> str:
    if issue_type == "task":
        return "The required travel detail may be missing or hard to verify."
    if issue_type == "problem_solving":
        return "This can change how the travel situation is judged."
    if issue_type == "politeness":
        return "Polite, direct wording helps keep the official interaction stable."
    return "A clearer complete sentence helps the listener understand the travel answer quickly."


def _decision_summary(decision: ScenarioDecision) -> dict[str, Any]:
    return {
        "verdict": decision.verdict,
        "branch_type": decision.branch_type,
        "next_action": decision.next_action,
        "next_node_id": decision.next_node_id,
        "patience_delta": decision.patience_delta,
        "suspicion_delta": decision.suspicion_delta,
        "retry_count_delta": decision.retry_count_delta,
        "hint_count_delta": decision.hint_count_delta,
    }


def _feedback_generation_summary(feedback_generation: Any) -> dict[str, Any]:
    trace = feedback_generation.trace
    summary = {
        "mode": trace.mode,
        "model": trace.model,
        "used_llm": trace.used_llm,
        "fallback_reason": trace.fallback_reason,
    }
    if getattr(feedback_generation, "llm_usage", None):
        summary["llm_usage"] = feedback_generation.llm_usage
    return summary


def _openkb_write_summary(openkb_write: OpenKBWriteResult) -> dict[str, Any]:
    return {
        "attempted": openkb_write.attempted,
        "succeeded": openkb_write.succeeded,
        "namespace": openkb_write.namespace,
        "record_id": openkb_write.record_id,
        "jsonl_path": openkb_write.jsonl_path,
        "markdown_path": openkb_write.markdown_path,
        "error_message": openkb_write.error_message,
    }


def _policy_output_summary(output: DevBPolicyOutput) -> dict[str, Any]:
    return {
        "verdict": output.evaluation.verdict,
        "branch_type": output.branch.branch_type,
        "next_action": output.branch.next_action,
        "next_node_id": output.branch.next_node_id,
        "npc_emotion": output.npc_emotion,
        "needs_hint": output.level_hint.needs_hint,
        "hint_type": output.level_hint.hint_type,
        "feedback_strategy": output.in_game_feedback.feedback_strategy,
        "state_delta": output.state_delta.model_dump(),
        "openkb_write_succeeded": output.openkb_write.succeeded if output.openkb_write else None,
        "feedback_generation_mode": output.feedback_generation.mode if output.feedback_generation else None,
    }


def _feedback_fallback_used(output: DevBPolicyOutput) -> bool:
    return bool(output.feedback_generation and output.feedback_generation.mode == "fallback")


def _model_name(output: DevBPolicyOutput) -> str:
    if output.feedback_generation and output.feedback_generation.model:
        return output.feedback_generation.model
    return "rule_based"


def _preview(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _validate_b_policy_output(payload: DevBPolicyInput, output: DevBPolicyOutput) -> None:
    if output.node_id != payload.current_node_id:
        raise ValueError("DevBPolicyOutput.node_id must match input current_node_id")
    if output.branch.next_node_id not in payload.node_context.allowed_next_nodes:
        raise ValueError("DevB branch.next_node_id is outside node_context.allowed_next_nodes")
    if payload.client_allowed_next_nodes and output.branch.next_node_id not in payload.client_allowed_next_nodes:
        raise ValueError("DevB branch.next_node_id is outside client_allowed_next_nodes")
    if not output.level_hint.needs_hint and (
        output.level_hint.hint_type is not None or output.level_hint.hint_kr is not None
    ):
        raise ValueError("DevB hint payload must be empty when needs_hint is false")
    if output.in_game_feedback.feedback_strategy == "recast" and not output.in_game_feedback.npc_recast_line_candidate:
        raise ValueError("DevB recast feedback requires npc_recast_line_candidate")
    if (
        output.in_game_feedback.feedback_strategy == "clarification_request"
        and not output.in_game_feedback.clarification_prompt_candidate
    ):
        raise ValueError("DevB clarification feedback requires clarification_prompt_candidate")
    if output.error_capture.should_record is False and (
        output.error_capture.error_items or output.error_capture.markdown_entry is not None
    ):
        raise ValueError("DevB error capture must be empty when should_record is false")
    if output.out_game_feedback_seed.include_in_final_report and not output.out_game_feedback_seed.focus_on_form_targets:
        raise ValueError("DevB final-report seed requires focus_on_form_targets")
    if output.rubric_scores is not None and not 0 <= output.rubric_scores.total <= 12:
        raise ValueError("DevB rubric_scores.total must be between 0 and 12")


def _immigration_focus_target(node_id: str) -> str | None:
    return {
        "IMM_002_PURPOSE": "purpose_statement",
        "IMM_003_DURATION": "duration_statement",
        "IMM_004_STAY_LOCATION": "stay_location_statement",
        "IMM_005_RETURN_TICKET": "return_ticket_statement",
        "IMM_006_DECLARATION_CHECK": "declaration_explanation",
        "IMM_006B_PACKED_BAG_CHECK": "bag_content_explanation",
        "IMM_ALPHA_GOLD_BAG_CONTENT_CHECK": "bag_content_explanation",
        "BAG_001_REPORT_MISSING_AT_DESK": "problem_statement",
        "BAG_002_PROVIDE_CLAIM_TAG": "flight_or_tag_statement",
        "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM": "customs_item_explanation",
        "BAG_007_CUSTOMS_CLEARANCE": "follow_up_question",
    }.get(node_id)
