from dataclasses import dataclass


@dataclass(frozen=True)
class NPCProfile:
    npc_id: str
    display_name: str
    role: str
    default_animation: str
    fallback_text: str
    mock_voice_id: str
    # Kokoro 모델에서 지원하는 voice id 중 이 NPC에 배정할 후보 목록이다.
    # 새 NPC를 추가할 때는 Kokoro가 실제 지원하는 voice id만 여기에 넣는다.
    kokoro_voices: tuple[str, ...]


_DEFAULT_NPC_ID = "officer_miller"

_NPC_ROSTER: dict[str, NPCProfile] = {
    "officer_miller": NPCProfile(
        npc_id="officer_miller",
        display_name="Officer Miller",
        role="immigration_officer",
        default_animation="officer_check_passport",
        fallback_text="Okay. Please continue.",
        mock_voice_id="officer_miller_mock_baritone",
        # Officer Miller의 기본 Kokoro voice 후보. NPC별로 이 tuple만 바꾸면 된다.
        kokoro_voices=("am_michael",),
    )
}


def resolve_npc_profile(npc_id: str | None) -> NPCProfile:
    normalized_id = _normalize_npc_id(npc_id)
    return _NPC_ROSTER.get(normalized_id, _NPC_ROSTER[_DEFAULT_NPC_ID])


def resolve_npc_profile_by_display_name(display_name: str | None) -> NPCProfile | None:
    if not display_name:
        return None
    normalized_name = display_name.strip().casefold()
    for profile in _NPC_ROSTER.values():
        if profile.display_name.casefold() == normalized_name:
            return profile
    return None


def _normalize_npc_id(npc_id: str | None) -> str:
    if not npc_id:
        return _DEFAULT_NPC_ID
    return npc_id.strip().lower()
