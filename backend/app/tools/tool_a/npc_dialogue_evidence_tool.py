from datetime import UTC, datetime
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def build_npc_dialogue_evidence_summary(payload: dict[str, Any]) -> dict[str, Any]:
    # 원문 전체 대신 AgentRun에서 역추적 가능한 짧은 근거 요약만 저장한다.
    player = _as_dict(payload.get("player"))
    evaluation = _as_dict(payload.get("evaluation"))
    node_id = _text(payload.get("node_id"), "unknown_node")
    turn_id = _text(payload.get("turn_id"), "unknown_turn")
    player_text = _text(player.get("utterance"), _text(payload.get("player_text"), ""))
    branch_type = _text(evaluation.get("branch_type"), _text(payload.get("branch_type"), "neutral"))
    target_slot = _text(evaluation.get("target_slot"), _text(payload.get("target_slot"), "unknown_slot"))

    return {
        "source_type": "level_design",
        "cache_hit": False,
        "selection_strategy": "single_turn_level_design_payload",
        "evidence_summary": [
            {
                "rank": 1,
                "source_id": f"{node_id}:{turn_id}",
                "source_url": None,
                "timestamp": datetime.now(UTC).isoformat(),
                "author": "level_design_agent",
                "permission_level": "runtime_user_session",
                "channel_id": None,
                "importance_score": 100,
                "snippet": (
                    f"Player answered: {player_text}. "
                    f"Branch: {branch_type}. Target slot: {target_slot}."
                ),
            }
        ],
    }
