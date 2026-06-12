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
    """동일한 대사 제공자(Provider), 텍스트 대사(Text), 음성 캐릭터(Voice), 발화 속도(Speed), 샘플 레이트(Sample Rate) 등을 
    조합하여 오디오 파일의 고유한 캐시 키(Cache Key)를 해시(Hash) 문자열로 생성합니다.
    """
    raw = "|".join([provider, text, voice, f"{speed:.3f}", str(sample_rate), output_format, model_version])
    # SHA-256 해시 함수(Hash Function)를 사용하여 캐시 유일성을 보장합니다.
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
    """음성 출력 파일이 로컬(Local) 디스크 또는 스토리지(Storage)에 저장될 최종 절대 경로(Absolute Path) 객체를 구성합니다."""
    # 사람이 식별 가능한 힌트 정보를 바탕으로 안전한 파일 이름(File Name)을 구성합니다.
    filename = build_audio_filename(
        cache_key=cache_key,
        output_format=output_format,
        node_id=node_id,
        target_slot=target_slot,
        branch_type=branch_type,
        voice_id=voice_id,
    )
    # 특정 제공자별 하위 디렉토리에 파일을 격리하여 저장합니다.
    return root / "audio" / _safe_slug(provider or "kokoro") / filename


def build_audio_filename(
    cache_key: str,
    output_format: str,
    node_id: str | None = None,
    target_slot: str | None = None,
    branch_type: str | None = None,
    voice_id: str | None = None,
) -> str:
    """디버깅 시 개발자가 쉽게 파일을 눈으로 구분할 수 있는 프리픽스(Prefix)와 캐시 해시값의 일부분을 결합해 파일명을 만듭니다."""
    parts = [
        _safe_slug(node_id or "unknown_node"),
        _safe_slug(target_slot or "unknown_slot"),
        _safe_slug(branch_type or "neutral"),
        _safe_slug(voice_id or "unknown_voice"),
        cache_key[:8], # 해시 문자열의 앞 8자리만 사용하여 식별자로 씁니다.
    ]
    return f"{'_'.join(parts)}.{_safe_slug(output_format or 'wav')}"


def _safe_slug(value: str) -> str:
    """운영체제(OS) 파일 명명 규칙 및 URL 주소 체계에서 오작동을 유발할 수 있는 특수문자를 제거하고 안전한 문자열(Slug)로 변환합니다."""
    # 정규식(Regular Expression)을 사용하여 알파벳, 숫자, 밑줄(_)을 제외한 문자를 밑줄로 대체합니다.
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "unknown"
