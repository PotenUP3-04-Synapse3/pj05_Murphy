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
    "long_stay_reason": "The reason for a long stay is {value}.",
    "hotel_reservation_status": "The hotel reservation status is {value}.",
    "hotel_choice_reason": "The reason for choosing this hotel is {value}.",
    "itinerary_status": "The itinerary status is {value}.",
    "first_visit_status": "The first visit status is {value}.",
    "occupation": "The occupation is {value}.",
    "cash_amount": "The cash amount is {value}.",
    "payment_source": "The trip payment source is {value}.",
    "denied_entry_status": "The denied entry history status is {value}."
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
    ],
    "long_stay_reason": [
        "why are you staying so long?",
        "what is the reason for your extended stay?",
        "why do you need to stay that long?"
    ],
    "hotel_reservation_status": [
        "do you have a hotel reservation?",
        "is your hotel booking confirmed?",
        "can you show me your hotel booking?"
    ],
    "hotel_choice_reason": [
        "why did you choose this hotel?",
        "what is the reason for selecting this hotel?",
        "why stay at this specific hotel?"
    ],
    "itinerary_status": [
        "do you have a travel itinerary?",
        "is your itinerary confirmed?",
        "what is your travel plan?"
    ],
    "first_visit_status": [
        "is this your first visit?",
        "have you visited the united states before?",
        "is this your first time visiting?"
    ],
    "occupation": [
        "what is your occupation?",
        "what is your job?",
        "what do you do for a living?"
    ],
    "cash_amount": [
        "how much cash are you carrying?",
        "how much money do you have?",
        "how much cash do you have with you?"
    ],
    "payment_source": [
        "who is paying for your trip?",
        "what is your source of funding?",
        "how are you funding this trip?"
    ],
    "denied_entry_status": [
        "have you ever been denied entry?",
        "have you been refused entry to the united states?",
        "any history of denied entry?"
    ]
}


def build_session_context_card(
    normalized: dict[str, Any],
    npc_profile: Any,
    payload: dict[str, Any],
    npc_memory: dict[str, Any] | None = None,
    strict_unknown_slot: bool = False
) -> dict[str, Any]:
    """dialogue_history 혹은 자체 NPC 단기 메모리를 바탕으로 LLM 대사 생성 시 참고할 
    구조화된 '세션 컨텍스트 카드' 사전을 작성합니다.
    """
    import logging
    logger = logging.getLogger("backend.app.services.service_a")

    # 메모리가 존재하고 유효한 정보가 적재되어 있다면 메모리 우선 사용
    use_memory = False
    if npc_memory:
        turn_buffer = npc_memory.get("turn_buffer") or []
        accumulated_slots = npc_memory.get("accumulated_slots") or {}
        if turn_buffer or accumulated_slots:
            use_memory = True
            
    if use_memory:
        assert npc_memory is not None
        turn_buffer = npc_memory.get("turn_buffer") or []
        accumulated_slots = npc_memory.get("accumulated_slots") or {}
        
        # 현재 페이로드 상에 들어있는 slots 보강
        curr_filled = normalized.get("dialogue_seed", {}).get("filled_slots") or {}
        for k, v in curr_filled.items():
            if v:
                accumulated_slots[k] = v
                
        confirmed_facts: list[str] = []
        forbidden_repeat_questions: list[str] = []
        
        for slot_name, slot_val in accumulated_slots.items():
            if slot_name not in SLOT_TO_PHRASE:
                if strict_unknown_slot:
                    raise ValueError(f"unknown slot in session memory: {slot_name}")
                logger.warning(f"unknown slot in session memory: {slot_name}")
                continue
                
            # 자연어 설명 추가
            phrase_tpl = SLOT_TO_PHRASE[slot_name]
            confirmed_facts.append(phrase_tpl.format(value=slot_val))
            
            # 금지 질문 리스트 수집
            questions = SLOT_TO_FORBIDDEN_QUESTIONS.get(slot_name) or []
            for q in questions:
                if q not in forbidden_repeat_questions:
                    forbidden_repeat_questions.append(q)
                    
        # 2. 플레이어 마지막 발화에서 명사/단어 open_hooks 추출
        player_text = normalized.get("player_text") or ""
        if not player_text and turn_buffer:
            player_text = turn_buffer[-1].get("player_text") or ""
            
        open_hooks: list[str] = []
        if player_text:
            cleaned = re.sub(r'[^a-zA-Z]', ' ', player_text.lower())
            words = cleaned.split()
            for w in words:
                if len(w) >= 3 and w not in open_hooks:
                    if w not in ["the", "and", "for", "you", "are", "have", "this", "that", "stay", "with"]:
                        open_hooks.append(w)
        open_hooks = open_hooks[:5]
        
        # 3. 직전 NPC 발화의 의도
        last_npc_intent = npc_memory.get("last_npc_intent") or ""
        
        # 4. 최근 8턴 요약 리스트
        recent_turns_compact: list[str] = []
        sub_buffer = turn_buffer[-8:]
        total_turns = len(sub_buffer)
        for idx, turn in enumerate(sub_buffer):
            if turn is None:
                continue
            t_num = total_turns - idx
            p_text = turn.get("player_text") or ""
            n_text = turn.get("npc_text") or ""
            filled = turn.get("filled_slots") or {}
            recent_turns_compact.append(f"T-{t_num} player='{p_text}' npc='{n_text}' filled={filled}")
            
        # 5. 토픽 스레드
        topic_thread: list[str] = []
        for turn in turn_buffer:
            if turn is None:
                continue
            sg = turn.get("surface_goal")
            if sg:
                if sg not in topic_thread:
                    topic_thread.append(sg)
            else:
                n_preview = turn.get("npc_text") or ""
                n_words = re.sub(r'[^a-zA-Z]', ' ', n_preview.lower()).split()
                for w in n_words:
                    if len(w) >= 4 and w not in ["stay", "have", "with", "your", "that", "this", "what", "where"]:
                        if w not in topic_thread:
                            topic_thread.append(w)
        topic_thread = list(dict.fromkeys(topic_thread))[:10]
        
    else:
        # 기존 dialogue_history 기반 (cold-start fallback)
        dialogue_history = normalized.get("dialogue_history") or []
        
        accumulated_slots = {}
        for turn in dialogue_history:
            if turn is None:
                continue
            filled = turn.get("filled_slots") or {}
            for k, v in filled.items():
                if v:
                    accumulated_slots[k] = v
                    
        curr_filled = normalized.get("dialogue_seed", {}).get("filled_slots") or {}
        for k, v in curr_filled.items():
            if v:
                accumulated_slots[k] = v
                
        confirmed_facts = []
        forbidden_repeat_questions = []
        
        for slot_name, slot_val in accumulated_slots.items():
            if slot_name not in SLOT_TO_PHRASE:
                if strict_unknown_slot:
                    raise ValueError(f"unknown slot in session memory: {slot_name}")
                logger.warning(f"unknown slot in session memory: {slot_name}")
                continue
            phrase_tpl = SLOT_TO_PHRASE[slot_name]
            confirmed_facts.append(phrase_tpl.format(value=slot_val))
            
            questions = SLOT_TO_FORBIDDEN_QUESTIONS.get(slot_name) or []
            for q in questions:
                if q not in forbidden_repeat_questions:
                    forbidden_repeat_questions.append(q)
                    
        player_text = normalized.get("player_text") or ""
        if not player_text and dialogue_history:
            last_turn = dialogue_history[-1]
            if last_turn is not None:
                player_text = last_turn.get("player_text_preview") or ""
            
        open_hooks = []
        if player_text:
            cleaned = re.sub(r'[^a-zA-Z]', ' ', player_text.lower())
            words = cleaned.split()
            for w in words:
                if len(w) >= 3 and w not in open_hooks:
                    if w not in ["the", "and", "for", "you", "are", "have", "this", "that", "stay", "with"]:
                        open_hooks.append(w)
        open_hooks = open_hooks[:5]
        
        last_npc_intent = ""
        if dialogue_history:
            last_turn = dialogue_history[-1]
            if last_turn is not None:
                intent = last_turn.get("surface_goal")
                if intent:
                    last_npc_intent = intent
                else:
                    npc_preview = last_turn.get("npc_text_preview") or ""
                    if npc_preview:
                        sentences = re.split(r'[.!?]', npc_preview)
                        last_npc_intent = sentences[0].strip() if sentences else ""
                    
        recent_turns_compact = []
        total_turns = len(dialogue_history)
        for idx, turn in enumerate(dialogue_history):
            if turn is None:
                continue
            t_num = total_turns - idx
            p_text = turn.get("player_text_preview") or ""
            n_text = turn.get("npc_text_preview") or ""
            filled = turn.get("filled_slots") or {}
            recent_turns_compact.append(f"T-{t_num} player='{p_text}' npc='{n_text}' filled={filled}")
            
        topic_thread = []
        for turn in dialogue_history:
            if turn is None:
                continue
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
