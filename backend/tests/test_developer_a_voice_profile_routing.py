from unittest.mock import patch
from backend.app.services.service_a.voice_profile_service import resolve_voice_profile
from backend.app.services.service_a.voice_output_service import _per_npc_voice_or_override

# 1. ElevenLabs 프로바이더 환경에서 정상 등록된 NPC(arabella)의 voice_id가 맵핑되는지 검증합니다.
def test_resolve_voice_profile_elevenlabs_known_npc() -> None:
    profile = resolve_voice_profile("user_test", "arabella", tts_provider="elevenlabs")
    
    assert profile.user_id == "user_test"
    assert profile.npc_id == "arabella"
    assert profile.voice_profile_id == "user_test:arabella:elevenlabs"
    assert profile.provider == "elevenlabs"
    assert profile.voice_id == "Z3R5wn05IrDiVCyEkUrK"

# 2. Edge 프로바이더 환경에서 정상 등록된 NPC(arabella)의 voice_id가 맵핑되는지 검증합니다.
def test_resolve_voice_profile_edge_known_npc() -> None:
    profile = resolve_voice_profile("user_test", "arabella", tts_provider="edge")
    
    assert profile.user_id == "user_test"
    assert profile.npc_id == "arabella"
    assert profile.voice_profile_id == "user_test:arabella:edge"
    assert profile.provider == "edge"
    assert profile.voice_id == "en-US-AvaNeural"

# 3. 미등록 NPC 혹은 알 수 없는 NPC의 경우 ElevenLabs 및 Edge 환경에서 적절한 fallback 목소리가 맵핑되는지 검증합니다.
def test_resolve_voice_profile_unknown_npc_fallback() -> None:
    # ElevenLabs fallback 검증
    profile_eleven = resolve_voice_profile("user_test", "unknown_npc", tts_provider="elevenlabs")
    assert profile_eleven.npc_id == "hale"  # 기본 Hale로 노멀라이즈
    assert profile_eleven.voice_id == "dXtC3XhB9GtPusIpNtQx"  # Hale의 ElevenLabs 목소리

    # Edge fallback 검증
    profile_edge = resolve_voice_profile("user_test", "unknown_npc", tts_provider="edge")
    assert profile_edge.npc_id == "hale"
    assert profile_edge.voice_id == "en-US-GuyNeural"

# 4. _per_npc_voice_or_override 헬퍼 함수의 우선순위 규칙이 제대로 적용되는지 검증합니다.
def test_per_npc_voice_or_override_rules(monkeypatch) -> None:
    # 준비물 정의
    force_key = "MURPHY_ELEVENLABS_VOICE_ID_FORCE"
    deprecated_key = "MURPHY_ELEVENLABS_VOICE_ID"
    fallback_val = "CwhRBWXzGAHq8TQ4Fs17"
    npc_val = "npc_specific_voice_id"
    forced_val = "forced_voice_id"
    deprecated_val = "deprecated_voice_id"

    # 모든 환경변수가 비어있고 NPC 목소리가 주어졌을 때 -> NPC 목소리 우선 적용 검증
    monkeypatch.delenv(force_key, raising=False)
    monkeypatch.delenv(deprecated_key, raising=False)
    
    result = _per_npc_voice_or_override(
        npc_voice=npc_val,
        force_env_key=force_key,
        deprecated_env_key=deprecated_key,
        fallback=fallback_val
    )
    assert result == npc_val

    # 강제 오버라이드 환경변수(_FORCE)가 주어졌을 때 -> 강제 오버라이드가 최우선 적용 검증
    monkeypatch.setenv(force_key, forced_val)
    result = _per_npc_voice_or_override(
        npc_voice=npc_val,
        force_env_key=force_key,
        deprecated_env_key=deprecated_key,
        fallback=fallback_val
    )
    assert result == forced_val
    
    # 강제 오버라이드가 없고, NPC 목소리도 없고, deprecated 환경변수만 설정되었을 때 -> deprecated 값이 하위 호환으로 적용되는지 검증
    monkeypatch.delenv(force_key, raising=False)
    monkeypatch.setenv(deprecated_key, deprecated_val)
    
    # logger warning 출력을 확인하기 위해 patch
    with patch("backend.app.services.service_a.voice_output_service.logger.warning") as mock_warn:
        result = _per_npc_voice_or_override(
            npc_voice="",
            force_env_key=force_key,
            deprecated_env_key=deprecated_key,
            fallback=fallback_val
        )
        assert result == deprecated_val
        mock_warn.assert_called_once()

    # 모든 값이 없을 때 -> fallback(기본값) 적용 검증
    monkeypatch.delenv(force_key, raising=False)
    monkeypatch.delenv(deprecated_key, raising=False)
    result = _per_npc_voice_or_override(
        npc_voice="",
        force_env_key=force_key,
        deprecated_env_key=deprecated_key,
        fallback=fallback_val
    )
    assert result == fallback_val
