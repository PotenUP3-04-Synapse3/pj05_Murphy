from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from backend.app.agents.agent_b.feedback_hint_llm_client import (
    FeedbackHintLLMClient,
    OpenAIFeedbackHintLLMClient,
)
from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    DevBPolicyOutput,
    FeedbackGenerationTrace,
    RubricScores,
)
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision
from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyResult


FeedbackMode = Literal["rule", "llm"]


class _LLMRubricScores(BaseModel):
    comprehension: int = Field(ge=0, le=2)
    fluency: int = Field(ge=0, le=2)
    grammar_accuracy: int = Field(ge=0, le=2)
    vocabulary_range: int = Field(ge=0, le=2)
    clarity: int = Field(ge=0, le=2)
    interaction_problem_solving: int = Field(ge=0, le=2)


class _LLMFeedbackPayload(BaseModel):
    hint_kr: str | None = None
    feedback_note: str = Field(min_length=1)
    report_summary: str = Field(min_length=1)
    report_improvement: str = Field(min_length=1)
    example_answer: str = Field(min_length=1)
    focus_on_form_explanation_kr: str = Field(min_length=1)
    rubric_scores: _LLMRubricScores | None = None


@dataclass(frozen=True)
class FeedbackHintGeneration:
    hint_kr: str | None
    feedback_note: str
    report_summary: str
    report_improvement: str
    example_answer: str
    focus_on_form_explanation_kr: str
    rubric_scores: RubricScores | None
    trace: FeedbackGenerationTrace


class FeedbackHintGenerator:
    def __init__(
        self,
        *,
        mode: str | None = None,
        llm_client: FeedbackHintLLMClient | None = None,
        env_path: Path | None = None,
    ) -> None:
        self.mode = self._normalize_mode(mode or self._mode_from_environment(env_path))
        self.llm_client = llm_client
        self.env_path = env_path

    def generate(
        self,
        *,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        base_output: DevBPolicyOutput,
        tier_result: TierDifficultyResult,
        focus_on_form_explanation_kr: str,
    ) -> FeedbackHintGeneration:
        if self.mode == "rule":
            return self._fallback_generation(
                base_output=base_output,
                tier_result=tier_result,
                focus_on_form_explanation_kr=focus_on_form_explanation_kr,
                mode="rule",
                reason=None,
            )

        try:
            client = self.llm_client or OpenAIFeedbackHintLLMClient.from_environment(self.env_path)
            raw_result = client.generate(
                self._llm_payload(
                    payload=payload,
                    decision=decision,
                    base_output=base_output,
                    tier_result=tier_result,
                    focus_on_form_explanation_kr=focus_on_form_explanation_kr,
                )
            )
            validated = _LLMFeedbackPayload.model_validate(raw_result)
        except Exception as exc:
            return self._fallback_generation(
                base_output=base_output,
                tier_result=tier_result,
                focus_on_form_explanation_kr=focus_on_form_explanation_kr,
                mode="fallback",
                reason=str(exc),
            )

        rubric_scores = self._rubric_scores_from_llm(validated)
        return FeedbackHintGeneration(
            hint_kr=validated.hint_kr if base_output.level_hint.needs_hint else None,
            feedback_note=validated.feedback_note,
            report_summary=validated.report_summary,
            report_improvement=validated.report_improvement,
            example_answer=validated.example_answer,
            focus_on_form_explanation_kr=validated.focus_on_form_explanation_kr,
            rubric_scores=rubric_scores,
            trace=FeedbackGenerationTrace(
                mode="llm",
                model=getattr(client, "model", None),
                used_llm=True,
                fallback_reason=None,
            ),
        )

    def _fallback_generation(
        self,
        *,
        base_output: DevBPolicyOutput,
        tier_result: TierDifficultyResult,
        focus_on_form_explanation_kr: str,
        mode: Literal["rule", "fallback"],
        reason: str | None,
    ) -> FeedbackHintGeneration:
        return FeedbackHintGeneration(
            hint_kr=base_output.level_hint.hint_kr if base_output.level_hint.needs_hint else None,
            feedback_note=base_output.evaluation.feedback_note or "The answer was evaluated by rule-based policy.",
            report_summary=base_output.report_item.summary,
            report_improvement=base_output.report_item.improvement,
            example_answer=base_output.report_item.example_answer,
            focus_on_form_explanation_kr=focus_on_form_explanation_kr,
            rubric_scores=tier_result.rubric_scores,
            trace=FeedbackGenerationTrace(
                mode=mode,
                model=None,
                used_llm=False,
                fallback_reason=reason,
            ),
        )

    def _llm_payload(
        self,
        *,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        base_output: DevBPolicyOutput,
        tier_result: TierDifficultyResult,
        focus_on_form_explanation_kr: str,
    ) -> dict[str, Any]:
        return {
            "contract_version": payload.contract_version,
            "node_id": payload.current_node_id,
            "player_text": payload.player_text,
            "player_profile": payload.player_profile.model_dump(),
            "node_context": {
                "npc_question": payload.node_context.npc_question,
                "npc_question_goal": payload.node_context.npc_question_goal,
                "recommended_expression": payload.node_context.recommended_expression,
                "base_hint_kr": payload.node_context.base_hint_kr,
                "required_slots": payload.node_context.required_slots,
            },
            "understanding": payload.understanding.model_dump(),
            "rule_policy": {
                "verdict": decision.verdict,
                "branch_type": decision.branch_type,
                "feedback_tags": base_output.evaluation.feedback_tags,
                "needs_hint": base_output.level_hint.needs_hint,
                "hint_type": base_output.level_hint.hint_type,
            },
            "rule_feedback": {
                "hint_kr": base_output.level_hint.hint_kr,
                "feedback_note": base_output.evaluation.feedback_note,
                "report_item": base_output.report_item.model_dump(),
                "focus_on_form_explanation_kr": focus_on_form_explanation_kr,
            },
            "rule_rubric_scores": tier_result.rubric_scores.model_dump(),
            "safety": {
                "do_not_generate": [
                    "branch",
                    "next_node_id",
                    "next_action",
                    "state_delta",
                    "verdict",
                    "npc_dialogue",
                    "tts",
                    "unreal_command",
                ]
            },
        }

    def _rubric_scores_from_llm(self, validated: _LLMFeedbackPayload) -> RubricScores | None:
        if validated.rubric_scores is None:
            return None
        values = validated.rubric_scores
        total = (
            values.comprehension
            + values.fluency
            + values.grammar_accuracy
            + values.vocabulary_range
            + values.clarity
            + values.interaction_problem_solving
        )
        try:
            return RubricScores(
                comprehension=values.comprehension,
                fluency=values.fluency,
                grammar_accuracy=values.grammar_accuracy,
                vocabulary_range=values.vocabulary_range,
                clarity=values.clarity,
                interaction_problem_solving=values.interaction_problem_solving,
                total=total,
            )
        except ValidationError:
            return None

    def _mode_from_environment(self, env_path: Path | None) -> str:
        values = self._read_env_file(env_path or Path(".env"))
        return os.getenv("DEV_B_FEEDBACK_LLM_MODE") or values.get("DEV_B_FEEDBACK_LLM_MODE", "rule")

    def _normalize_mode(self, mode: str) -> FeedbackMode:
        if mode == "llm":
            return "llm"
        return "rule"

    def _read_env_file(self, path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        values: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values
