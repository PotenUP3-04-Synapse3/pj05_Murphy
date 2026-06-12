from typing import Any

from backend.app.services.service_a.dialogue_policy_service import DialoguePolicy
from backend.app.services.service_a.npc_emotion_service import NPCEmotionState
from backend.app.services.service_a.player_language_profile_service import PlayerLanguageProfile


def polish_tts_text(
    npc_text: str,
    profile: PlayerLanguageProfile,
    emotion_state: NPCEmotionState,
    policy: DialoguePolicy,
) -> str:
    """TTS 엔진이 구어체로 가장 어색하지 않게 발음하도록 대사 텍스트에 호흡 주기(Sentence Pause) 및 안내용 시작 어구를 삽입하여 조율 및 보정합니다."""
    text = _normalize_spaces(npc_text)
    # 1. 자연스러운 가이드 대사(Recast)를 줄 때 학습자의 인지 부하를 줄이기 위해 끊어읽기 쉼표(Pause)를 명시적으로 삽입합니다.
    if policy.action == "recast_and_advance" and profile.complexity == "simple":
        text = _add_sentence_pause(text)
    # 2. 강경하고 엄격한 감정 상태일 경우 머뭇거림을 나타내는 기호('...')를 온점('.')으로 치환하여 단호한 발음을 유도합니다.
    if emotion_state.emotion in {"firm_official", "stern_official", "warning_official"}:
        return text.replace("...", ".")
    # 3. 정책 상 허용되는 경우 대화 앞에 확인 알림 어구(Alright., Okay.)를 붙여 자연스러움을 증가시킵니다.
    if policy.add_officer_ack and not text.startswith(("Alright.", "Okay.")):
        return f"Alright. {text}"
    return text


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
