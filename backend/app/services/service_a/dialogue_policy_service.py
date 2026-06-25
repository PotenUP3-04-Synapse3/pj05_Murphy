from dataclasses import dataclass
from typing import Any, Literal

from backend.app.services.service_a.npc_emotion_service import NPCEmotionState
from backend.app.services.service_a.player_language_profile_service import PlayerLanguageProfile
from backend.app.services.service_a.session_context_card_service import OPEN_HOOK_STOPLIST

# NPC가 다음에 취할 수 있는 대화 액션(Dialogue Action) 유형을 정의하는 리터럴(Literal) 타입입니다.
DialogueAction = Literal["recast_and_advance", "ask_retry", "continue"]


# 플레이어의 프로필과 NPC의 감정 상태를 기반으로 조립된 NPC 대화 생성 정책 사양서 클래스(Class)입니다.
@dataclass(frozen=True)
class DialoguePolicy:
    action: DialogueAction       # NPC가 취할 대화 액션 (예: 다음 진행, 재질문)
    tone: str                    # 대사 생성 시 LLM에 요구할 목소리 톤(Tone)
    max_sentence_count: int      # 생성할 대사 텍스트의 최대 문장 개수(Sentence Count)
    use_recast: bool             # 플레이어의 오류를 자연스럽게 수정해 다시 말해줄(Recast)지 여부
    add_officer_ack: bool        # 플레이어의 답변에 대해 격려 또는 확인 어구(Alright, Okay 등)를 붙일지 여부
    next_question_style: str     # 다음에 던질 질문의 스타일(Style) (예: 단답형, 자연스러운 대화형)


def build_dialogue_policy(
    normalized: dict[str, Any],
    profile: PlayerLanguageProfile,
    emotion_state: NPCEmotionState,
) -> DialoguePolicy:
    """플레이어의 영어 학습 수준(Profile) 및 NPC의 감정 상태(Emotion State)를 분석하여 최종적인 대사 생성 정책(Dialogue Policy)을 결정합니다."""
    branch_type = str(normalized.get("branch_type", ""))
    feedback_strategy = str(normalized.get("feedback_strategy", ""))

    # 감정이 심각한 경고 상태(warning_official)인 경우의 생성 정책입니다. (가장 엄격함)
    if emotion_state.emotion == "warning_official":
        return DialoguePolicy(
            action="ask_retry",
            tone="formal_warning",
            max_sentence_count=1,
            use_recast=False,
            add_officer_ack=False,
            next_question_style="direct_warning",
        )

    # 감정이 엄격한 상태(stern_official)인 경우의 생성 정책입니다.
    if emotion_state.emotion == "stern_official":
        return DialoguePolicy(
            action="ask_retry",
            tone="formal_stern",
            max_sentence_count=1,
            use_recast=False,
            add_officer_ack=False,
            next_question_style="direct_repeat_stern",
        )

    # 대화 분기가 재시도(Retry) 또는 실패(Fail)인 경우의 일반 정책입니다.
    if branch_type in {"retry", "fail"}:
        return DialoguePolicy(
            action="ask_retry",
            tone="formal_firm",
            max_sentence_count=2,
            use_recast=False,
            add_officer_ack=False,
            next_question_style="direct_repeat",
        )

    # 대화가 성공적으로 흘러가는 경우, 플레이어의 수준에 맞춰 친절도를 유연하게 조율하여 반환합니다.
    return DialoguePolicy(
        action="recast_and_advance" if feedback_strategy == "recast" else "continue",
        tone=_tone_from_emotion(emotion_state),
        max_sentence_count=2 if profile.complexity == "simple" else 3,
        use_recast=feedback_strategy == "recast",
        add_officer_ack=profile.feedback_depth != "minimal",
        next_question_style="short" if profile.complexity == "simple" else "natural",
    )


def _tone_from_emotion(emotion_state: NPCEmotionState) -> str:
    """NPC의 감정 상태(Emotion State)를 기반으로 발화 시 적절한 음성 톤(Dialogue Tone)을 추천해 줍니다."""
    if emotion_state.emotion == "warning_official":
        return "formal_warning"
    if emotion_state.emotion == "stern_official":
        return "formal_stern"
    if emotion_state.emotion == "firm_official":
        return "formal_firm"
    if emotion_state.emotion == "patient":
        return "formal_supportive"
    return "formal_neutral"


# surface_goal에 대응하는 룰베이스 다음 질문 템플릿 맵입니다.
SURFACE_GOAL_QUESTIONS = {
    # Flight 챕터
    "respond_to_polite_request": "Are you visiting New York for a trip?",
    "ask_travel_purpose_smalltalk": "Are you visiting New York for a trip?",
    "ask_stay_plan_smalltalk": "How long will you stay?",
    "check_clarification_or_ask_back": "Where will you stay?",
    "wrap_up_flight_smalltalk": "Do you have your arrival form?",
    
    # Immigration 챕터
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
    
    # 신규 입국심사 9개 surface_goal
    "ask_long_stay_reason": "Why are you staying for so long?",
    "ask_hotel_reservation": "Do you have a hotel reservation?",
    "ask_hotel_choice_reason": "Why did you choose this hotel?",
    "ask_travel_itinerary": "What is your travel itinerary?",
    "ask_first_visit": "Is this your first visit to the United States?",
    "ask_occupation": "What is your occupation?",
    "ask_cash_amount": "How much cash are you carrying?",
    "ask_trip_payment_source": "Who is paying for your trip?",
    "ask_denied_entry_history": "Have you ever been denied entry?",
    
    # Baggage 챕터
    "report_missing_bag_at_service_desk": "Do you have your baggage claim tag or ticket?",
    "ask_claim_tag_or_ticket": "May I see your baggage claim tag?",
    "confirm_carousel_search": "Did you check the carousel carefully before coming to the desk?",
    "redirect_to_customs_hold_area": "Please go to the customs hold area. Understood?",
    "customs_hold_explanation_before_unlock": "Please check the contents of the suitcase now.",
    "explain_random_customs_item": "Can you explain what this item is and why it is in your suitcase?",
    "complete_customs_baggage_clearance": "You're cleared now. You may take your suitcase and exit the airport.",
    "complete_baggage_claim_transition": "Chapter complete.",
    
    # Extra / Missing
    "complete_flight_smalltalk_transition": "Chapter complete.",
    "estimate_user_travel_speaking_level": "Could I borrow your pen for this arrival form?",
    "closing_eviction": "Sir, since you cannot provide the details, we cannot complete the report.",
    "scenario_complete": "Thank you for playing Murphy's Trippin Alpha.",
    "summarize_alpha_result": "Your airport arrival scenario is complete. Let's review your result."
}


def synthesize_fallback_next_question(
    fallback_text: str,
    surface_goal: str,
    open_hooks: list[str] | None = None,
    branch_type: str | None = None,
) -> str:
    """LLM 실패 시 사용될 폴백 텍스트(Fallback Text) 뒤에 surface_goal에 따른 룰베이스 다음 질문을 합성합니다."""
    question = SURFACE_GOAL_QUESTIONS.get(surface_goal)
    if not question:
        return fallback_text
    _ = open_hooks
    
    # 의미적 중복 점검 (예: "What is your job"이 있으면 "What is your occupation" 합성 생략)
    fallback_lower = fallback_text.lower()
    intent_options = RETRY_PARAPHRASES.get(surface_goal, [])
    all_intent_phrases = {question.lower()} | {opt.lower() for opt in intent_options}
    for phrase in all_intent_phrases:
        clean_phrase = phrase.replace("?", "").replace(".", "").replace("!", "").strip()
        clean_fallback = fallback_lower.replace("?", "").replace(".", "").replace("!", "").strip()
        if clean_phrase in clean_fallback:
            return fallback_text
        
    stripped = fallback_text.strip()
    if not stripped.endswith((".", "!", "?")):
        stripped += "."
        
    # open_hooks 가 있고 영어 1단어 이상일 때 hook prefix 합성 (success/neutral 분기거나 branch_type이 명시되지 않았을 때만)
    prefix = ""
    is_allowed_branch = branch_type is None or branch_type.lower() in ("success", "neutral")
    if is_allowed_branch and open_hooks and len(open_hooks) > 0:
        first_hook = open_hooks[0]
        if first_hook.lower() in {
            "hello",
            "hi",
            "hey",
            "what",
            "fine",
            "ok",
            "okay",
            "yes",
            "no",
            "um",
            "uh",
            "uhm",
            "ah",
        }:
            first_hook = ""
        # ASCII 영문 및 단어 형태 검증
        if first_hook.isascii() and first_hook.isalpha():
            if first_hook.lower() not in OPEN_HOOK_STOPLIST:
                prefix = f"You mentioned {first_hook} — "
            
    return f"{stripped} {prefix}{question}"


RETRY_PARAPHRASES = {
    "ask_visit_purpose": [
        "What is the purpose of your visit?",
        "Could you tell me why you're here?",
        "What brings you to the United States?",
    ],
    "ask_stay_duration": [
        "How long will you stay in the United States?",
        "How many days do you plan to stay?",
        "How long are you planning to remain here?",
    ],
    "ask_stay_location": [
        "Where will you stay in the United States?",
        "Could you tell me the address of your stay?",
        "Where are you going to stay?",
    ],
    "ask_travel_purpose_smalltalk": [
        "Are you visiting New York for a trip?",
        "What brings you to New York?",
        "Could you tell me the reason for your visit?",
    ],
    "ask_stay_plan_smalltalk": [
        "How long are you planning to stay in the US?",
        "How many days will you spend in New York?",
        "Could you share your stay plan with me?",
    ],
    "respond_to_polite_request": [
        "Are you visiting New York for a trip?",
        "Is this your first time traveling to New York?",
        "What is the main reason for your visit?",
    ],
    "ask_long_stay_reason": [
        "Why are you staying for so long?",
        "What is the reason for your extended stay?",
        "Why do you need to stay that long?",
    ],
    "ask_hotel_reservation": [
        "Do you have a hotel reservation?",
        "Is your hotel booking confirmed?",
        "Can you show me your hotel booking?",
    ],
    "ask_hotel_choice_reason": [
        "Why did you choose this hotel?",
        "What is the reason for selecting this hotel?",
        "Why stay at this specific hotel?",
    ],
    "ask_travel_itinerary": [
        "What is your travel itinerary?",
        "Do you have a confirmed travel plan?",
        "What is your schedule for the trip?",
    ],
    "ask_first_visit": [
        "Is this your first visit to the United States?",
        "Have you visited the United States before?",
        "Is this your first time visiting?",
    ],
    "ask_occupation": [
        "What is your occupation?",
        "What do you do for a living?",
        "What is your job?",
    ],
    "ask_cash_amount": [
        "How much cash are you carrying?",
        "How much money do you have with you?",
        "What is the amount of cash you have?",
    ],
    "ask_trip_payment_source": [
        "Who is paying for your trip?",
        "What is your source of funding?",
        "How are you funding this trip?",
    ],
    "ask_denied_entry_history": [
        "Have you ever been denied entry?",
        "Have you been refused entry to the United States?",
        "Is there any history of denied entry?",
    ],
    "confirm_carousel_search": [
        "Did you check the carousel carefully before coming to the desk?",
        "Are you sure you checked the baggage carousel thoroughly?",
        "Did you check the carousel belt before coming here?",
    ],
    "customs_hold_explanation_before_unlock": [
        "Please check the contents of the suitcase now.",
        "I need you to check what is inside the suitcase.",
        "Open the suitcase and check the contents, please.",
    ],
}


def get_retry_variation(surface_goal: str, last_npc_text: str, current_fallback_text: str) -> str:
    """재시도(Retry) 분기에서 직전 NPC 라인과 다른 표현을 선택하여 반환합니다."""
    import random
    options = RETRY_PARAPHRASES.get(surface_goal, [])
    if not options:
        if current_fallback_text.lower().strip() == last_npc_text.lower().strip():
            if "I need a clear answer." in current_fallback_text:
                return current_fallback_text.replace("I need a clear answer.", "Could you say that again?")
            return f"Pardon me? {current_fallback_text}"
        return current_fallback_text

    fresh_options = [opt for opt in options if opt.lower().strip() != last_npc_text.lower().strip()]
    if not fresh_options:
        fresh_options = options

    return random.choice(fresh_options)
