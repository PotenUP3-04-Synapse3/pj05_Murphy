from typing import Any


def build_text_fallback(normalized: dict[str, Any]) -> dict[str, Any]:
    """대사 후보(Candidate Text)가 없거나 필터링 정책에 의해 차단된 경우, 안전한 기본 대화 텍스트(Text Fallback)를 빌드합니다."""
    target_slot = normalized.get("target_slot")
    # 대화 목표 슬롯(Target Slot)이 체류 기간(Stay Duration)인지 식별하여 템플릿(Template) 대사를 다변화합니다.
    if target_slot == "stay_duration":
        text = "Okay. How long will you stay?"
    else:
        text = "Okay. Please continue."

    # 플레이어에게 제시될 한국어 피드백(Feedback) 내용을 가져오거나 기본 오류 안내 문구로 보정합니다.
    feedback_kr = (
        normalized.get("feedback_note")
        or "의미는 전달됐습니다. 조금 더 자연스럽게 말해 봅시다."
    )

    return {
        "speaker": "Officer Miller",
        "npc_text": text,
        "text": text,
        "feedback_kr": feedback_kr,
        "tone": "formal_neutral",
        "animation": "officer_check_passport",
        # 폴백이 사용되었음을 명시하고 디버깅용 추적 사유(Reason)를 첨부합니다.
        "fallback": {
            "used": True,
            "reason": "missing_or_blocked_candidate_text",
            "branch_type": normalized.get("branch_type"),
            "next_node_id": normalized.get("next_node_id"),
        },
    }


def build_audio_fallback(provider: str, voice_id: str, reason: str) -> dict[str, Any]:
    """TTS 음성 합성 생성 실패 시, 개발자 C 오케스트레이터가 처리 가능하도록 사후 처리를 돕는 음성 폴백 메타데이터(Audio Fallback Metadata)를 빌드합니다."""
    return {
        "provider": provider,
        "voice_id": voice_id,
        "audio_path": None,
        "audio_url": None,
        "sample_rate": None,
        "format": "wav",
        "status": "failed", # 음성 합성 상태를 'failed'로 마크하여 클라이언트에서 알 수 있게 합니다.
        "fallback": {"used": True, "reason": reason},
    }
