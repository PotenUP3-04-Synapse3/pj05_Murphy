from dataclasses import dataclass
from typing import Any, Literal

NPCEmotion = Literal[
    "calm_official",
    "patient",
    "procedural",
    "firm_official",
    "stern_official",
    "warning_official",
]


@dataclass(frozen=True)
class NPCEmotionState:
    emotion: NPCEmotion
    intensity: float
    reason: str


def infer_npc_emotion_state(normalized: dict[str, Any]) -> NPCEmotionState:
    """Level Design JSON의 평가/분기 정보를 Officer Miller 감정상태로 추론한다."""
    branch_type = str(normalized.get("branch_type", ""))
    tone_hint = str(normalized.get("tone_hint", "neutral"))
    priority = str(normalized.get("priority", "low"))
    task_success = int(normalized.get("task_success", 0) or 0)
    clarity = int(normalized.get("clarity", 0) or 0)
    retry_count = int(normalized.get("retry_count", 0) or 0)

    if tone_hint == "warning" or branch_type == "fail" or retry_count >= 3:
        return NPCEmotionState("warning_official", 0.92, "repeated_block_or_warning")
    if retry_count >= 2:
        return NPCEmotionState("stern_official", 0.82, "repeated_retry")
    if branch_type == "retry" or tone_hint == "firm":
        return NPCEmotionState("firm_official", 0.7, "retry_or_firm_tone_hint")
    if task_success >= 3 and clarity >= 2 and priority == "low":
        return NPCEmotionState("calm_official", 0.35, "successful_low_priority_answer")
    if clarity <= 1:
        return NPCEmotionState("patient", 0.5, "low_clarity_answer")
    return NPCEmotionState("procedural", 0.45, "default_procedural_flow")
