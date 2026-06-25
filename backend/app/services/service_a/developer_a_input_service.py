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
    # 단, 오케스트레이션 단계에서 A/C로 넘어가기 전에 blank 처리되므로 실제 운영시에는 비어 있으며, 테스트 환경 등 명시적 제공 시에만 검출용으로 작동합니다.
    recommended_expression = (
        in_game_feedback.get("recommended_expression")
        or level_hint.get("recommended_expression")
        or node_context.get("recommended_expression")
        or ""
    )

    # 억까 장소 및 수화물 관련 데이터 파싱
    random_item_obj = (
        payload.get("game_state", {}).get("random_customs_item")
        or (payload.get("dialogue_seed") or {}).get("random_customs_item")
        or payload.get("random_customs_item")
        or {}
    )
    if isinstance(random_item_obj, str):
        random_item_name = random_item_obj
        random_item_difficulty = 0
        random_item_suspicion_reason = ""
    elif isinstance(random_item_obj, dict):
        random_item_name = random_item_obj.get("item_name") or random_item_obj.get("item_id") or ""
        random_item_difficulty = random_item_obj.get("difficulty") or 0
        random_item_suspicion_reason = random_item_obj.get("suspicion_reason") or ""
    else:
        random_item_name = ""
        random_item_difficulty = 0
        random_item_suspicion_reason = ""

    dialogue_seed = payload.get("dialogue_seed") or {}
    game_state = payload.get("game_state") or {}
    understanding = payload.get("understanding") or {}
    social_context = understanding.get("social_context") or payload.get("social_context") or {}
    if social_context is not None and hasattr(social_context, "model_dump"):
        social_context = social_context.model_dump()
    social_context = dict(social_context) if isinstance(social_context, dict) else {}
    pragmatic_context = understanding.get("pragmatic_context") or payload.get("pragmatic_context") or {}
    if pragmatic_context is not None and hasattr(pragmatic_context, "model_dump"):
        pragmatic_context = pragmatic_context.model_dump()
    pragmatic_context = dict(pragmatic_context) if isinstance(pragmatic_context, dict) else {}
    branch_reason = _optional_text(branch.get("branch_reason"))
    _apply_social_lifecycle_from_branch(social_context, branch_reason)

    suspicion_scope = dialogue_seed.get("suspicion_scope") or "none"
    dialogue_history = list(dialogue_seed.get("dialogue_history") or [])

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
        "branch_reason": branch_reason,
        "dialogue_purpose": _optional_text(dialogue_directive.get("purpose")),
        "tone_hint": _optional_text(dialogue_directive.get("tone_hint")) or "neutral",
        "target_slot": _optional_text(dialogue_directive.get("target_slot")),
        "player_emotion": _optional_text(understanding.get("emotion")),  # 플레이어 원본 감정 상태 연동
        "social_context": social_context,
        "pragmatic_context": pragmatic_context,
        "risk_tags": list(understanding.get("risk_tags") or []),
        "risk_delta": _optional_int(understanding.get("risk_delta")),
        "dialogue_seed": dialogue_seed,
        "random_customs_item": _optional_text(random_item_name),
        "random_customs_item_difficulty": int(random_item_difficulty),
        "random_customs_item_suspicion_reason": _optional_text(random_item_suspicion_reason),
        "assigned_visit_location": _optional_text(
            dialogue_seed.get("assigned_visit_location")
            or game_state.get("assigned_visit_location")
        ),
        "assigned_visit_location_ko": _optional_text(
            dialogue_seed.get("assigned_visit_location_ko")
            or game_state.get("assigned_visit_location_ko")
        ),
        "visit_location_difficulty": int(
            dialogue_seed.get("visit_location_difficulty")
            or game_state.get("visit_location_difficulty")
            or 0
        ),
        "visit_location_suspicion_reason": _optional_text(
            dialogue_seed.get("visit_location_suspicion_reason")
            or game_state.get("visit_location_suspicion_reason")
        ),
        "transition": payload.get("transition") or {},
        "next_action": _optional_text(payload.get("next_action") or branch.get("next_action")),
        "suspicion_scope": _optional_text(suspicion_scope),
        "dialogue_history": dialogue_history,
    }


def _optional_text(value: Any) -> str:
    """Null 값이나 정의되지 않은 입력을 안전하게 빈 문자열(String)로 변환해 줍니다."""
    if value is None:
        return ""
    return str(value)


def _apply_social_lifecycle_from_branch(
    social_context: dict[str, Any],
    branch_reason: str,
) -> None:
    if not branch_reason:
        return

    lifecycle = ""
    should_close_hook = False
    if "social_pause_closed" in branch_reason or "engagement_give_space" in branch_reason:
        lifecycle = "paused_or_closed"
        should_close_hook = True
    elif "engagement_check" in branch_reason:
        lifecycle = "engagement_checked"
        should_close_hook = True
    elif "social_obligation_dropped" in branch_reason:
        lifecycle = "dropped"
        should_close_hook = True
    elif "repeated_social_repair" in branch_reason:
        lifecycle = "repaired_once"
    elif "social_obligation_open" in branch_reason:
        lifecycle = "open"

    if lifecycle:
        social_context["social_obligation_lifecycle"] = lifecycle
    if should_close_hook:
        _append_unique(social_context, "closed_hooks", "seatmate_pen_request")
        _append_unique(social_context, "do_not_reopen", "seatmate_pen_request")


def _append_unique(target: dict[str, Any], key: str, value: str) -> None:
    existing = target.get(key)
    values = list(existing) if isinstance(existing, list) else []
    if value not in values:
        values.append(value)
    target[key] = values


def _optional_int(value: Any) -> int:
    """Null 또는 문자열 등 비정형 형태로 입력될 수 있는 정수형 값을 검증하여 정수(Integer) 데이터로 변환합니다."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return 0
