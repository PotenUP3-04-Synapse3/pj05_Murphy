from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.app.schemas.game_turn import DevBPolicyInput, DifficultyProfile, RubricScores
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision


PlayerTier = Literal["Bronze", "Silver", "Gold"]


@dataclass(frozen=True)
class TierDifficultyResult:
    rubric_scores: RubricScores
    difficulty_profile: DifficultyProfile


class TierDifficultyController:
    def evaluate(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        *,
        has_form_issue: bool,
    ) -> TierDifficultyResult:
        comprehension = self._comprehension_score(payload)
        fluency = self._fluency_score(payload)
        grammar_accuracy = 1 if has_form_issue else 2
        if decision.verdict in {"UNCLEAR", "FAIL", "CRITICAL_FAIL"}:
            grammar_accuracy = min(grammar_accuracy, 1)
        vocabulary_range = self._vocabulary_score(payload, decision)
        clarity = self._clarity_score(payload, decision)
        interaction = self._interaction_score(payload, decision)
        return self.from_score_values(
            comprehension,
            fluency,
            grammar_accuracy,
            vocabulary_range,
            clarity,
            interaction,
            tier=payload.player_profile.tier,
        )

    def from_score_values(
        self,
        comprehension: int,
        fluency: int,
        grammar_accuracy: int,
        vocabulary_range: int,
        clarity: int,
        interaction_problem_solving: int,
        *,
        tier: PlayerTier = "Silver",
    ) -> TierDifficultyResult:
        rubric_scores = RubricScores(
            comprehension=self._clamp_score(comprehension),
            fluency=self._clamp_score(fluency),
            grammar_accuracy=self._clamp_score(grammar_accuracy),
            vocabulary_range=self._clamp_score(vocabulary_range),
            clarity=self._clamp_score(clarity),
            interaction_problem_solving=self._clamp_score(interaction_problem_solving),
            total=0,
        )
        total = (
            rubric_scores.comprehension
            + rubric_scores.fluency
            + rubric_scores.grammar_accuracy
            + rubric_scores.vocabulary_range
            + rubric_scores.clarity
            + rubric_scores.interaction_problem_solving
        )
        rubric_scores = rubric_scores.model_copy(update={"total": total})
        return TierDifficultyResult(
            rubric_scores=rubric_scores,
            difficulty_profile=self.difficulty_profile_for(rubric_scores, tier=tier),
        )

    def from_rubric_scores(
        self,
        rubric_scores: RubricScores,
        *,
        tier: PlayerTier = "Silver",
    ) -> TierDifficultyResult:
        return self.from_score_values(
            rubric_scores.comprehension,
            rubric_scores.fluency,
            rubric_scores.grammar_accuracy,
            rubric_scores.vocabulary_range,
            rubric_scores.clarity,
            rubric_scores.interaction_problem_solving,
            tier=tier,
        )

    def difficulty_profile_for(
        self,
        rubric_scores: RubricScores,
        *,
        tier: PlayerTier,
    ) -> DifficultyProfile:
        tsl = self.travel_speaking_level_for_total(rubric_scores.total)
        if tsl == "TSL_1_SURVIVAL":
            speed: Literal["slow", "normal", "natural"] = "slow"
            complexity: Literal["basic", "standard", "expanded", "complex"] = "basic"
            hint_frequency: Literal["high", "medium", "low"] = "high"
            pressure: Literal["low", "medium", "high"] = "low"
        elif tsl == "TSL_2_FUNCTIONAL":
            speed = "normal"
            complexity = "standard"
            hint_frequency = "medium"
            pressure = "low"
        elif tsl == "TSL_3_INDEPENDENT":
            speed = "normal"
            complexity = "expanded"
            hint_frequency = "medium"
            pressure = "medium"
        else:
            speed = "natural"
            complexity = "complex"
            hint_frequency = "low"
            pressure = "high"

        if tier == "Bronze":
            speed = "slow" if speed == "normal" else speed
            hint_frequency = "high" if hint_frequency == "medium" else hint_frequency
            pressure = "low" if pressure == "medium" else pressure
        elif tier == "Gold" and tsl != "TSL_1_SURVIVAL":
            hint_frequency = "low" if hint_frequency == "medium" else hint_frequency
            pressure = "high" if pressure == "medium" else pressure

        return DifficultyProfile(
            travel_speaking_level=tsl,
            npc_speech_speed=speed,
            question_complexity=complexity,
            hint_frequency=hint_frequency,
            pressure_level=pressure,
        )

    def travel_speaking_level_for_total(self, total: int) -> str:
        if total <= 3:
            return "TSL_1_SURVIVAL"
        if total <= 6:
            return "TSL_2_FUNCTIONAL"
        if total <= 9:
            return "TSL_3_INDEPENDENT"
        return "TSL_4_STRATEGIC"

    def _comprehension_score(self, payload: DevBPolicyInput) -> int:
        if payload.understanding.intent_success:
            return 2
        if payload.understanding.answer_relevance == "partially_related":
            return 1
        return 0

    def _fluency_score(self, payload: DevBPolicyInput) -> int:
        word_count = len(payload.player_text.strip().split())
        if word_count >= 6:
            return 2
        if word_count >= 3:
            return 1
        return 0

    def _vocabulary_score(self, payload: DevBPolicyInput, decision: ScenarioDecision) -> int:
        if decision.verdict == "CRITICAL_FAIL":
            return 0
        if payload.understanding.extracted_slots:
            return 2
        if payload.player_text.strip():
            return 1
        return 0

    def _clarity_score(self, payload: DevBPolicyInput, decision: ScenarioDecision) -> int:
        if decision.verdict == "CRITICAL_FAIL":
            return 0
        if payload.understanding.confidence >= 0.85 and not payload.understanding.missing_slots:
            return 2
        if payload.understanding.confidence >= 0.5:
            return 1
        return 0

    def _interaction_score(self, payload: DevBPolicyInput, decision: ScenarioDecision) -> int:
        if decision.verdict in {"SUCCESS", "PARTIAL"}:
            return 2
        if decision.branch_type in {"clarify", "hint", "retry"} and payload.player_text.strip():
            return 1
        return 0

    def _clamp_score(self, value: int) -> int:
        return max(0, min(2, int(value)))
