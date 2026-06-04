from dataclasses import dataclass
from typing import Any, Literal

NPCEmotion = Literal["calm_official", "patient", "firm_official", "procedural"]


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
    blocks_progression = bool(normalized.get("blocks_progression", False))
    task_success = int(normalized.get("task_success", 0) or 0)
    clarity = int(normalized.get("clarity", 0) or 0)

    if blocks_progression or branch_type in {"retry", "fail"} or tone_hint == "firm":
        return NPCEmotionState("firm_official", 0.7, "progression_block_or_retry")
    if task_success >= 3 and clarity >= 2 and priority == "low":
        return NPCEmotionState("calm_official", 0.35, "successful_low_priority_answer")
    if clarity <= 1:
        return NPCEmotionState("patient", 0.5, "low_clarity_answer")
    return NPCEmotionState("procedural", 0.45, "default_procedural_flow")
