from pathlib import Path
from typing import Any
import json
import os
import subprocess
import time
import wave

import httpx


API_BASE_URL = "https://api.elevenlabs.io/v1"
OUTPUT_DIR = Path("backend/runtime/generated/audio/elevenlabs/civilian_extreme_anger")
OUTPUT_FORMAT = "mp3_44100_128"


def main() -> None:
    _load_dotenv()
    api_key = os.getenv("MURPHY_ELEVENLABS_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ElevenLabs API key is required.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model_id = os.getenv("MURPHY_ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
    results = []
    with httpx.Client(timeout=120) as client:
        voices = _select_voice_candidates(client=client, api_key=api_key)
        for voice in voices:
            for sample in _samples():
                results.append(
                    _generate(
                        client=client,
                        api_key=api_key,
                        voice=voice,
                        model_id=model_id,
                        sample=sample,
                    )
                )

    metadata_path = OUTPUT_DIR / "civilian_extreme_anger_metadata.json"
    metadata_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        print(result)
    print({"metadata_path": str(metadata_path)})


def _select_voice_candidates(*, client: httpx.Client, api_key: str) -> list[dict[str, str]]:
    response = client.get(f"{API_BASE_URL}/voices", headers={"xi-api-key": api_key})
    response.raise_for_status()
    voices = response.json().get("voices", [])
    preferred_names = (
        "Adam",
        "George",
        "Brian",
        "Josh",
        "Roger - Laid-Back, Casual, Resonant",
    )
    selected: list[dict[str, str]] = []
    for preferred_name in preferred_names:
        for voice in voices:
            if str(voice.get("name", "")).lower() == preferred_name.lower():
                selected.append({"voice_id": str(voice["voice_id"]), "voice_name": str(voice["name"])})
                break
        if len(selected) >= 3:
            break
    if not selected:
        configured_voice_id = os.getenv("MURPHY_ELEVENLABS_VOICE_ID", "CwhRBWXzGAHq8TQ4Fs17")
        selected.append({"voice_id": configured_voice_id, "voice_name": "configured_voice"})
    return selected


def _samples() -> list[dict[str, Any]]:
    return [
        {
            "name": "rage_back_off",
            "text": (
                "Are you kidding me? "
                "What the hell is your problem? "
                "Back the fuck off. Right now."
            ),
            "emotion_state": {
                "friendliness": -100,
                "patience": 0,
                "anger": 100,
                "arousal": 100,
                "trust": -100,
                "conversation_state": "explosive_boundary",
            },
            "settings": {
                "stability": 0.12,
                "similarity_boost": 0.92,
                "style": 1.0,
                "speed": 0.93,
                "use_speaker_boost": True,
            },
        },
        {
            "name": "rage_stop_talking",
            "text": (
                "Shut your mouth. "
                "I am not your punching bag. "
                "Say one more word like that, and I am calling security."
            ),
            "emotion_state": {
                "friendliness": -100,
                "patience": 0,
                "anger": 100,
                "arousal": 96,
                "trust": -100,
                "conversation_state": "security_warning",
            },
            "settings": {
                "stability": 0.16,
                "similarity_boost": 0.9,
                "style": 1.0,
                "speed": 0.88,
                "use_speaker_boost": True,
            },
        },
        {
            "name": "rage_get_out",
            "text": (
                "No. We are done. "
                "Get the hell away from me. "
                "I do not want to hear another damn word from you."
            ),
            "emotion_state": {
                "friendliness": -100,
                "patience": 0,
                "anger": 98,
                "arousal": 92,
                "trust": -100,
                "conversation_state": "conversation_terminated",
            },
            "settings": {
                "stability": 0.18,
                "similarity_boost": 0.9,
                "style": 0.98,
                "speed": 0.86,
                "use_speaker_boost": True,
            },
        },
    ]


def _generate(
    *,
    client: httpx.Client,
    api_key: str,
    voice: dict[str, str],
    model_id: str,
    sample: dict[str, Any],
) -> dict[str, Any]:
    started_at = time.perf_counter()
    voice_slug = _slug(voice["voice_name"])
    mp3_path = OUTPUT_DIR / f"{voice_slug}_{sample['name']}.mp3"
    wav_path = OUTPUT_DIR / f"{voice_slug}_{sample['name']}.wav"
    response = client.post(
        f"{API_BASE_URL}/text-to-speech/{voice['voice_id']}",
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
        "voice_name": voice["voice_name"],
        "voice_id": voice["voice_id"],
        "name": sample["name"],
        "text": sample["text"],
        "emotion_state": sample["emotion_state"],
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


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_")


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
