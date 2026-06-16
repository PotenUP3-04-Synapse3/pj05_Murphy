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
        non_verbal_palette=["Hmph.", "Tsk.", "<break time='0.4s'/>"],
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
    assert profile.voice_profile_id == "session_1:hale:edge"
    assert profile.provider == "edge"
    assert profile.voice_id == "en-US-GuyNeural"


def test_resolve_voice_profile_unknown_npc_uses_default_roster_profile() -> None:
    profile = resolve_voice_profile(user_id="session_1", npc_id="UNKNOWN_NPC")

    assert profile.npc_id == "hale"
    assert profile.voice_profile_id == "session_1:hale:edge"
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


def test_resolve_new_npcs_and_non_canonical_mapping() -> None:
    # emily 신규 NPC 조회 검증
    profile_emily = resolve_npc_profile("emily")
    assert profile_emily.display_name == "Emily"
    assert profile_emily.role == "seatmate"
    
    # 비-canonical 표기 매핑 검증
    # SEATMATE_A_01 -> arabella
    profile_seatmate_a = resolve_npc_profile("SEATMATE_A_01")
    assert profile_seatmate_a.npc_id == "arabella"
    assert profile_seatmate_a.display_name == "Arabella"
    
    # SEATMATE_B_03 -> novak
    profile_seatmate_b = resolve_npc_profile("SEATMATE_B_03")
    assert profile_seatmate_b.npc_id == "novak"
    assert profile_seatmate_b.display_name == "Novak"

    # SEATMATE_C_01 -> emily
    profile_seatmate_c = resolve_npc_profile("SEATMATE_C_01")
    assert profile_seatmate_c.npc_id == "emily"
    assert profile_seatmate_c.display_name == "Emily"
    
    # BAGGAGE_STAFF -> brielle
    profile_baggage = resolve_npc_profile("BAGGAGE_STAFF")
    assert profile_baggage.npc_id == "brielle"
    assert profile_baggage.display_name == "Brielle"
    
    # CUSTOMS_OFFICER -> dan
    profile_customs = resolve_npc_profile("CUSTOMS_OFFICER")
    assert profile_customs.npc_id == "dan"
    assert profile_customs.display_name == "Officer Dan"
