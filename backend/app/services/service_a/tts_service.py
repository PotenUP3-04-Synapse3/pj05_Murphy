from dataclasses import dataclass
from typing import Any, Literal

from backend.app.services.service_a.npc_roster_service import resolve_npc_profile_by_display_name
from backend.app.services.service_a.tts_provider_service import TTSProviderRequest

# 음성 합성 상태(TTS Status)를 나타내는 리터럴(Literal) 타입입니다.
TTSStatus = Literal[
    "ok",            # 성공
    "failed",        # 합성 오류 발생
    "fallback_mock", # 모의(Mock) 합성으로 대체 제공됨
]


# 음성 합성을 호출하기 위한 텍스트 및 기본 메타정보를 묶은 요청 데이터 구조 클래스(Class)입니다.
@dataclass(frozen=True)
class TTSRequest:
    text: str    # 합성 대상 영문 대사 텍스트
    speaker: str # 발화 대상 화자 이름
    tone: str    # 발화 톤 명세 키값


# 최종 합성 완료된 오디오 음원의 속성 및 주소 정보를 담고 있는 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class TTSAudio:
    provider: str                    # 사용한 음성 엔진 이름 (예: mock, kokoro, edge)
    audio_url: str | None            # 클라이언트가 접근할 웹 다운로드 경로(URL)
    voice_id: str                    # 적용된 고유 음성 코드
    duration_ms: int                 # 음원의 실제 길이 (단위: 밀리초(ms))
    audio_path: str | None = None    # 서버 디스크 상의 저장 경로
    sample_rate: int | None = None   # 샘플 레이트 (Hz)
    status: TTSStatus = "ok"         # 합성 상태 코드
    fallback: dict[str, Any] | None = None # 대체 생성 시 작동 정보 사전


def synthesize_speech(request: TTSRequest) -> TTSAudio:
    """실제 클라우드 API 호출이나 AI 로드 없이 빠른 테스팅용 모의(Mock) 음성 정보 데이터를 생성하여 리턴합니다."""
    # 자격 증명(Credential) 설정이나 모델 부하 없이 유닛 테스트 및 기본 로컬 개발 환경에서 빠르게 재생 통계를 확인하기 위해 사용됩니다.
    return TTSAudio(
        provider="mock",
        audio_url=None,
        voice_id=_voice_id(request.speaker),
        duration_ms=_duration_ms(request.tone),
    )


def _voice_id(speaker: str) -> str:
    """전달받은 화자 이름을 기준으로 로컬 모의 음성 식별 코드를 찾아냅니다."""
    profile = resolve_npc_profile_by_display_name(speaker)
    if profile is not None:
        return profile.mock_voice_id
    return "generic_mock_voice"


def _duration_ms(tone: str) -> int:
    """발화 톤(Tone)에 맞게 물리 오디오 음원의 길이(ms)를 적합한 수치로 유추하여 대략적으로 결정합니다."""
    if tone == "formal_neutral":
        return 2400
    if tone == "formal_warning":
        return 1800
    if tone == "formal_stern":
        return 1900
    if tone == "formal_firm":
        return 2100
    return 2000


def build_edge_provider_request(
    text: str,
    speaker_id: str,
    voice_profile_id: str,
    edge_voice: str,
    tone: str,
    english_level: str,
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
    output_format: str = "wav",
) -> TTSProviderRequest:
    """Microsoft Edge 웹 서비스용 합성 규칙 및 부가 파라미터(volume, pitch 등)가 조립된 TTSProviderRequest 객체를 리턴합니다."""
    speed = _calculate_speaking_rate(tone=tone, english_level=english_level)
    return TTSProviderRequest(
        provider="edge",
        text=text,
        speaker_id=speaker_id,
        voice_profile_id=voice_profile_id,
        language="en",
        emotion=_emotion_for_tone(tone),
        tone=tone,
        intensity=_intensity_for_emotion(_emotion_for_tone(tone)),
        speaking_rate=speed,
        pitch=0.0,
        sample_rate=24000,
        output_format=output_format,
        # Edge TTS의 CLI에 전달할 고유 제어 속성들을 지정합니다.
        provider_options={
            "voice": edge_voice,
            "rate": rate,
            "volume": volume,
            "pitch": pitch,
            "edge_output_format": "audio-24khz-48kbitrate-mono-mp3",
        },
    )


def build_elevenlabs_provider_request(
    text: str,
    speaker_id: str,
    voice_profile_id: str,
    voice_id: str,
    tone: str,
    english_level: str,
    api_key: str,
    model_id: str,
    stability: float,
    similarity_boost: float,
    style: float,
    speed: float,
    api_output_format: str = "mp3_44100_128",
    output_format: str = "wav",
    base_url: str = "https://api.elevenlabs.io/v1",
    timeout_seconds: float = 60.0,
    use_speaker_boost: bool = True,
) -> TTSProviderRequest:
    """ElevenLabs REST API 규격에 명시된 인증 토큰, 모델 고유 코드 및 세부 목소리 제어 지표를 묶어 요청을 조립합니다."""
    tts_emotion = _emotion_for_tone(tone)
    return TTSProviderRequest(
        provider="elevenlabs",
        text=text,
        speaker_id=speaker_id,
        voice_profile_id=voice_profile_id,
        language="en",
        emotion=tts_emotion,
        tone=tone,
        intensity=style,
        speaking_rate=speed,
        pitch=0.0,
        sample_rate=24000,
        output_format=output_format,
        # API 헤더 및 페이로드에 들어갈 속성들을 매핑합니다.
        provider_options={
            "api_key": api_key,
            "base_url": base_url,
            "voice": voice_id,
            "model_id": model_id,
            "api_output_format": api_output_format,
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "speed": speed,
            "timeout_seconds": timeout_seconds,
            "use_speaker_boost": use_speaker_boost,
            "english_level": english_level,
        },
    )


def _calculate_speaking_rate(tone: str, english_level: str) -> float:
    """화자 상태 및 플레이어 수준을 판단하여 자연스러운 발화 재생 속도 비율을 조절합니다. (초보자일 경우 속도를 느리게 조절)"""
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
    """지정된 대사 톤(Tone)에 매핑되는 내부 감정 이름(Emotion Name) 문자열을 구합니다."""
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
    """감정 유형에 대응하는 기본적 표현 감정 세기(Intensity) 수치 값을 매핑합니다."""
    if emotion == "warning_official":
        return 0.92
    if emotion == "stern_official":
        return 0.82
    if emotion == "firm_official":
        return 0.7
    if emotion == "supportive_official":
        return 0.5
    return 0.35
