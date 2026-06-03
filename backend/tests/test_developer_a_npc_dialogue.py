from backend.app.agents.npc_dialogue_agent import (
    NPCDialogueInput,
    NPCDialogueResult,
    generate_npc_dialogue,
)
from backend.app.services.tts_service import TTSRequest, synthesize_speech
from backend.app.services.voice_output_service import build_voice_output


def test_generate_success_response_uses_officer_miller_style_and_feedback() -> None:
    payload = NPCDialogueInput(
        player_text="Travel. Trouble no.",
        node_context={
            "node_id": "IMM_002_PURPOSE",
            "npc_question": "What is the purpose of your visit?",
        },
        understanding={
            "intent": "visit_purpose_travel",
            "intent_success": True,
            "emotion": "nervous_humor",
            "konglish_detected": True,
        },
        level_hint={
            "english_level": "beginner",
            "recommended_expression": "I'm here for travel.",
        },
        branch={
            "branch_type": "success",
            "next_node_id": "IMM_003_DURATION",
        },
    )

    result = generate_npc_dialogue(payload)

    assert result == NPCDialogueResult(
        speaker="Officer Miller",
        text="Travel. Okay. How long will you stay?",
        tone="formal_neutral",
        animation="officer_check_passport",
        feedback_kr="좋아요. 더 자연스럽게는: I'm here for travel.",
    )


def test_generate_retry_response_stays_brief_formal_and_kind() -> None:
    payload = NPCDialogueInput(
        player_text="Me no remember hotel.",
        node_context={
            "node_id": "IMM_004_ADDRESS",
            "npc_question": "Where will you stay in the United States?",
        },
        understanding={
            "intent": "unknown_address",
            "intent_success": False,
            "emotion": "panic",
            "konglish_detected": True,
        },
        level_hint={
            "english_level": "beginner",
            "recommended_expression": "I will stay at a hotel.",
        },
        branch={
            "branch_type": "retry",
            "next_node_id": "IMM_004_ADDRESS",
        },
    )

    result = generate_npc_dialogue(payload)

    assert result.speaker == "Officer Miller"
    assert result.text == "I need a clear answer. Where will you stay?"
    assert result.tone == "formal_firm"
    assert result.animation == "officer_waiting"
    assert result.feedback_kr == "괜찮아요. 짧게 이렇게 말해보세요: I will stay at a hotel."


def test_synthesize_speech_returns_deterministic_mock_audio_metadata() -> None:
    audio = synthesize_speech(
        TTSRequest(
            text="Travel. Okay. How long will you stay?",
            speaker="Officer Miller",
            tone="formal_neutral",
        )
    )

    assert audio.provider == "mock"
    assert audio.audio_url is None
    assert audio.voice_id == "officer_miller_mock_baritone"
    assert audio.duration_ms == 2400


def test_build_voice_output_combines_dialogue_and_tts_metadata() -> None:
    dialogue = NPCDialogueResult(
        speaker="Officer Miller",
        text="I need a clear answer. Where will you stay?",
        tone="formal_firm",
        animation="officer_waiting",
        feedback_kr="괜찮아요. 짧게 이렇게 말해보세요: I will stay at a hotel.",
    )

    voice_output = build_voice_output(dialogue)

    assert voice_output.dialogue == dialogue
    assert voice_output.audio.provider == "mock"
    assert voice_output.audio.duration_ms == 2100
