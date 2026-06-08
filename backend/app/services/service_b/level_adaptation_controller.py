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
    def english_level(self, payload: DevBPolicyInput) -> EnglishLevel:
        if payload.player_profile.english_confidence:
            return payload.player_profile.english_confidence

        text = payload.player_text.strip()
        if len(text.split()) <= 3:
            return "beginner"
        if payload.understanding.confidence >= 0.85 and not payload.understanding.missing_slots:
            return "intermediate"
        return "beginner"

    def cefr_estimate(self, english_level: EnglishLevel) -> str:
        if english_level == "advanced":
            return "B1-B2"
        if english_level == "intermediate":
            return "A2-B1"
        return "A1-A2"

    def has_form_issue(self, payload: DevBPolicyInput) -> bool:
        text = payload.player_text.strip().lower()
        if not text:
            return False
        if len(text.split()) <= 3 and payload.understanding.intent_success:
            return True
        broken_patterns = ["i here", "i go travel", "i will stay five days", "my bag no come"]
        return any(pattern in text for pattern in broken_patterns)

    def hint_policy(self, payload: DevBPolicyInput, decision: ScenarioDecision) -> tuple[bool, HintLevel, HintType, str | None]:
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
