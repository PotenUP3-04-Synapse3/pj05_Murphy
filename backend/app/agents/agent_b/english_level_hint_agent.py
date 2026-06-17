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
from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import FlightSmallTalkDiagnosticPolicy


class OpenKBPolicyWriter(Protocol):
    """
    OpenKB 데이터베이스에 Developer B의 평가 결과 및 피드백 로그를 기록하기 위한 쓰기 어댑터의 공통 규격(Protocol)입니다.
    """
    def write_policy_output(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> OpenKBWriteResult:
        """
        주어진 입력 데이터와 도출된 정책 출력 결과를 바탕으로 OpenKB에 레코드를 기록합니다.
        """
        ...

    def failure_result(self, error: Exception) -> OpenKBWriteResult:
        """
        기록 과정 중 에러가 발생했을 때, 에러 정보를 담은 OpenKBWriteResult 객체를 반환합니다.
        """
        ...


class _EnglishLevelHintPolicyCore:
    """
    절차적 코드 실행 방식으로 구현된 영어 레벨 판정 및 시나리오 진행 핵심 정책 로직 클래스입니다.
    
    초보자 가이드: 이 클래스는 상태 그래프(LangGraph)가 도입되기 전에 사용되던 절차적(Procedural) 파이프라인의 원본 로직을 갖고 있습니다.
    현재는 디버깅 혹은 상태 그래프 비사용 모드에서 연계 동작의 참조용으로 유지되거나 상속되어 사용됩니다.
    """
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
        """
        의존성 컴포넌트들을 주입받아 핵심 정책 로직 클래스를 초기화합니다.
        """
        self.state_machine = state_machine or ScenarioStateMachine()
        self.level_controller = level_controller or LevelAdaptationController()
        self.tier_controller = tier_controller or TierDifficultyController()
        self.feedback_generator = feedback_generator or FeedbackHintGenerator()
        self.openkb_writer = openkb_writer or OpenKBFeedbackWriter()
        self.agent_run_logger = agent_run_logger or DeveloperBAgentRunLogger(agent_run_root)

    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        """
        단일 대화 턴(Turn)을 평가하여 시나리오 상의 판단, 힌트 필요 여부, 피드백 가이드라인 및 성적 결과를 도출합니다.
        
        Args:
            payload: 학습자 입력(텍스트), 시나리오 상태, 사용자 프로필 등을 포함하는 DevBPolicyInput 데이터 객체
            
        Returns:
            레벨 판정, 피드백 텍스트, 분기 판단 등이 종합된 DevBPolicyOutput 데이터 객체
        """
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
            is_flight_smalltalk = (payload.scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK" or payload.current_node_id.startswith("FLIGHT_"))
            if is_flight_smalltalk:
                diagnostic_policy = FlightSmallTalkDiagnosticPolicy()
                decision = diagnostic_policy.decide_conversational(payload)
                tool_name = "flight_smalltalk_diagnostic_policy.decide_conversational"
            else:
                decision = self.state_machine.decide(payload)
                tool_name = "scenario_state_machine.decide"

            self.agent_run_logger.record_event(
                agent_run,
                event="tool_call",
                status="completed",
                tool_name=tool_name,
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
                    cumulative_confidence=decision.cumulative_confidence if hasattr(decision, "cumulative_confidence") else None,
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
                    "dialogue_seed": self._build_dialogue_seed(payload, output, decision=decision),
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
        """
        이해도 결과(Intent/Slot 매칭 정보)와 문법적 어색함 유무(Form Issue)를 종합해 
        학습자의 대화 턴을 채점 및 다각도 평가(Scores)하고 Evaluation 객체를 반환합니다.
        """
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
        """
        인게임 화면에 실시간으로 표시될 피드백 데이터를 정의합니다.
        대화 흐름의 합격 여부에 맞춰 재진술(Recast), 명료화 요구(Clarification), 힌트(Scaffolding) 등의 후보를 선택합니다.
        """
        is_flight_smalltalk = (payload.scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK" or payload.current_node_id.startswith("FLIGHT_"))
        if is_flight_smalltalk:
            return InGameFeedback(
                show=False,
                feedback_strategy="none",
                timing="during_dialogue_turn",
                priority="low",
                purpose="maintain_communication",
                focus="smalltalk_response_clarity",
                npc_recast_line_candidate=None,
                clarification_prompt_candidate=None,
                elicitation_cue_candidate=None,
                scaffolding_hint=None,
                recommended_expression=payload.node_context.recommended_expression,
                display_duration_ms=None,
                blocks_progression=False,
            )

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
        """
        발생한 언어적 오류(문법 결함, 오답, 리스크 표현 등)의 세부 정보를 감지하고 
        오류 마크다운 텍스트와 개별 에러 아이템들을 포함한 ErrorCapture 데이터를 구성합니다.
        """
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
            should_surface_in_game=False if (payload.scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK" or payload.current_node_id.startswith("FLIGHT_")) else (decision.branch_type in {"clarify", "hint", "warning", "bad_end"}),
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
        """
        게임 종료 후 분석 리포트(Focus-on-Form 카드)를 생성할 때 활용할 
        태그(focus_on_form_targets) 및 리포트 중요도 가이드를 정의하여 씨앗(Seed) 데이터로 빌드합니다.
        """
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
        """
        이번 턴의 평가 성적, 강점, 오류 분석 및 교정 사례 등을 요약하여 
        최종 리포트 작성을 위한 ReportSeedSummary 객체를 구성합니다.
        """
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
        """
        플레이어가 이번 대화에서 잘했던 강점 항목(예: 필요한 정보 제공 등)을 최대 3개까지 선정하여 리스트로 반환합니다.
        """
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
        """
        발생한 형태적 결함이나 오류(Error Capture)들을 리포트에 기술할 수 있는 상세 오류 항목으로 변환하여 반환합니다.
        """
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
        """
        학습자가 낸 오답 문장과 교정된 올바른 표현 예시를 짝지어 리포트용 추천 리스트로 구성합니다.
        """
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
        """
        이번 턴의 평가 상태를 바탕으로 최종 통과 여부 후보군('passed', 'conditional_pass', 'failed') 중 하나를 매핑합니다.
        """
        if output.evaluation.verdict == "CRITICAL_FAIL" or output.branch.branch_type == "bad_end":
            return "failed"
        if output.evaluation.verdict == "SUCCESS":
            return "passed"
        return "conditional_pass"

    def _build_dialogue_seed(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
        decision: ScenarioDecision | None = None,
    ) -> DialogueSeed:
        """
        NPC Dialogue Agent가 다음 발화를 생성하거나 가이드를 잡을 때 필요한 
        대화 연동용 씨앗(DialogueSeed) 메타데이터 객체를 구성합니다.
        """
        is_flight_smalltalk = (payload.scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK" or payload.current_node_id.startswith("FLIGHT_"))
        surface_goal = payload.node_context.npc_question_goal
        cumulative_confidence = None
        if is_flight_smalltalk and decision and hasattr(decision, "selected_probe") and decision.selected_probe:
            probe = decision.selected_probe
            surface_goal = f"{probe['target_competency']}_{probe['topic_tag']}"
            cumulative_confidence = decision.cumulative_confidence

        return DialogueSeed(
            scene=payload.scene_id,
            npc_role=self._npc_role(payload),
            surface_goal=surface_goal,
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
            cumulative_confidence=cumulative_confidence,
        )

    def _npc_role(self, payload: DevBPolicyInput) -> str:
        """
        노드 ID 접두사를 확인하여 현재 질문을 하는 심 심사관이나 직원 NPC의 역할군 명칭을 구합니다.
        """
        if payload.current_node_id.startswith("FLIGHT_"):
            return "seatmate_passenger"
        if payload.current_node_id.startswith("BAG_"):
            return "baggage_service_agent"
        return "immigration_officer"

    def _opening_intent(self, payload: DevBPolicyInput) -> str:
        """
        다음 질문 대화를 이어갈 때 NPC가 먼저 열어야 할 의도(Intent)를 반환합니다.
        """
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
        """
        다음 대화 턴에서 플레이어가 취할 수 있는 허용된 후속 대화 의도(Intent) 목록을 제공합니다.
        """
        is_flight_smalltalk = (payload.scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK" or payload.current_node_id.startswith("FLIGHT_"))
        if is_flight_smalltalk:
            return ["acknowledge", "self_disclosure", "ask_question", "smalltalk_rapport", "advance_to_next_prompt"]

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
        """
        NPC가 대답할 때 어떤 어조와 목적을 따라야 하는지 지침을 담은 DialogueDirective 객체를 빌드합니다.
        """
        target_slot = payload.node_context.required_slots[0] if payload.node_context.required_slots else None
        is_flight_smalltalk = (payload.scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK" or payload.current_node_id.startswith("FLIGHT_"))
        if is_flight_smalltalk:
            topic_switch = False
            if hasattr(decision, "selected_probe") and decision.selected_probe:
                from backend.app.services.service_b.final_result_score_policy import OpenKBFinalResultRecordReader
                import json
                reader = OpenKBFinalResultRecordReader(runtime_root=getattr(self.openkb_writer, "runtime_root", None))
                records = reader.read_session_records(payload.session_id)
                flight_records = [r for r in records if str(r.get("node_id", "")).startswith("FLIGHT_")]
                if flight_records:
                    last_record = flight_records[-1]
                    dseed = last_record.get("dialogue_seed")
                    if dseed and isinstance(dseed, dict):
                        last_goal = dseed.get("surface_goal", "")
                        last_topic = "travel"
                        probes_path = Path("backend/app/data/flight_smalltalk_probes.json")
                        if probes_path.exists():
                            try:
                                probes = json.loads(probes_path.read_text(encoding="utf-8"))
                                for p in probes:
                                    if p["probe_id"] == last_goal or f"{p['target_competency']}_{p['topic_tag']}" == last_goal:
                                        last_topic = p["topic_tag"]
                                        break
                            except Exception:
                                pass
                        if last_topic != decision.selected_probe["topic_tag"]:
                            topic_switch = True

            player_len = len(payload.player_text.split())
            if player_len <= 3:
                length_target = 8
            elif player_len <= 5:
                length_target = 10
            else:
                length_target = 12

            return DialogueDirective(
                purpose="smalltalk_diagnostic",
                tone_hint="neutral_passenger",
                target_slot=target_slot,
                do_not_generate_npc_text=False,
                topic_switch=topic_switch,
                length_target=length_target,
            )

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


class EnglishLevelHintAgent:
    """
    Developer B의 주 진입점(Entry Point) 에이전트 클래스입니다.
    
    초보자 가이드: Developer C의 오케스트레이터가 이 클래스의 `evaluate_turn` 메서드를 호출하여 플레이어의 발화에 대한
    영어 학습 수준 평가 및 다음 시나리오 분기 판단 결과를 받아갑니다. 이 클래스는 내부적으로 LangGraph 기반 워크플로우를 이용해 작동합니다.
    """
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
        """
        필요한 하위 서비스 컴포넌트들과 LangGraph 도구들을 준비하여 에이전트를 초기화합니다.
        """
        from backend.app.agents.agent_b.policy_graph import build_developer_b_policy_graph
        from backend.app.tools.tool_b.developer_b_policy_graph_tools import DeveloperBPolicyGraphTools

        self.graph_tools = DeveloperBPolicyGraphTools(
            state_machine=state_machine,
            level_controller=level_controller,
            tier_controller=tier_controller,
            feedback_generator=feedback_generator,
            openkb_writer=openkb_writer,
            agent_run_root=agent_run_root,
            agent_run_logger=agent_run_logger,
        )
        self.graph = build_developer_b_policy_graph()

        self.state_machine = self.graph_tools.state_machine
        self.level_controller = self.graph_tools.level_controller
        self.tier_controller = self.graph_tools.tier_controller
        self.feedback_generator = self.graph_tools.feedback_generator
        self.openkb_writer = self.graph_tools.openkb_writer
        self.agent_run_logger = self.graph_tools.agent_run_logger
        self._test_streak_session_id: str | None = None
        self._test_incivility_t2_streak: int = 0

    def _get_incivility_t2_streak(self, payload: DevBPolicyInput) -> int:
        if self._test_streak_session_id == payload.session_id:
            return self._test_incivility_t2_streak

        records = []
        writer_any: Any = self.openkb_writer
        try:
            if hasattr(writer_any, "read_session_records"):
                records = writer_any.read_session_records(payload.session_id)
            else:
                from backend.app.services.service_b.final_result_score_policy import OpenKBFinalResultRecordReader
                runtime_root = getattr(writer_any, "runtime_root", None)
                reader = OpenKBFinalResultRecordReader(runtime_root=runtime_root)
                records = reader.read_session_records(payload.session_id)
        except Exception:
            pass

        if not records:
            return 0

        last_record = records[-1]
        under = last_record.get("understanding") or {}
        inciv = under.get("incivility") or {}
        last_tier = inciv.get("tier", 0)
        return 1 if last_tier == 2 else 0

    def _update_streak(self, payload: DevBPolicyInput, current_tier: int) -> None:
        if self._test_streak_session_id != payload.session_id:
            self._test_streak_session_id = payload.session_id
            self._test_incivility_t2_streak = 0

        if current_tier == 2:
            self._test_incivility_t2_streak += 1
        else:
            self._test_incivility_t2_streak = 0

    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        """
        LangGraph 기반 정책 워크플로우를 구동하여, 플레이어의 영어 대화 턴을 분석하고 적절한 힌트와 피드백을 계산합니다.
        
        Args:
            payload: 학습자의 이번 턴 발화 텍스트, 이해 결과(Understanding), 플레이어 정보 등이 담긴 객체
            
        Returns:
            최종 레벨 판정, 피드백 가이드, 힌트 내용 및 다음 분기 노드가 포함된 DevBPolicyOutput 객체
        """
        from backend.app.agents.agent_b.policy_graph import build_initial_developer_b_policy_state
        from backend.app.services.service_b.bad_ending_policy import build_bad_ending_output

        incivility = getattr(payload.understanding, "incivility", None)
        is_bad_end = False
        reason = None
        current_tier = 0

        if incivility is not None:
            current_tier = incivility.tier
            if current_tier >= 3:
                is_bad_end = True
                reason = "verbal_abuse_t3"
            elif current_tier == 2:
                streak = self._get_incivility_t2_streak(payload)
                if streak >= 1:
                    is_bad_end = True
                    reason = "verbal_abuse_t2_repeated"

        if is_bad_end and reason:
            output = build_bad_ending_output(payload, reason)
            
            # Start agent run logging
            agent_run = self.agent_run_logger.start_run(payload)
            input_summary = _policy_input_summary(payload)
            self.agent_run_logger.record_event(
                agent_run,
                event="agent_start",
                status="started",
                data_loaded=input_summary,
            )
            
            # Write to OpenKB
            try:
                openkb_write = self.openkb_writer.write_policy_output(payload, output)
            except Exception as exc:
                openkb_write = self.openkb_writer.failure_result(exc)
            output = output.model_copy(update={"openkb_write": openkb_write})
            
            # Finish agent run logging
            output_summary = _policy_output_summary(output)
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
                    "fallback_used": False,
                    "audio_url": None,
                },
                model_name="rule_based",
            )
            self._update_streak(payload, current_tier)
            return output

        state = build_initial_developer_b_policy_state(payload=payload, tools=self.graph_tools)
        try:
            final_state = self.graph.invoke(state)
        except Exception as exc:
            self.graph_tools.complete_failed_run(payload, exc)
            raise

        output = final_state.get("output")
        if not isinstance(output, DevBPolicyOutput):
            raise RuntimeError("Developer B graph did not produce DevBPolicyOutput")

        self._update_streak(payload, current_tier)
        return output


def _policy_input_summary(payload: DevBPolicyInput) -> dict[str, Any]:
    """
    입력 payload에서 로깅과 분석에 필요한 주요 필드(세션 ID, 턴 수, 노드 ID, 플레이어 발화 요약 등)를 추출하여 요약본 사전을 만듭니다.
    """
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
    """
    0~3점 척도의 루브릭 점수를 0~100점 척도 범위로 환산하여 정수로 반환합니다.
    """
    return max(0, min(100, round(score / 3 * 100)))


def _average_score_candidate(scores: list[int]) -> int:
    """
    100점 환산 점수들의 리스트를 받아 평균값을 계산하여 정수로 반환합니다.
    """
    if not scores:
        return 0
    return round(sum(scores) / len(scores))


def _unique_non_empty(values: Iterable[str | None]) -> list[str]:
    """
    문자열 리스트에서 공백과 None을 제외한 고유한(중복 없는) 값들만 추려내어 리스트로 반환합니다.
    """
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
    """
    에러 수집기(Error Capture)의 오류 유형명을 리포트 성적표용 표준 오류 카테고리 명칭으로 매핑합니다.
    """
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
    """
    특정 유형의 영어 학습 오류가 실제 공항 입국심사나 비즈니스 여행 상황에서 왜 문제가 되는지 설명 텍스트를 제공합니다.
    """
    if issue_type == "task":
        return "The required travel detail may be missing or hard to verify."
    if issue_type == "problem_solving":
        return "This can change how the travel situation is judged."
    if issue_type == "politeness":
        return "Polite, direct wording helps keep the official interaction stable."
    return "A clearer complete sentence helps the listener understand the travel answer quickly."


def _decision_summary(decision: ScenarioDecision) -> dict[str, Any]:
    """
    상태 머신이 결정한 핵심 결정 지표(판정 결과, 분기 타입, 수치 변화 델타 등)를 로그용 요약 사전으로 반환합니다.
    """
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
    """
    LLM 혹은 룰 기반으로 생성된 피드백의 실행 모델 정보 및 토큰 소모량 등의 메타데이터를 추출해 사전으로 반환합니다.
    """
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
    """
    오픈 지식베이스(OpenKB)에 로그 및 레코드를 기록한 결과를 요약하여 로그용 사전으로 반환합니다.
    """
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
    """
    최종 정책 연산의 출력 결과물(합격 여부, 힌트 필요성, 게임 상태 변동 수치 등)을 간결하게 요약하여 사전으로 반환합니다.
    """
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
    """
    피드백 생성 단계에서 LLM 오류 등으로 인해 규칙 기반의 대체(Fallback) 모드가 구동되었는지 여부를 판별합니다.
    """
    return bool(output.feedback_generation and output.feedback_generation.mode == "fallback")


def _model_name(output: DevBPolicyOutput) -> str:
    """
    피드백 생성에 실질적으로 사용된 기계학습 모델명(또는 규칙 기반 여부)을 반환합니다.
    """
    if output.feedback_generation and output.feedback_generation.model:
        return output.feedback_generation.model
    return "rule_based"


def _preview(text: str, limit: int = 120) -> str:
    """
    텍스트 줄바꿈을 공백으로 단일화하고, 지정된 글자 수를 초과할 경우 말줄임표(...)를 붙여 요약 뷰를 만듭니다.
    """
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _validate_b_policy_output(payload: DevBPolicyInput, output: DevBPolicyOutput) -> None:
    """
    출력 결과(output)가 데이터 계약 및 비즈니스 규칙(노드 일치, 힌트 값 누락 검사, 루브릭 범위 등)을 만족하는지 엄격히 검증합니다.
    """
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
    """
    입국심사 및 수하물 신고 단계 노드 ID에 매칭되는 형태 초점(Focus on Form) 교정 타겟 주제명을 반환합니다.
    """
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
