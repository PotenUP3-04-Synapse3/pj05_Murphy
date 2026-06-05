from backend.app.services.service_a.npc_roster_service import (
    NPCProfile,
    resolve_npc_profile,
)
from backend.app.services.service_a.tts_service import TTSRequest, synthesize_speech
from backend.app.services.service_a.voice_profile_service import resolve_voice_profile


def test_resolve_known_npc_profile_for_officer_miller() -> None:
    profile = resolve_npc_profile("OFFICER_MILLER")

    assert profile == NPCProfile(
        npc_id="officer_miller",
        display_name="Officer Miller",
        role="immigration_officer",
        default_animation="officer_check_passport",
        fallback_text="Okay. Please continue.",
        mock_voice_id="officer_miller_mock_baritone",
        kokoro_voices=("am_michael",),
    )
    assert profile.kokoro_voices == ("am_michael",)


def test_resolve_unknown_npc_profile_falls_back_to_officer_miller() -> None:
    profile = resolve_npc_profile("UNKNOWN_NPC")

    assert profile.npc_id == "officer_miller"
    assert profile.display_name == "Officer Miller"
    assert profile.mock_voice_id == "officer_miller_mock_baritone"


def test_resolve_voice_profile_uses_normalized_npc_id_and_roster_voice() -> None:
    profile = resolve_voice_profile(user_id="session_1", npc_id="OFFICER_MILLER")

    assert profile.user_id == "session_1"
    assert profile.npc_id == "officer_miller"
    assert profile.voice_profile_id == "session_1:officer_miller"
    assert profile.provider == "kokoro"
    assert profile.voice_id == "am_michael"


def test_resolve_voice_profile_unknown_npc_uses_default_roster_profile() -> None:
    profile = resolve_voice_profile(user_id="session_1", npc_id="UNKNOWN_NPC")

    assert profile.npc_id == "officer_miller"
    assert profile.voice_profile_id == "session_1:officer_miller"
    assert profile.voice_id == "am_michael"


def test_mock_tts_uses_roster_mock_voice_for_known_speaker() -> None:
    audio = synthesize_speech(
        TTSRequest(
            text="Passport, please.",
            speaker="Officer Miller",
            tone="formal_neutral",
        )
    )

    assert audio.voice_id == "officer_miller_mock_baritone"
