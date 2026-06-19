from typing import Any
import re

# 슬롯 필드명과 자연어 설명 맵핑
SLOT_TO_PHRASE: dict[str, str] = {
    "visit_purpose": "The purpose of visit is {value}.",
    "stay_duration": "The stay duration is {value}.",
    "stay_location": "The stay location is {value}.",
    "declared_item": "The declared customs item is {value}.",
    "item_purpose": "The purpose of the declared item is {value}.",
    "packed_bag_ownership": "The baggage ownership is confirmed as {value}.",
    "claim_tag": "The baggage claim tag is confirmed as {value}.",
}

# 이미 수집된 슬롯에 대해 다시 물어보면 안 되는 질문의 패턴
SLOT_TO_FORBIDDEN_QUESTIONS: dict[str, list[str]] = {
    "visit_purpose": [
        "what is the purpose of your visit?",
        "what brings you to the united states?",
        "why are you visiting?",
        "are you here for business or pleasure?"
    ],
    "stay_duration": [
        "how long will you stay?",
        "how long will you stay in the united states?",
        "how many days do you plan to stay?",
        "what is the duration of your stay?"
    ],
    "stay_location": [
        "where will you stay?",
        "where will you stay in the united states?",
        "what is your address in the united states?",
        "where are you staying?"
    ],
    "declared_item": [
        "do you have anything to declare?",
        "what is inside this package?",
        "what is this item?"
    ],
    "item_purpose": [
        "what is the purpose of this declared item?",
        "why did you bring this item?"
    ],
    "packed_bag_ownership": [
        "is this your bag?",
        "is this baggage yours?",
        "do you own this bag?"
    ]
}


def build_session_context_card(normalized: dict[str, Any], npc_profile: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """dialogue_history와 정규화된 페이로드를 바탕으로 LLM 대사 생성 시 참고할 
    구조화된 '세션 컨텍스트 카드' 사전을 작성합니다.
    """
    dialogue_history = normalized.get("dialogue_history") or []
    
    # 1. 누적 슬롯 획득 및 자연어 변환
    accumulated_slots: dict[str, Any] = {}
    for turn in dialogue_history:
        filled = turn.get("filled_slots") or {}
        for k, v in filled.items():
            if v:
                accumulated_slots[k] = v

    # 현재 페이로드 상에 들어있는 slots 보강
    curr_filled = normalized.get("dialogue_seed", {}).get("filled_slots") or {}
    for k, v in curr_filled.items():
        if v:
            accumulated_slots[k] = v
            
    confirmed_facts: list[str] = []
    forbidden_repeat_questions: list[str] = []
    
    for slot_name, slot_val in accumulated_slots.items():
        # 자연어 설명 추가
        phrase_tpl = SLOT_TO_PHRASE.get(slot_name, f"{slot_name} is {slot_val}.")
        confirmed_facts.append(phrase_tpl.format(value=slot_val))
        
        # 금지 질문 리스트 수집
        questions = SLOT_TO_FORBIDDEN_QUESTIONS.get(slot_name) or []
        for q in questions:
            if q not in forbidden_repeat_questions:
                forbidden_repeat_questions.append(q)

    # 2. 플레이어 마지막 발화에서 명사/단어 open_hooks 추출
    player_text = normalized.get("player_text") or ""
    if not player_text and dialogue_history:
        player_text = dialogue_history[-1].get("player_text_preview") or ""
        
    open_hooks: list[str] = []
    if player_text:
        # 영문 알파벳 단어만 공백으로 분리
        cleaned = re.sub(r'[^a-zA-Z]', ' ', player_text.lower())
        words = cleaned.split()
        for w in words:
            # 3글자 이상이며 중복되지 않는 단어 필터링
            if len(w) >= 3 and w not in open_hooks:
                # 일반적인 영어 불용어 중 일부 제외 (terse filtering)
                if w not in ["the", "and", "for", "you", "are", "have", "this", "that", "stay", "with"]:
                    open_hooks.append(w)
    open_hooks = open_hooks[:5]

    # 3. 직전 NPC 발화의 의도(last_npc_intent)
    last_npc_intent = ""
    if dialogue_history:
        last_turn = dialogue_history[-1]
        intent = last_turn.get("surface_goal")
        if intent:
            last_npc_intent = intent
        else:
            npc_preview = last_turn.get("npc_text_preview") or ""
            if npc_preview:
                sentences = re.split(r'[.!?]', npc_preview)
                last_npc_intent = sentences[0].strip() if sentences else ""

    # 4. 최근 5턴 요약 리스트(recent_turns_compact)
    recent_turns_compact: list[str] = []
    total_turns = len(dialogue_history)
    for idx, turn in enumerate(dialogue_history):
        t_num = total_turns - idx
        p_text = turn.get("player_text_preview") or ""
        n_text = turn.get("npc_text_preview") or ""
        filled = turn.get("filled_slots") or {}
        recent_turns_compact.append(f"T-{t_num} player='{p_text}' npc='{n_text}' filled={filled}")

    # 5. 토픽 스레드(topic_thread)
    topic_thread: list[str] = []
    for turn in dialogue_history:
        sg = turn.get("surface_goal")
        if sg:
            if sg not in topic_thread:
                topic_thread.append(sg)
        else:
            n_preview = turn.get("npc_text_preview") or ""
            n_words = re.sub(r'[^a-zA-Z]', ' ', n_preview.lower()).split()
            for w in n_words:
                if len(w) >= 4 and w not in ["stay", "have", "with", "your", "that", "this", "what", "where"]:
                    if w not in topic_thread:
                        topic_thread.append(w)
    topic_thread = list(dict.fromkeys(topic_thread))[:10]

    return {
        "confirmed_facts": confirmed_facts,
        "forbidden_repeat_questions": forbidden_repeat_questions,
        "open_hooks": open_hooks,
        "last_npc_intent": last_npc_intent,
        "recent_turns_compact": recent_turns_compact,
        "topic_thread": topic_thread,
    }
