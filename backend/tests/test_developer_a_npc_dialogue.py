from backend.app.agents.agent_a.npc_dialogue_agent import (
    NPCDialogueInput,
    NPCDialogueResult,
    generate_npc_dialogue,
    generate_npc_dialogue_from_level_design,
)
from backend.app.services.service_a.npc_roster_service import NPCProfile
from backend.app.services.service_a.tts_service import TTSRequest, synthesize_speech
from backend.app.services.service_a.voice_output_service import build_voice_output


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


def test_level_design_dialogue_uses_npc_roster_profile(monkeypatch) -> None:
    def fake_resolve_npc_profile(npc_id: str | None) -> NPCProfile:
        assert npc_id == "supervisor_lee"
        return NPCProfile(
            npc_id="supervisor_lee",
            display_name="Supervisor Lee",
            role="immigration_supervisor",
            default_animation="supervisor_review_passport",
            fallback_text="Please wait here.",
            mock_voice_id="supervisor_lee_mock",
            kokoro_voices=("af_heart",),
        )

    monkeypatch.setattr(
        "backend.app.agents.agent_a.npc_dialogue_agent.resolve_npc_profile",
        fake_resolve_npc_profile,
        raising=False,
    )

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "supervisor_lee"},
            "node_id": "IMM_003_DURATION",
            "player_text": "I will stay five days.",
            "node_context": {
                "node_id": "IMM_003_DURATION",
                "recommended_expression": "I will stay for five days.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {
                "npc_recast_line_candidate": "You'll stay for five days. Where are you staying?"
            },
            "branch": {"branch_type": "success"},
        },
        use_llm=False,
    )

    assert result["speaker"] == "Supervisor Lee"
    assert result["animation"] == "supervisor_review_passport"


def test_level_design_dialogue_ignores_developer_b_progression_control_fields() -> None:
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "officer_miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I am here for tourism.",
            "node_context": {"recommended_expression": "I'm here for tourism."},
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {
                "npc_recast_line_candidate": "Tourism. How long will you stay?",
                "blocks_progression": True,
            },
            "dialogue_directive": {"do_not_generate_npc_text": True},
            "branch": {"branch_type": "success"},
        },
        use_llm=False,
    )

    assert result["npc_text"] == "Tourism. How long will you stay?"
    assert result["fallback"] == {"used": False, "reason": None}


def test_level_design_llm_dialogue_keeps_roster_speaker_and_animation(monkeypatch) -> None:
    class FakeLLMClient:
        model = "fake-dialogue-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Wrong Speaker",
                "npc_text": "Please continue to the next counter.",
                "tts_text": "Please continue to the next counter.",
                "feedback_kr": "좋아요. 다음 단계로 이어갈게요.",
                "tone": "formal_neutral",
                "animation": "wrong_animation",
                "llm_reason": "fake test response",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    def fake_resolve_npc_profile(npc_id: str | None) -> NPCProfile:
        assert npc_id == "supervisor_lee"
        return NPCProfile(
            npc_id="supervisor_lee",
            display_name="Supervisor Lee",
            role="immigration_supervisor",
            default_animation="supervisor_review_passport",
            fallback_text="Please wait here.",
            mock_voice_id="supervisor_lee_mock",
            kokoro_voices=("af_heart",),
        )

    monkeypatch.setattr(
        "backend.app.agents.agent_a.npc_dialogue_agent.resolve_npc_profile",
        fake_resolve_npc_profile,
    )

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "supervisor_lee"},
            "node_id": "IMM_003_DURATION",
            "player_text": "I will stay five days.",
            "node_context": {"recommended_expression": "I will stay for five days."},
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": "You'll stay for five days."},
            "branch": {"branch_type": "success"},
        },
        use_llm=True,
        llm_client=FakeLLMClient(),
    )

    assert result["speaker"] == "Supervisor Lee"
    assert result["animation"] == "supervisor_review_passport"


def test_level_design_llm_dialogue_uses_rule_fields_when_llm_omits_optional_schema_fields() -> None:
    class PartialLLMClient:
        model = "google/gemma-4-26B-A4B-it"

        def generate(self, payload: dict) -> dict:
            return {
                "npc_text": "Tourism. How long will you stay?",
                "tts_text": "Tourism. How long will you stay?",
                "llm_reason": "fallback model omitted tone",
                "__fallback_model": "google/gemma-4-26B-A4B-it",
                "__llm_usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "officer_miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I am here for tourism.",
            "node_context": {"recommended_expression": "I'm here for tourism."},
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": "Tourism. How long will you stay?"},
            "branch": {"branch_type": "success"},
        },
        use_llm=True,
        llm_client=PartialLLMClient(),
    )

    assert result["npc_text"] == "Tourism. How long will you stay?"
    assert result["tone"] == "formal_supportive"
    assert result["feedback_kr"]
    assert result["llm"]["model_name"] == "google/gemma-4-26B-A4B-it"


def test_level_design_llm_dialogue_calls_llm_even_without_candidate_text() -> None:
    class FakeLLMClient:
        model = "google/gemma-4-26B-A4B-it"

        def __init__(self) -> None:
            self.payloads: list[dict] = []

        def generate(self, payload: dict) -> dict:
            self.payloads.append(payload)
            return {
                "npc_text": "Tell me your travel purpose clearly.",
                "tts_text": "Tell me your travel purpose clearly.",
                "feedback_kr": "방문 목적을 짧게 말하면 됩니다.",
                "tone": "formal_firm",
                "animation": "ignored_by_roster",
                "llm_reason": "no candidate text, generated from context",
                "__fallback_model": "google/gemma-4-26B-A4B-it",
                "__llm_usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            }

    client = FakeLLMClient()

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "officer_miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "uncle",
            "node_context": {
                "npc_question": "What is the purpose of your visit?",
                "recommended_expression": "I'm here to visit my uncle.",
            },
            "evaluation_summary": {"task_success": 1, "clarity": 1},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {},
            "branch": {"branch_type": "retry"},
        },
        use_llm=True,
        llm_client=client,
    )

    assert client.payloads
    assert client.payloads[0]["fallback_candidate"]["fallback"]["used"] is True
    assert result["npc_text"] == "Tell me your travel purpose clearly."
    assert result["tts_text"] == "Tell me your travel purpose clearly."
    assert result["fallback"] == {"used": False, "reason": None}
    assert result["llm"]["used"] is True
    assert result["llm"]["fallback_used"] is True
    assert result["llm"]["seed_fallback_used"] is True
    assert result["llm"]["model_name"] == "google/gemma-4-26B-A4B-it"
