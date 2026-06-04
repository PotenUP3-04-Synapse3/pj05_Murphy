from pathlib import Path
from typing import Any
import audioop
import wave


def analyze_wav_quality(path: Path) -> dict[str, Any]:
    """wav 파일의 기본 품질 metadata를 추출한다."""
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frame_count = wav.getnframes()
        data = wav.readframes(frame_count)

    duration_ms = int(frame_count / sample_rate * 1000)
    maxamp = (2 ** (8 * sample_width - 1)) - 1
    window = max(1, int(sample_rate * 0.02))
    threshold = maxamp * 0.01
    silent_windows = 0
    total_windows = 0

    for start in range(0, frame_count, window):
        end = min(frame_count, start + window)
        chunk = data[start * channels * sample_width : end * channels * sample_width]
        if chunk:
            total_windows += 1
            if audioop.rms(chunk, sample_width) < threshold:
                silent_windows += 1

    return {
        "sample_rate": sample_rate,
        "channels": channels,
        "bit_depth": sample_width * 8,
        "duration_ms": duration_ms,
        "silent_ratio": silent_windows / total_windows if total_windows else 0.0,
    }


def build_postprocess_policy(provider: str) -> dict[str, Any]:
    """1차 구현에서는 실제 DSP 처리 대신 후처리 정책만 metadata로 남긴다."""
    return {
        "provider": provider,
        "target_sample_rate": 24000,
        "target_format": "wav",
        "target_channels": 1,
        "target_peak_dbfs": -3.0,
        "trim_outer_silence": True,
        "preserve_sentence_pause": True,
        "actual_dsp_applied": False,
    }
