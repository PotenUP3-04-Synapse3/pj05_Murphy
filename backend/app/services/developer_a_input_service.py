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
        "node_id": str(payload.get("node_id", "")),
        "player_text": str(payload.get("player_text", "")),
        "npc_question": str(node_context.get("npc_question", "")),
        "recommended_expression": str(recommended_expression),
        "english_level": str(level_hint.get("english_level", "beginner")),
        "needs_hint": bool(level_hint.get("needs_hint", False)),
        "feedback_note": str(evaluation_summary.get("feedback_note", "")),
        "feedback_tag": str(evaluation_summary.get("main_feedback_tag", "")),
        "task_success": int(evaluation_summary.get("task_success", 0) or 0),
        "clarity": int(evaluation_summary.get("clarity", 0) or 0),
        "candidate_text": str(in_game_feedback.get("npc_recast_line_candidate", "")),
        "feedback_strategy": str(in_game_feedback.get("feedback_strategy", "")),
        "priority": str(in_game_feedback.get("priority", "low")),
        "blocks_progression": bool(in_game_feedback.get("blocks_progression", False)),
        "branch_type": str(branch.get("branch_type", "")),
        "next_node_id": str(branch.get("next_node_id", "")),
        "dialogue_purpose": str(dialogue_directive.get("purpose", "")),
        "tone_hint": str(dialogue_directive.get("tone_hint", "neutral")),
        "target_slot": str(dialogue_directive.get("target_slot", "")),
        "do_not_generate_npc_text": bool(
            dialogue_directive.get("do_not_generate_npc_text", False)
        ),
    }
