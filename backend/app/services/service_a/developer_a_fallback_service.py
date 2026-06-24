from typing import Any


# surface_goal 기반 디폴트 대사 매핑입니다.
SURFACE_GOAL_FALLBACK_TEXTS = {
    # Flight A (Friendly Seatmate)
    "respond_to_polite_request": "Sure, go ahead. Are you traveling to New York?",
    "ask_travel_purpose_smalltalk": "I see. What is the purpose of your visit?",
    "ask_stay_plan_smalltalk": "Got it. How long are you planning to stay in the US?",
    "check_clarification_or_ask_back": "Interesting. Where will you be staying?",
    "wrap_up_flight_smalltalk": "Okay. Do you have your arrival form ready? We will land soon.",
    
    # Flight B (Curious Seatmate)
    "ask_destination_after_arrival": "Where are you heading after we land?",
    "ask_companion_or_visit_plan": "Are you traveling alone or with someone?",
    "ask_accommodation_smalltalk": "Where are you staying in the city?",
    "ask_trip_activity_smalltalk": "What are you planning to do during your trip?",
    "close_curious_seatmate_smalltalk": "It was nice talking to you. Enjoy your time!",
    
    # Flight C (Travel Form Help)
    "respond_to_arrival_form_help_request": "Thanks. I'm filling out the arrival form — what brings you to New York?",
    "ask_first_time_entry": "Is this your first time visiting the US?",
    "explain_arrival_form_address_field": "You need to write your address here. Where will you stay?",
    "repair_hotel_hostel_confusion": "Is it a hotel or a hostel? You should write the exact name.",
    "close_travel_form_help_smalltalk": "You're all set now. Have a safe flight!",
    
    # Immigration 챕터 기존 키
    "request_passport_submission": "May I see your passport?",
    "ask_visit_purpose": "What is the purpose of your visit?",
    "ask_stay_duration": "How long will you stay in the United States?",
    "ask_stay_location": "Where will you stay in the United States?",
    "ask_return_ticket": "Do you have a return ticket to Korea?",
    "ask_gold_bag_contents_and_declaration": "Do you have anything to declare?",
    "ask_declared_item_purpose": "What is the purpose of this declared item?",
    "ask_packed_bag_ownership": "Is this your bag?",
    "confirm_immigration_clearance_transition": "Alright, here is your passport. Enjoy your stay.",
    "complete_immigration_clearance_transition": "All cleared.",

    # 신규 입국심사 9개 키
    "ask_long_stay_reason": "Why are you staying for so long?",
    "ask_hotel_reservation": "Do you have a hotel reservation?",
    "ask_hotel_choice_reason": "Why did you choose this hotel?",
    "ask_travel_itinerary": "What is your travel itinerary?",
    "ask_first_visit": "Is this your first visit to the United States?",
    "ask_occupation": "What is your occupation?",
    "ask_cash_amount": "How much cash are you carrying?",
    "ask_trip_payment_source": "Who is paying for your trip?",
    "ask_denied_entry_history": "Have you ever been denied entry?",
    
    # Baggage Desk 챕터
    "report_missing_bag_at_service_desk": "Hi, how can I help you today?",
    "ask_claim_tag_or_ticket": "Sure. I can look that up for you.",
    "confirm_carousel_search": "Let me check the baggage belt details.",
    "redirect_to_customs_hold_area": "I'm sorry, but we don't have it here. It seems your bag is held in the customs area. You must go there.",
    
    # Baggage Customs 챕터
    "customs_hold_explanation_before_unlock": "Please step forward.",
    "complete_customs_baggage_clearance": "Everything looks fine. You are good to go.",
    "complete_baggage_claim_transition": "You're all set. Have a nice day.",
    
    # Chapter Transition
    "complete_flight_smalltalk_transition": "Great. Have a nice trip!",
    
    # Extra / Missing Scenario goals
    "estimate_user_travel_speaking_level": "Could I borrow your pen for this arrival form?",
    "closing_eviction": "Sir, since you cannot provide the details, we cannot complete the report.",
    "scenario_complete": "Thank you for playing Murphy's Trippin Alpha.",
    "summarize_alpha_result": "Your airport arrival scenario is complete. Let's review your result.",
}


def build_text_fallback(normalized: dict[str, Any]) -> dict[str, Any]:
    """대사 후보(Candidate Text)가 없거나 필터링 정책에 의해 차단된 경우, 안전한 기본 대화 텍스트(Text Fallback)를 빌드합니다."""
    surface_goal = normalized.get("dialogue_seed", {}).get("surface_goal") or ""
    transition_status = normalized.get("transition", {}).get("status") or ""
    next_action = normalized.get("next_action") or ""
    npc_role = normalized.get("npc_role", "")
    purpose = normalized.get("dialogue_purpose") or ""
    reason = "missing_or_blocked_candidate_text"
    social_context_text = _social_context_fallback_text(normalized)
    
    # 1. transition_status == complete_chapter 또는 next_action == COMPLETE_CHAPTER
    if transition_status == "complete_chapter" or next_action == "COMPLETE_CHAPTER":
        if npc_role == "seatmate":
            text = "Enjoy your trip!"
        elif npc_role == "immigration_officer":
            text = "All right, you're cleared."
        elif npc_role == "baggage_agent":
            text = "You're all set."
        elif npc_role == "security_officer":
            text = "You're all set. Have a nice day."
        else:
            text = "You're all set."
        reason = "complete_chapter_fallback"

    # 1.5. social context repair before generic smalltalk/slot fallback
    elif social_context_text:
        text = social_context_text
        reason = "social_context_fallback"
        
    # 2. purpose == "smalltalk_diagnostic"
    elif purpose == "smalltalk_diagnostic":
        import random
        generic_neutral_responses = [
            "I see. Tell me more about that.",
            "That sounds interesting. Go on.",
            "Oh, really? That's good to know.",
            "I understand. What else can you tell me?",
            "Interesting. Let's keep talking.",
            "Right, I get what you mean.",
            "I hear you. Let's move forward."
        ]
        text = random.choice(generic_neutral_responses)
        reason = "smalltalk_diagnostic_fallback"
        
    # 3. surface_goal in SURFACE_GOAL_FALLBACK_TEXTS
    elif surface_goal in SURFACE_GOAL_FALLBACK_TEXTS:
        text = SURFACE_GOAL_FALLBACK_TEXTS[surface_goal]
        reason = f"surface_goal_{surface_goal}"
        
    # 4. surface_goal == "explain_random_customs_item" 특수
    elif surface_goal == "explain_random_customs_item":
        random_item = normalized.get("random_customs_item") or ""
        if random_item:
            text = f"What is this {random_item} in your bag?"
        else:
            text = "What is inside this package?"
        reason = "explain_random_customs_item"
        
    # 5. assigned_visit_location / random_customs_item seeded
    elif normalized.get("assigned_visit_location", "").strip():
        assigned_visit_location = normalized.get("assigned_visit_location", "").strip()
        text = f"{assigned_visit_location}? Tell me more about that."
        reason = "suspicion_visit_location_seeded"
    elif normalized.get("random_customs_item", "").strip():
        random_item = normalized.get("random_customs_item", "").strip()
        text = f"{random_item}? What is this for?"
        reason = "suspicion_customs_item_seeded"
        
    # 6. target_slot 기반
    elif normalized.get("target_slot") == "stay_duration":
        text = "Okay. How long will you stay?"
        reason = "stay_duration_fallback"
        
    # 7. silently default 금지: surface_goal이 비어 있지 않은데도 매핑이 없으면 KeyError
    else:
        if surface_goal:
            raise KeyError(f"unknown surface_goal: {surface_goal}")
        text = "Okay. Please continue."
        reason = "default_text_fallback"

    # 플레이어에게 제시될 한국어 피드백(Feedback) 내용을 가져오거나 기본 오류 안내 문구로 보정합니다.
    default_feedback = "의미는 전달됐습니다. 조금 더 자연스럽게 말해 봅시다."
    if purpose == "smalltalk_diagnostic":
        default_feedback = "자유롭게 스몰토크를 이어가고 있습니다. 계속 대화를 나누어 보세요."
    elif npc_role == "seatmate":
        default_feedback = "친절하게 답변해 주었어요. 더 자연스럽게 표현해 볼까요?"
    elif npc_role in {"customs_officer", "security_officer"}:
        default_feedback = "세관 질문에 적절히 대답했어요. 더 명확하게 표현해 볼까요?"
        
    feedback_kr = (
        normalized.get("feedback_note")
        or default_feedback
    )

    npc_id = normalized.get("npc_id")
    from backend.app.services.service_a.npc_roster_service import resolve_npc_profile
    npc_profile = resolve_npc_profile(npc_id)
    speaker = npc_profile.display_name

    return {
        "speaker": speaker,
        "npc_text": text,
        "text": text,
        "feedback_kr": feedback_kr,
        "tone": "formal_neutral",
        "animation": "move",
        # 폴백이 사용되었음을 명시하고 디버깅용 추적 사유(Reason)를 첨부합니다.
        "fallback": {
            "used": True,
            "reason": reason,
            "branch_type": normalized.get("branch_type"),
            "next_node_id": normalized.get("next_node_id"),
        },
    }


def _social_context_fallback_text(normalized: dict[str, Any]) -> str:
    social_context = normalized.get("social_context") or {}
    if not isinstance(social_context, dict):
        return ""
    obligation_status = str(social_context.get("obligation_status") or "")
    if obligation_status not in {"open", "ignored", "unclear"}:
        return ""

    pending_obligation = str(social_context.get("pending_social_obligation") or "")
    conversation_move = str(social_context.get("conversation_move") or "")
    scene_norm = str(social_context.get("scene_norm") or "")
    branch_reason = str(normalized.get("branch_reason") or "")
    surface_goal = str((normalized.get("dialogue_seed") or {}).get("surface_goal") or "")

    if pending_obligation == "seatmate_pen_request":
        if conversation_move == "repeated_greeting" or "repeated_greeting" in branch_reason:
            return "Are you playing with me? I still need your answer. Could I borrow your pen?"
        return "Hi. I mean, could I borrow your pen for this form?"

    fallback_question = SURFACE_GOAL_FALLBACK_TEXTS.get(surface_goal, "").strip()
    if scene_norm == "institutional_check" and fallback_question:
        return f"I need you to answer the question, please. {fallback_question}"
    if scene_norm == "service_recovery" and fallback_question:
        return f"No worries. I still need that detail so I can help. {fallback_question}"
    if fallback_question:
        return f"Let me ask that again. {fallback_question}"
    return ""


def build_audio_fallback(provider: str, voice_id: str, reason: str) -> dict[str, Any]:
    """TTS 음성 합성 생성 실패 시, 개발자 C 오케스트레이터가 처리 가능하도록 사후 처리를 돕는 음성 폴백 메타데이터(Audio Fallback Metadata)를 빌드합니다."""
    return {
        "provider": provider,
        "voice_id": voice_id,
        "audio_path": None,
        "audio_url": None,
        "sample_rate": None,
        "format": "wav",
        "status": "failed", # 음성 합성 상태를 'failed'로 마크하여 클라이언트에서 알 수 있게 합니다.
        "fallback": {"used": True, "reason": reason},
    }
