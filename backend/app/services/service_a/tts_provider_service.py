from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast
import httpx
import math
import os
import subprocess
import struct
import sys
import time
import wave

# Chatterbox 모델 인스턴스(Instance)를 메모리에 싱글톤(Singleton) 형태로 보관하기 위한 전역 캐시 변수(Variable)입니다.
_CHATTERBOX_MODEL_CACHE: dict[str, Any] = {}


# 각 TTS 엔진이 기술적으로 지원할 수 있는 하드웨어 및 소프트웨어 기능 명세 사양을 나타내는 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class TTSCapabilities:
    supports_emotion_prompt: bool  # 감정 유도 텍스트(Prompt) 입력 지원 여부
    supports_voice_clone: bool     # 참조 음성 복제(Voice Cloning) 지원 여부
    supports_speed: bool           # 말하기 속도(Speed) 조절 기능 지원 여부
    supports_pitch: bool           # 피치(Pitch, 음높이) 조절 기능 지원 여부
    output_sample_rates: tuple[int, ...]  # 합성 가능한 샘플 레이트(Sample Rate) 주파수 목록 (튜플 형식)


# Kokoro 엔진에 특화된 기능 명세 정보입니다.
KOKORO_CAPABILITIES = TTSCapabilities(
    supports_emotion_prompt=False,
    supports_voice_clone=False,
    supports_speed=True,
    supports_pitch=False,
    output_sample_rates=(24000,),
)
# Kokoro 모델 가중치를 다운로드할 기본 허그페이스(Hugging Face) 저장소 식별자(ID)입니다.
KOKORO_DEFAULT_REPO_ID = "hexgrad/Kokoro-82M"

# Microsoft Edge TTS 엔진에 특화된 기능 명세 정보입니다.
EDGE_TTS_CAPABILITIES = TTSCapabilities(
    supports_emotion_prompt=False,
    supports_voice_clone=False,
    supports_speed=True,
    supports_pitch=True,
    output_sample_rates=(24000,),
)

# 자체 개발용 Chatterbox TTS 엔진에 특화된 기능 명세 정보입니다.
CHATTERBOX_TTS_CAPABILITIES = TTSCapabilities(
    supports_emotion_prompt=True,
    supports_voice_clone=True,
    supports_speed=False,
    supports_pitch=False,
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
    provider: str                    # 호출할 대상 TTS 프로바이더 이름 (예: 'edge', 'kokoro')
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
class FakeKokoroProvider:
    provider_name = "kokoro"
    capabilities = KOKORO_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """실제 Kokoro 의존성 라이브러리 없이 분석 가능한 최소 크기의 가짜 WAV 파일을 생성합니다."""
        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_seconds = 1.0  # 1.0초 길이의 고정 주파수 음원을 생성합니다.
        
        # 물리 파형 신호 발생 함수를 호출하여 유효한 헤더를 갖춘 WAV 바이너리를 디스크에 씁니다.
        _write_valid_fake_wav(output_path, sample_rate=request.sample_rate, seconds=audio_seconds)
        generation_seconds = time.perf_counter() - started_at
        
        return {
            "provider": self.provider_name,
            "voice_id": str(request.provider_options.get("voice", "am_michael")),
            "audio_path": str(output_path),
            "audio_url": None,
            "sample_rate": request.sample_rate,
            "format": request.output_format,
            "audio_seconds": audio_seconds,
            "generation_seconds": generation_seconds,
            "real_time_factor": generation_seconds / audio_seconds if audio_seconds else None,
            "status": "ok",
        }


# Hugging Face로부터 Kokoro 모델 가중치(Weight)를 직접 가져와 로컬 PC 자원을 통해 온디바이스(On-device) 음성 합성을 구동하는 클래스(Class)입니다.
class RealKokoroProvider:
    provider_name = "kokoro"
    capabilities = KOKORO_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """Kokoro 실제 AI 모델을 사용하여 WAV 파일을 생성합니다."""
        # Windows OS 환경에서 espeak-ng 음소화 엔진 바인딩을 활성화합니다.
        configure_espeak_runtime()

        # 프로젝트 초기 로드 지연 및 모듈 간 임포트 충돌 완화를 위해 실제 프로바이더 호출 시점까지 AI 라이브러리 임포트를 지연합니다.
        sf = import_module("soundfile")
        kokoro_module = import_module("kokoro")
        pipeline_type = cast(Any, kokoro_module).KPipeline

        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. 언어 코드 및 레포지토리 식별자를 바인딩하여 텍스트 음소 변환용 파이프라인 인스턴스(Pipeline Instance)를 초기화합니다.
        pipeline = pipeline_type(
            lang_code=str(request.provider_options.get("lang_code", "a")),
            repo_id=KOKORO_DEFAULT_REPO_ID,
        )
        # 2. 파이프라인을 구동하여 원시 오디오 신호 배열(Audio Array)을 순차적으로 생성하는 제너레이터(Generator)를 실행합니다.
        generator = pipeline(
            request.text,
            voice=str(request.provider_options.get("voice", "am_michael")),
            speed=request.speaking_rate,
        )
        _, _, audio = next(generator)
        # 3. 도출된 오디오 파형 벡터 배열 데이터를 soundfile 모듈을 사용해 대상 경로에 WAV 파일로 저장합니다.
        sf.write(output_path, audio, request.sample_rate)

        generation_seconds = time.perf_counter() - started_at
        info = sf.info(output_path)
        audio_seconds = info.frames / info.samplerate if info.samplerate else 0.0
        
        return {
            "provider": self.provider_name,
            "voice_id": str(request.provider_options.get("voice", "am_michael")),
            "audio_path": str(output_path),
            "audio_url": None,
            "sample_rate": info.samplerate,
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


# 자체 연구용 Chatterbox 모델 가중치(Weight)를 기반으로 그래픽 카드 장치 자원(GPU)을 활용해 음성을 조절하고 합성해주는 로컬 딥러닝 음향 생성 클래스(Class)입니다.
class ChatterboxTTSProvider:
    provider_name = "chatterbox"
    capabilities = CHATTERBOX_TTS_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """Chatterbox TTS 모델을 메모리에 로드하고, 감정 매개변수와 참조 대상 음성을 반영한 WAV 파일을 생성합니다."""
        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sf = import_module("soundfile")
        # GPU 사용 가능 여부와 런타임 하드웨어 장치(Device)를 감지합니다.
        device = _resolve_chatterbox_device(str(request.provider_options.get("device", "auto")))
        model = _load_chatterbox_model(device=device)

        # 모델 발화 생성을 위한 매개변수(Arguments)들을 딕셔너리로 바인딩합니다.
        generate_kwargs: dict[str, Any] = {
            "exaggeration": float(request.provider_options.get("exaggeration", request.intensity)),  # 감정 극대화 강도
            "cfg_weight": float(request.provider_options.get("cfg_weight", 0.4)),                   # 분류기 없는 가이드 가중치(CFG Weight)
            "temperature": float(request.provider_options.get("temperature", 0.6)),                  # 샘플링 온도(Temperature)
        }
        audio_prompt_path = str(request.provider_options.get("audio_prompt_path", "")).strip()
        # 음성 복제(Cloning)를 수행할 훈련용 참조 대상 원본 음원 파일이 실제로 디스크에 존재하는지 검증합니다.
        if audio_prompt_path and Path(audio_prompt_path).exists():
            generate_kwargs["audio_prompt_path"] = audio_prompt_path

        # 딥러닝 모델 추론(Inference)을 구동하여 원시 오디오 신호 배열을 도출합니다.
        audio = model.generate(request.text, **generate_kwargs)
        sample_rate = int(getattr(model, "sr", request.sample_rate))
        # 도출된 파이토치 텐서(PyTorch Tensor) 파형 데이터를 사운드파일을 통해 디스크에 WAV 형식으로 기록합니다.
        cast(Any, sf).write(output_path, _to_soundfile_audio(audio), sample_rate)

        generation_seconds = time.perf_counter() - started_at
        info = cast(Any, sf).info(output_path)
        audio_seconds = info.frames / info.samplerate if info.samplerate else 0.0
        
        return {
            "provider": self.provider_name,
            "voice_id": str(request.provider_options.get("voice", request.voice_profile_id)),
            "audio_path": str(output_path),
            "audio_url": None,
            "sample_rate": info.samplerate,
            "format": request.output_format,
            "audio_seconds": audio_seconds,
            "generation_seconds": generation_seconds,
            "real_time_factor": generation_seconds / audio_seconds if audio_seconds else None,
            "status": "ok",
            "provider_options": {
                "audio_prompt_path": str(request.provider_options.get("audio_prompt_path", "")),
                "exaggeration": generate_kwargs["exaggeration"],
                "cfg_weight": generate_kwargs["cfg_weight"],
                "temperature": generate_kwargs["temperature"],
                "device": device,
                "language_id": request.provider_options.get("language_id"),
                "reference_audio_exists": bool(audio_prompt_path and Path(audio_prompt_path).exists()),
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

        # HTTP 클라이언트를 실행하여 ElevenLabs API에 음성 합성을 원격 요청(Remote HTTP Post Request)합니다.
        with httpx.Client(timeout=float(request.provider_options.get("timeout_seconds", 60.0))) as client:
            response = client.post(
                f"{base_url}/text-to-speech/{voice_id}",
                params={"output_format": api_output_format},
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "text": request.text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": float(request.provider_options.get("stability", 0.52)),         # 음성 합성 안정성
                        "similarity_boost": float(request.provider_options.get("similarity_boost", 0.82)),  # 원본 유사도 가중치
                        "style": float(request.provider_options.get("style", 0.42)),                 # 스타일 연출 수치
                        "speed": float(request.provider_options.get("speed", request.speaking_rate)),  # 말하기 속도 조절
                        "use_speaker_boost": bool(request.provider_options.get("use_speaker_boost", True)),
                    },
                },
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


def _load_chatterbox_model(*, device: str) -> Any:
    """싱글톤(Singleton) 패턴 형태로 Chatterbox 모델 데이터를 최초 1회에 한하여 메모리에 로드 및 캐싱(Caching)합니다."""
    cached = _CHATTERBOX_MODEL_CACHE.get(device)
    if cached is not None:
        return cached
    chatterbox_module = import_module("chatterbox.tts")
    model_type = cast(Any, chatterbox_module).ChatterboxTTS
    # 지정한 장치(CPU/CUDA) 상으로 사전 학습된 체크포인트를 올립니다.
    model = model_type.from_pretrained(device=device)
    _CHATTERBOX_MODEL_CACHE[device] = model
    return model


def _resolve_chatterbox_device(device: str) -> str:
    """시스템 런타임 환경에서 NVIDIA CUDA GPU 그래픽 가속 장치가 작동하는지 검출하여 적절한 디바이스 명칭을 리턴합니다."""
    if device != "auto":
        return device
    try:
        torch_module = import_module("torch")
    except ImportError:
        return "cpu"
    cuda = getattr(cast(Any, torch_module), "cuda", None)
    if cuda is not None and cuda.is_available():
        return "cuda"
    return "cpu"


def _to_soundfile_audio(audio: Any) -> Any:
    """딥러닝 파형 시계열 텐서(Tensor) 객체를 일반 사운드 입출력 모듈이 해석할 수 있는 넘파이(Numpy) 다차원 배열 형태로 가공합니다."""
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    if getattr(audio, "ndim", 1) == 2 and audio.shape[0] < audio.shape[1]:
        return audio.T
    return audio


def configure_espeak_runtime() -> None:
    """Windows 운영체제 환경에서 온디바이스 Kokoro AI 가 정상 작동하도록 음소 변환용 espeak-ng 런타임 라이브러리 DLL 절대 경로를 주입하는 환경 셋업(Environment Setup) 함수입니다."""
    try:
        espeakng_loader = import_module("espeakng_loader")
        wrapper_module = import_module("phonemizer.backend.espeak.wrapper")
    except ImportError:
        return

    espeak_wrapper = cast(Any, wrapper_module).EspeakWrapper
    library_path = cast(Any, espeakng_loader).get_library_path()
    data_path = cast(Any, espeakng_loader).get_data_path()
    # 파이썬 런타임 엔진이 espeak C-library를 동적 로드하도록 환경 변수를 설정하고 싱글톤 클래스 속성에 주입합니다.
    os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = library_path
    os.environ["ESPEAK_DATA_PATH"] = data_path
    espeak_wrapper.set_library(library_path)
    if not hasattr(espeak_wrapper, "set_data_path"):

        def set_data_path(path: str) -> None:
            espeak_wrapper.data_path = path

        espeak_wrapper.set_data_path = staticmethod(set_data_path)
    espeak_wrapper.set_data_path(data_path)


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

