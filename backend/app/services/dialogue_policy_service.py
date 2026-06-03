from dataclasses import dataclass
from typing import Any, Literal

from backend.app.services.npc_emotion_service import NPCEmotionState
from backend.app.services.player_language_profile_service import PlayerLanguageProfile

DialogueAction = Literal["recast_and_advance", "ask_retry", "continue"]


@dataclass(frozen=True)
class DialoguePolicy:
    action: DialogueAction
    tone: str
    max_sentence_count: int
    use_recast: bool
    add_officer_ack: bool
    next_question_style: str


def build_dialogue_policy(
    normalized: dict[str, Any],
    profile: PlayerLanguageProfile,
    emotion_state: NPCEmotionState,
) -> DialoguePolicy:
    """언어 실력과 NPC 감정상태를 실제 대사 생성 정책으로 바꾼다."""
    branch_type = str(normalized.get("branch_type", ""))
    feedback_strategy = str(normalized.get("feedback_strategy", ""))
    blocks_progression = bool(normalized.get("blocks_progression", False))

    if blocks_progression or branch_type in {"retry", "fail"}:
        return DialoguePolicy(
            action="ask_retry",
            tone="formal_firm",
            max_sentence_count=2,
            use_recast=False,
            add_officer_ack=False,
            next_question_style="direct_repeat",
        )

    return DialoguePolicy(
        action="recast_and_advance" if feedback_strategy == "recast" else "continue",
        tone=_tone_from_emotion(emotion_state),
        max_sentence_count=2 if profile.complexity == "simple" else 3,
        use_recast=feedback_strategy == "recast",
        add_officer_ack=profile.feedback_depth != "minimal",
        next_question_style="short" if profile.complexity == "simple" else "natural",
    )


def _tone_from_emotion(emotion_state: NPCEmotionState) -> str:
    if emotion_state.emotion == "firm_official":
        return "formal_firm"
    if emotion_state.emotion == "patient":
        return "formal_supportive"
    return "formal_neutral"
