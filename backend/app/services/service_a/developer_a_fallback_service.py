from typing import Any


def build_text_fallback(normalized: dict[str, Any]) -> dict[str, Any]:
    """대사 후보가 없거나 차단된 경우 안전한 Officer Miller 대사를 만든다."""
    target_slot = normalized.get("target_slot")
    if target_slot == "stay_duration":
        text = "Okay. How long will you stay?"
    else:
        text = "Okay. Please continue."

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
        "fallback": {
            "used": True,
            "reason": "missing_or_blocked_candidate_text",
            "branch_type": normalized.get("branch_type"),
            "next_node_id": normalized.get("next_node_id"),
        },
    }


def build_audio_fallback(provider: str, voice_id: str, reason: str) -> dict[str, Any]:
    """TTS 생성 실패 시 Developer C가 처리 가능한 음성 fallback metadata를 만든다."""
    return {
        "provider": provider,
        "voice_id": voice_id,
        "audio_path": None,
        "audio_url": None,
        "sample_rate": None,
        "format": "wav",
        "status": "failed",
        "fallback": {"used": True, "reason": reason},
    }
