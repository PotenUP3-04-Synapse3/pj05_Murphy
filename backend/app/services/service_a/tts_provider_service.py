from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
import httpx
import math
import struct
import subprocess
import sys
import time
import wave


# 각 TTS 엔진이 기술적으로 지원할 수 있는 하드웨어 및 소프트웨어 기능 명세 사양을 나타내는 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class TTSCapabilities:
    supports_emotion_prompt: bool  # 감정 유도 텍스트(Prompt) 입력 지원 여부
    supports_voice_clone: bool     # 참조 음성 복제(Voice Cloning) 지원 여부
    supports_speed: bool           # 말하기 속도(Speed) 조절 기능 지원 여부
    supports_pitch: bool           # 피치(Pitch, 음높이) 조절 기능 지원 여부
    output_sample_rates: tuple[int, ...]  # 합성 가능한 샘플 레이트(Sample Rate) 주파수 목록 (튜플 형식)


# Microsoft Edge TTS 엔진에 특화된 기능 명세 정보입니다.
EDGE_TTS_CAPABILITIES = TTSCapabilities(
    supports_emotion_prompt=False,
    supports_voice_clone=False,
    supports_speed=True,
    supports_pitch=True,
    output_sample_rates=(24000,),
)

# ElevenLabs 상용 클라우드 TTS 엔진에 특화된 기능 명세 정보입니다.
ELEVENLABS_TTS_CAPABILITIES = TTSCapabilities(
    supports_emotion_prompt=True,
    supports_voice_clone=True,
    supports_speed=True,
    supports_pitch=False,
    output_sample_rates=(24000,),
)


# 음성 합성을 요청할 때 엔진에 전달되어야 할 설정값들을 담는 단일 파라미터(Parameter) 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class TTSProviderRequest:
    provider: str                    # 호출할 대상 TTS 프로바이더 이름 (예: 'edge', 'elevenlabs')
    text: str                        # 합성할 영어 대사 텍스트
    speaker_id: str                  # 발화할 NPC 캐릭터 식별자(ID) (예: 'officer_miller')
    voice_profile_id: str            # 유저별 개인화 세션 음성 프로필 식별자(ID)
    language: str                    # 언어 코드 (기본값: 'en')
    emotion: str                     # 발화 감정 상태 키값
    tone: str                        # 발화 톤 명세 키값
    intensity: float                 # 감정 표현의 극대화 세기 강도 (0.0 ~ 1.0)
    speaking_rate: float             # 발화 속도 배율 (기본값: 1.0)
    pitch: float                     # 음높이(Pitch) 조정 값
    sample_rate: int                 # 결과 WAV 파일의 샘플 레이트 주파수 (Hz)
    output_format: str               # 저장할 오디오 포맷 규격 (예: 'wav', 'mp3')
    provider_options: dict[str, Any] = field(default_factory=dict)  # 엔진별 특화 추가 제어 옵션을 위한 사전(Dictionary)


# 모든 구체적인 TTS 합성기 클래스(Class)가 반드시 상속하여 구현해야 하는 동작 스펙 프로토콜(Protocol) 인터페이스입니다.
class TTSProvider(Protocol):
    provider_name: str
    capabilities: TTSCapabilities

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """주어진 음성 합성 요청 규격에 따라 음향 데이터(Audio Data)를 생성하여 대상 경로(Output Path)에 파일로 저장합니다."""
        ...


# 외부 인공지능 가중치 모델 로드 및 복잡한 환경 설정 절차 없이, 유효한 포맷의 모의(Mock) WAV 파일만을 즉시 자동 작성하는 테스트 목적의 모의 합성 클래스(Class)입니다.
class FakeTTSProvider:
    provider_name = "mock"
    capabilities = EDGE_TTS_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """실제 라이브러리 없이 분석 가능한 최소 크기의 가짜 WAV 파일을 생성합니다."""
        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_seconds = 1.0  # 1.0초 길이의 고정 주파수 음원을 생성합니다.
        
        # 물리 파형 신호 발생 함수를 호출하여 WAV 바이너리를 디스크에 씁니다.
        _write_valid_fake_wav(output_path, sample_rate=request.sample_rate, seconds=audio_seconds)
        generation_seconds = time.perf_counter() - started_at
        
        return {
            "provider": self.provider_name,
            "voice_id": str(request.provider_options.get("voice", "mock_voice")),
            "audio_path": str(output_path),
            "audio_url": None,
            "sample_rate": request.sample_rate,
            "format": request.output_format,
            "audio_seconds": audio_seconds,
            "generation_seconds": generation_seconds,
            "real_time_factor": generation_seconds / audio_seconds if audio_seconds else None,
            "status": "ok",
        }


# Microsoft Edge의 무료 웹 TTS 스크래핑 라이브러리를 활용하여 MP3 오디오 파일을 획득한 후, ffmpeg 프로그램으로 형변환하여 WAV 출력을 최종 생성하는 클래스(Class)입니다.
class EdgeTTSProvider:
    provider_name = "edge"
    capabilities = EDGE_TTS_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """Edge TTS 엔진으로 MP3 파일을 생성한 뒤, 요청한 출력 포맷이 WAV이면 FFmpeg 프로그램으로 PCM WAV 형식으로 변환합니다."""
        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 프로바이더 옵션에서 목소리, 속도, 볼륨, 피치 정보들을 문자열 포맷으로 추출합니다.
        voice = str(request.provider_options.get("voice", "en-US-GuyNeural"))
        rate = str(request.provider_options.get("rate", "+0%"))
        volume = str(request.provider_options.get("volume", "+0%"))
        pitch = str(request.provider_options.get("pitch", "+0Hz"))
        
        # 출력 포맷이 mp3이면 바로 저장하고, wav인 경우 임시 mp3 파일을 생성한 뒤 변환합니다.
        media_path = output_path if request.output_format == "mp3" else output_path.with_suffix(".edge.mp3")

        # CLI 커맨드를 통해 edge_tts 패키지를 실행하고 음향 데이터를 다운로드합니다.
        _run_edge_tts_cli(
            text=request.text,
            voice=voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
            output_path=media_path,
        )

        conversion_seconds = 0.0
        # 클라이언트가 WAV 포맷을 요구할 경우 로컬에 설치된 FFmpeg 엔진을 이용해 PCM 변환 처리를 후속 수행합니다.
        if request.output_format == "wav":
            conversion_started_at = time.perf_counter()
            _convert_mp3_to_wav(
                input_path=media_path,
                output_path=output_path,
                sample_rate=request.sample_rate,
            )
            conversion_seconds = time.perf_counter() - conversion_started_at

        generation_seconds = time.perf_counter() - started_at
        audio_seconds = _wav_duration_seconds(output_path) if request.output_format == "wav" else 0.0
        
        return {
            "provider": self.provider_name,
            "voice_id": voice,
            "audio_path": str(output_path),
            "audio_url": None,
            "sample_rate": request.sample_rate,
            "format": request.output_format,
            "audio_seconds": audio_seconds,
            "generation_seconds": generation_seconds,
            "conversion_seconds": conversion_seconds,
            "real_time_factor": generation_seconds / audio_seconds if audio_seconds else None,
            "status": "ok",
            "provider_options": {
                "rate": rate,
                "volume": volume,
                "pitch": pitch,
                "edge_media_path": str(media_path),
            },
        }


# ElevenLabs 상용 SaaS 클라우드 API를 호출하여 최상의 품질을 지닌 고성능 성우 음성을 가져오는 인터페이스 클라이언트 구현 클래스(Class)입니다.
class ElevenLabsTTSProvider:
    provider_name = "elevenlabs"
    capabilities = ELEVENLABS_TTS_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """ElevenLabs 원격 API 엔드포인트를 호출하여 음향 파일을 다운로드하고, 필요한 경우 PCM WAV 형식으로 변환합니다."""
        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        api_key = str(request.provider_options.get("api_key", "")).strip()
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY is required")

        base_url = str(request.provider_options.get("base_url", "https://api.elevenlabs.io/v1")).rstrip("/")
        voice_id = str(request.provider_options.get("voice", "CwhRBWXzGAHq8TQ4Fs17"))
        model_id = str(request.provider_options.get("model_id", "eleven_flash_v2_5"))
        api_output_format = str(request.provider_options.get("api_output_format", "mp3_44100_128"))
        media_path = output_path if request.output_format == "mp3" else output_path.with_suffix(".elevenlabs.mp3")

        # JSON 요청 바디 조립
        request_body: dict[str, Any] = {
            "text": request.text,
            "model_id": model_id,
            "voice_settings": {
                # stability (안정도, 0.0 ~ 1.0):
                # - 낮을수록(0.3~0.5) 감정이 풍부하고 역동적인 발화가 연출됩니다. (분노, 패닉, 공포 등에 권장)
                # - 높을수록(0.6 이상) 목소리가 차분하고 일관성 있게 유지되나, 너무 높으면 기계음처럼 단조로워질 수 있습니다.
                "stability": float(request.provider_options.get("stability", 0.52)),
                
                # similarity_boost (클론 음성 유사도 가중치, 0.0 ~ 1.0):
                # - 높을수록 원본 성우 목소리의 고유한 억양, 액센트, 기교가 더 정교하게 재현됩니다.
                # - 낮을수록 일반적이고 평범한 음성으로 융합되지만, 너무 높이면 노이즈나 발음 깨짐이 발생할 수 있습니다.
                "similarity_boost": float(request.provider_options.get("similarity_boost", 0.82)),
                
                # style (스타일 과장성/유사성, 0.0 ~ 1.0):
                # - 높을수록 모델이 원본 목소리의 스타일과 감정 표현을 더 적극적이고 과장되게 모사합니다.
                # - 너무 높이면 오디오 품질이 손상되거나 연출이 지나치게 인위적일 수 있습니다. (기본값: 0.42)
                "style": float(request.provider_options.get("style", 0.42)),
                
                # speed (말하기 속도 조절, 0.7 ~ 1.2):
                # - 배율 기반이며, 1.0이 성우 본래의 표준 속도입니다.
                # - 플레이어의 영어 수준(Bronze/Silver/Gold)에 따라 느리게(0.8) 혹은 빠르게(1.0~1.1) 동적으로 주입됩니다.
                "speed": float(request.provider_options.get("speed", request.speaking_rate)),
                
                # use_speaker_boost (화자 증폭, Boolean):
                # - ElevenLabs에서 원본 클론 화자의 목소리를 더 선명하고 뚜렷하게 강조하여 백그라운드 잡음을 줄여줍니다.
                "use_speaker_boost": bool(request.provider_options.get("use_speaker_boost", True)),
            },
        }

        # previous_text 파라미터가 유효하게 존재할 경우 요청 바디에 주입 (문맥 인지 감정 전이 증대)
        previous_text = request.provider_options.get("previous_text")
        if previous_text and str(previous_text).strip():
            request_body["previous_text"] = str(previous_text).strip()

        # HTTP 클라이언트를 실행하여 ElevenLabs API에 음성 합성을 원격 요청(Remote HTTP Post Request)합니다.
        with httpx.Client(timeout=float(request.provider_options.get("timeout_seconds", 60.0))) as client:
            response = client.post(
                f"{base_url}/text-to-speech/{voice_id}",
                params={"output_format": api_output_format},
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json=request_body,
            )
            response.raise_for_status()
            # 네트워크 응답으로부터 반환받은 미디어 데이터 바이너리를 디스크 파일에 임시 저장합니다.
            media_path.write_bytes(response.content)

        conversion_seconds = 0.0
        # 클라이언트가 WAV 출력을 요구할 경우 로컬 머신에 설비된 FFmpeg 엔진을 이용해 PCM 변환 처리를 후속 수행합니다.
        if request.output_format == "wav":
            conversion_started_at = time.perf_counter()
            _convert_mp3_to_wav(
                input_path=media_path,
                output_path=output_path,
                sample_rate=request.sample_rate,
            )
            conversion_seconds = time.perf_counter() - conversion_started_at

        generation_seconds = time.perf_counter() - started_at
        audio_seconds = _wav_duration_seconds(output_path) if request.output_format == "wav" else 0.0
        
        return {
            "provider": self.provider_name,
            "voice_id": voice_id,
            "audio_path": str(output_path),
            "audio_url": None,
            "sample_rate": request.sample_rate,
            "format": request.output_format,
            "audio_seconds": audio_seconds,
            "generation_seconds": generation_seconds,
            "conversion_seconds": conversion_seconds,
            "real_time_factor": generation_seconds / audio_seconds if audio_seconds else None,
            "status": "ok",
            "provider_options": {
                "model_id": model_id,
                "api_output_format": api_output_format,
                "stability": float(request.provider_options.get("stability", 0.52)),
                "similarity_boost": float(request.provider_options.get("similarity_boost", 0.82)),
                "style": float(request.provider_options.get("style", 0.42)),
                "speed": float(request.provider_options.get("speed", request.speaking_rate)),
                "use_speaker_boost": bool(request.provider_options.get("use_speaker_boost", True)),
                "elevenlabs_media_path": str(media_path),
            },
        }


def _run_edge_tts_cli(
    *,
    text: str,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
    output_path: Path,
) -> None:
    """Edge-TTS 라이브러리의 커맨드 라인 도구(CLI, Command Line Interface)를 하위 프로세스(Subprocess) 형태로 호출하여 음향 파일을 다운로드합니다."""
    command = [
        sys.executable,
        "-m",
        "edge_tts",
        f"--voice={voice}",
        f"--rate={rate}",
        f"--volume={volume}",
        f"--pitch={pitch}",
        "--text",
        text,
        "--write-media",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def _convert_mp3_to_wav(input_path: Path, output_path: Path, sample_rate: int) -> None:
    """오픈소스 미디어 변환기인 FFmpeg 프로그램을 하위 프로세스로 호출하여 MP3 압축 오디오를 헤더가 규격화된 PCM 16비트 단일 채널(Mono) WAV 파일로 트랜스코딩(Transcoding)합니다."""
    command = [
        "ffmpeg",
        "-y",                 # 기존 파일 강제 덮어쓰기 허용 (Overwrite)
        "-i",
        str(input_path),
        "-acodec",
        "pcm_s16le",          # 16-bit 리틀 엔디언 PCM 부호화 형식 지정
        "-ac",
        "1",                  # 단일 채널(Mono) 지정
        "-ar",
        str(sample_rate),     # 대상 샘플 레이트 설정 (예: 24000)
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def _wav_duration_seconds(path: Path) -> float:
    """WAV 파일 포맷 헤더를 디코딩하여 오디오 총 재생 시간(초)을 물리적으로 연산하여 반환합니다."""
    with wave.open(str(path), "rb") as wav:
        frame_rate = wav.getframerate()
        return wav.getnframes() / frame_rate if frame_rate else 0.0


def _write_valid_fake_wav(path: Path, sample_rate: int, seconds: float) -> None:
    """수치 수학적으로 순수한 사인파(Sine Wave) 물리 신호를 생성하여 디바이스에서 재생 가능한 16비트 PCM WAV 파일 형식으로 디스크에 직접 기록합니다."""
    frame_count = int(sample_rate * seconds)
    amplitude = 1200
    frequency = 220.0
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        # 루프를 순회하며 220Hz 기준 사인 곡선 물리 데이터 청크를 패킹해 물리 파일 스트림에 순차 기록합니다.
        for index in range(frame_count):
            value = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            wav.writeframes(struct.pack("<h", value))

