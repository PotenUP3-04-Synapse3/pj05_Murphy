from __future__ import annotations

from typing import Literal

from backend.app.schemas.game_turn import DevBPolicyInput
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision


EnglishLevel = Literal["beginner", "intermediate", "advanced"]
HintLevel = Literal["none", "low", "medium", "high"]
HintType = Literal["keyword", "sentence_pattern", "situation_hint", "action_hint"] | None
FeedbackStrategy = Literal[
    "recast",
    "clarification_request",
    "elicitation",
    "scaffolding_hint",
    "warning",
    "none",
]


class LevelAdaptationController:
    """
    학습자의 영어 실력(Level)과 상태를 분석하여 게임의 난이도 조절 및 개인화된 학습 피드백 전략을 조정하는 컨트롤러 클래스입니다.
    
    초보자 가이드: 플레이어의 프로필 설정이나 실제 입력 문장의 길이를 분석해 영어 레벨('beginner', 'intermediate' 등)을 추정하고, 
    플레이어의 게임 진행 등급(Bronze, Silver, Gold 티어)과 상황에 맞춰 어떤 유형의 힌트(키워드, 문장 패턴 등)와 
    어떤 방식의 피드백(재진술, 명료화 요구 등)을 줄 것인지 세부 정책을 결정합니다.
    """
    def english_level(self, payload: DevBPolicyInput) -> EnglishLevel:
        """
        플레이어의 입력 정보나 발화 길이를 통해 영어 실력 등급(beginner, intermediate, advanced)을 판단합니다.
        """
        if payload.player_profile.english_confidence:
            return payload.player_profile.english_confidence

        text = payload.player_text.strip()
        if len(text.split()) <= 3:
            return "beginner"
        if payload.understanding.confidence >= 0.85 and not payload.understanding.missing_slots:
            return "intermediate"
        return "beginner"

    def cefr_estimate(self, english_level: EnglishLevel) -> str:
        """
        영어 실력 등급에 부합하는 유럽공통참조기준(CEFR) 레벨(A1-A2, A2-B1, B1-B2) 추정치를 반환합니다.
        """
        if english_level == "advanced":
            return "B1-B2"
        if english_level == "intermediate":
            return "A2-B1"
        return "A1-A2"

    def has_form_issue(self, payload: DevBPolicyInput) -> bool:
        """
        플레이어의 발화에 문법 오류나 형태적 결함(어색한 표현 등)이 존재하는지 확인합니다.
        """
        text = payload.player_text.strip().lower()
        if not text:
            return False
        if len(text.split()) <= 3 and payload.understanding.intent_success:
            return True
        broken_patterns = ["i here", "i go travel", "i will stay five days", "my bag no come"]
        return any(pattern in text for pattern in broken_patterns)

    def hint_policy(self, payload: DevBPolicyInput, decision: ScenarioDecision) -> tuple[bool, HintLevel, HintType, str | None]:
        """
        플레이어의 등급(Tier) 및 현재 상태 머신의 판단을 고려하여 힌트 제공 여부와 힌트 내용(키워드, 패턴 등)을 결정합니다.
        
        Returns:
            (힌트 필요 여부, 힌트 수준, 힌트 타입, 힌트 한글 텍스트) 튜플
        """
        if decision.branch_type == "warning" or decision.branch_type == "bad_end":
            return False, "none", None, None

        if decision.branch_type == "success" and not self.has_form_issue(payload):
            return False, "none", None, None

        if decision.branch_type == "hint":
            return True, "high", "sentence_pattern", payload.node_context.hint_policy.sentence_pattern

        if decision.branch_type == "clarify":
            return True, "medium", "situation_hint", payload.node_context.hint_policy.situation_hint

        if payload.player_profile.tier == "Bronze" and payload.understanding.missing_slots:
            return True, "medium", "sentence_pattern", payload.node_context.hint_policy.sentence_pattern

        if payload.player_profile.tier == "Silver" and (
            payload.understanding.missing_slots or payload.scenario_state.retry_count >= 1
        ):
            return True, "low", "keyword", ", ".join(payload.node_context.hint_policy.keyword)

        if payload.player_profile.tier == "Gold" and payload.scenario_state.retry_count >= 2:
            return True, "low", "action_hint", payload.node_context.hint_policy.action_hint

        return False, "none", None, None

    def feedback_strategy(self, decision: ScenarioDecision) -> FeedbackStrategy:
        """
        상태 머신의 분기 결과를 바탕으로 학습자에게 제공할 최적의 피드백 전략을 수집합니다.
        """
        if decision.branch_type == "success" or decision.branch_type == "final":
            return "recast"
        if decision.branch_type == "clarify":
            return "clarification_request"
        if decision.branch_type == "hint":
            return "scaffolding_hint"
        if decision.branch_type == "warning" or decision.branch_type == "bad_end":
            return "warning"
        return "elicitation"

    def feedback_focus(self, payload: DevBPolicyInput) -> str:
        if payload.node_context.required_slots:
            return payload.node_context.required_slots[0]
        return payload.node_context.npc_question_goal

    def feedback_priority(self, decision: ScenarioDecision) -> Literal["low", "medium", "high"]:
        if decision.branch_type in {"warning", "bad_end", "hint"}:
            return "high"
        if decision.branch_type in {"clarify", "retry"}:
            return "medium"
        return "low"
