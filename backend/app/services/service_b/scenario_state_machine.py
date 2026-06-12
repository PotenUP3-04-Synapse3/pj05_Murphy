from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.app.schemas.game_turn import DevBPolicyInput


BranchType = Literal["success", "retry", "clarify", "hint", "warning", "bad_end", "final"]
NextAction = Literal["ADVANCE", "REASK", "GIVE_HINT", "WARNING", "FAIL_END", "FINAL_DECISION", "COMPLETE_CHAPTER"]
Verdict = Literal["SUCCESS", "PARTIAL", "UNCLEAR", "FAIL", "CRITICAL_FAIL"]

GOLD_CHALLENGE_SOURCE_NODE_ID = "IMM_005_RETURN_TICKET"
GOLD_BAG_CONTENT_CHALLENGE_NODE_ID = "IMM_ALPHA_GOLD_BAG_CONTENT_CHECK"
ALPHA_FINAL_SCOREBOARD_NODE_ID = "ALPHA_999_FINAL_SCOREBOARD"
CHAPTER_COMPLETE_NODE_IDS = {"FLIGHT_999_COMPLETE", "IMM_999_CLEARED", "BAG_999_COMPLETE"}


@dataclass(frozen=True)
class ScenarioDecision:
    verdict: Verdict
    branch_type: BranchType
    next_action: NextAction
    next_node_id: str
    branch_reason: str
    patience_delta: int
    suspicion_delta: int
    retry_count_delta: int
    hint_count_delta: int


class ScenarioStateMachine:
    def decide(self, payload: DevBPolicyInput) -> ScenarioDecision:
        self._validate_allowed_nodes(payload)

        risk_total = payload.scenario_state.suspicion + payload.understanding.risk_delta
        if self._is_critical_risk(payload, risk_total):
            return self._critical_fail(payload, risk_total)

        if self._is_success(payload):
            if payload.current_node_id == ALPHA_FINAL_SCOREBOARD_NODE_ID:
                return self._success(payload, branch_type="final", next_action="FINAL_DECISION")
            return self._success(payload, branch_type="success", next_action="ADVANCE")

        if self._is_unclear(payload):
            return self._clarify(payload)

        if self._should_give_hint(payload):
            return self._hint(payload)

        return self._retry(payload)

    def _validate_allowed_nodes(self, payload: DevBPolicyInput) -> None:
        if not payload.node_context.allowed_next_nodes:
            raise ValueError("node_context.allowed_next_nodes must not be empty")

    def _is_success(self, payload: DevBPolicyInput) -> bool:
        return payload.understanding.intent_success and not payload.understanding.missing_slots

    def _is_unclear(self, payload: DevBPolicyInput) -> bool:
        return (
            payload.input_source.needs_repeat
            or payload.understanding.needs_clarification
            or payload.understanding.confidence < 0.5
            or payload.understanding.answer_relevance == "partially_related"
        )

    def _should_give_hint(self, payload: DevBPolicyInput) -> bool:
        if payload.scenario_state.retry_count >= 2:
            return True
        if payload.player_profile.tier == "Bronze" and payload.understanding.missing_slots:
            return True
        return payload.scenario_state.previous_fail_count >= 2

    def _is_critical_risk(self, payload: DevBPolicyInput, risk_total: int) -> bool:
        critical_tags = {
            "illegal_work_intent",
            "overstay_intent",
            "unknown_contents",
            "received_from_stranger",
            "dangerous_use",
            "commercial_resale",
            "refuse_submission",
        }
        return (
            payload.understanding.risk_delta >= 20
            or risk_total >= 50
            or bool(critical_tags.intersection(payload.understanding.risk_tags))
        )

    def _success(
        self,
        payload: DevBPolicyInput,
        *,
        branch_type: BranchType,
        next_action: NextAction,
    ) -> ScenarioDecision:
        next_node_id = self._checked_next_node(self._preferred_success_node(payload), payload)
        if next_node_id in CHAPTER_COMPLETE_NODE_IDS:
            next_action = "COMPLETE_CHAPTER"
        return ScenarioDecision(
            verdict="SUCCESS",
            branch_type=branch_type,
            next_action=next_action,
            next_node_id=next_node_id,
            branch_reason="Required intent and required slots were satisfied.",
            patience_delta=0,
            suspicion_delta=max(payload.understanding.risk_delta, 0),
            retry_count_delta=0,
            hint_count_delta=0,
        )

    def _preferred_success_node(self, payload: DevBPolicyInput) -> str:
        if self._should_route_gold_bag_content_challenge(payload):
            return GOLD_BAG_CONTENT_CHALLENGE_NODE_ID
        return payload.node_context.success_next_node

    def _should_route_gold_bag_content_challenge(self, payload: DevBPolicyInput) -> bool:
        return (
            payload.current_node_id == GOLD_CHALLENGE_SOURCE_NODE_ID
            and payload.player_profile.tier == "Gold"
            and payload.understanding.confidence >= 0.85
            and not payload.understanding.missing_slots
            and GOLD_BAG_CONTENT_CHALLENGE_NODE_ID in payload.node_context.allowed_next_nodes
        )

    def _clarify(self, payload: DevBPolicyInput) -> ScenarioDecision:
        next_node_id = self._checked_next_node(payload.node_context.clarify_next_node, payload)
        return ScenarioDecision(
            verdict="UNCLEAR",
            branch_type="clarify",
            next_action="REASK",
            next_node_id=next_node_id,
            branch_reason="Meaning is unclear or needs clarification.",
            patience_delta=-5,
            suspicion_delta=max(payload.understanding.risk_delta, 0),
            retry_count_delta=1,
            hint_count_delta=0,
        )

    def _hint(self, payload: DevBPolicyInput) -> ScenarioDecision:
        next_node_id = self._checked_next_node(payload.node_context.hint_next_node, payload)
        return ScenarioDecision(
            verdict="FAIL",
            branch_type="hint",
            next_action="GIVE_HINT",
            next_node_id=next_node_id,
            branch_reason="Repeated failure or beginner support policy requires a hint.",
            patience_delta=-10,
            suspicion_delta=max(payload.understanding.risk_delta, 0),
            retry_count_delta=1,
            hint_count_delta=1,
        )

    def _retry(self, payload: DevBPolicyInput) -> ScenarioDecision:
        next_node_id = self._checked_next_node(payload.node_context.retry_next_node, payload)
        return ScenarioDecision(
            verdict="FAIL",
            branch_type="retry",
            next_action="REASK",
            next_node_id=next_node_id,
            branch_reason="Required intent or slot was not satisfied.",
            patience_delta=-8,
            suspicion_delta=max(payload.understanding.risk_delta, 0),
            retry_count_delta=1,
            hint_count_delta=0,
        )

    def _critical_fail(self, payload: DevBPolicyInput, risk_total: int) -> ScenarioDecision:
        branch_type: BranchType = "bad_end" if risk_total >= 70 or payload.scenario_state.retry_count >= 2 else "warning"
        next_action: NextAction = "FAIL_END" if branch_type == "bad_end" else "WARNING"
        preferred = self._preferred_bad_end_node(payload) if branch_type == "bad_end" else payload.node_context.warning_next_node
        next_node_id = self._checked_next_node(preferred, payload)
        return ScenarioDecision(
            verdict="CRITICAL_FAIL",
            branch_type=branch_type,
            next_action=next_action,
            next_node_id=next_node_id,
            branch_reason="Risk expression increased immigration suspicion.",
            patience_delta=-20,
            suspicion_delta=max(payload.understanding.risk_delta, 20),
            retry_count_delta=1,
            hint_count_delta=0,
        )

    def _preferred_bad_end_node(self, payload: DevBPolicyInput) -> str:
        if "END_SECONDARY_INSPECTION" in payload.node_context.allowed_next_nodes:
            return "END_SECONDARY_INSPECTION"
        return payload.node_context.warning_next_node

    def _checked_next_node(self, preferred_next_node: str, payload: DevBPolicyInput) -> str:
        allowed_next_nodes = payload.node_context.allowed_next_nodes
        if preferred_next_node in allowed_next_nodes and self._client_allows(preferred_next_node, payload):
            return preferred_next_node

        for candidate in allowed_next_nodes:
            if self._client_allows(candidate, payload):
                return candidate

        raise ValueError("No next_node_id is allowed by both node_context and client_allowed_next_nodes")

    def _client_allows(self, next_node_id: str, payload: DevBPolicyInput) -> bool:
        return not payload.client_allowed_next_nodes or next_node_id in payload.client_allowed_next_nodes
