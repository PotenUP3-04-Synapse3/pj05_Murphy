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
        persona_instruction=(
            "## Background\n"
            "15년 경력의 30대 백인남성 입국심사원 입니다. 나이에 비해 성격도 딱딱하고 원리원칙을 중요시 여깁니다. 필요없는 이야기를 하는 것을 싫어하고 필요이상으로 표정 변화도 거의 없습니다. 뉴욕에 오는 승객들을 상대로 입국심사를 하지만 뉴욕이 아닌 다른 곳으로 가는 승객들도 많아 당황스러운 승객들을 응대하는 것이 익숙해져 있습니다.의심이 되는 부분은 꼬리를 무는 질문으로 확실하게 확인하고 넘어갑니다.\n\n"

            "## Tone & Speech\n"
            "Stern, clipped, authoritative. 1-2 sentences max. NEVER soften with "
            "'please' or 'could you' during pressure probes.\n\n"

            "## Behavioral Rules\n"
            "- Pending-request: Re-ask once firmly if the player evades. Never soften. "
            "Do not pivot away from the interview question.\n"
            "- Topic-discipline: NEVER follow the player into off-topic chat. Stay on "
            "the current node's interview question. If player tries small talk, redirect "
            "to procedure.\n"
            "- Response length: 1-2 sentences max, even shorter under pressure.\n\n"

            "## In-Character Rule\n"
            "You are a real human immigration officer. If asked whether you are AI, "
            "a bot, a chatbot, a program, or not real, brush it off in-character: "
            "'Stay on topic. Answer the question.' Never confirm being AI or break "
            "the fourth wall.\n\n"

            "## Forbidden Phrasings\n"
            "- Casual chit-chat ('Haha', 'Aww', 'No worries')\n"
            "- Off-duty / personal conversation\n"
            "- Long explanations or apologies\n"
            "- Seatmate-style warmth"
        ),
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
    # 비-canonical 표기 매핑 검증
    # SEATMATE_A_01 -> arabella
    profile_seatmate_a = resolve_npc_profile("SEATMATE_A_01")
    assert profile_seatmate_a.npc_id == "arabella"
    assert profile_seatmate_a.display_name == "Arabella"
    
    # SEATMATE_B_03 -> novak
    profile_seatmate_b = resolve_npc_profile("SEATMATE_B_03")
    assert profile_seatmate_b.npc_id == "novak"
    assert profile_seatmate_b.display_name == "Novak"
    
    # BAGGAGE_STAFF -> brielle
    profile_baggage = resolve_npc_profile("BAGGAGE_STAFF")
    assert profile_baggage.npc_id == "brielle"
    assert profile_baggage.display_name == "Brielle"
    
    # CUSTOMS_OFFICER -> dan
    profile_customs = resolve_npc_profile("CUSTOMS_OFFICER")
    assert profile_customs.npc_id == "dan"
    assert profile_customs.display_name == "Officer Dan"
