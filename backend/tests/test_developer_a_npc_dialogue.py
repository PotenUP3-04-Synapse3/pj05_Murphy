from typing import Any

from backend.app.agents.agent_a.npc_dialogue_agent import (
    NPCDialogueResult,
    generate_npc_dialogue_from_level_design as _orig_generate_npc_dialogue_from_level_design,
)
from backend.app.services.service_a.dialogue_policy_service import synthesize_fallback_next_question
from backend.app.services.service_a.npc_roster_service import NPCProfile
from backend.app.services.service_a.tts_service import TTSRequest, synthesize_speech
from backend.app.services.service_a.voice_output_service import build_voice_output

import uuid

def generate_npc_dialogue_from_level_design(payload: dict, *args, **kwargs):
    if "session_id" not in payload:
        has_session = False
        if "turn" in payload and isinstance(payload["turn"], dict):
            session = payload["turn"].get("session")
            if isinstance(session, dict) and "session_id" in session:
                has_session = True
        if not has_session:
            payload = dict(payload)
            payload["session_id"] = f"test_session_{uuid.uuid4().hex}"
    return _orig_generate_npc_dialogue_from_level_design(payload, *args, **kwargs)


def test_synthesize_speech_returns_deterministic_mock_audio_metadata() -> None:
    audio = synthesize_speech(
        TTSRequest(
            text="Travel. Okay. How long will you stay?",
            speaker="Officer Hale",
            tone="formal_neutral",
        )
    )

    assert audio.provider == "mock"
    assert audio.audio_url is None
    assert audio.voice_id == "hale_mock"
    assert audio.duration_ms == 2400


def test_build_voice_output_combines_dialogue_and_tts_metadata() -> None:
    dialogue = NPCDialogueResult(
        speaker="Officer Miller",
        text="I need a clear answer. Where will you stay?",
        tone="formal_firm",
        animation="move",
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
            default_animation="move",
            fallback_text="Please wait here.",
            mock_voice_id="supervisor_lee_mock",
            persona_instruction="friendly, warm passenger.",
            elevenlabs_voice_id=None,
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
                "npc_recast_line_candidate": None
            },
            "branch": {"branch_type": "success"},
        },
        use_llm=False,
    )

    assert result["speaker"] == "Supervisor Lee"
    assert result["animation"] == "move"


def test_level_design_dialogue_ignores_developer_b_progression_control_fields() -> None:
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I am here for tourism.",
            "node_context": {"recommended_expression": "I'm here for tourism."},
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {
                "npc_recast_line_candidate": None,
                "blocks_progression": True,
            },
            "dialogue_directive": {"do_not_generate_npc_text": True},
            "branch": {"branch_type": "success"},
        },
        use_llm=False,
    )

    assert result["npc_text"] == "Okay. Please continue."
    assert result["fallback"]["used"] is True


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
            default_animation="move",
            fallback_text="Please wait here.",
            mock_voice_id="supervisor_lee_mock",
            persona_instruction="friendly, warm passenger.",
            elevenlabs_voice_id=None,
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
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
        },
        use_llm=True,
        llm_client=FakeLLMClient(),
    )

    assert result["speaker"] == "Supervisor Lee"
    assert result["animation"] == "move"


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
            "npc": {"npc_id": "miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I am here for tourism.",
            "node_context": {"recommended_expression": "I'm here for tourism."},
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
        },
        use_llm=True,
        llm_client=PartialLLMClient(),
    )

    assert result["npc_text"] == "Tourism. How long will you stay?"
    assert result["tone"] == "formal_neutral"
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
            "npc": {"npc_id": "miller"},
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


def test_level_design_llm_dialogue_rejects_non_english_npc_text() -> None:
    class NonEnglishLLMClient:
        model = "gpt-4o-mini"

        def generate(self, payload: dict) -> dict:
            return {
                "npc_text": "방문 목적을 명확히 말해주세요.",
                "tts_text": "방문 목적을 명확히 말해주세요.",
                "feedback_kr": "방문 목적을 말하면 됩니다.",
                "tone": "formal_supportive",
                "animation": "ignored_by_roster",
                "llm_reason": "invalid language test",
                "__llm_usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I am Korean.",
            "node_context": {"recommended_expression": "I'm here for tourism."},
            "evaluation_summary": {"task_success": 0, "clarity": 1},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "clarify"},
        },
        use_llm=True,
        llm_client=NonEnglishLLMClient(),
    )

    assert result["npc_text"] == "Okay. Please continue."
    assert result["tts_text"].isascii()
    assert result["llm"]["used"] is False
    assert result["llm"]["fallback_used"] is True
    assert result["llm"]["reason"] == "invalid_llm_dialogue_language"


def test_level_design_dialogue_does_not_convert_none_candidate_to_text() -> None:
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I'm here for tourism.",
            "node_context": {
                "npc_question": "What is the purpose of your visit?",
                "recommended_expression": None,
            },
            "evaluation_summary": {"task_success": 3, "clarity": 3},
            "level_hint": {"english_level": "beginner", "recommended_expression": None},
            "in_game_feedback": {
                "npc_recast_line_candidate": None,
                "recommended_expression": None,
            },
            "branch": {"branch_type": "success", "next_node_id": "IMM_003_DURATION"},
        },
        use_llm=False,
    )

    assert result["npc_text"] != "None"
    assert result["tts_text"] != "Alright. None"
    assert result["fallback"]["used"] is True


def test_surface_goal_fallback_synthesizes_next_question() -> None:
    # LLM이 실패하여 룰베이스 폴백으로 흘러갔을 때 다음 질문 합성 검증
    class FailingLLMClient:
        model = "failing-model"
        def generate(self, payload: dict) -> dict:
            from backend.app.agents.agent_a.npc_llm_client import NPCDialogueLLMUnavailable
            raise NPCDialogueLLMUnavailable("Test LLM fail")

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I am here for tourism.",
            "node_context": {
                "npc_question": "What is the purpose of your visit?",
                "recommended_expression": "I'm here for tourism.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_seed": {
                "surface_goal": "ask_travel_purpose_smalltalk"
            }
        },
        use_llm=True,
        llm_client=FailingLLMClient(),
    )
    
    # LLM이 실패하여 폴백으로 가야 하고, 폴백 대사 뒤에 surface_goal 질문이 합성되어야 함
    assert "I see. What is the purpose of your visit?" in result["npc_text"]
    assert "Are you visiting New York for a trip?" in result["npc_text"]
    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "NPCDialogueLLMUnavailable"


def test_llm_dialogue_rejects_recommended_expression_echo() -> None:
    # LLM이 추천 표현을 그대로 에코한 경우 에러 폴백 감지 검증
    class EchoLLMClient:
        model = "fake-echo-model"
        def generate(self, payload: dict) -> dict:
            return {
                "npc_text": "I'm here to visit my uncle.", # 추천 표현 그대로 리턴
                "tts_text": "I'm here to visit my uncle.",
                "feedback_kr": "좋아요.",
                "tone": "formal_neutral",
                "animation": "move",
                "llm_reason": "echoed expression",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I visit uncle.",
            "node_context": {
                "npc_question": "What is the purpose of your visit?",
                "recommended_expression": "I'm here to visit my uncle.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
        },
        use_llm=True,
        llm_client=EchoLLMClient(),
    )
    
    # 에코로 인해 fallback으로 가야 함
    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "recommended_expression_echo"
    assert result["fallback"]["used"] is True


def test_llm_dialogue_rejects_recommended_expression_echo_variants() -> None:
    # 구두점/대소문자/추가 문구가 섞여도, 또 tts_text에만 새도 에코로 감지해야 함.
    # (예: recommended_expression="Thank you, officer." 가 NPC 대사에 그대로 흘러든 케이스)
    class VariantEchoLLMClient:
        model = "fake-echo-model"

        def generate(self, payload: dict) -> dict:
            return {
                # npc_text는 깨끗하지만 tts_text에 추천 표현이 변형되어 새어든 경우
                "npc_text": "All right. Move on to baggage claim.",
                "tts_text": "Okay. <break time=\"0.4s\"/> thank you, OFFICER! Then move on.",
                "feedback_kr": "좋아요.",
                "tone": "formal_neutral",
                "animation": "move",
                "llm_reason": "echoed expression in tts",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "miller"},
            "node_id": "IMM_007_FINAL_DECISION",
            "player_text": "thank you",
            "node_context": {
                "npc_question": "All right, you're cleared to enter. Enjoy your stay.",
                "recommended_expression": "Thank you, officer.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
        },
        use_llm=True,
        llm_client=VariantEchoLLMClient(),
    )

    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "recommended_expression_echo"
    assert result["fallback"]["used"] is True


def test_llm_dialogue_rejects_missing_followup_question() -> None:
    # surface_goal이 주어졌는데 질문이 아닌 문장 1개만 생성한 경우 에러 감지 검증
    class ReactionOnlyLLMClient:
        model = "fake-reaction-model"
        def generate(self, payload: dict) -> dict:
            return {
                "npc_text": "That sounds nice.", # 질문이 없음
                "tts_text": "That sounds nice.",
                "feedback_kr": "좋아요.",
                "tone": "formal_neutral",
                "animation": "move",
                "llm_reason": "missing question",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "miller"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I am traveling.",
            "node_context": {
                "npc_question": "What is the purpose of your visit?",
                "recommended_expression": "I'm here for tourism.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_seed": {
                "surface_goal": "ask_travel_purpose_smalltalk"
            }
        },
        use_llm=True,
        llm_client=ReactionOnlyLLMClient(),
    )
    
    # 질문 누락으로 인해 fallback으로 가야 함
    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "missing_followup_question"
    assert result["fallback"]["used"] is True


def test_flight_a_friendly_seatmate_fallback_dialogue() -> None:
    # Flight A의 1번째 노드와 5번째 노드 폴백 대사 합성 검증
    result_start = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Hello.",
            "node_context": {
                "recommended_expression": "Nice to meet you.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_seed": {
                "surface_goal": "respond_to_polite_request"
            }
        },
        use_llm=False,
    )
    assert result_start["speaker"] == "Arabella"
    assert "Sure, go ahead. Are you traveling to New York?" in result_start["npc_text"]
    assert result_start["feedback_kr"] == "친절하게 답변해 주었어요. 더 자연스럽게 표현해 볼까요?"

    result_end = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Thank you.",
            "node_context": {
                "recommended_expression": "Thank you very much.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_seed": {
                "surface_goal": "wrap_up_flight_smalltalk"
            }
        },
        use_llm=False,
    )
    assert result_end["speaker"] == "Arabella"
    assert "Okay. Do you have your arrival form ready? We will land soon." in result_end["npc_text"]


def test_flight_b_curious_seatmate_fallback_dialogue() -> None:
    # Flight B의 2번째 노드(ask_companion_or_visit_plan) 폴백 검증
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_B_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "I am traveling alone.",
            "node_context": {
                "recommended_expression": "I am traveling by myself.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_seed": {
                "surface_goal": "ask_companion_or_visit_plan"
            }
        },
        use_llm=False,
    )
    assert result["speaker"] == "Novak"
    assert "Are you traveling alone or with someone?" in result["npc_text"]



def test_baggage_service_desk_fallback_dialogue() -> None:
    # Baggage 1번째 노드(report_missing_bag_at_service_desk) 폴백 검증
    result_start = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "BAGGAGE_STAFF", "npc_role": "baggage_agent"},
            "node_id": "BAG_001_REPORT_MISSING_AT_DESK",
            "player_text": "I lost my bag.",
            "node_context": {
                "recommended_expression": "I cannot find my baggage.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_seed": {
                "surface_goal": "report_missing_bag_at_service_desk"
            }
        },
        use_llm=False,
    )
    assert result_start["speaker"] == "Brielle"
    assert result_start["npc_text"] == "Hi, how can I help you today?"

    # Baggage 4번째 노드(redirect_to_customs_hold_area) 폴백 검증 (재지시 멘트 포함)
    result_end = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "BAGGAGE_STAFF", "npc_role": "baggage_agent"},
            "node_id": "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD",
            "player_text": "Okay, where is it?",
            "node_context": {
                "recommended_expression": "Where is the customs hold area?",
            },
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_seed": {
                "surface_goal": "redirect_to_customs_hold_area"
            }
        },
        use_llm=False,
    )
    assert result_end["speaker"] == "Brielle"
    assert result_end["npc_text"] == "I'm sorry, but we don't have it here. It seems your bag is held in the customs area. You must go there."


def test_baggage_customs_random_item_fallback_dialogue() -> None:
    # red ginseng medicine 주입 테스트
    result_medicine = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "CUSTOMS_OFFICER", "npc_role": "customs_officer"},
            "node_id": "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM",
            "player_text": "It is medicine.",
            "node_context": {
                "recommended_expression": "It is health medicine.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_seed": {
                "surface_goal": "explain_random_customs_item"
            },
            "game_state": {
                "random_customs_item": "red ginseng medicine"
            }
        },
        use_llm=False,
    )
    assert result_medicine["speaker"] == "Officer Dan"
    assert result_medicine["npc_text"] == "What is this red ginseng medicine in your bag?"
    assert result_medicine["feedback_kr"] == "세관 질문에 적절히 대답했어요. 더 명확하게 표현해 볼까요?"

    # laptop 주입 테스트
    result_laptop = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "CUSTOMS_OFFICER", "npc_role": "customs_officer"},
            "node_id": "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM",
            "player_text": "It is laptop.",
            "node_context": {
                "recommended_expression": "It is my personal computer.",
            },
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_seed": {
                "surface_goal": "explain_random_customs_item"
            },
            "game_state": {
                "random_customs_item": "laptop"
            }
        },
        use_llm=False,
    )
    assert result_laptop["speaker"] == "Officer Dan"
    assert result_laptop["npc_text"] == "What is this laptop in your bag?"


def test_complete_chapter_transition_returns_closing_phrase_for_each_role() -> None:
    # seatmate role chapter completion
    res_seatmate = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Bye.",
            "node_context": {"recommended_expression": "Goodbye."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success", "next_action": "COMPLETE_CHAPTER"},
            "transition": {"status": "complete_chapter"},
        },
        use_llm=False,
    )
    assert res_seatmate["npc_text"] == "Enjoy your trip!"

    # immigration_officer role chapter completion
    res_immigration = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_999_CLEARED",
            "player_text": "Thank you.",
            "node_context": {"recommended_expression": "Thank you very much."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success", "next_action": "COMPLETE_CHAPTER"},
            "transition": {"status": "complete_chapter"},
        },
        use_llm=False,
    )
    assert res_immigration["npc_text"] == "All right, you're cleared."


def test_smalltalk_complete_chapter_llm_question_falls_back_to_closing() -> None:
    class QuestionOnCompleteLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Arabella",
                "npc_text": "Fun sounds great. What do you like to do there?",
                "tts_text": "Fun sounds great. What do you like to do there?",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "joy",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[COHERENT] It answers, but wrongly asks another question.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "I'm staying there for fun. My name is John. What is your name?",
            "node_context": {"recommended_expression": "Nice to meet you."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "success",
                "next_action": "COMPLETE_CHAPTER",
                "next_node_id": "FLIGHT_999_COMPLETE",
            },
            "transition": {"status": "chapter_complete"},
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "target_slot": None,
                "topic_switch": False,
                "length_target": 12,
            },
            "dialogue_seed": {
                "surface_goal": "travel_purpose_travel",
                "required_slots": [],
            },
        },
        use_llm=True,
        llm_client=QuestionOnCompleteLLMClient(),
    )

    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "complete_chapter_question_violation"
    assert result["npc_text"] == "Enjoy your trip!"
    assert "?" not in result["npc_text"]


def test_immigration_success_llm_must_follow_branch_surface_goal_question() -> None:
    class HostQuestionLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Officer Hale",
                "npc_text": "Friend's house. Who is your host?",
                "tts_text": "Friend's house. Who is your host?",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "normal",
                "llm_reason": "Wrongly asks a suspicion hook instead of the next node question.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_004_STAY_LOCATION",
            "player_text": "I'm staying in my friend's house.",
            "node_context": {"recommended_expression": "I'm staying at my friend's house."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "success",
                "next_action": "ADVANCE",
                "next_node_id": "IMM_005_RETURN_TICKET",
            },
            "dialogue_directive": {
                "purpose": "continue_to_next_question",
                "target_slot": "stay_location",
            },
            "dialogue_seed": {
                "surface_goal": "ask_return_ticket",
                "required_slots": ["stay_location"],
            },
        },
        use_llm=True,
        llm_client=HostQuestionLLMClient(),
    )

    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "immigration_surface_goal_mismatch"
    assert result["npc_text"] == "Do you have a return ticket to Korea?"
    assert "host" not in result["npc_text"].lower()


def test_immigration_retry_llm_hook_prefix_falls_back_to_direct_question() -> None:
    class MentionedHookLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Officer Hale",
                "npc_text": "What is your occupation. You mentioned mentioned — What is your occupation?",
                "tts_text": "What is your occupation. You mentioned mentioned — What is your occupation?",
                "feedback_kr": "Try again.",
                "tone": "formal_firm",
                "animation": "move",
                "npc_emotion": "confusion",
                "llm_reason": "Wrongly uses an open hook in a formal retry.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_009_OCCUPATION",
            "player_text": "I went to school here before.",
            "node_context": {"recommended_expression": "I'm a student."},
            "evaluation_summary": {"task_success": False, "clarity": 0.3},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "clarify",
                "next_action": "REASK",
                "next_node_id": "IMM_009_OCCUPATION_CLARIFY_OCCUPATION",
            },
            "dialogue_directive": {
                "purpose": "support_retry",
                "target_slot": "occupation",
            },
            "dialogue_seed": {
                "surface_goal": "ask_occupation",
                "required_slots": ["occupation"],
            },
        },
        use_llm=True,
        llm_client=MentionedHookLLMClient(),
    )

    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "immigration_retry_hook_violation"
    assert result["npc_text"] == "What is your occupation?"
    assert "mentioned" not in result["npc_text"].lower()


def test_fallback_question_synthesis_does_not_quote_low_content_hooks() -> None:
    text = synthesize_fallback_next_question(
        "Pardon me?",
        "customs_hold_explanation_before_unlock",
        ["hello"],
    )

    assert "mentioned" not in text.lower()
    assert "hello" not in text.lower()
    assert "check" in text.lower()
    assert "contents" in text.lower()
    assert "what brings you" not in text.lower()


def test_customs_hold_greeting_retry_uses_procedure_not_hook_or_wrong_question() -> None:
    class DriftLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Officer Dan",
                "npc_text": "Understood. You mentioned hello - What brings you to the customs hold area?",
                "tts_text": "Understood. You mentioned hello - What brings you to the customs hold area?",
                "feedback_kr": "Try again.",
                "tone": "formal_firm",
                "animation": "move",
                "npc_emotion": "confusion",
                "llm_reason": "Wrongly quotes a greeting and asks the wrong customs question.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "dan", "npc_role": "customs_officer"},
            "node_id": "BAG_005_CUSTOMS_HOLD_EXPLANATION",
            "player_text": "Hello.",
            "node_context": {
                "node_id": "BAG_005_CUSTOMS_HOLD_EXPLANATION",
                "npc_question": (
                    "This suitcase was locked for inspection because there may be a questionable item. "
                    "I'll unlock it, so please check the contents."
                ),
                "recommended_expression": "Okay, I'll open it and check the contents.",
            },
            "understanding": {
                "answer_relevance": "off_topic",
                "missing_slots": ["customs_hold_acknowledgement"],
                "social_context": {
                    "scene_norm": "service_recovery",
                    "conversation_move": "greeting_only",
                    "pending_social_obligation": "check_suitcase_contents",
                    "obligation_status": "open",
                    "recommended_npc_move": "service_repair",
                },
            },
            "evaluation_summary": {"task_success": False, "clarity": 0.2},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "hint",
                "next_action": "GIVE_HINT",
                "next_node_id": "BAG_005_RETRY_CUSTOMS_HOLD_EXPLANATION",
                "branch_reason": "Repeated failure or beginner support policy requires a hint.",
            },
            "dialogue_directive": {
                "purpose": "support_retry",
                "target_slot": "customs_hold_acknowledgement",
            },
            "dialogue_seed": {
                "surface_goal": "customs_hold_explanation_before_unlock",
                "required_slots": ["customs_hold_acknowledgement"],
                "dialogue_history": [],
            },
        },
        use_llm=True,
        llm_client=DriftLLMClient(),
    )

    text = result["npc_text"].lower()
    assert "mentioned" not in text
    assert "hello" not in text
    assert "what brings you" not in text
    assert "check" in text
    assert "contents" in text


def _customs_hold_social_payload(
    *,
    branch_reason: str,
    conversation_move: str,
    player_text: str,
) -> dict[str, Any]:
    return {
        "npc": {"npc_id": "dan", "npc_role": "customs_officer"},
        "node_id": "BAG_005_CUSTOMS_HOLD_EXPLANATION",
        "player_text": player_text,
        "node_context": {
            "node_id": "BAG_005_CUSTOMS_HOLD_EXPLANATION",
            "recommended_expression": "Okay, I'll open it and check the contents.",
        },
        "understanding": {
            "answer_relevance": "off_topic",
            "missing_slots": ["customs_hold_acknowledgement"],
            "social_context": {
                "scene_norm": "service_recovery",
                "conversation_move": conversation_move,
                "pending_social_obligation": "check_suitcase_contents",
                "obligation_status": "ignored",
                "engagement_quality": "stalled",
                "recommended_npc_move": "service_repair",
            },
        },
        "evaluation_summary": {"task_success": False, "clarity": 0.2},
        "level_hint": {"english_level": "beginner"},
        "in_game_feedback": {"npc_recast_line_candidate": None},
        "branch": {
            "branch_type": "clarify",
            "next_action": "REASK",
            "next_node_id": "BAG_005_RETRY_CUSTOMS_HOLD_EXPLANATION",
            "branch_reason": branch_reason,
        },
        "dialogue_directive": {
            "purpose": "support_retry",
            "target_slot": "customs_hold_acknowledgement",
        },
        "dialogue_seed": {
            "surface_goal": "customs_hold_explanation_before_unlock",
            "required_slots": ["customs_hold_acknowledgement"],
        },
    }


def test_customs_social_engagement_check_fallback_checks_understanding_without_repeating_template() -> None:
    result = generate_npc_dialogue_from_level_design(
        _customs_hold_social_payload(
            branch_reason="service_recovery_engagement_check",
            conversation_move="clarification_request",
            player_text="What?",
        ),
        use_llm=False,
    )

    text = result["npc_text"].lower()
    assert result["fallback"]["reason"] == "social_context_fallback"
    assert "no worries. i still need that detail" not in text
    assert "hello" not in text
    assert "trouble understanding" in text


def test_customs_social_warning_fallback_sets_boundary_without_repeating_contents_prompt() -> None:
    result = generate_npc_dialogue_from_level_design(
        _customs_hold_social_payload(
            branch_reason="service_recovery_procedure_warning",
            conversation_move="off_topic",
            player_text="Can you rap for me?",
        ),
        use_llm=False,
    )

    text = result["npc_text"].lower()
    assert result["fallback"]["reason"] == "social_context_fallback"
    assert "no worries. i still need that detail" not in text
    assert "please check the contents of the suitcase now" not in text
    assert "cannot continue" in text
    assert "cooperation" in text


def test_passport_refusal_warning_fallback_does_not_ask_for_clear_answer() -> None:
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_001_PASSPORT",
            "player_text": "I answered the question. The answer is no.",
            "node_context": {"recommended_expression": "Here you are."},
            "evaluation_summary": {"task_success": False, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "bad_end",
                "next_action": "FAIL_END",
                "next_node_id": "END_SECONDARY_INSPECTION",
                "branch_reason": "passport_submission_refused",
            },
            "dialogue_directive": {
                "purpose": "warn_and_control_risk",
                "target_slot": "passport_submission_status",
            },
            "dialogue_seed": {
                "surface_goal": "request_passport_submission",
                "required_slots": ["passport_submission_status"],
            },
        },
        use_llm=False,
    )

    text = result["npc_text"].lower()
    assert "clear answer" not in text
    assert "may i see your passport" not in text
    assert "refuse" in text or "secondary inspection" in text


def test_passport_refusal_llm_output_is_not_overridden_back_to_passport_question() -> None:
    class RefusalWarningLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Officer Hale",
                "npc_text": (
                    "I understand. Refusing to present your passport means "
                    "I must send you to secondary inspection."
                ),
                "tts_text": (
                    "I understand. Refusing to present your passport means "
                    "I must send you to secondary inspection."
                ),
                "feedback_kr": "At immigration, refusing to present a passport is serious.",
                "tone": "formal_warning",
                "animation": "officer_warning",
                "npc_emotion": "suspicion",
                "llm_reason": "[COHERENT] The player explicitly refused to present the passport.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_001_PASSPORT",
            "player_text": "I answered the question. The answer is no.",
            "node_context": {"recommended_expression": "Here you are."},
            "evaluation_summary": {"task_success": False, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "bad_end",
                "next_action": "FAIL_END",
                "next_node_id": "END_SECONDARY_INSPECTION",
                "branch_reason": "passport_submission_refused",
            },
            "dialogue_directive": {
                "purpose": "warn_and_control_risk",
                "target_slot": "passport_submission_status",
            },
            "dialogue_seed": {
                "surface_goal": "request_passport_submission",
                "required_slots": ["passport_submission_status"],
            },
        },
        use_llm=True,
        llm_client=RefusalWarningLLMClient(),
    )

    text = result["npc_text"].lower()
    assert result["llm"]["used"] is True
    assert "clear answer" not in text
    assert "may i see your passport" not in text
    assert "secondary inspection" in text


def test_violent_threat_warning_fallback_does_not_reask_visit_purpose() -> None:
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I'm going to punch Trump in the face.",
            "node_context": {"recommended_expression": "I'm here for tourism."},
            "understanding": {
                "risk_tags": ["violent_threat", "threat_to_public_figure"],
                "risk_delta": 80,
                "pragmatic_context": {
                    "player_move": "violent_threat",
                    "target": "public_figure",
                    "procedural_posture": "secondary_inspection",
                },
            },
            "evaluation_summary": {"task_success": False, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "bad_end",
                "next_action": "FAIL_END",
                "next_node_id": "END_SECONDARY_INSPECTION",
                "branch_reason": "violent_threat_to_public_figure",
            },
            "dialogue_directive": {
                "purpose": "warn_and_control_risk",
                "target_slot": "visit_purpose",
            },
            "dialogue_seed": {
                "surface_goal": "ask_visit_purpose",
                "required_slots": ["visit_purpose"],
            },
        },
        use_llm=False,
    )

    text = result["npc_text"].lower()
    assert "what is the purpose" not in text
    assert "what brings you" not in text
    assert "threat" in text or "secondary inspection" in text


def test_violent_threat_llm_output_is_not_accepted_as_visit_purpose_reask() -> None:
    class RiskReaskLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Officer Hale",
                "npc_text": "What brings you to the United States?",
                "tts_text": "What brings you to the United States?",
                "feedback_kr": "Threats require formal handling.",
                "tone": "formal_warning",
                "animation": "officer_warning",
                "npc_emotion": "suspicion",
                "llm_reason": "[COHERENT] Test model incorrectly re-asked the visit purpose.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "I'm going to punch Trump in the face.",
            "node_context": {"recommended_expression": "I'm here for tourism."},
            "understanding": {
                "risk_tags": ["violent_threat", "threat_to_public_figure"],
                "risk_delta": 80,
                "pragmatic_context": {
                    "player_move": "violent_threat",
                    "target": "public_figure",
                    "procedural_posture": "secondary_inspection",
                },
            },
            "evaluation_summary": {"task_success": False, "clarity": 0.9},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "bad_end",
                "next_action": "FAIL_END",
                "next_node_id": "END_SECONDARY_INSPECTION",
                "branch_reason": "violent_threat_to_public_figure",
            },
            "dialogue_directive": {
                "purpose": "warn_and_control_risk",
                "target_slot": "visit_purpose",
            },
            "dialogue_seed": {
                "surface_goal": "ask_visit_purpose",
                "required_slots": ["visit_purpose"],
            },
        },
        use_llm=True,
        llm_client=RiskReaskLLMClient(),
    )

    text = result["npc_text"].lower()
    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "risk_control_reask_violation"
    assert "what brings you" not in text
    assert "purpose of your visit" not in text
    assert "threat" in text or "secondary inspection" in text


def test_immigration_non_advance_override_does_not_add_open_hook_prefix() -> None:
    class NeutralRetryLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Officer Hale",
                "npc_text": "Now go to baggage claim.",
                "tts_text": "Now go to baggage claim.",
                "feedback_kr": "Try again.",
                "tone": "formal_firm",
                "animation": "confusion",
                "npc_emotion": "confusion",
                "llm_reason": "A neutral retry sentence before fallback synthesis.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_007_FINAL_DECISION",
            "player_text": "Good. Thanks.",
            "node_context": {"recommended_expression": "Thank you, officer."},
            "evaluation_summary": {"task_success": False, "clarity": 0.5},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "clarify",
                "next_action": "REASK",
                "next_node_id": "IMM_EXTRA_007_CLARIFY_FINAL_DECISION",
            },
            "dialogue_directive": {
                "purpose": "support_retry",
                "target_slot": "immigration_transition_acknowledgement",
            },
            "dialogue_seed": {
                "surface_goal": "confirm_immigration_clearance_transition",
                "required_slots": ["immigration_transition_acknowledgement"],
            },
        },
        use_llm=True,
        llm_client=NeutralRetryLLMClient(),
    )

    assert result["llm"]["used"] is True
    assert "you mentioned" not in result["npc_text"].lower()
    assert result["npc_text"].endswith("Alright, here is your passport. Enjoy your stay.")


def test_immigration_llm_cannot_contradict_current_occupation_slot() -> None:
    class StaleOccupationLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Officer Hale",
                "npc_text": "Unemployed. That is clear. Move on.",
                "tts_text": "Unemployed. That is clear. Move on.",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "normal",
                "llm_reason": "Wrongly uses a previous occupation fact.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_009_OCCUPATION",
            "player_text": "I'm a student.",
            "node_context": {"recommended_expression": "I'm a student."},
            "evaluation_summary": {"task_success": True, "clarity": 0.8},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "success",
                "next_action": "ADVANCE",
                "next_node_id": "IMM_007_FINAL_DECISION",
            },
            "dialogue_directive": {
                "purpose": "continue_to_next_question",
                "target_slot": "occupation",
            },
            "dialogue_seed": {
                "surface_goal": "confirm_immigration_clearance_transition",
                "required_slots": ["occupation"],
            },
            "understanding": {
                "extracted_slots": {"occupation": "student"},
            },
        },
        use_llm=True,
        llm_client=StaleOccupationLLMClient(),
    )

    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "current_slot_contradiction"
    assert "unemployed" not in result["npc_text"].lower()
    assert result["npc_text"] == "Alright, here is your passport. Enjoy your stay."


def test_immigration_success_llm_cannot_open_question_on_clearance_transition() -> None:
    class WorkQuestionLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Officer Hale",
                "npc_text": "OpenAI engineer. Good. Any work here in the United States?",
                "tts_text": "OpenAI engineer. Good. Any work here in the United States?",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "normal",
                "llm_reason": "Wrongly opens a new work question on the clearance transition.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
            "node_id": "IMM_009_OCCUPATION",
            "player_text": "Um, I work at OpenAI as a AI engineer.",
            "node_context": {"recommended_expression": "I'm an engineer."},
            "evaluation_summary": {"task_success": True, "clarity": 0.86},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "success",
                "next_action": "ADVANCE",
                "next_node_id": "IMM_007_FINAL_DECISION",
            },
            "dialogue_directive": {
                "purpose": "continue_to_next_question",
                "target_slot": "occupation",
            },
            "dialogue_seed": {
                "surface_goal": "confirm_immigration_clearance_transition",
                "required_slots": ["occupation"],
            },
            "understanding": {
                "extracted_slots": {"occupation": "engineer"},
            },
        },
        use_llm=True,
        llm_client=WorkQuestionLLMClient(),
    )

    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "immigration_surface_goal_mismatch"
    assert result["npc_text"] == "Alright, here is your passport. Enjoy your stay."
    assert "?" not in result["npc_text"]
    assert "work here" not in result["npc_text"].lower()


def test_animation_resolved_by_emotion() -> None:
    # joy emotion -> joy animation
    res_joy = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate", "emotion": "joy"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Hello.",
            "node_context": {"recommended_expression": "Nice to meet you."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "npc_emotion": "joy",
        },
        use_llm=False,
    )
    assert res_joy["animation"] == "joy"

    # panic emotion -> panic animation
    res_panic = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "hale", "npc_role": "immigration_officer", "emotion": "panic"},
            "node_id": "IMM_002_PURPOSE",
            "player_text": "Hello.",
            "node_context": {"recommended_expression": "Hello sir."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "npc_emotion": "panic",
        },
        use_llm=False,
    )
    assert res_panic["animation"] == "panic"


def test_emotion_based_tts_parameter_mapping(monkeypatch) -> None:
    # .env 파일 오버라이드가 동작하지 않도록 _read_env_file을 모킹합니다.
    monkeypatch.setattr(
        "backend.app.services.service_a.voice_output_service._read_env_file",
        lambda path: {},
    )
    # OS 환경 변수 오버라이드도 제거합니다.
    monkeypatch.delenv("MURPHY_ELEVENLABS_STABILITY", raising=False)
    monkeypatch.delenv("MURPHY_ELEVENLABS_SIMILARITY_BOOST", raising=False)
    monkeypatch.delenv("MURPHY_ELEVENLABS_STYLE", raising=False)
    monkeypatch.delenv("MURPHY_ELEVENLABS_SPEED", raising=False)

    from backend.app.services.service_a.voice_output_service import _build_provider_request
    
    dialogue_joy = {
        "npc_text": "Hello, how are you?",
        "npc_emotion": "joy",
        "tone": "formal_neutral",
    }
    
    req = _build_provider_request(
        provider_name="elevenlabs",
        text="Hello, how are you?",
        speaker_id="arabella",
        voice_profile_id="arabella_profile",
        voice_id="Z3R5wn05IrDiVCyEkUrK",
        tone="formal_neutral",
        english_level="beginner",
        dialogue=dialogue_joy,
    )
    assert req.provider_options["stability"] == 0.65
    assert req.provider_options["style"] == 0.20
    assert req.provider_options["speed"] == 0.95
    assert req.provider_options["similarity_boost"] == 0.85


def test_smalltalk_diagnostic_bypasses_missing_question_guard() -> None:
    class FlatDialogueLLMClient:
        model = "fake-model"
        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Arabella",
                "npc_text": "I see. Let's talk about it.",  # No question
                "tts_text": "I see. Let's talk about it.",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "joy",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[COHERENT] Reaction-only statement for testing",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "I am traveling alone.",
            "node_context": {"recommended_expression": "I am traveling by myself."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {"purpose": "smalltalk_diagnostic"},
            "dialogue_seed": {
                "surface_goal": "ask_companion_or_visit_plan"
            }
        },
        use_llm=True,
        llm_client=FlatDialogueLLMClient(),
    )
    
    assert result["npc_text"] == "I see. Let's talk about it."
    assert result["fallback"]["used"] is False


def test_smalltalk_diagnostic_triggers_coherence_guard_for_naked_question() -> None:
    class NakedQuestionLLMClient:
        model = "fake-model"
        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Arabella",
                "npc_text": "What is your purpose?",  # Naked question (first sentence ends with ?)
                "tts_text": "What is your purpose?",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "joy",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[COHERENT] Naked question without reaction",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "I am traveling alone.",
            "node_context": {"recommended_expression": "I am traveling by myself."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {"purpose": "smalltalk_diagnostic"},
            "dialogue_seed": {
                "surface_goal": "ask_companion_or_visit_plan"
            }
        },
        use_llm=True,
        llm_client=NakedQuestionLLMClient(),
    )
    
    # Should fall back due to coherence guard (naked question)
    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "coherence_violation_naked_question"
    assert result["fallback"]["used"] is True


def test_smalltalk_diagnostic_triggers_coherence_guard_for_non_sequitur() -> None:
    class NonSequiturLLMClient:
        model = "fake-model"
        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Arabella",
                "npc_text": "Oh, that's nice. What are you going to do?",
                "tts_text": "Oh, that's nice. What are you going to do?",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "joy",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[NON-SEQUITUR] Random statement test",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "I am traveling alone.",
            "node_context": {"recommended_expression": "I am traveling by myself."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {"purpose": "smalltalk_diagnostic"},
            "dialogue_seed": {
                "surface_goal": "ask_companion_or_visit_plan"
            }
        },
        use_llm=True,
        llm_client=NonSequiturLLMClient(),
    )
    
    # Should fall back due to coherence guard (non-sequitur)
    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "coherence_violation_non_sequitur"
    assert result["fallback"]["used"] is True


def test_smalltalk_diagnostic_fallback_uses_generic_neutral_responses() -> None:
    class FailingLLMClient:
        model = "failing-model"
        def generate(self, payload: dict) -> dict:
            from backend.app.agents.agent_a.npc_llm_client import NPCDialogueLLMUnavailable
            raise NPCDialogueLLMUnavailable("Test fail")

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Hello.",
            "node_context": {"recommended_expression": "Nice to meet you."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {"purpose": "smalltalk_diagnostic"},
            "dialogue_seed": {
                "surface_goal": "ask_companion_or_visit_plan"
            }
        },
        use_llm=True,
        llm_client=FailingLLMClient(),
    )
    
    generic_neutral_responses = [
        "I see. Tell me more about that.",
        "That sounds interesting. Go on.",
        "Oh, really? That's good to know.",
        "I understand. What else can you tell me?",
        "Interesting. Let's keep talking.",
        "Right, I get what you mean.",
        "I hear you. Let's move forward."
    ]
    
    assert result["npc_text"] in generic_neutral_responses
    assert result["feedback_kr"] == "자유롭게 스몰토크를 이어가고 있습니다. 계속 대화를 나누어 보세요."


def test_smalltalk_diagnostic_handles_topic_switch_and_length_target() -> None:
    class OkLLMClient:
        model = "fake-model"
        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Arabella",
                "npc_text": "I see. Let's keep going.",  # No pivot initially
                "tts_text": "I see. Let's keep going.",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "joy",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[COHERENT] Valid dialogue response",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Yes.",
            "node_context": {"recommended_expression": "Yes, it is."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "topic_switch": True,
                "length_target": 8
            },
            "dialogue_seed": {
                "surface_goal": "ask_companion_or_visit_plan"
            }
        },
        use_llm=True,
        llm_client=OkLLMClient(),
    )
    
    # Topic switch True should trigger post-processing pivot addition
    assert result["npc_text"].startswith("Anyway, ")
    assert result["tts_text"].startswith("Anyway, ")


def test_smalltalk_diagnostic_blocks_repeated_pen_request_after_history() -> None:
    class PenLoopLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Arabella",
                "npc_text": "Sorry about that. Could I borrow your pen for this form?",
                "tts_text": "Sorry about that. Could I borrow your pen for this form?",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "joy",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[COHERENT] It acknowledges the player but repeats the old pen request.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Why do you keep asking about my pen? I already gave it to you.",
            "node_context": {"recommended_expression": "Let's talk about the trip."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "target_slot": None,
                "topic_switch": True,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "destination_travel",
                "required_slots": [],
                "dialogue_history": [
                    {
                        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
                        "player_text_preview": "Hi. Sure, here you go. You can have that.",
                        "npc_text_preview": "Thanks, that's kind. Do you have a spare pen too?",
                        "filled_slots": {},
                    }
                ],
            },
        },
        use_llm=True,
        llm_client=PenLoopLLMClient(),
    )

    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "smalltalk_repeated_object_request"
    assert "borrow your pen" not in result["npc_text"].lower()


def test_smalltalk_diagnostic_blocks_repeated_pen_request_using_in_memory_checkpointer() -> None:
    from backend.app.agents.agent_a.npc_dialogue_agent import reset_graph_singleton_for_testing

    reset_graph_singleton_for_testing()

    class PenLoopLLMClient:
        model = "fake-model"

        def __init__(self) -> None:
            self.call_count = 0

        def generate(self, payload: dict) -> dict:
            self.call_count += 1
            text = (
                "Thanks. Could I borrow your pen for this form?"
                if self.call_count == 1
                else "Sorry about that. Could I borrow your pen for this form?"
            )
            return {
                "speaker": "Arabella",
                "npc_text": text,
                "tts_text": text,
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "joy",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[COHERENT] Pen request.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    llm_client = PenLoopLLMClient()
    session_id = "session_test_memory_pen_loop_0001"
    npc = {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"}

    # Turn 1: NPC asks, player gives pen
    result1 = generate_npc_dialogue_from_level_design(
        {
            "session_id": session_id,
            "npc": npc,
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Sure, here you are. You can borrow it.",
            "node_context": {"recommended_expression": "Let's talk about the trip."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "target_slot": None,
                "topic_switch": False,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "destination_travel",
                "required_slots": [],
            },
        },
        use_llm=True,
        llm_client=llm_client,
    )
    assert result1["llm"]["used"] is True
    assert "borrow your pen" in result1["npc_text"].lower()

    # Turn 2: Player complains about repetition, NPC tries to ask again, gets blocked
    result2 = generate_npc_dialogue_from_level_design(
        {
            "session_id": session_id,
            "npc": npc,
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Why do you keep asking about my pen? I already gave it to you.",
            "node_context": {"recommended_expression": "Let's talk about the trip."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "target_slot": None,
                "topic_switch": True,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "destination_travel",
                "required_slots": [],
            },
        },
        use_llm=True,
        llm_client=llm_client,
    )
    assert result2["llm"]["used"] is False
    assert result2["llm"]["reason"] == "smalltalk_repeated_object_request"
    assert "borrow your pen" not in result2["npc_text"].lower()


def test_smalltalk_diagnostic_blocks_repeated_pen_request_using_in_memory_checkpointer_neutral_player() -> None:
    from backend.app.agents.agent_a.npc_dialogue_agent import reset_graph_singleton_for_testing

    reset_graph_singleton_for_testing()

    class PenLoopLLMClient:
        model = "fake-model"

        def __init__(self) -> None:
            self.call_count = 0

        def generate(self, payload: dict) -> dict:
            self.call_count += 1
            text = (
                "Thanks. Could I borrow your pen for this form?"
                if self.call_count == 1
                else "Sorry about that. Could I borrow your pen for this form?"
            )
            return {
                "speaker": "Arabella",
                "npc_text": text,
                "tts_text": text,
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "joy",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[COHERENT] Pen request.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    llm_client = PenLoopLLMClient()
    session_id = "session_test_memory_pen_loop_neutral_0001"
    npc = {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"}

    # Turn 1: NPC asks, player gives pen
    result1 = generate_npc_dialogue_from_level_design(
        {
            "session_id": session_id,
            "npc": npc,
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Sure, here you are. You can borrow it.",
            "node_context": {"recommended_expression": "Let's talk about the trip."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "target_slot": None,
                "topic_switch": False,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "destination_travel",
                "required_slots": [],
            },
        },
        use_llm=True,
        llm_client=llm_client,
    )
    assert result1["llm"]["used"] is True
    assert "borrow your pen" in result1["npc_text"].lower()

    # Turn 2: Player replies neutrally, NPC tries to ask again, gets blocked by turn_buffer memory
    result2 = generate_npc_dialogue_from_level_design(
        {
            "session_id": session_id,
            "npc": npc,
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Yes, it is very nice.",
            "node_context": {"recommended_expression": "Let's talk about the trip."},
            "evaluation_summary": {"task_success": True, "clarity": 1.0},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {"branch_type": "success"},
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "target_slot": None,
                "topic_switch": True,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "destination_travel",
                "required_slots": [],
            },
        },
        use_llm=True,
        llm_client=llm_client,
    )
    assert result2["llm"]["used"] is False
    assert result2["llm"]["reason"] == "smalltalk_repeated_object_request"
    assert "borrow your pen" not in result2["npc_text"].lower()


def test_smalltalk_social_context_open_falls_back_to_repair_request() -> None:
    class TravelQuestionLLMClient:
        model = "fake-model"

        def generate(self, payload: dict) -> dict:
            return {
                "speaker": "Arabella",
                "npc_text": "Hi again. Do you travel often?",
                "tts_text": "Hi again. Do you travel often?",
                "feedback_kr": "Good.",
                "tone": "formal_neutral",
                "animation": "move",
                "npc_emotion": "confusion",
                "stability": 0.75,
                "style": 0.45,
                "speed": 1.0,
                "similarity_boost": 0.85,
                "llm_reason": "[COHERENT] The player greeted again, then I pivoted to a travel question.",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Hello?",
            "node_context": {"recommended_expression": "Sure, here you go."},
            "understanding": {
                "social_context": {
                    "scene_norm": "peer_smalltalk",
                    "conversation_move": "greeting_only",
                    "pending_social_obligation": "seatmate_pen_request",
                    "obligation_status": "open",
                    "engagement_quality": "thin",
                    "recommended_npc_move": "acknowledge_and_retry_request",
                    "reason": "The player greeted but did not answer the seatmate's pen request.",
                }
            },
            "evaluation_summary": {"task_success": False, "clarity": 0.3},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "clarify",
                "next_action": "REASK",
                "branch_reason": "flight_smalltalk_social_obligation_open",
            },
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "tone_hint": "warm_social_repair",
                "target_slot": None,
                "topic_switch": False,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "estimate_user_travel_speaking_level",
                "required_slots": [],
            },
        },
        use_llm=True,
        llm_client=TravelQuestionLLMClient(),
    )

    assert result["llm"]["used"] is False
    assert result["llm"]["reason"] == "smalltalk_social_obligation_ignored"
    assert "pen" in result["npc_text"].lower()
    assert "travel often" not in result["npc_text"].lower()


def test_smalltalk_dropped_social_obligation_fallback_stops_asking_pen() -> None:
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Hello?",
            "node_context": {"recommended_expression": "Sure, here you go."},
            "understanding": {
                "social_context": {
                    "scene_norm": "peer_smalltalk",
                    "conversation_move": "repeated_greeting",
                    "pending_social_obligation": "seatmate_pen_request",
                    "obligation_status": "ignored",
                    "engagement_quality": "stalled",
                    "recommended_npc_move": "playful_boundary",
                    "reason": "The player repeatedly greeted instead of answering the pen request.",
                }
            },
            "evaluation_summary": {"task_success": False, "clarity": 0.3},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "success",
                "next_action": "ADVANCE",
                "branch_reason": "flight_smalltalk_social_obligation_dropped",
            },
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "tone_hint": "warm_social_repair",
                "target_slot": None,
                "topic_switch": False,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "estimate_user_travel_speaking_level",
                "required_slots": [],
            },
        },
        use_llm=False,
    )

    text = result["npc_text"].lower()
    assert result["fallback"]["reason"] == "social_context_fallback"
    assert "pen" not in text
    assert "borrow" not in text
    assert "ask someone else" in text


def test_smalltalk_engagement_check_fallback_asks_if_player_is_okay() -> None:
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Hello?",
            "node_context": {"recommended_expression": "Sure, here you go."},
            "understanding": {
                "social_context": {
                    "scene_norm": "peer_smalltalk",
                    "conversation_move": "repeated_greeting",
                    "pending_social_obligation": "seatmate_pen_request",
                    "obligation_status": "ignored",
                    "engagement_quality": "stalled",
                    "recommended_npc_move": "playful_boundary",
                    "reason": "The player keeps greeting after the pen request was dropped.",
                }
            },
            "evaluation_summary": {"task_success": False, "clarity": 0.3},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "clarify",
                "next_action": "REASK",
                "branch_reason": "flight_smalltalk_engagement_check",
            },
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "tone_hint": "warm_social_repair",
                "target_slot": None,
                "topic_switch": False,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "estimate_user_travel_speaking_level",
                "required_slots": [],
            },
        },
        use_llm=False,
    )

    text = result["npc_text"].lower()
    assert result["fallback"]["reason"] == "social_context_fallback"
    assert "pen" not in text
    assert "travel" not in text
    assert "are you okay" in text


def test_smalltalk_engagement_check_fallback_does_not_assume_greeting() -> None:
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "What?",
            "node_context": {"recommended_expression": "Sure, here you go."},
            "understanding": {
                "social_context": {
                    "scene_norm": "peer_smalltalk",
                    "conversation_move": "clarification_request",
                    "pending_social_obligation": "seatmate_pen_request",
                    "obligation_status": "ignored",
                    "engagement_quality": "stalled",
                    "recommended_npc_move": "playful_boundary",
                    "reason": "The player keeps asking what after the request was dropped.",
                }
            },
            "evaluation_summary": {"task_success": False, "clarity": 0.3},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "clarify",
                "next_action": "REASK",
                "branch_reason": "flight_smalltalk_engagement_check",
            },
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "tone_hint": "warm_social_repair",
                "target_slot": None,
                "topic_switch": False,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "estimate_user_travel_speaking_level",
                "required_slots": [],
            },
        },
        use_llm=False,
    )

    text = result["npc_text"].lower()
    assert result["fallback"]["reason"] == "social_context_fallback"
    assert "hello" not in text
    assert "are you having trouble" in text


def test_smalltalk_engagement_give_space_fallback_stops_pushing_conversation() -> None:
    result = generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Hello.",
            "node_context": {"recommended_expression": "Sure, here you go."},
            "understanding": {
                "social_context": {
                    "scene_norm": "peer_smalltalk",
                    "conversation_move": "repeated_greeting",
                    "pending_social_obligation": "seatmate_pen_request",
                    "obligation_status": "ignored",
                    "engagement_quality": "stalled",
                    "recommended_npc_move": "playful_boundary",
                    "reason": "The player keeps greeting after engagement was checked.",
                }
            },
            "evaluation_summary": {"task_success": False, "clarity": 0.3},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "clarify",
                "next_action": "REASK",
                "branch_reason": "flight_smalltalk_engagement_give_space",
            },
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "tone_hint": "warm_social_repair",
                "target_slot": None,
                "topic_switch": False,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "estimate_user_travel_speaking_level",
                "required_slots": [],
            },
        },
        use_llm=False,
    )

    text = result["npc_text"].lower()
    assert result["fallback"]["reason"] == "social_context_fallback"
    assert "pen" not in text
    assert "travel" not in text
    assert "give you some space" in text


def test_smalltalk_dropped_obligation_payload_marks_pen_closed() -> None:
    captured: dict[str, Any] = {}

    generate_npc_dialogue_from_level_design(
        {
            "npc": {"npc_id": "SEATMATE_A_01", "npc_role": "seatmate"},
            "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "player_text": "Hello. Hello.",
            "node_context": {"recommended_expression": "Sure, here you go."},
            "understanding": {
                "social_context": {
                    "scene_norm": "peer_smalltalk",
                    "conversation_move": "repeated_greeting",
                    "pending_social_obligation": "seatmate_pen_request",
                    "obligation_status": "ignored",
                    "engagement_quality": "stalled",
                    "recommended_npc_move": "playful_boundary",
                    "reason": "The player kept greeting after the pen request was dropped.",
                }
            },
            "evaluation_summary": {"task_success": False, "clarity": 0.3},
            "level_hint": {"english_level": "beginner"},
            "in_game_feedback": {"npc_recast_line_candidate": None},
            "branch": {
                "branch_type": "success",
                "next_action": "ADVANCE",
                "branch_reason": "flight_smalltalk_social_obligation_dropped",
            },
            "dialogue_directive": {
                "purpose": "smalltalk_diagnostic",
                "tone_hint": "warm_social_repair",
                "target_slot": None,
                "topic_switch": False,
                "length_target": 10,
            },
            "dialogue_seed": {
                "surface_goal": "estimate_user_travel_speaking_level",
                "required_slots": [],
            },
        },
        use_llm=True,
        llm_client=_CapturingLLMClient(captured),
    )

    payload = captured["payload"]
    assert "seatmate_pen_request" in payload["closed_hooks"]
    assert "seatmate_pen_request" in payload["do_not_reopen"]
    assert payload["social_obligation_lifecycle"] == "dropped"
    assert "seatmate_pen_request" not in payload["open_hooks"]


class _CapturingLLMClient:
    model = "fake-model"

    def __init__(self, captured: dict):
        self.captured = captured

    def generate(self, payload: dict) -> dict:
        self.captured["payload"] = payload
        return {
            "speaker": "Officer Hale",
            "npc_text": "I see you stay at MGM Grand Las Vegas.",
            "tts_text": "I see you stay at MGM Grand Las Vegas.",
            "feedback_kr": "Good.",
            "tone": "formal_neutral",
            "animation": "move",
            "npc_emotion": "joy",
            "stability": 0.75,
            "style": 0.45,
            "speed": 1.0,
            "similarity_boost": 0.85,
            "llm_reason": "testing capture",
            "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }


def _eokkka_payload(
    assigned_visit_location: str = "",
    visit_location_suspicion_reason: str = "",
    visit_location_difficulty: int = 0,
    random_customs_item: str = "",
) -> dict:
    return {
        "npc": {"npc_id": "hale", "npc_role": "immigration_officer"},
        "node_id": "IMM_002_PURPOSE",
        "player_text": "I am traveling.",
        "node_context": {
            "npc_question": "What is the purpose of your visit?",
            "recommended_expression": "I'm here for tourism.",
        },
        "evaluation_summary": {"task_success": True, "clarity": 0.9},
        "level_hint": {"english_level": "beginner"},
        "in_game_feedback": {"npc_recast_line_candidate": None},
        "branch": {"branch_type": "success"},
        "dialogue_seed": {
            "assigned_visit_location": assigned_visit_location,
            "visit_location_suspicion_reason": visit_location_suspicion_reason,
            "visit_location_difficulty": visit_location_difficulty,
            "random_customs_item": random_customs_item,
        },
        "game_state": {
            "assigned_visit_location": assigned_visit_location,
            "visit_location_suspicion_reason": visit_location_suspicion_reason,
            "visit_location_difficulty": visit_location_difficulty,
            "random_customs_item": random_customs_item,
        }
    }


def test_dialogue_agent_includes_assigned_visit_location_in_prompt(monkeypatch):
    """CR-B-EOKKKA: dialogue_seed 의 assigned_visit_location 이 LLM 페이로드에 그대로 전달됨."""
    payload = _eokkka_payload(
        assigned_visit_location="MGM Grand Las Vegas",
        visit_location_suspicion_reason="luxury_hotel_at_business_trip",
        visit_location_difficulty=10,
    )
    captured = {}
    monkeypatch.setattr(
        "backend.app.agents.agent_a.npc_dialogue_agent.build_npc_dialogue_llm_client_from_environment",
        lambda: _CapturingLLMClient(captured),
    )
    generate_npc_dialogue_from_level_design(payload, use_llm=True)
    assert "MGM Grand Las Vegas" in str(captured.get("payload", {}))


def test_dialogue_agent_fallback_seeds_assigned_visit_location():
    """LLM 실패 시 폴백이 generic 이 아닌 assigned_visit_location 시드 응답."""
    payload = _eokkka_payload(assigned_visit_location="MGM Grand Las Vegas")
    result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
    # 룰베이스 시드 시점에 MGM Grand Las Vegas 가 텍스트에 포함되어야 함
    assert "MGM Grand Las Vegas" in result["npc_text"]


def test_dialogue_agent_fallback_seeds_customs_item():
    """customs item 시드 폴백."""
    payload = _eokkka_payload(random_customs_item="red ginseng box")
    result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
    assert "red ginseng" in result["npc_text"].lower()


def test_dialogue_agent_no_suspicion_meta_uses_default_fallback():
    """assigned_visit_location 도 customs_item 도 없으면 기존 default 폴백 유지."""
    payload = _eokkka_payload()
    result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
    assert result["npc_text"]  # 기존 동작 회귀 보호


def _payload(**kwargs: Any) -> dict[str, Any]:
    base = _eokkka_payload(
        assigned_visit_location=kwargs.get("assigned_visit_location", ""),
        visit_location_suspicion_reason=kwargs.get("visit_location_suspicion_reason", ""),
        visit_location_difficulty=kwargs.get("visit_location_difficulty", 0),
        random_customs_item=kwargs.get("random_customs_item", ""),
    )
    if "suspicion_scope" in kwargs:
        base["dialogue_seed"]["suspicion_scope"] = kwargs["suspicion_scope"]
        base["game_state"]["suspicion_scope"] = kwargs["suspicion_scope"]
    if "dialogue_history" in kwargs:
        base["dialogue_seed"]["dialogue_history"] = kwargs["dialogue_history"]
        base["game_state"]["dialogue_history"] = kwargs["dialogue_history"]
    if "dialogue_purpose" in kwargs:
        if "dialogue_directive" not in base:
            base["dialogue_directive"] = {}
        base["dialogue_directive"]["purpose"] = kwargs["dialogue_purpose"]
    if "branch_type" in kwargs:
        base["branch"]["branch_type"] = kwargs["branch_type"]
    if "surface_goal" in kwargs:
        base["dialogue_seed"]["surface_goal"] = kwargs["surface_goal"]
    return base


def _capture_llm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    client = _CapturingLLMClient(captured)
    generate_npc_dialogue_from_level_design(payload, use_llm=True, llm_client=client)
    return captured.get("payload", {})


def _render_system_prompt(llm_payload: dict[str, Any]) -> str:
    from backend.app.agents.agent_a.npc_llm_client import _render_developer_instructions
    return _render_developer_instructions(llm_payload)


def test_suspicion_mode_active_only_when_scope_location():
    """scope=location 일 때만 location 정보가 프롬프트에 노출."""
    payload = _payload(suspicion_scope="location", assigned_visit_location="MGM Grand Las Vegas")
    captured = _capture_llm_payload(payload)
    assert captured["suspicion_scope"] == "location"
    assert "MGM Grand Las Vegas" in str(captured)
    
    rendered = _render_system_prompt(captured)
    assert "SUSPICION MODE" in rendered
    assert "MGM Grand Las Vegas" in rendered


def test_suspicion_mode_hidden_when_scope_none():
    """scope=none 일 때 SUSPICION MODE 가 렌더링되지 않음."""
    payload = _payload(suspicion_scope="none", assigned_visit_location="MGM Grand Las Vegas")
    captured = _capture_llm_payload(payload)
    rendered = _render_system_prompt(captured)
    assert "SUSPICION MODE" not in rendered


def test_dialogue_history_passed_in_all_purposes():
    """dialogue_history 가 smalltalk 외 purpose 에서도 llm_payload 에 전달됨."""
    history = [
        {"turn_index": 1, "player_text_preview": "business",
         "npc_text_preview": "How long?", "filled_slots": {"visit_purpose": "business"}}
    ]
    payload = _payload(dialogue_purpose="default", dialogue_history=history)
    captured = _capture_llm_payload(payload)
    assert captured["dialogue_history"] == history


def test_retry_paraphrase_varies_from_previous():
    """retry 분기에서 직전 NPC 라인과 다른 표현이 폴백으로 선택됨."""
    payload = _payload(
        branch_type="retry",
        dialogue_history=[{"player_text_preview": "I dunno",
                           "npc_text_preview": "What is the purpose of your visit?"}],
        surface_goal="ask_visit_purpose",
    )
    result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
    assert result["npc_text"] != "What is the purpose of your visit?"


def test_suspicion_not_blurted_before_answer():
    """scope=location 이지만 dialogue_history 에서 visit_purpose 슬롯 미응답이면
    프롬프트에 'do NOT challenge preemptively' 가이드 적용 검증."""
    payload = _payload(
        suspicion_scope="location",
        assigned_visit_location="MGM Grand Las Vegas",
        dialogue_history=[],
    )
    captured = _capture_llm_payload(payload)
    rendered = _render_system_prompt(captured)
    assert "answer" in rendered.lower() and "preemptive" in rendered.lower() or "Answer-first" in rendered


def test_desync_guard_overrides_llm_next_node_question() -> None:
    # LLM이 분기를 어기고 임의로 다음 노드의 질문("Where will you stay?")을 유출하는 상황을 모사
    class BadDialogueLLMClient:
        model = "fake-model"
        def generate(self, payload: dict) -> dict:
            return {
                "npc_text": "I see. Tell me where you will stay in the US.",  # 다음 질문(location)을 유출함
                "tts_text": "I see. Tell me where you will stay in the US.",
                "feedback_kr": "좋아요.",
                "tone": "formal_neutral",
                "animation": "move",
                "llm_reason": "off-topic progression",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    # 입력: branch_type="clarify", next_action="REASK", dialogue_purpose="support_retry", surface_goal="ask_stay_duration"
    payload = _payload(
        branch_type="clarify",
        dialogue_purpose="support_retry",
        surface_goal="ask_stay_duration",
        dialogue_history=[{"player_text_preview": "maybe 13days", "npc_text_preview": "How long will you stay?"}]
    )
    # next_action을 REASK로 명시적으로 전달
    payload["branch"]["next_action"] = "REASK"
    payload["next_action"] = "REASK"

    result = generate_npc_dialogue_from_level_design(
        payload,
        use_llm=True,
        llm_client=BadDialogueLLMClient()
    )

    # 비-ADVANCE 가드로 인해 다음 질문("stay")이 override되어, 원래 노드의 질문(stay_duration)만 질문해야 함
    assert "stay in the United States" in result["npc_text"] or "plan to stay" in result["npc_text"] or "remain here" in result["npc_text"]
    assert "where you will stay" not in result["npc_text"].lower()


def test_duplicate_intent_question_guard_blocks_repeated_phrasing() -> None:
    """LLM이 'What is your job. What is your occupation?' 같이 같은 의도를
    두 번 출력할 때 duplicate_intent_question 가드가 작동하여 fallback으로 전환되는지 검증."""
    class DuplicateIntentLLMClient:
        model = "fake-model"
        def generate(self, payload: dict) -> dict:
            return {
                "npc_text": "What is your job? What is your occupation?",
                "tts_text": "What is your job? What is your occupation?",
                "feedback_kr": "좋아요.",
                "tone": "formal_neutral",
                "animation": "move",
                "llm_reason": "duplicate question",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    payload = _payload(
        branch_type="success",
        surface_goal="ask_occupation",
    )
    result = generate_npc_dialogue_from_level_design(
        payload,
        use_llm=True,
        llm_client=DuplicateIntentLLMClient()
    )

    # 가드가 감지하여 fallback을 사용하는지 검증
    assert result["llm"]["reason"] == "duplicate_intent_question"
    assert result["llm"]["fallback_used"] is True


def test_clearance_failure_contradiction_guard_blocks_mixed_tone() -> None:
    """LLM이 success closing과 fail message를 함께 출력할 때 가드 발동."""
    class MixedToneLLMClient:
        model = "fake-model"
        def generate(self, payload: dict) -> dict:
            return {
                "npc_text": "All right. Go to baggage claim. Sir, since you cannot provide the details, we cannot complete the report.",
                "tts_text": "All right. Go to baggage claim. Sir, since you cannot provide the details, we cannot complete the report.",
                "feedback_kr": "좋아요.",
                "tone": "formal_neutral",
                "animation": "move",
                "llm_reason": "mixed tone closing",
                "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    payload = _payload(
        branch_type="fail",
        surface_goal="closing_eviction",
    )
    result = generate_npc_dialogue_from_level_design(
        payload,
        use_llm=True,
        llm_client=MixedToneLLMClient()
    )

    # 가드가 감지하여 fallback을 사용하는지 검증
    assert result["llm"]["reason"] == "clearance_failure_contradiction"
    assert result["llm"]["fallback_used"] is True


def test_dialogue_policy_service_confirm_carousel_search() -> None:
    from backend.app.services.service_a.dialogue_policy_service import SURFACE_GOAL_QUESTIONS, RETRY_PARAPHRASES
    assert SURFACE_GOAL_QUESTIONS["confirm_carousel_search"] == "Did you check the carousel carefully before coming to the desk?"
    assert "confirm_carousel_search" in RETRY_PARAPHRASES
    assert "Did you check the carousel belt before coming here?" in RETRY_PARAPHRASES["confirm_carousel_search"]


def test_open_hooks_stoplist_filter() -> None:
    from backend.app.services.service_a.session_context_card_service import _extract_open_hooks
    # Test text containing stop words and content words
    player_text = "Yeah, hi. I checked the carousel but my Hermes bag was not there."
    hooks = _extract_open_hooks(player_text)
    # Stop words like "yeah", "hi", "the", "but", "my", "was", "not", "there" must be filtered out
    assert "hermes" in hooks
    assert "bag" in hooks
    assert "carousel" in hooks
    assert "yeah" not in hooks
    assert "hi" not in hooks


def test_synthesize_fallback_next_question_gated_by_branch_type() -> None:
    from backend.app.services.service_a.dialogue_policy_service import synthesize_fallback_next_question
    # Case 1: branch_type is success or neutral (or None) -> prefix is added
    res_success = synthesize_fallback_next_question(
        fallback_text="Hold on.",
        surface_goal="ask_occupation",
        open_hooks=["engineer"],
        branch_type="success"
    )
    assert "You mentioned engineer —" in res_success

    # Case 2: branch_type is retry or clarify or warning -> prefix is NOT added
    res_retry = synthesize_fallback_next_question(
        fallback_text="Hold on.",
        surface_goal="ask_occupation",
        open_hooks=["engineer"],
        branch_type="retry"
    )
    assert "You mentioned engineer —" not in res_retry
