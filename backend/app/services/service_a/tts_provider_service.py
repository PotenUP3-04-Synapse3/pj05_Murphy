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

_CHATTERBOX_MODEL_CACHE: dict[str, Any] = {}


@dataclass(frozen=True)
class TTSCapabilities:
    supports_emotion_prompt: bool
    supports_voice_clone: bool
    supports_speed: bool
    supports_pitch: bool
    output_sample_rates: tuple[int, ...]


KOKORO_CAPABILITIES = TTSCapabilities(
    supports_emotion_prompt=False,
    supports_voice_clone=False,
    supports_speed=True,
    supports_pitch=False,
    output_sample_rates=(24000,),
)
KOKORO_DEFAULT_REPO_ID = "hexgrad/Kokoro-82M"
EDGE_TTS_CAPABILITIES = TTSCapabilities(
    supports_emotion_prompt=False,
    supports_voice_clone=False,
    supports_speed=True,
    supports_pitch=True,
    output_sample_rates=(24000,),
)
CHATTERBOX_TTS_CAPABILITIES = TTSCapabilities(
    supports_emotion_prompt=True,
    supports_voice_clone=True,
    supports_speed=False,
    supports_pitch=False,
    output_sample_rates=(24000,),
)
ELEVENLABS_TTS_CAPABILITIES = TTSCapabilities(
    supports_emotion_prompt=True,
    supports_voice_clone=True,
    supports_speed=True,
    supports_pitch=False,
    output_sample_rates=(24000,),
)


@dataclass(frozen=True)
class TTSProviderRequest:
    provider: str
    text: str
    speaker_id: str
    voice_profile_id: str
    language: str
    emotion: str
    tone: str
    intensity: float
    speaking_rate: float
    pitch: float
    sample_rate: int
    output_format: str
    provider_options: dict[str, Any] = field(default_factory=dict)


class TTSProvider(Protocol):
    provider_name: str
    capabilities: TTSCapabilities

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        ...


class FakeKokoroProvider:
    provider_name = "kokoro"
    capabilities = KOKORO_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """실제 Kokoro dependency 없이 분석 가능한 최소 wav 파일을 만든다."""
        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_seconds = 1.0
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


class RealKokoroProvider:
    provider_name = "kokoro"
    capabilities = KOKORO_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """Kokoro 실제 모델로 wav 파일을 생성한다."""
        configure_espeak_runtime()

        # 실제 dependency import는 real provider 호출 시점까지 지연한다.
        sf = import_module("soundfile")
        kokoro_module = import_module("kokoro")
        pipeline_type = cast(Any, kokoro_module).KPipeline

        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pipeline = pipeline_type(
            lang_code=str(request.provider_options.get("lang_code", "a")),
            repo_id=KOKORO_DEFAULT_REPO_ID,
        )
        generator = pipeline(
            request.text,
            voice=str(request.provider_options.get("voice", "am_michael")),
            speed=request.speaking_rate,
        )
        _, _, audio = next(generator)
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


class EdgeTTSProvider:
    provider_name = "edge"
    capabilities = EDGE_TTS_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """Edge TTS로 MP3를 생성한 뒤, 요청 format이 wav이면 ffmpeg로 PCM WAV로 변환한다."""
        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        voice = str(request.provider_options.get("voice", "en-US-GuyNeural"))
        rate = str(request.provider_options.get("rate", "+0%"))
        volume = str(request.provider_options.get("volume", "+0%"))
        pitch = str(request.provider_options.get("pitch", "+0Hz"))
        media_path = output_path if request.output_format == "mp3" else output_path.with_suffix(".edge.mp3")

        _run_edge_tts_cli(
            text=request.text,
            voice=voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
            output_path=media_path,
        )

        conversion_seconds = 0.0
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


class ChatterboxTTSProvider:
    provider_name = "chatterbox"
    capabilities = CHATTERBOX_TTS_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """Chatterbox TTS 모델로 감정 파라미터와 참조 음성을 반영한 wav를 생성한다."""
        started_at = time.perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sf = import_module("soundfile")
        device = _resolve_chatterbox_device(str(request.provider_options.get("device", "auto")))
        model = _load_chatterbox_model(device=device)

        generate_kwargs: dict[str, Any] = {
            "exaggeration": float(request.provider_options.get("exaggeration", request.intensity)),
            "cfg_weight": float(request.provider_options.get("cfg_weight", 0.4)),
            "temperature": float(request.provider_options.get("temperature", 0.6)),
        }
        audio_prompt_path = str(request.provider_options.get("audio_prompt_path", "")).strip()
        if audio_prompt_path and Path(audio_prompt_path).exists():
            generate_kwargs["audio_prompt_path"] = audio_prompt_path

        audio = model.generate(request.text, **generate_kwargs)
        sample_rate = int(getattr(model, "sr", request.sample_rate))
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


class ElevenLabsTTSProvider:
    provider_name = "elevenlabs"
    capabilities = ELEVENLABS_TTS_CAPABILITIES

    def synthesize(self, request: TTSProviderRequest, output_path: Path) -> dict[str, Any]:
        """ElevenLabs API로 음성을 생성하고 Unreal 전달용 wav로 변환한다."""
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

        with httpx.Client(timeout=float(request.provider_options.get("timeout_seconds", 60.0))) as client:
            response = client.post(
                f"{base_url}/text-to-speech/{voice_id}",
                params={"output_format": api_output_format},
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "text": request.text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": float(request.provider_options.get("stability", 0.52)),
                        "similarity_boost": float(request.provider_options.get("similarity_boost", 0.82)),
                        "style": float(request.provider_options.get("style", 0.42)),
                        "speed": float(request.provider_options.get("speed", request.speaking_rate)),
                        "use_speaker_boost": bool(request.provider_options.get("use_speaker_boost", True)),
                    },
                },
            )
            response.raise_for_status()
            media_path.write_bytes(response.content)

        conversion_seconds = 0.0
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
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def _wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        frame_rate = wav.getframerate()
        return wav.getnframes() / frame_rate if frame_rate else 0.0


def _load_chatterbox_model(*, device: str) -> Any:
    cached = _CHATTERBOX_MODEL_CACHE.get(device)
    if cached is not None:
        return cached
    chatterbox_module = import_module("chatterbox.tts")
    model_type = cast(Any, chatterbox_module).ChatterboxTTS
    model = model_type.from_pretrained(device=device)
    _CHATTERBOX_MODEL_CACHE[device] = model
    return model


def _resolve_chatterbox_device(device: str) -> str:
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
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    if getattr(audio, "ndim", 1) == 2 and audio.shape[0] < audio.shape[1]:
        return audio.T
    return audio


def configure_espeak_runtime() -> None:
    """Windows 환경에서 Kokoro phonemizer가 espeak-ng runtime을 찾도록 설정한다."""
    try:
        espeakng_loader = import_module("espeakng_loader")
        wrapper_module = import_module("phonemizer.backend.espeak.wrapper")
    except ImportError:
        return

    espeak_wrapper = cast(Any, wrapper_module).EspeakWrapper
    library_path = cast(Any, espeakng_loader).get_library_path()
    data_path = cast(Any, espeakng_loader).get_data_path()
    os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = library_path
    os.environ["ESPEAK_DATA_PATH"] = data_path
    espeak_wrapper.set_library(library_path)
    if not hasattr(espeak_wrapper, "set_data_path"):

        def set_data_path(path: str) -> None:
            espeak_wrapper.data_path = path

        espeak_wrapper.set_data_path = staticmethod(set_data_path)
    espeak_wrapper.set_data_path(data_path)


def _write_valid_fake_wav(path: Path, sample_rate: int, seconds: float) -> None:
    frame_count = int(sample_rate * seconds)
    amplitude = 1200
    frequency = 220.0
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frame_count):
            # 단순 사인파로 유효한 16-bit PCM wav를 만든다.
            value = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            wav.writeframes(struct.pack("<h", value))
