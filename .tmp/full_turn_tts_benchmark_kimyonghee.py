from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import subprocess
import sys
import time
import wave

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.main import app


TURN_JSON_PATH = Path("demo/input/imm_002_purpose.json")
AUDIO_PATH = Path("samples/tour.wav")
OUTPUT_DIR = Path("backend/runtime/generated/audio/tts_full_turn_benchmark")
ELEVENLABS_API_BASE_URL = "https://api.elevenlabs.io/v1"
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _load_dotenv()
    _configure_real_llm_turn()

    results: list[dict[str, Any]] = []
    for provider in ("kokoro", "edge", "chatterbox", "elevenlabs"):
        results.append(_run_full_turn_provider(provider=provider))

    npc_text = str(results[0].get("npc_text") or "How long will you be staying?")
    results.append(_run_elevenlabs_tts_only(npc_text=npc_text))

    output_path = OUTPUT_DIR / "full_turn_tts_benchmark_metadata.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print({"metadata_path": str(output_path)})
    for result in results:
        print(result)


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


def _configure_real_llm_turn() -> None:
    os.environ["MURPHY_STT_MODE"] = "local"
    os.environ["MURPHY_TTS_MODE"] = "real"
    os.environ["MURPHY_UNDERSTANDING_MODE"] = "llm"
    os.environ["MURPHY_NPC_DIALOGUE_MODE"] = "llm"
    os.environ["DEV_B_FEEDBACK_LLM_MODE"] = "llm"
    os.environ.setdefault("MURPHY_CHATTERBOX_DEVICE", "auto")


def _run_full_turn_provider(*, provider: str) -> dict[str, Any]:
    os.environ["MURPHY_TTS_PROVIDER"] = provider
    payload = json.loads(TURN_JSON_PATH.read_text(encoding="utf-8"))
    payload["request_id"] = f"req_benchmark_{provider}_{int(time.time() * 1000)}"
    payload["session"]["session_id"] = f"session_benchmark_{provider}"
    started_at = time.perf_counter()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/game/ai/respond",
            data={"turn": json.dumps(payload, ensure_ascii=False)},
            files={"audio": (AUDIO_PATH.name, AUDIO_PATH.read_bytes(), "audio/wav")},
        )
    elapsed = time.perf_counter() - started_at
    try:
        response_body = response.json()
    except Exception:
        response_body = {"raw_text": response.text}
    tts = _extract_tts(response_body)
    return {
        "provider": provider,
        "scope": "full_unreal_input_to_final_response",
        "http_status": response.status_code,
        "elapsed_seconds": round(elapsed, 3),
        "npc_text": response_body.get("npc", {}).get("text") or response_body.get("npc_text"),
        "stt_text": response_body.get("player_text") or response_body.get("transcript"),
        "next_action": response_body.get("next_action"),
        "next_node_id": response_body.get("next_node_id"),
        "audio_url": _deep_get(response_body, ("audio", "audio_url")) or tts.get("audio_url"),
        "tts": tts,
    }


def _extract_tts(response_body: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        response_body.get("tts"),
        response_body.get("audio"),
        _deep_get(response_body, ("npc", "tts")),
        _deep_get(response_body, ("voice", "tts")),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    agent_runs = response_body.get("agent_runs")
    if isinstance(agent_runs, list):
        for run in agent_runs:
            metadata = run.get("metadata") if isinstance(run, dict) else None
            if isinstance(metadata, dict) and isinstance(metadata.get("tts_summary"), dict):
                return metadata["tts_summary"]
    return {}


def _deep_get(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _run_elevenlabs_tts_only(*, npc_text: str) -> dict[str, Any]:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return {
            "provider": "elevenlabs",
            "scope": "tts_only_after_same_npc_text",
            "status": "skipped",
            "reason": "ELEVENLABS_API_KEY missing",
        }

    headers = {"xi-api-key": api_key}
    with httpx.Client(timeout=120) as client:
        voice = _select_elevenlabs_voice(client=client, headers=headers)
        started_at = time.perf_counter()
        mp3_path = OUTPUT_DIR / "elevenlabs_flash_same_npc_text.mp3"
        wav_path = OUTPUT_DIR / "elevenlabs_flash_same_npc_text.wav"
        response = client.post(
            f"{ELEVENLABS_API_BASE_URL}/text-to-speech/{voice['voice_id']}",
            params={"output_format": ELEVENLABS_OUTPUT_FORMAT},
            headers={**headers, "Content-Type": "application/json"},
            json={
                "text": npc_text,
                "model_id": "eleven_flash_v2_5",
                "voice_settings": {
                    "stability": 0.52,
                    "similarity_boost": 0.82,
                    "style": 0.42,
                    "speed": 0.8,
                    "use_speaker_boost": True,
                },
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
        "provider": "elevenlabs",
        "scope": "tts_only_after_same_npc_text",
        "model_id": "eleven_flash_v2_5",
        "voice_id": voice["voice_id"],
        "voice_name": voice["name"],
        "npc_text": npc_text,
        "api_seconds": round(api_seconds, 3),
        "conversion_seconds": round(conversion_seconds, 3),
        "elapsed_seconds": round(total_seconds, 3),
        "audio_seconds": round(audio_seconds, 3),
        "real_time_factor": round(total_seconds / audio_seconds, 3) if audio_seconds else None,
        "wav_path": str(wav_path),
    }


def _select_elevenlabs_voice(*, client: httpx.Client, headers: dict[str, str]) -> dict[str, Any]:
    configured_voice_id = os.getenv("ELEVENLABS_VOICE_ID")
    response = client.get(f"{ELEVENLABS_API_BASE_URL}/voices", headers=headers)
    response.raise_for_status()
    voices = response.json().get("voices", [])
    if configured_voice_id:
        for voice in voices:
            if voice.get("voice_id") == configured_voice_id:
                return voice
        return {"voice_id": configured_voice_id, "name": "configured_voice"}
    preferred_names = ("Roger - Laid-Back, Casual, Resonant", "Adam", "George", "Brian")
    for preferred_name in preferred_names:
        for voice in voices:
            if str(voice.get("name", "")).lower() == preferred_name.lower():
                return voice
    if not voices:
        raise RuntimeError("ElevenLabs voice 목록이 비어 있습니다.")
    return voices[0]


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


if __name__ == "__main__":
    main()
