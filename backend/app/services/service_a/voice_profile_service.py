from dataclasses import dataclass
import hashlib

from backend.app.services.service_a.npc_roster_service import resolve_npc_profile


@dataclass(frozen=True)
class VoiceProfile:
    user_id: str
    npc_id: str
    voice_profile_id: str
    provider: str
    voice_id: str


def resolve_voice_profile(user_id: str, npc_id: str) -> VoiceProfile:
    """동일 user+npc 조합에는 항상 같은 voice profile을 반환한다."""
    safe_user_id = user_id or "user_unknown"
    npc_profile = resolve_npc_profile(npc_id)
    digest = hashlib.sha256(f"{safe_user_id}:{npc_profile.npc_id}".encode("utf-8")).hexdigest()[:12]
    return VoiceProfile(
        user_id=safe_user_id,
        npc_id=npc_profile.npc_id,
        voice_profile_id=f"{safe_user_id}:{npc_profile.npc_id}",
        provider="kokoro",
        voice_id=_select_voice(digest, npc_profile.kokoro_voices),
    )


def _select_voice(digest: str, voices: tuple[str, ...]) -> str:
    index = int(digest[:4], 16) % len(voices)
    return voices[index]
