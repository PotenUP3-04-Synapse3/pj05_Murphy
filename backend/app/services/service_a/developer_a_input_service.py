from typing import Any


def normalize_level_design_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """외부 레벨 디자인 에이전트(Level Design Agent)로부터 수신한 비정형 JSON 데이터를 개발자 A 컴포넌트 내부에서 다루기 편한 표준 사전(Dictionary) 구조로 정규화(Normalize)합니다."""
    node_context = payload.get("node_context") or {}
    evaluation_summary = payload.get("evaluation_summary") or {}
    level_hint = payload.get("level_hint") or {}
    in_game_feedback = payload.get("in_game_feedback") or {}
    branch = payload.get("branch") or {}
    dialogue_directive = payload.get("dialogue_directive") or {}
    
    # NPC 정보 및 Level Design 감정 데이터 파싱
    npc = payload.get("npc") or {}
    npc_id = npc.get("npc_id") or npc.get("id") or ""
    npc_role = npc.get("npc_role") or npc.get("role") or ""
    ld_emotion = payload.get("npc_emotion") or npc.get("npc_emotion") or npc.get("emotion") or ""

    # 플레이어에게 제시할 추천 표현(Recommended Expression)은 피드백 페이로드, 레벨 힌트, 노드 컨텍스트 순으로 우선순위(Priority)를 부여해 파싱합니다.
    recommended_expression = (
        in_game_feedback.get("recommended_expression")
        or level_hint.get("recommended_expression")
        or node_context.get("recommended_expression")
        or ""
    )

    return {
        "node_id": _optional_text(payload.get("node_id")),
        "player_text": _optional_text(payload.get("player_text")),
        "npc_id": _optional_text(npc_id),
        "npc_role": _optional_text(npc_role),
        "npc_emotion": _optional_text(ld_emotion),
        "npc_question": _optional_text(node_context.get("npc_question")),
        "recommended_expression": _optional_text(recommended_expression),
        "english_level": (
            _optional_text(level_hint.get("english_level"))
            or _optional_text(payload.get("player_profile", {}).get("tier"))
            or "beginner"
        ),
        "needs_hint": bool(level_hint.get("needs_hint", False)),
        "feedback_note": _optional_text(evaluation_summary.get("feedback_note")),
        "feedback_tag": _optional_text(evaluation_summary.get("main_feedback_tag")),
        "task_success": int(evaluation_summary.get("task_success", 0) or 0),
        "clarity": int(evaluation_summary.get("clarity", 0) or 0),
        # 개발자 B가 생성한 NPC 대사 후보 후보군(Candidate Text)을 추출합니다.
        "candidate_text": _optional_text(in_game_feedback.get("npc_recast_line_candidate")),
        "feedback_strategy": _optional_text(in_game_feedback.get("feedback_strategy")),
        "priority": _optional_text(in_game_feedback.get("priority")) or "low",
        # 여러 구성 요소에 혼재되어 들어올 수 있는 재시도 카운트(Retry Count)를 안전하게 정수로 통합 파싱합니다.
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
        "player_emotion": _optional_text(payload.get("understanding", {}).get("emotion")),  # 플레이어 원본 감정 상태 연동
        "dialogue_seed": payload.get("dialogue_seed") or {},
        "random_customs_item": _optional_text(
            payload.get("game_state", {}).get("random_customs_item")
            or payload.get("random_customs_item")
        ),
        "transition": payload.get("transition") or {},
        "next_action": _optional_text(payload.get("next_action") or branch.get("next_action")),
    }


def _optional_text(value: Any) -> str:
    """Null 값이나 정의되지 않은 입력을 안전하게 빈 문자열(String)로 변환해 줍니다."""
    if value is None:
        return ""
    return str(value)


def _optional_int(value: Any) -> int:
    """Null 또는 문자열 등 비정형 형태로 입력될 수 있는 정수형 값을 검증하여 정수(Integer) 데이터로 변환합니다."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return 0
