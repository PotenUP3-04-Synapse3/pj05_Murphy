# 감정(Emotion)에 대응하는 언리얼 엔진 애니메이션(Animation) 키를 매핑하는 서비스입니다.

def resolve_animation_by_emotion(default_animation: str, emotion: str) -> str:
    """NPC의 기본 애니메이션(Default Animation)과 현재 감정 상태(Emotion State)를 기반으로 
    최종 매핑된 언리얼 애니메이션 명칭을 반환합니다.
    """
    if not emotion:
        return default_animation
        
    emo = emotion.strip().lower()
    
    # 감정별 애니메이션 마이크로 배리언트(Micro-variant) 매핑 사전(Dictionary)
    mapping = {
        "joy": "joy",
        "panic": "panic",
        "sad": "sad",
        "suspicion": "suspicion",
        "disgust": "disgust",
        "fear": "fear",
        "smirk": "smirk",
        "anger": "anger",
        "surprise": "surprise",
        "pain": "pain",
        "confusion": "confusion",
        "boredom": "boredom",
        "normal": default_animation,
    }
    return mapping.get(emo, default_animation)
