from pathlib import Path
import hashlib
import re


def build_audio_cache_key(
    text: str,
    voice: str,
    speed: float,
    sample_rate: int,
    output_format: str,
    model_version: str,
    provider: str = "kokoro",
) -> str:
    """같은 provider, 대사, 음성 설정이면 같은 파일 경로를 쓰도록 cache key를 만든다."""
    raw = "|".join([provider, text, voice, f"{speed:.3f}", str(sample_rate), output_format, model_version])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def audio_output_path(
    root: Path,
    cache_key: str,
    output_format: str,
    node_id: str | None = None,
    target_slot: str | None = None,
    branch_type: str | None = None,
    voice_id: str | None = None,
    provider: str = "kokoro",
) -> Path:
    filename = build_audio_filename(
        cache_key=cache_key,
        output_format=output_format,
        node_id=node_id,
        target_slot=target_slot,
        branch_type=branch_type,
        voice_id=voice_id,
    )
    return root / "audio" / _safe_slug(provider or "kokoro") / filename


def build_audio_filename(
    cache_key: str,
    output_format: str,
    node_id: str | None = None,
    target_slot: str | None = None,
    branch_type: str | None = None,
    voice_id: str | None = None,
) -> str:
    """사람이 구분 가능한 prefix와 짧은 hash를 결합한 파일명을 만든다."""
    parts = [
        _safe_slug(node_id or "unknown_node"),
        _safe_slug(target_slot or "unknown_slot"),
        _safe_slug(branch_type or "neutral"),
        _safe_slug(voice_id or "unknown_voice"),
        cache_key[:8],
    ]
    return f"{'_'.join(parts)}.{_safe_slug(output_format or 'wav')}"


def _safe_slug(value: str) -> str:
    # Windows 파일명과 URL 경로에서 모두 안전하도록 영문, 숫자, 밑줄만 남긴다.
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "unknown"
