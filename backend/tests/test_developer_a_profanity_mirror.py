import pytest
import os
from backend.app.services.service_a.profanity_lexicon import contains_blocked, allowed_for
from backend.app.services.service_a.profanity_response_policy import get_profanity_fallback_response, get_incivility_tts_bias
from backend.app.agents.agent_a.npc_dialogue_agent import generate_npc_dialogue_from_level_design


def test_profanity_lexicon():
    # 1. ALWAYS_BLOCKED 검출
    assert contains_blocked("You are a bitch!") == ["bitch"]
    assert contains_blocked("kill yourself now") == ["kill yourself"]
    assert contains_blocked("Have a nice day") == []

    # 2. allowed_for 검증
    assert "damn" in allowed_for("mirror", "mild")
    assert "shit" not in allowed_for("mirror", "mild")
    assert "shit" in allowed_for("mirror", "strong")
    assert allowed_for("off", "mild") == set()


def test_profanity_response_policy():
    # 1. Officer Hale의 T2 mirror 응답 확인
    res = get_profanity_fallback_response("hale", 2, "mirror")
    assert res is not None
    assert "damn" in res["npc_text"]
    assert res["npc_emotion"] == "anger"

    # 2. Seatmate Arabella의 T2 mirror 응답 확인
    res_ara = get_profanity_fallback_response("arabella", 2, "mirror")
    assert res_ara is not None
    assert "hell" in res_ara["npc_text"]

    # 3. Off 모드 일 때는 폴백 응답 없음 (None 반환)
    assert get_profanity_fallback_response("hale", 2, "off") is None


def test_get_incivility_tts_bias():
    bias0 = get_incivility_tts_bias(0)
    assert bias0["stability"] == 0.0
    
    bias2 = get_incivility_tts_bias(2)
    assert bias2["stability"] == -0.2
    assert bias2["style"] == 0.2
    assert bias2["speed"] == 0.05


def test_dialogue_agent_rule_profanity(monkeypatch):
    # 환경 변수를 mirror 로 조작하고, T2 인격모독 신호를 보내서 룰베이스 반응 검증 (LLM 미사용 경로)
    monkeypatch.setenv("MURPHY_NPC_PROFANITY_MIRROR_MODE", "mirror")
    payload = {
        "player_text": "you idiot",
        "npc": {"npc_id": "hale"},
        "node_context": {
            "node_id": "IMM_002_PURPOSE",
            "npc_question": "What is the purpose of your visit?",
            "npc_role": "immigration_officer",
        },
        "understanding": {},
        "level_hint": {"english_level": "intermediate"},
        "branch": {"branch_type": "retry"},
        "incivility": {
            "tier": 2,
            "detected_terms": ["idiot"]
        }
    }
    
    result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
    # 룰베이스 폴백 매트릭스에 의해 Watch your damn mouth. 가 최종 npc_text 로 반환되어야 함
    assert "damn" in result["npc_text"]
    assert result["npc_emotion"] == "anger"
