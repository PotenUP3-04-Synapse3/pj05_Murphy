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
    "respond_to_arrival_form_help_request": "Sure, I can help you with the form. What do you need?",
    "ask_first_time_entry": "Is this your first time visiting the US?",
    "explain_arrival_form_address_field": "You need to write your address here. Where will you stay?",
    "repair_hotel_hostel_confusion": "Is it a hotel or a hostel? You should write the exact name.",
    "close_travel_form_help_smalltalk": "You're all set now. Have a safe flight!",
    
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
}


def build_text_fallback(normalized: dict[str, Any]) -> dict[str, Any]:
    """대사 후보(Candidate Text)가 없거나 필터링 정책에 의해 차단된 경우, 안전한 기본 대화 텍스트(Text Fallback)를 빌드합니다."""
    # dialogue_seed의 surface_goal을 가장 먼저 확인하여 대사를 다변화합니다.
    surface_goal = normalized.get("dialogue_seed", {}).get("surface_goal") or ""
    transition_status = normalized.get("transition", {}).get("status") or ""
    next_action = normalized.get("next_action") or ""
    npc_role = normalized.get("npc_role", "")
    
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
    elif surface_goal == "explain_random_customs_item":
        random_item = normalized.get("random_customs_item") or ""
        if random_item:
            text = f"What is this {random_item} in your bag?"
        else:
            text = "What is inside this package?"
    elif surface_goal in SURFACE_GOAL_FALLBACK_TEXTS:
        text = SURFACE_GOAL_FALLBACK_TEXTS[surface_goal]
    else:
        target_slot = normalized.get("target_slot")
        # 대화 목표 슬롯(Target Slot)이 체류 기간(Stay Duration)인지 식별하여 템플릿(Template) 대사를 다변화합니다.
        if target_slot == "stay_duration":
            text = "Okay. How long will you stay?"
        else:
            text = "Okay. Please continue."

    # 플레이어에게 제시될 한국어 피드백(Feedback) 내용을 가져오거나 기본 오류 안내 문구로 보정합니다.
    default_feedback = "의미는 전달됐습니다. 조금 더 자연스럽게 말해 봅시다."
    if npc_role == "seatmate":
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
            "reason": "missing_or_blocked_candidate_text",
            "branch_type": normalized.get("branch_type"),
            "next_node_id": normalized.get("next_node_id"),
        },
    }


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
