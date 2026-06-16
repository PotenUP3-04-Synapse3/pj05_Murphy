from dataclasses import dataclass

from backend.app.services.service_a.npc_roster_service import resolve_npc_profile


# 유저와 NPC 캐릭터 조합에 귀속되는 단일 음성 출력 프로필 사양 정보 클래스(Class)입니다.
@dataclass(frozen=True)
class VoiceProfile:
    user_id: str          # 유저 식별값 (User ID)
    npc_id: str           # NPC 캐릭터 식별값 (NPC ID)
    voice_profile_id: str # 해시 매핑을 위한 가상 음성 프로필 ID
    provider: str         # 적용 대상 TTS 엔진명 (예: kokoro)
    voice_id: str         # 엔진이 음성 출력 시 사용할 고유 voice id


_NPC_EDGE_VOICES: dict[str, str] = {
    "arabella": "en-US-AvaNeural",
    "novak": "en-US-BrianNeural",
    "hale": "en-US-GuyNeural",
    "harris": "en-US-SoniaNeural",
    "dan": "en-US-GuyNeural",
    "brielle": "en-US-AvaNeural",
    "emily": "en-US-AvaNeural",
}


def resolve_voice_profile(
    user_id: str,
    npc_id: str,
    *,
    tts_provider: str = "edge",
) -> VoiceProfile:
    """동일 유저(User)와 NPC 조합의 경우 항상 일관된(Deterministic) voice profile 결과를 결정 및 유지하도록 반환합니다.
    tts_provider 매개변수(Parameter)를 도입하여 ElevenLabs와 Edge 엔진(Engine)별 고유 음성 ID를 다르게 선택합니다.
    """
    safe_user_id = user_id or "user_unknown"
    npc_profile = resolve_npc_profile(npc_id)
    
    # elevenlabs를 사용하는 경우에는 ElevenLabs 전용 voice_id를 적용하고, 
    # 그렇지 않은 경우에는 기존 Edge TTS용 voice_id 사전을 이용해 맵핑합니다.
    if tts_provider == "elevenlabs":
        voice_id = npc_profile.elevenlabs_voice_id or "CwhRBWXzGAHq8TQ4Fs17"
    else:
        voice_id = _NPC_EDGE_VOICES.get(npc_profile.npc_id, "en-US-GuyNeural")
        
    return VoiceProfile(
        user_id=safe_user_id,
        npc_id=npc_profile.npc_id,
        # 엔진별로 서로 다른 오디오 캐시(Audio Cache)가 만들어질 수 있도록 voice_profile_id 식별 문자열에 tts_provider를 명시합니다.
        voice_profile_id=f"{safe_user_id}:{npc_profile.npc_id}:{tts_provider}",
        provider=tts_provider,
        voice_id=voice_id,
    )
