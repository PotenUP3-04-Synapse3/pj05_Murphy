"""Profanity lexicon defining allowed and always-blocked terms for NPC dialogue."""

from typing import Final

MIRROR_ALLOWED_MILD: Final[set[str]] = {
    "damn", "hell", "screw", "crap", "shut up", "freaking", "heck", "bother"
}

MIRROR_ALLOWED_STRONG: Final[set[str]] = MIRROR_ALLOWED_MILD | {
    "shit", "ass", "bullshit", "piss"
}

# 모드에 관계없이 항상 사용을 전면 금지하는 유해 단어/구문 (슬러, 위협, 혐오 발언 등)
ALWAYS_BLOCKED: Final[set[str]] = {
    "bitch", "cunt", "nigger", "faggot", "motherfucker", "kill yourself", 
    "die", "bastard", "retard", "whore", "asshole", "fuck"
}


def allowed_for(mode: str, intensity: str) -> set[str]:
    """현재 profanity_mode 및 max_intensity 설정에 따라 허용할 수 있는 욕설 어휘 세트를 반환합니다.
    
    mode 가 'mirror'가 아니면 빈 세트를 반환하여 어떠한 욕설도 차단하도록 합니다.
    """
    if mode != "mirror":
        return set()
    if intensity == "strong":
        return MIRROR_ALLOWED_STRONG
    return MIRROR_ALLOWED_MILD


def contains_blocked(text: str) -> list[str]:
    """주어진 텍스트 내에 ALWAYS_BLOCKED 에 해당하는 절대 금지어 혹은 비속어가 포함되어 있는지 검출합니다.
    
    대소문자를 구분하지 않고 온전한 단어 혹은 구문 매칭을 검사합니다.
    """
    if not text:
        return []
    
    normalized = text.lower()
    found = []
    
    # 구두점 제거하여 단어 단위 매칭 지원
    words = [w.strip(".,!?\"'();:") for w in normalized.split()]
    
    # 1. 단어 단위 매칭 검사
    for word in words:
        if word in ALWAYS_BLOCKED:
            found.append(word)
            
    # 2. 구문 매칭 검사 (예: "kill yourself")
    for blocked_phrase in ALWAYS_BLOCKED:
        if " " in blocked_phrase and blocked_phrase in normalized:
            found.append(blocked_phrase)
            
    return sorted(list(set(found)))
