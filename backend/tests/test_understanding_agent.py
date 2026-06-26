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


def _flight_smalltalk_node_context():
    return _alpha_node_context("CH0_01_FLIGHT_SMALLTALK", "FLIGHT_A_001_SEATMATE_SMALLTALK")


def _baggage_customs_hold_node_context():
    return _alpha_node_context("CH0_04_BAGGAGE_CLAIM", "BAG_005_CUSTOMS_HOLD_EXPLANATION")


def test_understanding_agent_flight_hello_marks_open_social_obligation() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text("Hello?", _flight_smalltalk_node_context())

    assert output.intent_success is False
    assert output.needs_clarification is True
    assert output.social_context.scene_norm == "peer_smalltalk"
    assert output.social_context.conversation_move == "greeting_only"
    assert output.social_context.pending_social_obligation == "seatmate_pen_request"
    assert output.social_context.obligation_status == "open"
    assert output.social_context.recommended_npc_move == "acknowledge_and_retry_request"


def test_understanding_agent_customs_hold_hello_marks_open_procedural_obligation() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text("Hello.", _baggage_customs_hold_node_context())

    assert output.intent_success is False
    assert output.answer_relevance == "off_topic"
    assert output.social_context.scene_norm == "service_recovery"
    assert output.social_context.conversation_move == "greeting_only"
    assert output.social_context.pending_social_obligation == "check_suitcase_contents"
    assert output.social_context.obligation_status == "open"
    assert output.social_context.recommended_npc_move == "service_repair"


def test_understanding_agent_customs_hold_mixed_everyday_non_answer_marks_low_content() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text("Okay. Hello?", _baggage_customs_hold_node_context())

    assert output.intent_success is False
    assert output.answer_relevance == "off_topic"
    assert output.social_context.scene_norm == "service_recovery"
    assert output.social_context.conversation_move == "low_content_non_answer"
    assert output.social_context.pending_social_obligation == "check_suitcase_contents"
    assert output.social_context.obligation_status == "ignored"
    assert output.social_context.recommended_npc_move == "service_repair"


def test_understanding_agent_flight_what_marks_clarification_request() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text("What?", _flight_smalltalk_node_context())

    assert output.intent_success is False
    assert output.needs_clarification is True
    assert output.social_context.scene_norm == "peer_smalltalk"
    assert output.social_context.conversation_move == "clarification_request"
    assert output.social_context.pending_social_obligation == "seatmate_pen_request"
    assert output.social_context.obligation_status == "unclear"
    assert output.social_context.engagement_quality == "thin"
    assert output.social_context.recommended_npc_move == "clarify"


def test_understanding_agent_flight_fine_marks_low_content_non_answer() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text("Fine.", _flight_smalltalk_node_context())

    assert output.intent_success is False
    assert output.needs_clarification is True
    assert output.social_context.scene_norm == "peer_smalltalk"
    assert output.social_context.conversation_move == "low_content_non_answer"
    assert output.social_context.pending_social_obligation == "seatmate_pen_request"
    assert output.social_context.obligation_status == "ignored"
    assert output.social_context.engagement_quality == "thin"
    assert output.social_context.recommended_npc_move == "acknowledge_and_retry_request"


def test_understanding_agent_flight_self_disclosure_marks_social_duty() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text(
        "Yes, I'm going to a wedding, uh, my friend's wedding.",
        _flight_smalltalk_node_context(),
    )

    assert output.intent_success is True
    assert output.conversation_act.player_act == "self_disclosure"
    assert output.conversation_act.relation_to_previous == "extends_current_topic"
    assert output.conversation_act.npc_social_duty == "respond_to_disclosure_then_follow_up"
    assert output.conversation_act.natural_next_move == "specific_acknowledgement"
    assert output.conversation_act.topic_anchor == "wedding"
    assert output.conversation_act.should_avoid_generic_ack is True


def test_understanding_agent_flight_reciprocal_question_marks_answer_duty() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text("What about you?", _flight_smalltalk_node_context())

    assert output.intent_success is True
    assert output.conversation_act.player_act == "reciprocal_question"
    assert output.conversation_act.relation_to_previous == "asks_npc_same_question"
    assert output.conversation_act.npc_social_duty == "answer_briefly_then_continue"
    assert output.conversation_act.natural_next_move == "self_disclose_then_follow_up"
    assert output.conversation_act.should_answer_player_question is True
    assert output.conversation_act.should_avoid_generic_ack is True


def test_understanding_agent_flight_second_person_smalltalk_question_marks_answer_duty() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text("Do you travel often?", _flight_smalltalk_node_context())

    assert output.intent_success is True
    assert output.conversation_act.player_act == "reciprocal_question"
    assert output.conversation_act.npc_social_duty == "answer_briefly_then_continue"
    assert output.conversation_act.should_answer_player_question is True


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
            "slot_evidence": [
                {
                    "slot": "visit_purpose",
                    "value": "tourism",
                    "confidence": 0.91,
                    "evidence_text": "museums",
                }
            ],
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
    assert output.slot_evidence[0].evidence_text == "museums"
    assert llm_client.calls[0]["player_text"] == "I want to visit museums."
    assert llm_client.calls[0]["node_context"]["node_id"] == "IMM_002_PURPOSE"
    assert agent.last_trace["mode"] == "llm"
    assert agent.last_trace["fallback_used"] is False
    assert agent.last_trace["tool_calls"][0]["event"] == "tool_call"
    assert agent.last_trace["tool_calls"][0]["tool_name"] == "understanding_llm_client.analyze"
    assert agent.last_trace["tool_calls"][0]["status"] == "completed"
    assert agent.last_trace["tool_calls"][0]["output_summary"]["intent"] == "state_visit_purpose"
    assert agent.last_trace["postprocessing"]["generic_slot_evidence_applied"] is True
    assert agent.last_trace["postprocessing"]["accepted_slot_evidence"] == ["visit_purpose"]
    assert agent.last_trace["postprocessing"]["weak_required_slot_evidence"] is False


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
    assert agent.last_trace["tool_calls"][0]["error_details"] == {
        "error_type": "UnderstandingLLMUnavailable",
        "error_message": "Understanding LLM returned forbidden keys: next_node_id",
        "phase": "understanding_llm",
        "tool_name": "understanding_llm_client.analyze",
    }


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
    assert agent.last_trace["postprocessing"]["slot_repair_applied"] is True
    assert agent.last_trace["postprocessing"]["source"] == "rule_stay_duration_classifier"
    assert agent.last_trace["postprocessing"]["slot"] == "stay_duration"
    assert agent.last_trace["postprocessing"]["value"] == "5 days"
    assert agent.last_trace["postprocessing"]["reason"] == "llm_missing_allowed_slot"


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

    assert output.intent == "estimate_user_travel_speaking_level"
    assert output.intent_success is False
    assert output.confidence < 0.9
    assert output.answer_relevance == "off_topic"
    assert output.extracted_slots == {}
    assert output.missing_slots == []
    assert output.needs_clarification is False
    assert output.slot_evidence == []
    assert agent.last_trace["postprocessing"]["flight_smalltalk_diagnostic_slot_neutralized"] is True


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
            "CH0_03_IMMIGRATION_CHECK",
            "IMM_004_STAY_LOCATION",
            "I will stay at 123 Main Street in Queens.",
            "stay_location",
            "address",
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


def test_understanding_agent_rule_mode_recognizes_new_immigration_slot_values() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    cases = [
        (
            "IMM_003B_LONG_STAY_REASON",
            "I will study at an academy.",
            "long_stay_reason",
            "study",
        ),
        (
            "IMM_004B_HOTEL_RESERVATION",
            "I have a digital confirmation email.",
            "hotel_reservation_status",
            "has_digital_confirmation",
        ),
        (
            "IMM_004C_WHY_THIS_HOTEL",
            "I chose it because the price is cheap.",
            "hotel_choice_reason",
            "price",
        ),
        (
            "IMM_005B_TRAVEL_ITINERARY",
            "Yes, I have a travel itinerary and schedule.",
            "itinerary_status",
            "has_itinerary",
        ),
        (
            "IMM_008_FIRST_VISIT",
            "No, I have visited before.",
            "first_visit_status",
            "no_visited_before",
        ),
        (
            "IMM_009_OCCUPATION",
            "I'm a software engineer.",
            "occupation",
            "engineer",
        ),
        (
            "IMM_010_CASH",
            "I have 500 dollars in cash.",
            "cash_amount",
            "specific_amount",
        ),
        (
            "IMM_010B_WHO_PAID",
            "My parents paid for the trip.",
            "payment_source",
            "parents",
        ),
        (
            "IMM_011_DENIED_ENTRY",
            "No, I have never been denied entry.",
            "denied_entry_status",
            "never_denied",
        ),
    ]
    for node_id, player_text, slot_name, slot_value in cases:
        output = agent.analyze_player_text(
            player_text,
            _alpha_node_context("CH0_03_IMMIGRATION_CHECK", node_id),
        )

        assert output.intent_success is True
        assert output.extracted_slots == {slot_name: slot_value}
        assert output.missing_slots == []


def test_understanding_agent_llm_mode_builds_new_immigration_slot_from_evidence() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_occupation",
            "intent_success": True,
            "confidence": 0.9,
            "meaning_summary_kr": "The player said they are an engineer.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "slot_evidence": [
                {
                    "slot": "occupation",
                    "value": "engineer",
                    "confidence": 0.91,
                    "evidence_text": "software engineer",
                }
            ],
            "missing_slots": [],
            "needs_clarification": False,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text(
        "I'm a software engineer.",
        _alpha_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_009_OCCUPATION"),
    )

    assert output.intent_success is True
    assert output.extracted_slots == {"occupation": "engineer"}
    assert output.missing_slots == []
    assert output.slot_evidence[0].slot == "occupation"
    assert output.slot_evidence[0].value == "engineer"


def test_understanding_agent_llm_mode_upgrades_here_you_go_passport_handover() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "submit_passport",
            "intent_success": False,
            "confidence": 0.34,
            "meaning_summary_kr": "The player made a vague handover phrase.",
            "emotion": "calm",
            "answer_relevance": "partially_related",
            "ambiguity_type": "vague_reference",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "slot_evidence": [
                {
                    "slot": "passport_submission_status",
                    "value": "available",
                    "confidence": 0.72,
                    "evidence_text": "Here you go.",
                }
            ],
            "missing_slots": [],
            "needs_clarification": False,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text(
        "Hi. Here you go.",
        _alpha_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_001_PASSPORT"),
    )

    assert output.intent == "submit_passport"
    assert output.intent_success is True
    assert output.intent_satisfied is True
    assert output.confidence >= 0.9
    assert output.answer_relevance == "on_topic"
    assert output.extracted_slots == {"passport_submission_status": "submitted"}
    assert output.missing_slots == []
    assert output.needs_clarification is False
    assert agent.last_trace["postprocessing"]["passport_handover_repair_applied"] is True


def test_understanding_agent_passport_no_marks_explicit_submission_refusal() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text(
        "I answered the question. The answer is no.",
        _alpha_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_001_PASSPORT"),
    )

    assert output.intent == "submit_passport"
    assert output.intent_success is False
    assert output.intent_satisfied is False
    assert output.answer_relevance == "on_topic"
    assert output.needs_clarification is False
    assert output.missing_slots == []
    assert output.extracted_slots["refuse_submission"] == "true"
    assert "refuse_submission" in output.risk_tags
    assert output.social_context.scene_norm == "institutional_check"
    assert output.social_context.conversation_move == "refusal"
    assert output.social_context.pending_social_obligation == "answer_request_passport_submission"
    assert output.social_context.obligation_status == "addressed"
    assert output.social_context.recommended_npc_move == "firm_redirect"


def test_understanding_agent_rule_mode_marks_public_figure_threat_as_pragmatic_risk() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text(
        "I'm going to punch Trump in the face.",
        _purpose_node_context(),
    )

    assert output.intent_success is False
    assert output.intent_satisfied is False
    assert output.needs_clarification is False
    assert output.answer_relevance == "off_topic"
    assert output.risk_delta >= 70
    assert "violent_threat" in output.risk_tags
    assert "threat_to_public_figure" in output.risk_tags
    assert output.pragmatic_context.player_move == "violent_threat"
    assert output.pragmatic_context.target == "public_figure"
    assert output.pragmatic_context.procedural_posture == "secondary_inspection"
    assert output.social_context.recommended_npc_move == "firm_redirect"


def test_understanding_agent_llm_pragmatic_card_escalates_threat_risk() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_visit_purpose",
            "intent_success": False,
            "confidence": 0.82,
            "meaning_summary_kr": "The player threatened a public figure instead of answering the purpose.",
            "emotion": "angry",
            "answer_relevance": "off_topic",
            "ambiguity_type": "threatening_off_topic_response",
            "risk_delta": 0,
            "risk_reason": "The model did not assign numeric risk.",
            "risk_tags": [],
            "slot_evidence": [],
            "extracted_slots": {},
            "missing_slots": ["visit_purpose"],
            "needs_clarification": True,
            "intent_satisfied": False,
            "judgment_reason": "This does not answer the visit purpose question.",
            "pragmatic_context": {
                "player_move": "violent_threat",
                "target": "public_figure",
                "threat_directness": "explicit_intent",
                "risk_level": "critical",
                "procedural_posture": "secondary_inspection",
                "recommended_b_move": "secondary_inspection",
                "recommended_a_move": "stern_boundary",
                "confidence": 0.86,
                "evidence": "punch Trump in the face",
                "reason": "The utterance states intent to harm a public figure.",
            },
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text("I'm gonna punch Trump in the face.", _purpose_node_context())

    assert output.risk_delta >= 70
    assert "violent_threat" in output.risk_tags
    assert "threat_to_public_figure" in output.risk_tags
    assert output.needs_clarification is False
    assert output.pragmatic_context.player_move == "violent_threat"
    assert output.pragmatic_context.recommended_b_move == "secondary_inspection"


def test_understanding_agent_llm_pragmatic_card_escalates_work_purpose_risk() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_visit_purpose",
            "intent_success": False,
            "confidence": 0.87,
            "meaning_summary_kr": "The player says they are coming to work, which needs visa-status handling.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "visa_work_mismatch",
            "risk_delta": 2,
            "risk_reason": "The model treated this as weak risk before pragmatic review.",
            "risk_tags": [],
            "slot_evidence": [
                {
                    "slot": "illegal_work_intent",
                    "value": "possible",
                    "confidence": 0.88,
                    "evidence_text": "here to work",
                }
            ],
            "extracted_slots": {},
            "missing_slots": [],
            "needs_clarification": False,
            "intent_satisfied": False,
            "judgment_reason": "The statement may be a work-purpose visa mismatch, not a simple visit purpose.",
            "pragmatic_context": {
                "player_move": "visa_work_mismatch",
                "target": "officer",
                "threat_directness": "none",
                "risk_level": "high",
                "procedural_posture": "stop_normal_interview",
                "recommended_b_move": "warning",
                "recommended_a_move": "formal_boundary",
                "confidence": 0.88,
                "evidence": "I'm here to work.",
                "reason": "A traveler claiming they are here to work may need visa/work authorization verification.",
            },
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text("I'm here to work.", _purpose_node_context())

    assert output.intent_success is False
    assert output.intent_satisfied is False
    assert output.needs_clarification is False
    assert output.risk_delta >= 30
    assert "visa_work_mismatch" in output.risk_tags
    assert "illegal_work_intent" in output.risk_tags
    assert output.pragmatic_context.player_move == "visa_work_mismatch"
    assert output.pragmatic_context.recommended_b_move == "warning"
    assert agent.last_trace["postprocessing"]["pragmatic_context_source"] == "llm"


def test_understanding_agent_llm_mode_repairs_first_visit_prior_visit_phrase() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "confirm_first_visit",
            "intent_success": False,
            "confidence": 0.64,
            "meaning_summary_kr": "The player mentions prior visits but the slot was missed.",
            "emotion": "calm",
            "answer_relevance": "partially_related",
            "ambiguity_type": "unclear_confirmation",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "slot_evidence": [],
            "extracted_slots": {},
            "missing_slots": ["first_visit_status"],
            "needs_clarification": True,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text(
        "No, uh, it's actually my, uh... I've been here quite a long... quite a lot.",
        _alpha_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_008_FIRST_VISIT"),
    )

    assert output.intent == "confirm_first_visit"
    assert output.intent_success is True
    assert output.intent_satisfied is True
    assert output.confidence >= 0.9
    assert output.answer_relevance == "on_topic"
    assert output.extracted_slots == {"first_visit_status": "no_visited_before"}
    assert output.missing_slots == []
    assert output.needs_clarification is False
    assert agent.last_trace["postprocessing"]["first_visit_repair_applied"] is True


def test_understanding_agent_llm_mode_repairs_final_clearance_acknowledgement() -> None:
    cases = [
        ("Good. Thanks.", "thanked_officer"),
        ("Am I good to go right now? Am I good to go now?", "ready_for_baggage_claim"),
    ]
    for player_text, slot_value in cases:
        llm_client = FakeUnderstandingLLMClient(
            {
                "intent": "acknowledge_immigration_clearance",
                "intent_success": False,
                "confidence": 0.94,
                "meaning_summary_kr": "The player is responding to the clearance.",
                "emotion": "calm",
                "answer_relevance": "partially_related",
                "ambiguity_type": "unclear_confirmation",
                "risk_delta": 0,
                "risk_reason": "No risk expression was found.",
                "risk_tags": [],
                "slot_evidence": [],
                "extracted_slots": {},
                "missing_slots": ["immigration_transition_acknowledgement"],
                "needs_clarification": False,
            }
        )
        agent = UnderstandingAgent(
            settings=AppSettings(murphy_understanding_mode="llm"),
            llm_client=llm_client,
        )

        output = agent.analyze_player_text(
            player_text,
            _alpha_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_007_FINAL_DECISION"),
        )

        assert output.intent == "acknowledge_immigration_clearance"
        assert output.intent_success is True
        assert output.intent_satisfied is True
        assert output.confidence >= 0.9
        assert output.answer_relevance == "on_topic"
        assert output.extracted_slots == {
            "immigration_transition_acknowledgement": slot_value,
        }
        assert output.missing_slots == []
        assert output.needs_clarification is False
        assert agent.last_trace["postprocessing"]["final_clearance_ack_repair_applied"] is True


def test_understanding_agent_llm_mode_ignores_extracted_slot_without_evidence() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_occupation",
            "intent_success": True,
            "intent_satisfied": False,
            "confidence": 0.95,
            "meaning_summary_kr": "The player said they are an engineer.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "slot_evidence": [],
            "extracted_slots": {"occupation": "engineer"},
            "missing_slots": [],
            "needs_clarification": False,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text(
        "I like pizza.",
        _alpha_node_context("CH0_03_IMMIGRATION_CHECK", "IMM_009_OCCUPATION"),
    )

    assert output.intent_success is False
    assert output.extracted_slots == {}
    assert output.missing_slots == ["occupation"]
    assert output.needs_clarification is True
    assert output.confidence == 0.89


def test_understanding_agent_llm_mode_repairs_freeform_address_slot() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "state_stay_location",
            "intent_success": False,
            "confidence": 0.62,
            "meaning_summary_kr": "The stay location is unclear.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "unclear_location",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "extracted_slots": {},
            "missing_slots": ["stay_location"],
            "needs_clarification": True,
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text(
        "I will stay at 123 Main Street in Queens.",
        _location_node_context(),
    )

    assert output.intent == "state_stay_location"
    assert output.intent_success is True
    assert output.extracted_slots == {"stay_location": "address"}
    assert output.missing_slots == []
    assert agent.last_trace["postprocessing"]["slot_repair_applied"] is True
    assert agent.last_trace["postprocessing"]["slot"] == "stay_location"


def test_understanding_agent_rule_mode_keeps_flight_diagnostic_node_slot_neutral_but_successful() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text(
        "Sure, here you are.",
        _alpha_node_context("CH0_01_FLIGHT_SMALLTALK", "FLIGHT_A_001_SEATMATE_SMALLTALK"),
    )

    assert output.intent == "estimate_user_travel_speaking_level"
    assert output.intent_success is True
    assert output.intent_satisfied is True
    assert output.answer_relevance == "on_topic"
    assert output.extracted_slots == {}
    assert output.missing_slots == []
    assert output.needs_clarification is False


def test_understanding_agent_rule_mode_treats_flight_followup_as_free_smalltalk() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text(
        "Quite a long time. I'm gonna work here.",
        _alpha_node_context("CH0_01_FLIGHT_SMALLTALK", "FLIGHT_A_001_SEATMATE_SMALLTALK"),
    )

    assert output.intent == "estimate_user_travel_speaking_level"
    assert output.intent_success is True
    assert output.intent_satisfied is True
    assert output.confidence >= 0.7
    assert output.answer_relevance == "on_topic"
    assert output.extracted_slots == {}
    assert output.missing_slots == []
    assert output.needs_clarification is False


def test_understanding_agent_llm_mode_repairs_flight_followup_as_free_smalltalk() -> None:
    llm_client = FakeUnderstandingLLMClient(
        {
            "intent": "estimate_user_travel_speaking_level",
            "intent_success": False,
            "confidence": 0.17,
            "meaning_summary_kr": "The answer does not respond to the old pen request.",
            "emotion": "calm",
            "answer_relevance": "off_topic",
            "ambiguity_type": "off_topic_response",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "slot_evidence": [],
            "extracted_slots": {},
            "missing_slots": [],
            "needs_clarification": False,
            "intent_satisfied": False,
            "judgment_reason": "Judged against legacy pen request.",
        }
    )
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )

    output = agent.analyze_player_text(
        "Quite a long time. I'm gonna work here.",
        _alpha_node_context("CH0_01_FLIGHT_SMALLTALK", "FLIGHT_A_001_SEATMATE_SMALLTALK"),
    )

    assert output.intent == "estimate_user_travel_speaking_level"
    assert output.intent_success is True
    assert output.intent_satisfied is True
    assert output.confidence >= 0.7
    assert output.answer_relevance == "on_topic"
    assert output.extracted_slots == {}
    assert output.missing_slots == []
    assert output.needs_clarification is False
    assert agent.last_trace["postprocessing"]["flight_smalltalk_free_response_applied"] is True


def test_understanding_agent_rule_mode_rejects_off_topic_idiom_for_flight_diagnostic_node() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text(
        "Okay, you're on.",
        _alpha_node_context("CH0_01_FLIGHT_SMALLTALK", "FLIGHT_A_001_SEATMATE_SMALLTALK"),
    )

    assert output.intent == "estimate_user_travel_speaking_level"
    assert output.intent_success is False
    assert output.confidence < 0.9
    assert output.answer_relevance == "off_topic"
    assert output.extracted_slots == {}
    assert output.missing_slots == []
    assert output.needs_clarification is False


def test_understanding_agent_rule_mode_accepts_travel_detail_in_flight_diagnostic_node() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    output = agent.analyze_player_text(
        "I am traveling alone.",
        _alpha_node_context("CH0_01_FLIGHT_SMALLTALK", "FLIGHT_A_001_SEATMATE_SMALLTALK"),
    )

    assert output.intent == "estimate_user_travel_speaking_level"
    assert output.intent_success is True
    assert output.answer_relevance == "on_topic"
    assert output.extracted_slots == {}
    assert output.missing_slots == []
    assert output.needs_clarification is False


def test_understanding_agent_rule_mode_recognizes_hotel_brands() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    for brand in ["Grand Hyatt", "Hilton", "Marriott", "Sheraton", "Holiday Inn", "Westin", "hostel"]:
        output = agent.analyze_player_text(
            f"I will stay at the {brand}.",
            _location_node_context(),
        )
        assert output.intent == "state_stay_location"
        assert output.intent_success is True
        assert output.extracted_slots == {"stay_location": "hotel"}


def test_understanding_agent_rule_mode_rejects_meta_talk_stay_location() -> None:
    agent = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))

    for phrase in ["I said hotel", "I told you hotel", "already told you hotel", "as I said hotel"]:
        output = agent.analyze_player_text(
            phrase,
            _location_node_context(),
        )
        # Should detect mismatch/off-topic due to ALPHA_SLOT_OFF_TOPIC_PHRASES stay_location
        assert output.intent_success is False
        assert output.confidence < 0.9 or output.answer_relevance == "off_topic"

