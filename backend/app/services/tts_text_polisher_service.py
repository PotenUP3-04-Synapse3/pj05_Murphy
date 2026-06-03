from typing import Any

from backend.app.services.dialogue_policy_service import DialoguePolicy
from backend.app.services.npc_emotion_service import NPCEmotionState
from backend.app.services.player_language_profile_service import PlayerLanguageProfile


def polish_tts_text(
    npc_text: str,
    profile: PlayerLanguageProfile,
    emotion_state: NPCEmotionState,
    policy: DialoguePolicy,
) -> str:
    """Kokoro가 더 자연스럽게 읽도록 대사 호흡과 문장 길이를 보정한다."""
    text = _normalize_spaces(npc_text)
    if policy.action == "recast_and_advance" and profile.complexity == "simple":
        text = _add_sentence_pause(text)
    if emotion_state.emotion == "firm_official":
        return text.replace("...", ".")
    if policy.add_officer_ack and not text.startswith(("Alright.", "Okay.")):
        return f"Alright. {text}"
    return text


def build_tts_style_metadata(
    profile: PlayerLanguageProfile,
    emotion_state: NPCEmotionState,
    policy: DialoguePolicy,
) -> dict[str, Any]:
    """대사 생성 판단 근거를 TTS metadata로 남긴다."""
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
    return " ".join(text.split())


def _add_sentence_pause(text: str) -> str:
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
