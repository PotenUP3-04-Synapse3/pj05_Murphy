# -*- coding: utf-8 -*-
"""
NPC 단기 메모리 서비스 (NPC Short Term Memory Service)
이 파일은 Developer A 소유이며, 각 (session_id, npc_id) 쌍으로 격리되고
N=20 슬라이딩 윈도우가 적용되는 NPC 단기 메모리의 읽기/쓰기 및
슬롯 매핑, 금지 질문 유도 등의 코어 로직을 구현합니다.
"""

from typing import Any
import logging

logger = logging.getLogger("backend.app.services.service_a.npc_short_term_memory_service")

# §0.4 Fail-fast 원칙에 따라, 필수 키 누락 시 silently default 대신 ValueError를 발생시킵니다.
def build_thread_id(session_id: str | None, npc_id: str | None) -> str:
    """
    (session_id, npc_id) 쌍을 이용해 격리된 메모리 세션을 구분하는 thread_id를 빌드합니다.
    session_id 또는 npc_id가 없거나 빈 값이면 ValueError를 던집니다. (Fail-fast)
    """
    if not session_id or not npc_id:
        raise ValueError("session_id and npc_id are required for memory isolation")
    return f"{session_id}:{npc_id}"


def empty_memory_state() -> dict[str, Any]:
    """
    초기화된 빈 메모리 상태를 반환합니다.
    """
    return {
        "turn_buffer": [],
        "accumulated_slots": {},
        "forbidden_questions": [],
        "last_npc_intent": None,
    }


def append_turn(
    memory: dict[str, Any],
    *,
    node_id: str | None,
    surface_goal: str | None,
    branch_type: str | None,
    player_text: str | None,
    npc_text: str | None,
    filled_slots: dict[str, Any] | None,
    npc_emotion: str | None,
) -> dict[str, Any]:
    """
    turn_buffer에 새 턴을 기록합니다.
    turn_buffer의 최대 크기는 N=20으로 제한되며, 이를 초과할 경우
    가장 오래된 턴부터 드롭됩니다. (N=20 슬라이딩 윈도우)
    """
    if memory is None:
        memory = empty_memory_state()

    turn_buffer = memory.setdefault("turn_buffer", [])
    
    new_turn = {
        "node_id": node_id,
        "surface_goal": surface_goal,
        "branch_type": branch_type,
        "player_text": player_text,
        "npc_text": npc_text,
        "filled_slots": filled_slots or {},
        "npc_emotion": npc_emotion,
    }
    turn_buffer.append(new_turn)

    # N=20 슬라이딩 윈도우 적용
    if len(turn_buffer) > 20:
        turn_buffer.pop(0)

    return memory


def merge_slots(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """
    기존 수집된 슬롯(existing)과 새로 들어온 슬롯(incoming)을 병합합니다.
    """
    merged = dict(existing)
    for k, v in (incoming or {}).items():
        if v is not None and v != "":
            merged[k] = v
    return merged


def derive_forbidden_questions(slots: dict[str, Any]) -> list[str]:
    """
    수집된 슬롯을 기반으로, 다시 물어보면 안 되는 질문들의 패턴을 유도하여 반환합니다.
    (session_context_card_service of SLOT_TO_FORBIDDEN_QUESTIONS 참조)
    """
    from backend.app.services.service_a.session_context_card_service import SLOT_TO_FORBIDDEN_QUESTIONS
    forbidden = []
    for slot_name, slot_val in slots.items():
        if slot_val:
            questions = SLOT_TO_FORBIDDEN_QUESTIONS.get(slot_name) or []
            for q in questions:
                if q not in forbidden:
                    forbidden.append(q)
    return forbidden


def clear_memory_state(memory: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    메모리 상태를 깨끗하게 비웁니다.
    """
    return empty_memory_state()
