import json
from typing import Any

import httpx
import pytest

from backend.app.agents.agent_c.understanding_llm_client import (
    FallbackUnderstandingLLMClient,
    OpenAICompatibleUnderstandingLLMClient,
    OpenAIUnderstandingLLMClient,
    UnderstandingLLMUnavailable,
    _extract_chat_completion_structured_json,
    _extract_structured_json,
    _understanding_schema,
)


def test_understanding_schema_is_openai_strict_compatible() -> None:
    schema = _understanding_schema()

    _assert_strict_object_schema(schema)
    extracted_slots = schema["properties"]["extracted_slots"]
    assert extracted_slots["additionalProperties"] is False
    assert extracted_slots["required"] == ["visit_purpose", "stay_duration"]
    assert extracted_slots["properties"]["visit_purpose"]["type"] == ["string", "null"]
    assert extracted_slots["properties"]["stay_duration"]["type"] == ["string", "null"]
    slot_evidence = schema["properties"]["slot_evidence"]
    assert slot_evidence["type"] == "array"
    assert slot_evidence["items"]["required"] == [
        "slot",
        "value",
        "confidence",
        "evidence_text",
    ]


def test_extract_structured_json_drops_null_optional_slot_values() -> None:
    result = _extract_structured_json(
        {
            "output_text": json.dumps(
                {
                    "intent": "unknown",
                    "intent_success": False,
                    "confidence": 0.55,
                    "meaning_summary_kr": "방문 목적이 불명확합니다.",
                    "emotion": "nervous",
                    "answer_relevance": "partially_related",
                    "ambiguity_type": "unclear_purpose",
                    "risk_delta": 0,
                    "risk_reason": "No risk expression was found.",
                    "risk_tags": [],
                    "extracted_slots": {"visit_purpose": None, "stay_duration": None},
                    "missing_slots": ["visit_purpose"],
                    "needs_clarification": True,
                },
                ensure_ascii=False,
            )
        }
    )

    assert result["extracted_slots"] == {}


def test_extract_structured_json_builds_slots_from_generic_evidence() -> None:
    result = _extract_structured_json(
        {
            "output_text": json.dumps(
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
                            "slot": "",
                            "value": "ignored",
                            "confidence": 0.4,
                            "evidence_text": "ignored",
                        },
                    ],
                    "extracted_slots": {},
                    "missing_slots": ["stay_location"],
                    "needs_clarification": True,
                },
                ensure_ascii=False,
            )
        }
    )

    assert result["slot_evidence"] == [
        {
            "slot": "stay_location",
            "value": "hotel",
            "confidence": 0.9,
            "evidence_text": "hotel",
        }
    ]
    assert result["extracted_slots"] == {"stay_location": "hotel"}


def test_extract_structured_json_preserves_llm_usage() -> None:
    result = _extract_structured_json(
        {
            "output_text": json.dumps(
                {
                    "intent": "state_visit_purpose",
                    "intent_success": True,
                    "confidence": 0.91,
                    "meaning_summary_kr": "방문 목적을 말했다.",
                    "emotion": "calm",
                    "answer_relevance": "on_topic",
                    "ambiguity_type": "none",
                    "risk_delta": 0,
                    "risk_reason": "No risk expression was found.",
                    "risk_tags": [],
                    "extracted_slots": {"visit_purpose": "family_visit"},
                    "missing_slots": [],
                    "needs_clarification": False,
                },
                ensure_ascii=False,
            ),
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500,
            },
        }
    )

    assert result["__llm_usage"] == {
        "input_tokens": 1000,
        "output_tokens": 500,
        "total_tokens": 1500,
    }


def test_extract_chat_completion_structured_json_preserves_usage() -> None:
    result = _extract_chat_completion_structured_json(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "intent": "state_visit_purpose",
                                "intent_success": True,
                                "confidence": 0.91,
                                "meaning_summary_kr": "방문 목적을 말했다.",
                                "emotion": "calm",
                                "answer_relevance": "on_topic",
                                "ambiguity_type": "none",
                                "risk_delta": 0,
                                "risk_reason": "No risk expression was found.",
                                "risk_tags": [],
                                "extracted_slots": {"visit_purpose": "tourism"},
                                "missing_slots": [],
                                "needs_clarification": False,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        }
    )

    assert result["extracted_slots"] == {"visit_purpose": "tourism"}
    assert result["__llm_usage"] == {
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
    }


def test_openai_understanding_client_includes_responses_api_error_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": "invalid_json_schema",
                    "message": "Invalid schema for response_format 'developer_c_understanding_result'",
                }
            },
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = OpenAIUnderstandingLLMClient(api_key="test-api-key")

    with pytest.raises(UnderstandingLLMUnavailable, match="invalid_json_schema.*Invalid schema"):
        client.analyze({"player_text": "I'm here to visit my uncle."})


def test_openai_compatible_understanding_client_calls_vllm_chat_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
        calls.append({"args": args, "kwargs": kwargs})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "state_visit_purpose",
                                    "intent_success": True,
                                    "confidence": 0.91,
                                    "meaning_summary_kr": "방문 목적을 말했다.",
                                    "emotion": "calm",
                                    "answer_relevance": "on_topic",
                                    "ambiguity_type": "none",
                                    "risk_delta": 0,
                                    "risk_reason": "No risk expression was found.",
                                    "risk_tags": [],
                                    "extracted_slots": {"visit_purpose": "tourism"},
                                    "missing_slots": [],
                                    "needs_clarification": False,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            },
            request=httpx.Request("POST", "http://100.95.34.69:8001/v1/chat/completions"),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = OpenAICompatibleUnderstandingLLMClient(
        api_key="dummy",
        model="google/gemma-4-26B-A4B-it",
        base_url="http://100.95.34.69:8001/v1",
    )

    result = client.analyze({"player_text": "I'm here for tourism."})

    assert result["intent"] == "state_visit_purpose"
    assert calls[0]["args"][0] == "http://100.95.34.69:8001/v1/chat/completions"
    assert calls[0]["kwargs"]["headers"]["Authorization"] == "Bearer dummy"
    assert calls[0]["kwargs"]["json"]["model"] == "google/gemma-4-26B-A4B-it"


class _UnavailableUnderstandingClient:
    model = "primary"

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise UnderstandingLLMUnavailable("primary unavailable")


class _SuccessfulUnderstandingClient:
    model = "google/gemma-4-26B-A4B-it"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {
            "intent": "state_visit_purpose",
            "intent_success": True,
            "confidence": 0.91,
            "meaning_summary_kr": "방문 목적을 말했다.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "extracted_slots": {"visit_purpose": "tourism"},
            "missing_slots": [],
            "needs_clarification": False,
            "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }


def test_fallback_understanding_client_uses_gemma4_after_primary_failure() -> None:
    fallback = _SuccessfulUnderstandingClient()
    client = FallbackUnderstandingLLMClient(
        primary=_UnavailableUnderstandingClient(),
        fallback=fallback,
    )

    result = client.analyze({"player_text": "I'm here for tourism."})

    assert result["intent"] == "state_visit_purpose"
    assert result["__fallback_model"] == "google/gemma-4-26B-A4B-it"
    assert fallback.calls == [{"player_text": "I'm here for tourism."}]


def _assert_strict_object_schema(schema: dict[str, Any]) -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties", {})
        assert schema.get("additionalProperties") is False
        assert set(schema.get("required", [])) == set(properties)
        for property_schema in properties.values():
            if isinstance(property_schema, dict):
                _assert_strict_object_schema(property_schema)

    if schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            _assert_strict_object_schema(items)
