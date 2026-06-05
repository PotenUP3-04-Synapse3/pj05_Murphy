from typing import Any


def normalize_level_design_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Level Design Agent JSON을 Developer A 내부 처리용 dict로 정규화한다."""
    node_context = payload.get("node_context") or {}
    evaluation_summary = payload.get("evaluation_summary") or {}
    level_hint = payload.get("level_hint") or {}
    in_game_feedback = payload.get("in_game_feedback") or {}
    branch = payload.get("branch") or {}
    dialogue_directive = payload.get("dialogue_directive") or {}

    # 추천 표현은 feedback payload, level hint, node context 순서로 가장 가까운 값을 우선한다.
    recommended_expression = (
        in_game_feedback.get("recommended_expression")
        or level_hint.get("recommended_expression")
        or node_context.get("recommended_expression")
        or ""
    )

    return {
        "node_id": _optional_text(payload.get("node_id")),
        "player_text": _optional_text(payload.get("player_text")),
        "npc_question": _optional_text(node_context.get("npc_question")),
        "recommended_expression": _optional_text(recommended_expression),
        "english_level": _optional_text(level_hint.get("english_level")) or "beginner",
        "needs_hint": bool(level_hint.get("needs_hint", False)),
        "feedback_note": _optional_text(evaluation_summary.get("feedback_note")),
        "feedback_tag": _optional_text(evaluation_summary.get("main_feedback_tag")),
        "task_success": int(evaluation_summary.get("task_success", 0) or 0),
        "clarity": int(evaluation_summary.get("clarity", 0) or 0),
        "candidate_text": _optional_text(in_game_feedback.get("npc_recast_line_candidate")),
        "feedback_strategy": _optional_text(in_game_feedback.get("feedback_strategy")),
        "priority": _optional_text(in_game_feedback.get("priority")) or "low",
        "retry_count": _optional_int(
            dialogue_directive.get("retry_count")
            or in_game_feedback.get("retry_count")
            or branch.get("retry_count")
            or payload.get("retry_count")
        ),
        "branch_type": _optional_text(branch.get("branch_type")),
        "next_node_id": _optional_text(branch.get("next_node_id")),
        "dialogue_purpose": _optional_text(dialogue_directive.get("purpose")),
        "tone_hint": _optional_text(dialogue_directive.get("tone_hint")) or "neutral",
        "target_slot": _optional_text(dialogue_directive.get("target_slot")),
    }


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _optional_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return 0
