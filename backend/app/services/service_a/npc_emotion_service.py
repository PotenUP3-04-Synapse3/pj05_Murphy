from dataclasses import dataclass
from typing import Any, Literal

# NPC가 취할 수 있는 13가지 정적/동적 감정 상태 목록을 정의하는 리터럴 타입입니다.
NPCEmotion = Literal[
    "joy",          # 즐거움
    "panic",        # 패닉
    "sad",          # 슬픔
    "suspicion",    # 의심
    "disgust",      # 극혐/짜증
    "fear",         # 공포/겁먹음
    "smirk",        # 비웃음/조롱
    "normal",       # 평온/사무적
    "anger",        # 분노/압박
    "surprise",     # 놀람
    "pain",         # 고통/신음
    "confusion",    # 혼란/머뭇거림
    "boredom",      # 지루함/단조로움
    # 레거시 하위 호환 감정 명세
    "calm_official",
    "patient",
    "procedural",
    "firm_official",
    "stern_official",
    "warning_official",
]


# NPC 감정 상태의 유형, 감정 세기(Intensity), 그리고 해당 감정이 유발된 사유(Reason)를 묶어 관리하는 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class NPCEmotionState:
    emotion: NPCEmotion
    intensity: float  # 감정 세기의 척도 (0.0에서 1.0 사이의 값)
    reason: str       # 감정이 변한 구체적 원인 기록


def infer_npc_emotion_state(normalized: dict[str, Any]) -> NPCEmotionState:
    """사용자가 입력한 대사(player_text), 영어 난이도(english_level), 플레이어 감정 데이터(player_emotion) 등을 종합하여 NPC 감정을 결정합니다."""
    player_text = normalized.get("player_text", "").lower()
    english_level = normalized.get("english_level", "beginner").lower()
    player_emotion = normalized.get("player_emotion", "").lower()
    retry_count = normalized.get("retry_count", 0)
    branch_type = str(normalized.get("branch_type", "")).lower()
    tone_hint = str(normalized.get("tone_hint", "neutral")).lower()
    task_success = int(normalized.get("task_success", 0) or 0)
    clarity = int(normalized.get("clarity", 0) or 0)
    node_id = str(normalized.get("node_id", "")).lower()
    ld_emotion = normalized.get("npc_emotion", "").lower().strip()

    # 13종 공식 감정 세트 정의
    emotions_13 = {"joy", "panic", "sad", "suspicion", "disgust", "fear", "smirk", "normal", "anger", "surprise", "pain", "confusion", "boredom"}

    # Level Design Agent가 직접 전달한 13종 감정 정보가 있을 경우 최우선 매핑
    if ld_emotion in emotions_13:
        intensity = 0.5
        if branch_type == "fail":
            intensity = 0.95
        elif retry_count >= 2:
            intensity = 0.85
        elif retry_count == 1:
            intensity = 0.65
        return NPCEmotionState(ld_emotion, intensity, "level_design_agent_direct_input")
    is_new_13_emotion_flow = (player_emotion in emotions_13) or any(
        keyword in node_id 
        for keyword in ["seatmate", "arabella", "novak", "harris", "dan", "brielle", "hale"]
    )

    if is_new_13_emotion_flow:
        # 1. 시나리오 실패(fail) 및 패닉 유발 상황
        if branch_type == "fail":
            if any(keyword in node_id for keyword in ["imm", "officer", "dan", "hale", "harris"]):
                return NPCEmotionState("anger", 0.95, "critical_failure_at_airport_security")
            return NPCEmotionState("panic", 0.9, "critical_failure_in_flight")

        # 2. 재시도(Retry) 누적 및 경고 상황
        if tone_hint == "warning" or retry_count >= 3:
            if any(keyword in node_id for keyword in ["desk", "brielle", "seatmate"]):
                return NPCEmotionState("disgust", 0.85, "repeated_retry_bothered")
            return NPCEmotionState("anger", 0.9, "repeated_errors_warning")
            
        if retry_count == 2:
            if "seatmate" in node_id:
                return NPCEmotionState("boredom", 0.75, "social_smalltalk_stalled")
            return NPCEmotionState("suspicion", 0.8, "repeated_retry_suspicion")
            
        if retry_count == 1:
            return NPCEmotionState("confusion", 0.6, "first_retry_confusion")

        # 3. 플레이어 감정 데이터(player_emotion)에 따른 동적 감정 전이
        if player_emotion in {"angry", "anger", "hostile"}:
            return NPCEmotionState("suspicion", 0.85, "player_expresses_anger")
            
        if player_emotion in {"nervous", "panic", "scared", "fear"}:
            # 초보자가 긴장한 경우 차분하게 돕거나 혼란을 느낌, 상급자가 긴장하면 수상하게 여겨 의심
            if english_level in {"beginner", "bronze"}:
                return NPCEmotionState("confusion", 0.5, "beginner_nervous_confusion")
            return NPCEmotionState("suspicion", 0.75, "advanced_nervous_suspicion")

        # 4. 플레이어 대사(Text)의 특징 분석에 따른 전이
        if not player_text.strip() or len(player_text.split()) < 2:
            # 무응답 혹은 단답일 때 지루함을 느낌
            return NPCEmotionState("boredom", 0.7, "empty_or_too_short_response")

        # 5. 성공(Success) 및 활기찬 응답 상황
        if branch_type == "success" or (task_success >= 3 and clarity >= 2):
            if any(keyword in node_id for keyword in ["seatmate", "arabella", "novak"]):
                return NPCEmotionState("joy", 0.8, "successful_social_smoltalk")
            return NPCEmotionState("normal", 0.5, "successful_procedural_flow")

        # 6. 기본 평온 상태
        return NPCEmotionState("normal", 0.4, "default_normal_flow")

    else:
        # 레거시 하위 호환 감정 전이 로직 (기존 Miller 노드 대상)
        if tone_hint == "warning" or branch_type == "fail" or retry_count >= 3:
            return NPCEmotionState("warning_official", 0.92, "repeated_block_or_warning")
        if retry_count >= 2:
            return NPCEmotionState("stern_official", 0.82, "repeated_retry")
        if branch_type == "retry" or tone_hint == "firm":
            return NPCEmotionState("firm_official", 0.7, "retry_or_firm_tone_hint")
        if task_success >= 3 and clarity >= 2:
            return NPCEmotionState("calm_official", 0.35, "successful_low_priority_answer")
        if clarity <= 1:
            return NPCEmotionState("patient", 0.5, "low_clarity_answer")
        return NPCEmotionState("procedural", 0.45, "default_procedural_flow")

