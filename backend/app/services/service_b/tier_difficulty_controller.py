from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.app.schemas.game_turn import DevBPolicyInput, DifficultyProfile, RubricScores
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision


PlayerTier = Literal["Bronze", "Silver", "Gold"]


@dataclass(frozen=True)
class TierDifficultyResult:
    """
    학습자 등급 및 루브릭 평가 연산의 결과 데이터를 담고 있는 데이터 클래스입니다.
    
    초보자 가이드: 세부 평가 영역별 점수(rubric_scores)와 이 점수에 맞춰 추천되는 
    NPC 말하기 속도 및 질문 복잡도 설정(difficulty_profile)을 묶어줍니다.
    """
    rubric_scores: RubricScores
    difficulty_profile: DifficultyProfile


class TierDifficultyController:
    """
    플레이어의 영어 말하기 수준에 맞춰 게임 내 NPC의 반응 난이도를 조절하는 역할을 하는 컨트롤러 클래스입니다.
    
    초보자 가이드: 플레이어의 실시간 영어 발화 결과(이해력, 유창성, 문법, 어휘, 명확성, 문제 해결 등)를 
    각각 0~2점 사이로 평가하여 총합 점수를 내고, 이에 따라 학습 난이도 레벨(TSL_1~TSL_4)을 판정합니다. 
    최종적으로 플레이어의 게임 티어(Bronze, Silver, Gold)를 고려하여 NPC의 대사 말하기 속도나 힌트 주기 등을 보정합니다.
    """
    def evaluate(
        self,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        *,
        has_form_issue: bool,
    ) -> TierDifficultyResult:
        """
        현재 턴의 플레이어 발화 성향과 대화 결과 데이터를 기준으로 루브릭 영역별 평가 및 난이도 수준을 판정합니다.
        
        Args:
            payload: 학습자 입력 상태 데이터
            decision: 상태 머신 분기 판단 결과
            has_form_issue: 문법 형태 오류가 감지되었는지 여부
            
        Returns:
            평가 점수와 난이도 정보가 담긴 TierDifficultyResult 객체
        """
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
        """
        이해력 점수를 계산합니다. 의도가 정확히 맞으면 2점, 부분적이면 1점, 무관한 대답이면 0점을 줍니다.
        """
        if payload.understanding.intent_success:
            return 2
        if payload.understanding.answer_relevance == "partially_related":
            return 1
        return 0

    def _fluency_score(self, payload: DevBPolicyInput) -> int:
        """
        발화 단어 개수를 기준으로 유창성(Fluency) 점수를 계산합니다. (6개 이상 2점, 3개 이상 1점, 3개 미만 0점)
        """
        word_count = len(payload.player_text.strip().split())
        if word_count >= 6:
            return 2
        if word_count >= 3:
            return 1
        return 0

    def _vocabulary_score(self, payload: DevBPolicyInput, decision: ScenarioDecision) -> int:
        """
        추출된 슬롯 수 및 발화 존재 유무를 확인해 어휘 범주(Vocabulary Range) 점수를 0~2점 척도로 계산합니다.
        """
        if decision.verdict == "CRITICAL_FAIL":
            return 0
        if payload.understanding.extracted_slots:
            return 2
        if payload.player_text.strip():
            return 1
        return 0

    def _clarity_score(self, payload: DevBPolicyInput, decision: ScenarioDecision) -> int:
        """
        발화 이해도 분석 신뢰성(Confidence) 수치를 기반으로 발화의 명확성(Clarity) 점수를 계산합니다.
        """
        if decision.verdict == "CRITICAL_FAIL":
            return 0
        if payload.understanding.confidence >= 0.85 and not payload.understanding.missing_slots:
            return 2
        if payload.understanding.confidence >= 0.5:
            return 1
        return 0

    def _interaction_score(self, payload: DevBPolicyInput, decision: ScenarioDecision) -> int:
        """
        턴 판정 결과와 발화 여부를 바탕으로 상호작용 및 과업 해결력(Interaction) 점수를 계산합니다.
        """
        if decision.verdict in {"SUCCESS", "PARTIAL"}:
            return 2
        if decision.branch_type in {"clarify", "hint", "retry"} and payload.player_text.strip():
            return 1
        return 0

    def _clamp_score(self, value: int) -> int:
        """
        개별 루브릭 수치 값을 0점 하한선 및 2점 상한선으로 보정(Clamp)하여 반환합니다.
        """
        return max(0, min(2, int(value)))
