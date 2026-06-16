import logging
from typing import Any

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.agents.agent_c.understanding_llm_client import UnderstandingLLMUnavailable
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


class UnavailableUnderstandingLLMClient:
    model = "fake-understanding-model"

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise UnderstandingLLMUnavailable("OpenAI Responses API 400 invalid_json_schema")


def _purpose_node_context():
    return OpenKBService().get_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_002_PURPOSE")


def _duration_node_context():
    return OpenKBService().get_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_003_DURATION")


def _location_node_context():
    return OpenKBService().get_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_004_STAY_LOCATION")


def _alpha_node_context(chapter_id: str, node_id: str):
    return OpenKBService().get_node_context(chapter_id, node_id)


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
    assert output.confidence == 0.89
    assert output.extracted_slots == {"visit_purpose": "tourism"}
    assert llm_client.calls[0]["player_text"] == "I want to visit museums."
    assert llm_client.calls[0]["node_context"]["node_id"] == "IMM_002_PURPOSE"
    assert agent.last_trace["mode"] == "llm"
    assert agent.last_trace["fallback_used"] is False
    assert agent.last_trace["tool_calls"][0]["event"] == "tool_call"
    assert agent.last_trace["tool_calls"][0]["tool_name"] == "understanding_llm_client.analyze"
    assert agent.last_trace["tool_calls"][0]["status"] == "completed"
    assert agent.last_trace["tool_calls"][0]["output_summary"]["intent"] == "state_visit_purpose"
    assert agent.last_trace["postprocessing"]["confidence_evidence_guard_applied"] is True
    assert agent.last_trace["postprocessing"]["weak_required_slot_evidence"] is True


def test_understanding_agent_llm_mode_attaches_rule_incivility_signal() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_visit_purpose",
            "intent_success": False,
            "confidence": 0.55,
            "meaning_summary_kr": "The player did not answer the visit purpose.",
            "emotion": "angry",
            "answer_relevance": "off_topic",
            "ambiguity_type": "off_topic_response",
            "risk_delta": 0,
            "risk_reason": "No immigration risk expression was found.",
            "risk_tags": [],
            "extracted_slots": {},
            "missing_slots": ["visit_purpose"],
            "needs_clarification": True,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text("f*ck you", _purpose_node_context())

    assert output.incivility is not None
    assert output.incivility.tier == 3
    assert output.incivility.category == "profanity"
    assert output.incivility.source == "rule"
    assert output.intent_success is False
    assert agent.last_trace["output_summary"]["incivility"]["tier"] == 3


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
    assert agent.last_trace["mode"] == "fallback"
    assert agent.last_trace["fallback_used"] is True
    assert agent.last_trace["tool_calls"][0]["status"] == "failed"
    assert agent.last_trace["tool_calls"][0]["error_type"] == "UnderstandingLLMUnavailable"


def test_understanding_agent_logs_llm_failure_before_rule_fallback(caplog) -> None:
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=UnavailableUnderstandingLLMClient(),
    )

    with caplog.at_level(logging.WARNING):
        output = agent.analyze_player_text("I'm here to visit my uncle.", _purpose_node_context())

    assert output.intent_success is True
    assert output.extracted_slots == {"visit_purpose": "family_visit"}
    assert any(
        "Understanding Agent LLM failed; using rule fallback" in record.message
        and "invalid_json_schema" in record.message
        for record in caplog.records
    )


def test_understanding_agent_repairs_llm_missing_allowed_visit_purpose_slot() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_visit_purpose",
            "intent_success": False,
            "confidence": 0.92,
            "meaning_summary_kr": "The visit purpose is unclear.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "unclear_purpose",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "extracted_slots": {},
            "missing_slots": ["visit_purpose"],
            "needs_clarification": True,
            "__llm_usage": {"input_tokens": 753, "output_tokens": 153, "total_tokens": 906},
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text("I'm here to visit my uncle.", _purpose_node_context())

    assert output.intent == "state_visit_purpose"
    assert output.intent_success is True
    assert output.extracted_slots == {"visit_purpose": "family_visit"}
    assert output.missing_slots == []
    assert output.needs_clarification is False
    assert agent.last_trace["mode"] == "llm"
    assert agent.last_trace["fallback_used"] is False
    assert agent.last_trace["postprocessing"] == {
        "slot_repair_applied": True,
        "source": "rule_visit_purpose_classifier",
        "slot": "visit_purpose",
        "value": "family_visit",
        "reason": "llm_missing_allowed_slot",
    }


def test_understanding_agent_repairs_llm_missing_stay_duration_slot() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_stay_duration",
            "intent_success": True,
            "confidence": 0.9,
            "meaning_summary_kr": "The player gave a stay duration.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "extracted_slots": {},
            "missing_slots": ["stay_duration"],
            "needs_clarification": False,
            "__llm_usage": {"input_tokens": 640, "output_tokens": 120, "total_tokens": 760},
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text("I will stay for 5 days.", _duration_node_context())

    assert output.intent == "state_stay_duration"
    assert output.intent_success is True
    assert output.extracted_slots == {"stay_duration": "5 days"}
    assert output.missing_slots == []
    assert output.needs_clarification is False
    assert agent.last_trace["postprocessing"] == {
        "slot_repair_applied": True,
        "source": "rule_stay_duration_classifier",
        "slot": "stay_duration",
        "value": "5 days",
        "reason": "llm_missing_allowed_slot",
    }


def test_understanding_agent_accepts_generic_llm_slot_evidence_for_required_slot() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_stay_location",
            "intent_success": True,
            "confidence": 0.89,
            "meaning_summary_kr": "The player said they will stay at a hotel.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "slot_evidence": [
                {
                    "slot": "stay_location",
                    "value": "hotel",
                    "confidence": 0.9,
                    "evidence_text": "at a hotel",
                }
            ],
            "extracted_slots": {},
            "missing_slots": ["stay_location"],
            "needs_clarification": True,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text("I'll stay at a hotel.", _location_node_context())

    assert output.intent == "state_stay_location"
    assert output.intent_success is True
    assert output.extracted_slots == {"stay_location": "hotel"}
    assert output.missing_slots == []
    assert output.needs_clarification is False
    assert output.slot_evidence[0].slot == "stay_location"
    assert output.slot_evidence[0].value == "hotel"
    assert agent.last_trace["postprocessing"]["generic_slot_evidence_applied"] is True


def test_understanding_agent_filters_generic_llm_slot_evidence_to_node_slots() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_stay_location",
            "intent_success": True,
            "confidence": 0.88,
            "meaning_summary_kr": "The player said they will stay at a hotel.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "slot_evidence": [
                {
                    "slot": "stay_location",
                    "value": "hotel",
                    "confidence": 0.9,
                    "evidence_text": "hotel",
                },
                {
                    "slot": "next_node_id",
                    "value": "IMM_005_RETURN_TICKET",
                    "confidence": 0.99,
                    "evidence_text": "go next",
                },
                {
                    "slot": "npc_text",
                    "value": "You may pass.",
                    "confidence": 0.99,
                    "evidence_text": "you may pass",
                },
            ],
            "extracted_slots": {},
            "missing_slots": ["stay_location"],
            "needs_clarification": True,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text("Hotel.", _location_node_context())

    assert output.extracted_slots == {"stay_location": "hotel"}
    assert [evidence.slot for evidence in output.slot_evidence] == ["stay_location"]
    assert agent.last_trace["postprocessing"]["dropped_slot_evidence"] == [
        "next_node_id",
        "npc_text",
    ]


def test_understanding_agent_rejects_off_topic_idiom_despite_valid_polite_response_value() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "respond_to_seatmate_request",
            "intent_success": True,
            "confidence": 0.98,
            "meaning_summary_kr": "The player gave a short acknowledgement.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "slot_evidence": [
                {
                    "slot": "polite_response",
                    "value": "short_acknowledgement",
                    "confidence": 0.98,
                    "evidence_text": "Okay, you're on.",
                }
            ],
            "extracted_slots": {"polite_response": "short_acknowledgement"},
            "missing_slots": [],
            "needs_clarification": False,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text(
        "Okay, you're on.",
        _alpha_node_context("CH0_01_FLIGHT_SMALLTALK", "FLIGHT_A_001_SEATMATE_SMALLTALK"),
    )

    assert output.intent == "respond_to_seatmate_request"
    assert output.intent_success is False
    assert output.confidence < 0.9
    assert output.answer_relevance == "off_topic"
    assert output.extracted_slots == {}
    assert output.missing_slots == ["polite_response"]
    assert output.needs_clarification is True
    assert output.slot_evidence == []


def test_understanding_agent_rule_mode_recognizes_allowed_visit_purpose_values() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text("I'm here to visit my uncle.", _purpose_node_context())

    assert output.intent == "state_visit_purpose"
    assert output.intent_success is True
    assert output.extracted_slots == {"visit_purpose": "family_visit"}
    assert output.missing_slots == []


def test_understanding_agent_rule_mode_attaches_incivility_signal_without_branching() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text("fuck you", _purpose_node_context())

    assert output.incivility is not None
    assert output.incivility.tier == 3
    assert output.incivility.category == "profanity"
    assert output.incivility.source == "rule"
    assert output.intent_success is False
    assert output.missing_slots == ["visit_purpose"]
    assert agent.last_trace["output_summary"]["incivility"]["tier"] == 3


def test_understanding_agent_rule_mode_recognizes_stay_duration_values() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    cases = {
        "I will stay for 5 days.": "5 days",
        "I will stay for five days.": "five days",
        "I will stay one week.": "one week",
        "I will stay until Friday.": "until friday",
    }
    for player_text, stay_duration in cases.items():
        output = agent.analyze_player_text(player_text, _duration_node_context())

        assert output.intent == "state_stay_duration"
        assert output.intent_success is True
        assert output.extracted_slots == {"stay_duration": stay_duration}
        assert output.missing_slots == []


def test_understanding_agent_rule_mode_recognizes_alpha_flight_and_baggage_slot_values() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    cases = [
        (
            "CH0_01_FLIGHT_SMALLTALK",
            "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "Of course, please take it.",
            "polite_response",
            "offered_help",
        ),
        (
            "CH0_04_BAGGAGE_CLAIM",
            "BAG_002_PROVIDE_CLAIM_TAG",
            "I have the tag right here.",
            "claim_tag_status",
            "has_claim_tag",
        ),
        (
            "CH0_04_BAGGAGE_CLAIM",
            "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM",
            "It's red ginseng medicine for my health.",
            "customs_item_explanation",
            "medicine",
        ),
    ]
    for chapter_id, node_id, player_text, slot_name, slot_value in cases:
        output = agent.analyze_player_text(
            player_text,
            _alpha_node_context(chapter_id, node_id),
        )

        assert output.intent_success is True
        assert output.extracted_slots == {slot_name: slot_value}
        assert output.missing_slots == []


def test_understanding_agent_rule_mode_rejects_off_topic_idiom_for_flight_polite_response() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text(
        "Okay, you're on.",
        _alpha_node_context("CH0_01_FLIGHT_SMALLTALK", "FLIGHT_A_001_SEATMATE_SMALLTALK"),
    )

    assert output.intent == "respond_to_seatmate_request"
    assert output.intent_success is False
    assert output.confidence < 0.9
    assert output.answer_relevance == "off_topic"
    assert output.extracted_slots == {}
    assert output.missing_slots == ["polite_response"]
    assert output.needs_clarification is True
