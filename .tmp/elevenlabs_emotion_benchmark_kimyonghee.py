from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import subprocess
import time
import wave

import httpx


API_BASE_URL = "https://api.elevenlabs.io/v1"
OUTPUT_DIR = Path("backend/runtime/generated/audio/elevenlabs/emotion_samples")
OUTPUT_FORMAT = "mp3_44100_128"
MODEL_IDS = ("eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2")


@dataclass(frozen=True)
class EmotionSample:
    name: str
    text: str
    stability: float
    similarity_boost: float
    style: float
    speed: float
    use_speaker_boost: bool


def main() -> None:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY 환경변수가 필요합니다.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=120)
    headers = {"xi-api-key": api_key}
    voice = _select_voice(client=client, headers=headers)
    print({"selected_voice_id": voice["voice_id"], "selected_voice_name": voice["name"]})

    samples = [
        EmotionSample(
            name="calm",
            text="All right. How long will you be staying?",
            stability=0.72,
            similarity_boost=0.78,
            style=0.10,
            speed=0.86,
            use_speaker_boost=True,
        ),
        EmotionSample(
            name="firm",
            text="Okay. Tell me clearly. How long will you be staying?",
            stability=0.62,
            similarity_boost=0.80,
            style=0.28,
            speed=0.84,
            use_speaker_boost=True,
        ),
        EmotionSample(
            name="suspicious",
            text="Hmm. You are here for tourism. How long will you be staying?",
            stability=0.52,
            similarity_boost=0.82,
            style=0.42,
            speed=0.80,
            use_speaker_boost=True,
        ),
        EmotionSample(
            name="irritated",
            text="Sir. Listen carefully. I need a direct answer. How long will you be staying?",
            stability=0.44,
            similarity_boost=0.84,
            style=0.62,
            speed=0.78,
            use_speaker_boost=True,
        ),
        EmotionSample(
            name="secondary_warning",
            text=(
                "If you cannot answer clearly, I may send you to secondary inspection. "
                "How long will you be staying?"
            ),
            stability=0.38,
            similarity_boost=0.86,
            style=0.78,
            speed=0.76,
            use_speaker_boost=True,
        ),
    ]

    results: list[dict[str, Any]] = []
    for model_id in MODEL_IDS:
        for sample in samples:
            results.append(
                _generate_sample(
                    client=client,
                    headers=headers,
                    voice_id=str(voice["voice_id"]),
                    voice_name=str(voice["name"]),
                    model_id=model_id,
                    sample=sample,
                )
            )

    metadata_path = OUTPUT_DIR / "elevenlabs_emotion_benchmark_metadata.json"
    metadata_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print({"metadata_path": str(metadata_path), "sample_count": len(results)})
    for result in results:
        print(result)


def _select_voice(*, client: httpx.Client, headers: dict[str, str]) -> dict[str, Any]:
    configured_voice_id = os.getenv("ELEVENLABS_VOICE_ID")
    response = client.get(f"{API_BASE_URL}/voices", headers=headers)
    response.raise_for_status()
    voices = response.json().get("voices", [])
    if configured_voice_id:
        for voice in voices:
            if voice.get("voice_id") == configured_voice_id:
                return voice
        return {"voice_id": configured_voice_id, "name": "configured_voice"}

    # Officer Miller 역할에 맞게 낮고 단호한 남성 premade voice를 우선 선택한다.
    preferred_names = ("Adam", "George", "Brian", "Antoni", "Josh")
    for preferred_name in preferred_names:
        for voice in voices:
            if str(voice.get("name", "")).lower() == preferred_name.lower():
                return voice
    if not voices:
        raise RuntimeError("ElevenLabs voice 목록이 비어 있습니다.")
    return voices[0]


def _generate_sample(
    *,
    client: httpx.Client,
    headers: dict[str, str],
    voice_id: str,
    voice_name: str,
    model_id: str,
    sample: EmotionSample,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    mp3_path = OUTPUT_DIR / f"officer_miller_{model_id}_{sample.name}.mp3"
    wav_path = OUTPUT_DIR / f"officer_miller_{model_id}_{sample.name}.wav"
    payload = {
        "text": sample.text,
        "model_id": model_id,
        "voice_settings": {
            "stability": sample.stability,
            "similarity_boost": sample.similarity_boost,
            "style": sample.style,
            "speed": sample.speed,
            "use_speaker_boost": sample.use_speaker_boost,
        },
    }
    response = client.post(
        f"{API_BASE_URL}/text-to-speech/{voice_id}",
        params={"output_format": OUTPUT_FORMAT},
        headers={**headers, "Content-Type": "application/json"},
        json=payload,
    )
    response.raise_for_status()
    mp3_path.write_bytes(response.content)
    api_seconds = time.perf_counter() - started_at

    conversion_started_at = time.perf_counter()
    _convert_mp3_to_wav(mp3_path=mp3_path, wav_path=wav_path)
    conversion_seconds = time.perf_counter() - conversion_started_at
    audio_seconds = _wav_duration_seconds(wav_path)
    total_seconds = time.perf_counter() - started_at

    return {
        "provider": "elevenlabs",
        "model_id": model_id,
        "voice_id": voice_id,
        "voice_name": voice_name,
        "emotion": sample.name,
        "text": sample.text,
        "voice_settings": payload["voice_settings"],
        "mp3_path": str(mp3_path),
        "wav_path": str(wav_path),
        "api_seconds": round(api_seconds, 3),
        "conversion_seconds": round(conversion_seconds, 3),
        "total_seconds": round(total_seconds, 3),
        "audio_seconds": round(audio_seconds, 3),
        "real_time_factor": round(total_seconds / audio_seconds, 3) if audio_seconds else None,
    }


def _convert_mp3_to_wav(*, mp3_path: Path, wav_path: Path) -> None:
    # Unreal 전달 테스트를 위해 MP3 응답을 24kHz mono PCM WAV로 변환한다.
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp3_path),
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "24000",
            str(wav_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        frame_rate = wav.getframerate()
        return wav.getnframes() / frame_rate if frame_rate else 0.0


if __name__ == "__main__":
    main()
