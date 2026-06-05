from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast
import math
import os
import struct
import time
import wave


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
