from dataclasses import dataclass
from typing import Any, Literal

from backend.app.services.service_a.npc_emotion_service import NPCEmotionState
from backend.app.services.service_a.player_language_profile_service import PlayerLanguageProfile

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
    
    # Baggage 챕터
    "report_missing_bag_at_service_desk": "Do you have your baggage claim tag or ticket?",
    "ask_claim_tag_or_ticket": "May I see your baggage claim tag?",
    "confirm_carousel_search": "Let me search the carousel. Can you describe your bag?",
    "redirect_to_customs_hold_area": "Please go to the customs hold area. Understood?",
    "customs_hold_explanation_before_unlock": "What brings you to the customs hold area?",
    "explain_random_customs_item": "",
    "complete_customs_baggage_clearance": "",
    "complete_baggage_claim_transition": ""
}


def synthesize_fallback_next_question(fallback_text: str, surface_goal: str) -> str:
    """LLM 실패 시 사용될 폴백 텍스트(Fallback Text) 뒤에 surface_goal에 따른 룰베이스 다음 질문을 합성합니다."""
    question = SURFACE_GOAL_QUESTIONS.get(surface_goal)
    if not question:
        return fallback_text
    
    if question in fallback_text:
        return fallback_text
        
    stripped = fallback_text.strip()
    if not stripped.endswith((".", "!", "?")):
        stripped += "."
    return f"{stripped} {question}"


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
    ]
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
