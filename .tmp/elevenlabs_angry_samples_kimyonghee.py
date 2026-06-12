from pathlib import Path
from typing import Any
import json
import os
import subprocess
import time
import wave

import httpx


API_BASE_URL = "https://api.elevenlabs.io/v1"
OUTPUT_DIR = Path("backend/runtime/generated/audio/elevenlabs/angry_samples")
OUTPUT_FORMAT = "mp3_44100_128"


def main() -> None:
    _load_dotenv()
    api_key = os.getenv("MURPHY_ELEVENLABS_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ElevenLabs API key is required.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    voice_id = os.getenv("MURPHY_ELEVENLABS_VOICE_ID", "CwhRBWXzGAHq8TQ4Fs17")
    model_id = os.getenv("MURPHY_ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
    samples: list[dict[str, Any]] = [
        {
            "name": "angry_firm_reask",
            "text": "No. Listen carefully. Answer the question directly. How long will you be staying?",
            "settings": {
                "stability": 0.34,
                "similarity_boost": 0.88,
                "style": 0.82,
                "speed": 0.74,
                "use_speaker_boost": True,
            },
        },
        {
            "name": "angry_secondary_warning",
            "text": (
                "Sir. This is your warning. If you cannot answer clearly, "
                "I may send you to secondary inspection."
            ),
            "settings": {
                "stability": 0.30,
                "similarity_boost": 0.90,
                "style": 0.92,
                "speed": 0.72,
                "use_speaker_boost": True,
            },
        },
        {
            "name": "angry_short_command",
            "text": "Stop. Answer only the question. How long are you staying?",
            "settings": {
                "stability": 0.28,
                "similarity_boost": 0.88,
                "style": 0.95,
                "speed": 0.76,
                "use_speaker_boost": True,
            },
        },
    ]

    results = []
    with httpx.Client(timeout=120) as client:
        for sample in samples:
            results.append(
                _generate(
                    client=client,
                    api_key=api_key,
                    voice_id=voice_id,
                    model_id=model_id,
                    sample=sample,
                )
            )

    metadata_path = OUTPUT_DIR / "elevenlabs_angry_samples_metadata.json"
    metadata_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        print(result)
    print({"metadata_path": str(metadata_path)})


def _generate(
    *,
    client: httpx.Client,
    api_key: str,
    voice_id: str,
    model_id: str,
    sample: dict[str, Any],
) -> dict[str, Any]:
    started_at = time.perf_counter()
    mp3_path = OUTPUT_DIR / f"officer_miller_{sample['name']}.mp3"
    wav_path = OUTPUT_DIR / f"officer_miller_{sample['name']}.wav"
    response = client.post(
        f"{API_BASE_URL}/text-to-speech/{voice_id}",
        params={"output_format": OUTPUT_FORMAT},
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": sample["text"],
            "model_id": model_id,
            "voice_settings": sample["settings"],
        },
    )
    response.raise_for_status()
    mp3_path.write_bytes(response.content)
    api_seconds = time.perf_counter() - started_at

    conversion_started_at = time.perf_counter()
    _convert_mp3_to_wav(mp3_path=mp3_path, wav_path=wav_path)
    conversion_seconds = time.perf_counter() - conversion_started_at
    total_seconds = time.perf_counter() - started_at
    audio_seconds = _wav_duration_seconds(wav_path)
    return {
        "name": sample["name"],
        "text": sample["text"],
        "voice_id": voice_id,
        "model_id": model_id,
        "settings": sample["settings"],
        "wav_path": str(wav_path),
        "api_seconds": round(api_seconds, 3),
        "conversion_seconds": round(conversion_seconds, 3),
        "total_seconds": round(total_seconds, 3),
        "audio_seconds": round(audio_seconds, 3),
    }


def _convert_mp3_to_wav(*, mp3_path: Path, wav_path: Path) -> None:
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


def _load_dotenv() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()
