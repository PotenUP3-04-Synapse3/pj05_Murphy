from dataclasses import dataclass
from typing import Any, Literal

from backend.app.services.service_a.npc_roster_service import resolve_npc_profile_by_display_name
from backend.app.services.service_a.tts_provider_service import TTSProviderRequest

TTSStatus = Literal["ok", "failed", "fallback_mock"]


@dataclass(frozen=True)
class TTSRequest:
    text: str
    speaker: str
    tone: str


@dataclass(frozen=True)
class TTSAudio:
    provider: str
    audio_url: str | None
    voice_id: str
    duration_ms: int
    audio_path: str | None = None
    sample_rate: int | None = None
    status: TTSStatus = "ok"
    fallback: dict[str, Any] | None = None


def synthesize_speech(request: TTSRequest) -> TTSAudio:
    """외부 TTS provider 호출 없이 mock 음성 metadata를 반환한다."""
    # 테스트와 로컬 개발은 실제 TTS credential 없이 재현 가능해야 한다.
    return TTSAudio(
        provider="mock",
        audio_url=None,
        voice_id=_voice_id(request.speaker),
        duration_ms=_duration_ms(request.tone),
    )


def _voice_id(speaker: str) -> str:
    profile = resolve_npc_profile_by_display_name(speaker)
    if profile is not None:
        return profile.mock_voice_id
    return "generic_mock_voice"


def _duration_ms(tone: str) -> int:
    if tone == "formal_neutral":
        return 2400
    if tone == "formal_warning":
        return 1800
    if tone == "formal_stern":
        return 1900
    if tone == "formal_firm":
        return 2100
    return 2000


def build_kokoro_provider_request(
    text: str,
    speaker_id: str,
    voice_profile_id: str,
    kokoro_voice: str,
    tone: str,
    english_level: str,
    emotion: str | None = None,
    emotion_intensity: float | None = None,
) -> TTSProviderRequest:
    """Kokoro 교체 가능 provider interface에 맞춘 TTS 요청을 만든다."""
    speed = _kokoro_speed(tone=tone, english_level=english_level)
    tts_emotion = emotion or _emotion_for_tone(tone)
    return TTSProviderRequest(
        provider="kokoro",
        text=text,
        speaker_id=speaker_id,
        voice_profile_id=voice_profile_id,
        language="en",
        emotion=tts_emotion,
        tone=tone,
        intensity=emotion_intensity if emotion_intensity is not None else _intensity_for_emotion(tts_emotion),
        speaking_rate=speed,
        pitch=0.0,
        sample_rate=24000,
        output_format="wav",
        provider_options={"voice": kokoro_voice, "lang_code": "a"},
    )


def _kokoro_speed(tone: str, english_level: str) -> float:
    if tone == "formal_warning":
        return 0.84
    if tone == "formal_stern":
        return 0.87
    if tone == "formal_firm":
        return 0.9
    if tone == "formal_supportive":
        return 0.92
    if english_level == "beginner":
        return 0.95
    return 1.0


def _emotion_for_tone(tone: str) -> str:
    if tone == "formal_warning":
        return "warning_official"
    if tone == "formal_stern":
        return "stern_official"
    if tone == "formal_firm":
        return "firm_official"
    if tone == "formal_supportive":
        return "supportive_official"
    return "calm_official"


def _intensity_for_emotion(emotion: str) -> float:
    if emotion == "warning_official":
        return 0.92
    if emotion == "stern_official":
        return 0.82
    if emotion == "firm_official":
        return 0.7
    if emotion == "supportive_official":
        return 0.5
    return 0.35
