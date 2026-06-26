from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import DevBPolicyInput
from backend.app.services.service_b.final_result_score_policy import OpenKBFinalResultRecordReader
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision


class SocialObligationLifecyclePolicy:
    """Advance repeated social non-answers without turning them into hint loops.

    Beginner guide:
    This policy does not decide normal scenario success.  It only handles the
    narrow case where C says the player did not answer an open social/procedural
    obligation, such as a customs officer waiting for cooperation.  B uses the
    saved OpenKB turn records to choose the next repair stage.
    """

    def __init__(self, runtime_root: Path | None = None) -> None:
        self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_b")

    def decide(self, payload: DevBPolicyInput) -> ScenarioDecision | None:
        social_context = _social_context_dict(payload.understanding)
        scene_norm = str(social_context.get("scene_norm") or "")
        pending_obligation = str(social_context.get("pending_social_obligation") or "")
        obligation_status = str(social_context.get("obligation_status") or "")

        if scene_norm not in {"service_recovery", "institutional_check"}:
            return None
        if not pending_obligation or obligation_status not in {"open", "ignored", "unclear"}:
            return None
        if not _is_social_stall_move(payload.player_text, social_context):
            return None

        reader = OpenKBFinalResultRecordReader(runtime_root=self.runtime_root)
        records = reader.read_session_records(payload.session_id)
        related_records = [
            record
            for record in records
            if _record_matches_obligation(record, pending_obligation, scene_norm)
        ]
        lifecycle = _latest_lifecycle(scene_norm, related_records)
        streak = _social_stall_streak(payload, related_records)

        if lifecycle == "engagement_checked" or streak >= 4:
            return _decision(
                payload,
                branch_reason=f"{scene_norm}_procedure_warning",
                next_action="WARNING",
                next_node_id=_first_allowed(
                    payload,
                    payload.node_context.warning_next_node,
                    payload.node_context.retry_next_node,
                ),
                verdict="FAIL",
                branch_type="warning",
                patience_delta=-5,
            )
        if lifecycle == "repaired_once" or streak >= 3:
            return _decision(
                payload,
                branch_reason=f"{scene_norm}_engagement_check",
                next_action="REASK",
                next_node_id=_first_allowed(
                    payload,
                    payload.node_context.retry_next_node,
                    payload.node_context.clarify_next_node,
                ),
            )
        if lifecycle == "open" or streak >= 2:
            return _decision(
                payload,
                branch_reason=f"{scene_norm}_repeated_social_repair",
                next_action="REASK",
                next_node_id=_first_allowed(
                    payload,
                    payload.node_context.retry_next_node,
                    payload.node_context.clarify_next_node,
                ),
            )
        return _decision(
            payload,
            branch_reason=f"{scene_norm}_social_obligation_open",
            next_action="REASK",
            next_node_id=_first_allowed(
                payload,
                payload.node_context.retry_next_node,
                payload.node_context.clarify_next_node,
            ),
        )


def _decision(
    payload: DevBPolicyInput,
    *,
    branch_reason: str,
    next_action: str,
    next_node_id: str,
    verdict: str = "UNCLEAR",
    branch_type: str = "clarify",
    patience_delta: int = 0,
) -> ScenarioDecision:
    return ScenarioDecision(
        verdict=verdict,  # type: ignore[arg-type]
        branch_type=branch_type,  # type: ignore[arg-type]
        next_action=next_action,  # type: ignore[arg-type]
        next_node_id=next_node_id,
        branch_reason=branch_reason,
        patience_delta=patience_delta,
        suspicion_delta=max(payload.understanding.risk_delta, 0),
        retry_count_delta=0,
        hint_count_delta=0,
        selected_probe=None,
        cumulative_confidence=0.0,
    )


def _social_context_dict(understanding: Any) -> dict[str, Any]:
    social_context = getattr(understanding, "social_context", None)
    if isinstance(social_context, dict):
        return social_context
    if social_context is not None and hasattr(social_context, "model_dump"):
        return social_context.model_dump()
    return {}


def _record_matches_obligation(record: dict[str, Any], pending_obligation: str, scene_norm: str) -> bool:
    understanding = record.get("understanding") if isinstance(record, dict) else {}
    social_context = understanding.get("social_context") if isinstance(understanding, dict) else {}
    if not isinstance(social_context, dict):
        return False
    return (
        str(social_context.get("pending_social_obligation") or "") == pending_obligation
        and str(social_context.get("scene_norm") or "") == scene_norm
    )


def _latest_lifecycle(scene_norm: str, records: list[dict[str, Any]]) -> str:
    prefix = f"{scene_norm}_"
    for record in reversed(records):
        branch = record.get("branch") if isinstance(record, dict) else {}
        branch_reason = str(branch.get("branch_reason") or "") if isinstance(branch, dict) else ""
        if not branch_reason.startswith(prefix):
            continue
        if "procedure_warning" in branch_reason:
            return "paused_or_closed"
        if "engagement_check" in branch_reason:
            return "engagement_checked"
        if "repeated_social_repair" in branch_reason:
            return "repaired_once"
        if "social_obligation_open" in branch_reason:
            return "open"
    return "none"


def _social_stall_streak(payload: DevBPolicyInput, records: list[dict[str, Any]]) -> int:
    count = 1 if _is_social_stall_move(payload.player_text, _social_context_dict(payload.understanding)) else 0
    for record in reversed(records):
        understanding = record.get("understanding") if isinstance(record, dict) else {}
        social_context = understanding.get("social_context") if isinstance(understanding, dict) else {}
        player_text = str(record.get("player_text") or "") if isinstance(record, dict) else ""
        if _is_social_stall_move(player_text, social_context if isinstance(social_context, dict) else {}):
            count += 1
            continue
        break
    return count


def _is_social_stall_move(player_text: str, social_context: dict[str, Any]) -> bool:
    conversation_move = str(social_context.get("conversation_move") or "")
    if conversation_move in {"meaningful_answer", "refusal"}:
        return False
    if conversation_move in {
        "greeting_only",
        "repeated_greeting",
        "low_content_non_answer",
        "meta_non_answer",
        "filler",
        "off_topic",
        "clarification_request",
        "unknown",
    }:
        return True
    engagement_quality = str(social_context.get("engagement_quality") or "")
    obligation_status = str(social_context.get("obligation_status") or "")
    if engagement_quality in {"thin", "stalled"} and obligation_status in {"open", "ignored", "unclear"}:
        return True
    normalized = " ".join(player_text.lower().replace("?", " ").replace(".", " ").split())
    return normalized in {"what", "what what", "fine", "fine fine", "hello", "hello hello"}


def _first_allowed(payload: DevBPolicyInput, *candidates: str) -> str:
    allowed_by_node = set(payload.node_context.allowed_next_nodes)
    allowed_by_client = set(payload.client_allowed_next_nodes or payload.node_context.allowed_next_nodes)
    for candidate in candidates:
        if candidate in allowed_by_node and candidate in allowed_by_client:
            return candidate
    for candidate in payload.node_context.allowed_next_nodes:
        if candidate in allowed_by_client:
            return candidate
    raise ValueError("No next_node_id is allowed by both node_context and client_allowed_next_nodes")
