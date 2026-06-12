from dataclasses import dataclass
from typing import Any, Literal

# NPC가 취할 수 있는 구체적인 감정 상태(NPC Emotion) 목록을 정의하는 리터럴(Literal) 타입입니다.
NPCEmotion = Literal[
    "calm_official",    # 차분하고 공식적인 상태
    "patient",          # 유저를 기다려주며 인내하는 상태
    "procedural",       # 사무적이고 절차적인 상태
    "firm_official",    # 단호한 공식 상태
    "stern_official",   # 매우 엄격한 공식 상태
    "warning_official", # 강력히 경고하는 공식 상태
]


# NPC 감정 상태의 유형, 감정 세기(Intensity), 그리고 해당 감정이 유발된 사유(Reason)를 묶어 관리하는 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class NPCEmotionState:
    emotion: NPCEmotion
    intensity: float  # 감정 세기의 척도 (0.0에서 1.0 사이의 값)
    reason: str       # 감정이 변한 구체적 원인 기록


def infer_npc_emotion_state(normalized: dict[str, Any]) -> NPCEmotionState:
    """레벨 디자인(Level Design) 평가 및 분기 통계 정보(재시도 횟수, 답변 명확성 등)를 분석하여 NPC의 감정 상태(NPCEmotionState)를 유추합니다."""
    branch_type = str(normalized.get("branch_type", ""))
    tone_hint = str(normalized.get("tone_hint", "neutral"))
    priority = str(normalized.get("priority", "low"))
    task_success = int(normalized.get("task_success", 0) or 0)
    clarity = int(normalized.get("clarity", 0) or 0)
    retry_count = int(normalized.get("retry_count", 0) or 0)

    # 1. 3회 이상 답변을 재시도했거나 강한 경고(Warning)가 필요할 때 가장 높은 세기(0.92)로 warning_official 감정을 매핑합니다.
    if tone_hint == "warning" or branch_type == "fail" or retry_count >= 3:
        return NPCEmotionState("warning_official", 0.92, "repeated_block_or_warning")
    # 2. 2회 재시도 시 엄격한 상태(stern_official)로 판정합니다.
    if retry_count >= 2:
        return NPCEmotionState("stern_official", 0.82, "repeated_retry")
    # 3. 분기가 단순 재시도(Retry)이거나 지시 톤이 firm(단호함)일 때 단호한 상태(firm_official)로 판정합니다.
    if branch_type == "retry" or tone_hint == "firm":
        return NPCEmotionState("firm_official", 0.7, "retry_or_firm_tone_hint")
    # 4. 플레이어가 높은 성공도와 명확한 발음으로 연속 답변 시 차분한 상태(calm_official)로 판정합니다.
    if task_success >= 3 and clarity >= 2 and priority == "low":
        return NPCEmotionState("calm_official", 0.35, "successful_low_priority_answer")
    # 5. 플레이어 발화의 명확성(Clarity) 점수가 매우 낮을 때 기다려주는 상태(patient)로 설정합니다.
    if clarity <= 1:
        return NPCEmotionState("patient", 0.5, "low_clarity_answer")
    # 6. 기본값으로 단순 절차를 밟는 사무적 상태(procedural)를 리턴합니다.
    return NPCEmotionState("procedural", 0.45, "default_procedural_flow")
