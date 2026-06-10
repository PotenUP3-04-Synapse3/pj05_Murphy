from pathlib import Path
from typing import Any
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.service_a.tts_provider_service import (
    ChatterboxTTSProvider,
    TTSProviderRequest,
)


OUTPUT_DIR = Path("backend/runtime/generated/audio/chatterbox/emotion_samples")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = [
        {
            "name": "calm_slow",
            "emotion": "calm_official",
            "tone": "formal_neutral",
            "text": "All right. How long will you be staying?",
            "exaggeration": 0.45,
            "cfg_weight": 0.50,
            "temperature": 0.55,
            "atempo": 0.88,
        },
        {
            "name": "firm_slow",
            "emotion": "firm_official",
            "tone": "formal_firm",
            "text": "Okay. Tell me clearly. How long will you be staying?",
            "exaggeration": 0.65,
            "cfg_weight": 0.38,
            "temperature": 0.58,
            "atempo": 0.84,
        },
        {
            "name": "suspicious_slow",
            "emotion": "suspicious_official",
            "tone": "formal_stern",
            "text": "Hmm. You are here for tourism. How long will you be staying?",
            "exaggeration": 0.78,
            "cfg_weight": 0.32,
            "temperature": 0.62,
            "atempo": 0.80,
        },
        {
            "name": "irritated_slow",
            "emotion": "irritated_official",
            "tone": "formal_warning",
            "text": "Sir. Listen carefully. I need a direct answer. How long will you be staying?",
            "exaggeration": 0.92,
            "cfg_weight": 0.24,
            "temperature": 0.64,
            "atempo": 0.78,
        },
        {
            "name": "secondary_warning_slow",
            "emotion": "warning_official",
            "tone": "formal_warning",
            "text": "If you cannot answer clearly, I may send you to secondary inspection. How long will you be staying?",
            "exaggeration": 1.05,
            "cfg_weight": 0.20,
            "temperature": 0.66,
            "atempo": 0.76,
        },
    ]

    for sample in samples:
        started_at = time.perf_counter()
        raw_path = OUTPUT_DIR / f"officer_miller_{sample['name']}_raw.wav"
        slow_path = OUTPUT_DIR / f"officer_miller_{sample['name']}.wav"
        request = TTSProviderRequest(
            provider="chatterbox",
            text=str(sample["text"]),
            speaker_id="officer_miller",
            voice_profile_id="emotion_samples:officer_miller",
            language="en",
            emotion=str(sample["emotion"]),
            tone=str(sample["tone"]),
            intensity=float(sample["exaggeration"]),
            speaking_rate=1.0,
            pitch=0.0,
            sample_rate=24000,
            output_format="wav",
            provider_options={
                "voice": "officer_miller_ref",
                "audio_prompt_path": "",
                "exaggeration": float(sample["exaggeration"]),
                "cfg_weight": float(sample["cfg_weight"]),
                "temperature": float(sample["temperature"]),
                "device": "auto",
                "language_id": "en",
            },
        )
        metadata = ChatterboxTTSProvider().synthesize(request, raw_path)
        _slow_audio(raw_path=raw_path, slow_path=slow_path, atempo=float(sample["atempo"]))
        elapsed = time.perf_counter() - started_at
        print(
            {
                "name": sample["name"],
                "text": sample["text"],
                "raw_path": str(raw_path),
                "slow_path": str(slow_path),
                "atempo": sample["atempo"],
                "provider_device": metadata.get("provider_options", {}).get("device"),
                "raw_generation_seconds": metadata.get("generation_seconds"),
                "elapsed_seconds": elapsed,
            }
        )


def _slow_audio(*, raw_path: Path, slow_path: Path, atempo: float) -> None:
    # Chatterbox에는 속도 파라미터가 없어서 ffmpeg atempo로 pitch를 유지한 채 재생 시간을 늘린다.
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_path),
            "-filter:a",
            f"atempo={atempo}",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "24000",
            str(slow_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


if __name__ == "__main__":
    main()
