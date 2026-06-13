from backend.app.services.service_a.npc_roster_service import (
    NPCProfile,
    resolve_npc_profile,
)
from backend.app.services.service_a.tts_service import TTSRequest, synthesize_speech
from backend.app.services.service_a.voice_profile_service import resolve_voice_profile


def test_resolve_known_npc_profile_for_officer_hale() -> None:
    profile = resolve_npc_profile("OFFICER_HALE")

    assert profile == NPCProfile(
        npc_id="hale",
        display_name="Officer Hale",
        role="immigration_officer",
        default_animation="move",
        fallback_text="State the purpose of your visit clearly.",
        mock_voice_id="hale_mock",
        persona_instruction="stern, direct, and authoritative immigration officer.",
        elevenlabs_voice_id="dXtC3XhB9GtPusIpNtQx",
    )


def test_resolve_unknown_npc_profile_falls_back_to_default_hale() -> None:
    profile = resolve_npc_profile("UNKNOWN_NPC")

    assert profile.npc_id == "hale"
    assert profile.display_name == "Officer Hale"
    assert profile.mock_voice_id == "hale_mock"


def test_resolve_voice_profile_uses_normalized_npc_id_and_roster_voice() -> None:
    profile = resolve_voice_profile(user_id="session_1", npc_id="OFFICER_HALE")

    assert profile.user_id == "session_1"
    assert profile.npc_id == "hale"
    assert profile.voice_profile_id == "session_1:hale"
    assert profile.provider == "edge"
    assert profile.voice_id == "en-US-GuyNeural"


def test_resolve_voice_profile_unknown_npc_uses_default_roster_profile() -> None:
    profile = resolve_voice_profile(user_id="session_1", npc_id="UNKNOWN_NPC")

    assert profile.npc_id == "hale"
    assert profile.voice_profile_id == "session_1:hale"
    assert profile.voice_id == "en-US-GuyNeural"


def test_mock_tts_uses_roster_mock_voice_for_known_speaker() -> None:
    audio = synthesize_speech(
        TTSRequest(
            text="Passport, please.",
            speaker="Officer Hale",
            tone="formal_neutral",
        )
    )

    assert audio.voice_id == "hale_mock"
