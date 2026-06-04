from dataclasses import dataclass
import hashlib


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
    safe_npc_id = npc_id or "officer_miller"
    digest = hashlib.sha256(f"{safe_user_id}:{safe_npc_id}".encode("utf-8")).hexdigest()[:12]
    return VoiceProfile(
        user_id=safe_user_id,
        npc_id=safe_npc_id,
        voice_profile_id=f"{safe_user_id}:{safe_npc_id}",
        provider="kokoro",
        voice_id=_select_officer_miller_voice(digest),
    )


def _select_officer_miller_voice(digest: str) -> str:
    # 1차 구현은 Officer Miller의 기본 Kokoro voice를 고정한다.
    voices = ("am_michael",)
    index = int(digest[:4], 16) % len(voices)
    return voices[index]
