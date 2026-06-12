from dataclasses import dataclass
import hashlib

from backend.app.services.service_a.npc_roster_service import resolve_npc_profile


# 유저와 NPC 캐릭터 조합에 귀속되는 단일 음성 출력 프로필 사양 정보 클래스(Class)입니다.
@dataclass(frozen=True)
class VoiceProfile:
    user_id: str          # 유저 식별값 (User ID)
    npc_id: str           # NPC 캐릭터 식별값 (NPC ID)
    voice_profile_id: str # 해시 매핑을 위한 가상 음성 프로필 ID
    provider: str         # 적용 대상 TTS 엔진명 (예: kokoro)
    voice_id: str         # 엔진이 음성 출력 시 사용할 고유 voice id


def resolve_voice_profile(user_id: str, npc_id: str) -> VoiceProfile:
    """동일 유저(User)와 NPC 조합의 경우 항상 일관된(Deterministic) voice profile 결과를 결정 및 유지하도록 반환합니다."""
    safe_user_id = user_id or "user_unknown"
    npc_profile = resolve_npc_profile(npc_id)
    
    # 동일한 유저가 특정 NPC와 계속 대화 시 목소리가 임의로 바뀌지 않도록 SHA-256 해시 키(Hash Key)를 기준으로 고유 목소리 가중치를 추출합니다.
    digest = hashlib.sha256(f"{safe_user_id}:{npc_profile.npc_id}".encode("utf-8")).hexdigest()[:12]
    return VoiceProfile(
        user_id=safe_user_id,
        npc_id=npc_profile.npc_id,
        voice_profile_id=f"{safe_user_id}:{npc_profile.npc_id}",
        provider="kokoro",
        voice_id=_select_voice(digest, npc_profile.kokoro_voices),
    )


def _select_voice(digest: str, voices: tuple[str, ...]) -> str:
    """해시 키에서 16진수 일부분을 파싱하여 배정 가능한 음성 목록에서 인덱스(Index) 모듈러 연산으로 고정 음색을 안전하게 선정합니다."""
    index = int(digest[:4], 16) % len(voices)
    return voices[index]
