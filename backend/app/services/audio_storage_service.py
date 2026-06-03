from pathlib import Path
import hashlib


def build_audio_cache_key(
    text: str,
    voice: str,
    speed: float,
    sample_rate: int,
    output_format: str,
    model_version: str,
) -> str:
    """대사와 voice 설정이 같으면 같은 wav path를 쓰도록 stable cache key를 만든다."""
    raw = "|".join([text, voice, f"{speed:.3f}", str(sample_rate), output_format, model_version])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def audio_output_path(root: Path, cache_key: str, output_format: str) -> Path:
    return root / "audio" / "kokoro" / f"{cache_key}.{output_format}"
