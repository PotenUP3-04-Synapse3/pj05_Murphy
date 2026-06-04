from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
import json

import httpx

from backend.app.agents.agent_c.visit_purpose_classifier import VISIT_PURPOSE_VALUES
from backend.app.services.service_c.settings_service import AppSettings, get_settings


class UnderstandingLLMClient(Protocol):
    @property
    def model(self) -> str:
        ...

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class UnderstandingLLMUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAIUnderstandingLLMClient:
    api_key: str
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 10.0
    endpoint: str = "https://api.openai.com/v1/responses"

    @classmethod
    def from_settings(cls, settings: AppSettings | None = None) -> "OpenAIUnderstandingLLMClient":
        resolved_settings = settings or get_settings()
        if not resolved_settings.openai_api_key:
            raise UnderstandingLLMUnavailable("OPENAI_API_KEY is not configured.")
        return cls(
            api_key=resolved_settings.openai_api_key,
            model=resolved_settings.murphy_understanding_llm_model,
            timeout_seconds=resolved_settings.murphy_understanding_llm_timeout_seconds,
        )

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": _developer_instructions(),
                    "input": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": json.dumps(payload, ensure_ascii=False),
                                }
                            ],
                        }
                    ],
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "developer_c_understanding_result",
                            "strict": True,
                            "schema": _understanding_schema(),
                        }
                    },
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise UnderstandingLLMUnavailable(
                f"Understanding LLM request failed: {_http_status_error_detail(exc)}"
            ) from exc
        except httpx.HTTPError as exc:
            raise UnderstandingLLMUnavailable(f"Understanding LLM request failed: {exc}") from exc
        except ValueError as exc:
            raise UnderstandingLLMUnavailable("Understanding LLM returned non-JSON response.") from exc

        return _extract_structured_json(data)


def _developer_instructions() -> str:
    return (
        "You are Developer C's Understanding Agent for Murphy's Trippin. "
        "Return only JSON matching the schema. Produce semantic evidence from "
        "the player_text and node_context for Developer B to evaluate. Do not "
        "generate branch, next_node_id, next_action, verdict, scores, hints, "
        "NPC dialogue, TTS text, Unreal commands, or state_delta. Treat "
        "immigration risk expressions seriously and keep the Korean meaning "
        "summary concise."
        " For extracted_slots.visit_purpose, use one of "
        f"{', '.join(VISIT_PURPOSE_VALUES)} when the purpose is clear, or null "
        "when the visit purpose is missing."
    )


def _understanding_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "intent",
            "intent_success",
            "confidence",
            "meaning_summary_kr",
            "emotion",
            "answer_relevance",
            "ambiguity_type",
            "risk_delta",
            "risk_reason",
            "risk_tags",
            "extracted_slots",
            "missing_slots",
            "needs_clarification",
        ],
        "properties": {
            "intent": {"type": "string"},
            "intent_success": {"type": "boolean"},
            "confidence": {"type": "number"},
            "meaning_summary_kr": {"type": "string"},
            "emotion": {"type": "string"},
            "answer_relevance": {
                "type": "string",
                "enum": ["on_topic", "partially_related", "off_topic"],
            },
            "ambiguity_type": {"type": "string"},
            "risk_delta": {"type": "integer"},
            "risk_reason": {"type": "string"},
            "risk_tags": {"type": "array", "items": {"type": "string"}},
            "extracted_slots": {
                "type": "object",
                "additionalProperties": False,
                "required": ["visit_purpose"],
                "properties": {
                    "visit_purpose": {
                        "type": ["string", "null"],
                        "enum": [*VISIT_PURPOSE_VALUES, None],
                    }
                },
            },
            "missing_slots": {"type": "array", "items": {"type": "string"}},
            "needs_clarification": {"type": "boolean"},
        },
    }


def _extract_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("output_text"), str):
        result = _normalize_structured_result(json.loads(data["output_text"]))
        result["__llm_usage"] = _extract_usage(data)
        return result
    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                result = _normalize_structured_result(json.loads(str(content_item.get("text", ""))))
                result["__llm_usage"] = _extract_usage(data)
                return result
    raise UnderstandingLLMUnavailable("OpenAI response did not include output_text.")


def _normalize_structured_result(result: dict[str, Any]) -> dict[str, Any]:
    extracted_slots = result.get("extracted_slots")
    if isinstance(extracted_slots, dict):
        result["extracted_slots"] = {
            str(key): str(value)
            for key, value in extracted_slots.items()
            if value is not None
        }
    else:
        result["extracted_slots"] = {}
    return result


def _http_status_error_detail(exc: httpx.HTTPStatusError) -> str:
    response = exc.response
    try:
        payload = response.json()
    except ValueError:
        return f"status={response.status_code} body={response.text[:500]}"

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        code = error.get("code") or error.get("type") or "unknown"
        message = error.get("message") or response.text[:500]
        return f"status={response.status_code} code={code} message={message}"
    return f"status={response.status_code} body={response.text[:500]}"


def _extract_usage(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    input_tokens = _int_or_zero(usage.get("input_tokens"))
    output_tokens = _int_or_zero(usage.get("output_tokens"))
    total_tokens = _int_or_zero(usage.get("total_tokens")) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _int_or_zero(value: Any) -> int:
    return value if isinstance(value, int) else 0
