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
}


def resolve_voice_profile(user_id: str, npc_id: str) -> VoiceProfile:
    """동일 유저(User)와 NPC 조합의 경우 항상 일관된(Deterministic) voice profile 결과를 결정 및 유지하도록 반환합니다."""
    safe_user_id = user_id or "user_unknown"
    npc_profile = resolve_npc_profile(npc_id)
    
    return VoiceProfile(
        user_id=safe_user_id,
        npc_id=npc_profile.npc_id,
        voice_profile_id=f"{safe_user_id}:{npc_profile.npc_id}",
        provider="edge",
        voice_id=_NPC_EDGE_VOICES.get(npc_profile.npc_id, "en-US-GuyNeural"),
    )
