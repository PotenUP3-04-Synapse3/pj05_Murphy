from typing import Any
import re

from backend.app.services.service_a.dialogue_policy_service import DialoguePolicy
from backend.app.services.service_a.npc_emotion_service import NPCEmotionState
from backend.app.services.service_a.player_language_profile_service import PlayerLanguageProfile


def polish_tts_text(
    npc_text: str,
    profile: PlayerLanguageProfile,
    emotion_state: NPCEmotionState,
    policy: DialoguePolicy,
    non_verbal_palette: list[str] | None = None,
) -> str:
    """TTS 엔진이 구어체로 가장 어색하지 않게 발음하도록 대사 텍스트에 호흡 주기(Sentence Pause) 및 안내용 시작 어구를 삽입하여 조율 및 보정합니다."""
    text = _normalize_spaces(npc_text)
    
    # 1. 자연스러운 가이드 대사(Recast)를 줄 때 학습자의 인지 부하를 줄이기 위해 끊어읽기 쉼표(Pause)를 명시적으로 삽입합니다.
    if policy.action == "recast_and_advance" and profile.complexity == "simple":
        text = _add_sentence_pause(text)
        
    # 2. 강경하고 엄격한 감정 상태일 경우 머뭇거림을 나타내는 기호('...')를 온점('.')으로 치환하여 단호한 발음을 유도합니다.
    if emotion_state.emotion in {"firm_official", "stern_official", "warning_official", "anger", "suspicion"}:
        text = text.replace("...", ".")
        
    # 3. 정책 상 허용되는 경우 대화 앞에 확인 알림 어구(Alright., Okay.)를 붙여 자연스러움을 증가시킵니다.
    if policy.add_officer_ack and not text.startswith(("Alright.", "Okay.")):
        text = f"Alright. {text}"
        
    # 4. non_verbal_palette가 존재할 경우, 감정 상태에 맞춰 자연스럽게 비구어 표현을 자동 삽입합니다.
    if non_verbal_palette:
        has_verbal = any(item in text for item in non_verbal_palette)
        if not has_verbal and "<break" not in text:
            selected_non_verbal = None
            if emotion_state.emotion in {"anger", "suspicion", "disgust"}:
                negatives = [item for item in non_verbal_palette if item in {"Hmph.", "Tsk.", "Hmm..."}]
                if negatives:
                    selected_non_verbal = negatives[0]
            elif emotion_state.emotion in {"joy", "smirk"}:
                positives = [item for item in non_verbal_palette if item in {"Haha!", "Oh!"}]
                if positives:
                    selected_non_verbal = positives[0]
                    
            if not selected_non_verbal:
                breaks = [item for item in non_verbal_palette if "<break" in item]
                if breaks:
                    selected_non_verbal = breaks[0]
                elif non_verbal_palette:
                    selected_non_verbal = non_verbal_palette[0]
                    
            if selected_non_verbal:
                if "<break" in selected_non_verbal:
                    if ". " in text:
                        parts = text.split(". ", 1)
                        text = f"{parts[0]}. {selected_non_verbal} {parts[1]}"
                    else:
                        text = f"{text} {selected_non_verbal}"
                else:
                    text = f"{selected_non_verbal} {text}"
                    
    # 최종 결과 반환 시 SSML 검증 및 시간 한계(Clamp)를 항상 수행합니다.
    return validate_and_clamp_ssml(text)


def validate_and_clamp_ssml(text: str) -> str:
    """TTS 텍스트 내의 SSML break 태그 유효성을 검증하고, 시간 범위를 0.0s~3.0s로 강제 조율합니다."""
    pattern = r'(<break\s+time=["\']([^"\'\s]+)["\']\s*/>)'
    
    def replacer(match: re.Match) -> str:
        time_str = match.group(2).strip()
        time_match = re.match(r'^([0-9.]+)(ms|s)?$', time_str)
        if not time_match:
            return '<break time="0.5s"/>'
            
        val_str = time_match.group(1)
        unit = time_match.group(2)
        
        try:
            val = float(val_str)
        except ValueError:
            return '<break time="0.5s"/>'
            
        if unit == 'ms':
            val = val / 1000.0
        
        # 0.0s ~ 3.0s 범위로 클램핑
        clamped = max(0.0, min(3.0, val))
        return f'<break time="{clamped:.1f}s"/>'
        
    return re.sub(pattern, replacer, text)


def build_tts_style_metadata(
    profile: PlayerLanguageProfile,
    emotion_state: NPCEmotionState,
    policy: DialoguePolicy,
) -> dict[str, Any]:
    """텍스트 다듬기(Polishing) 및 발화 어조 튜닝 시 활용되었던 세션 입력 변수들을 메타데이터(Metadata) 딕셔너리로 조립하여 디버그 및 비용 추적용으로 활용합니다."""
    return {
        "english_level": profile.english_level,
        "complexity": profile.complexity,
        "feedback_depth": profile.feedback_depth,
        "emotion": emotion_state.emotion,
        "emotion_intensity": emotion_state.intensity,
        "emotion_reason": emotion_state.reason,
        "dialogue_action": policy.action,
        "next_question_style": policy.next_question_style,
    }


def _normalize_spaces(text: str) -> str:
    """줄바꿈이나 다중 스페이스 문자를 단일 공백으로 치환하여 TTS 변환 시 유효하지 않은 호흡이 발생하는 것을 예방합니다."""
    return " ".join(text.split())


def _add_sentence_pause(text: str) -> str:
    """문장 간 구분을 돕기 위해 온점 뒤에 말뭉치 끊어읽기 기호인 '...'를 지능적으로 삽입하여 발화 간격 호흡을 생성합니다."""
    if ". " not in text or "... " in text:
        return text
    if text.startswith("Alright. "):
        rest = text.removeprefix("Alright. ")
        if ". " not in rest:
            return text
        first, tail = rest.split(". ", 1)
        return f"Alright. {first}. ... {tail}"
    first, rest = text.split(". ", 1)
    return f"{first}. ... {rest}"
