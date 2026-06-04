from typing import Any

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.services.service_c.settings_service import AppSettings


class FakeUnderstandingLLMClient:
    model = "fake-understanding-model"

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return self.response


def _purpose_node_context():
    return OpenKBService().get_node_context("CH0_IMMIGRATION", "IMM_002_PURPOSE")


def test_understanding_agent_uses_llm_client_in_llm_mode() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_visit_purpose",
            "intent_success": True,
            "confidence": 0.91,
            "meaning_summary_kr": "플레이어는 박물관 방문 목적을 말했다.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "위험 표현 없음.",
            "risk_tags": [],
            "extracted_slots": {"visit_purpose": "tourism"},
            "missing_slots": [],
            "needs_clarification": False,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text("I want to visit museums.", _purpose_node_context())

    assert output.intent == "state_visit_purpose"
    assert output.intent_success is True
    assert output.confidence == 0.91
    assert output.extracted_slots == {"visit_purpose": "tourism"}
    assert llm_client.calls[0]["player_text"] == "I want to visit museums."
    assert llm_client.calls[0]["node_context"]["node_id"] == "IMM_002_PURPOSE"


def test_understanding_agent_falls_back_to_rule_mode_when_llm_output_is_forbidden() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_visit_purpose",
            "intent_success": True,
            "confidence": 0.99,
            "meaning_summary_kr": "분기까지 시도한 잘못된 응답.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "위험 표현 없음.",
            "risk_tags": [],
            "extracted_slots": {"visit_purpose": "tourism"},
            "missing_slots": [],
            "needs_clarification": False,
            "next_node_id": "IMM_003_DURATION",
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text("I'm here for tourism.", _purpose_node_context())

    assert output.intent == "state_visit_purpose"
    assert output.confidence == 0.94
    assert output.meaning_summary_kr == "The player said they are visiting for tourism."
    assert llm_client.calls
