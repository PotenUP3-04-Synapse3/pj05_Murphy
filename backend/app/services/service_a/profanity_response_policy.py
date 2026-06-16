"""Profanity Response Policy handling incivility tiers and profanity mirror modes."""

from typing import Any, Final

# 룰베이스 폴백 사전: [NPC ID][Incivility Tier][Profanity Mode] -> Response dict
# 기본적으로 off일 때는 일반 평상 대답을 그대로 활용하므로, 여기서는 firm 및 mirror 시의 고정 응답을 처리합니다.
_PROFANITY_FALLBACKS: Final[dict[str, dict[int, dict[str, dict[str, Any]]]]] = {
    "hale": {
        1: {
            "firm": {"npc_text": "Watch your tone, please.", "tone": "formal_firm", "npc_emotion": "suspicion"},
            "mirror": {"npc_text": "Watch your tone, please.", "tone": "formal_firm", "npc_emotion": "suspicion"},
        },
        2: {
            "firm": {"npc_text": "That's enough. One more remark and this stops.", "tone": "formal_stern", "npc_emotion": "suspicion"},
            "mirror": {"npc_text": "Watch your damn mouth. Last warning.", "tone": "formal_stern", "npc_emotion": "anger"},
        },
        3: {
            "firm": {"npc_text": "This interview is over.", "tone": "formal_warning", "npc_emotion": "anger"},
            "mirror": {"npc_text": "Get the hell out of my line. We're done.", "tone": "formal_warning", "npc_emotion": "anger"},
        }
    },
    "arabella": {
        1: {
            "firm": {"npc_text": "Please be polite.", "tone": "formal_firm", "npc_emotion": "suspicion"},
            "mirror": {"npc_text": "Please be polite.", "tone": "formal_firm", "npc_emotion": "suspicion"},
        },
        2: {
            "firm": {"npc_text": "Excuse me? That is not nice to say.", "tone": "formal_stern", "npc_emotion": "suspicion"},
            "mirror": {"npc_text": "Whoa, what the hell is your problem?", "tone": "formal_stern", "npc_emotion": "anger"},
        },
        3: {
            "firm": {"npc_text": "I am not talking to you anymore.", "tone": "formal_warning", "npc_emotion": "anger"},
            "mirror": {"npc_text": "Shut the hell up. I'm done.", "tone": "formal_warning", "npc_emotion": "anger"},
        }
    },
    "brielle": {
        1: {
            "firm": {"npc_text": "Sir, please keep it civil.", "tone": "formal_firm", "npc_emotion": "suspicion"},
            "mirror": {"npc_text": "Sir, please keep it civil.", "tone": "formal_firm", "npc_emotion": "suspicion"},
        },
        2: {
            "firm": {"npc_text": "Sir, I'm trying to help. Please keep it civil.", "tone": "formal_stern", "npc_emotion": "suspicion"},
            "mirror": {"npc_text": "What the heck is wrong with you?", "tone": "formal_stern", "npc_emotion": "anger"},
        },
        3: {
            "firm": {"npc_text": "I will have to ask you to leave.", "tone": "formal_warning", "npc_emotion": "anger"},
            "mirror": {"npc_text": "Get the hell away from my desk.", "tone": "formal_warning", "npc_emotion": "anger"},
        }
    }
}

# 기본 공통 폴백 (지정되지 않은 NPC용)
_DEFAULT_PROFANITY_FALLBACKS: Final[dict[int, dict[str, dict[str, Any]]]] = {
    1: {
        "firm": {"npc_text": "Please watch your language.", "tone": "formal_firm", "npc_emotion": "suspicion"},
        "mirror": {"npc_text": "Please watch your language.", "tone": "formal_firm", "npc_emotion": "suspicion"},
    },
    2: {
        "firm": {"npc_text": "That behavior is unacceptable.", "tone": "formal_stern", "npc_emotion": "suspicion"},
        "mirror": {"npc_text": "What the hell is that supposed to mean?", "tone": "formal_stern", "npc_emotion": "anger"},
    },
    3: {
        "firm": {"npc_text": "This interaction is now terminated.", "tone": "formal_warning", "npc_emotion": "anger"},
        "mirror": {"npc_text": "Shut the hell up and leave.", "tone": "formal_warning", "npc_emotion": "anger"},
    }
}


def get_profanity_fallback_response(npc_id: str, tier: int, mode: str) -> dict[str, Any] | None:
    """주어진 NPC ID, Incivility Tier, Profanity Mode 에 적합한 룰베이스 폴백 응답을 반환합니다.
    
    tier 가 0(정상)이거나 mode 가 'off'인 경우, 혹은 비정상적인 tier 값인 경우 None 을 반환하여 평상시 응답 흐름을 타게 합니다.
    """
    if tier <= 0 or mode == "off":
        return None
        
    # tier 최댓값 클램핑
    clamped_tier = min(3, max(1, tier))
    # mode 가 'mirror'가 아니면 전부 'firm' 정책으로 수렴
    policy_mode = "mirror" if mode == "mirror" else "firm"
    
    # NPC 전용 폴백 찾기
    npc_fallbacks = _PROFANITY_FALLBACKS.get(npc_id)
    if npc_fallbacks and clamped_tier in npc_fallbacks:
        res = npc_fallbacks[clamped_tier].get(policy_mode)
        if res:
            return res.copy()
            
    # 공통 폴백 적용
    res = _DEFAULT_PROFANITY_FALLBACKS[clamped_tier].get(policy_mode)
    if res:
        return res.copy()
        
    return None


def get_incivility_tts_bias(tier: int) -> dict[str, float]:
    """Incivility Tier 에 따른 stability, style, speed 오프셋(Bias)을 계산합니다."""
    if tier <= 0:
        return {"stability": 0.0, "style": 0.0, "speed": 0.0}
        
    clamped_tier = min(3, max(0, tier))
    
    if clamped_tier == 1:
        return {"stability": -0.1, "style": 0.1, "speed": 0.0}
    elif clamped_tier == 2:
        return {"stability": -0.2, "style": 0.2, "speed": 0.05}
    else: # tier == 3
        return {"stability": -0.3, "style": 0.3, "speed": 0.1}
