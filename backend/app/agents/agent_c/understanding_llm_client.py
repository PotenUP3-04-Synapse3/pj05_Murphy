from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
import json

import httpx

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
        except httpx.HTTPError as exc:
            raise UnderstandingLLMUnavailable("Understanding LLM request failed.") from exc
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
            "intent": {"type": "string", "minLength": 1, "maxLength": 80},
            "intent_success": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "meaning_summary_kr": {"type": "string", "minLength": 1, "maxLength": 240},
            "emotion": {"type": "string", "minLength": 1, "maxLength": 80},
            "answer_relevance": {
                "type": "string",
                "enum": ["on_topic", "partially_related", "off_topic"],
            },
            "ambiguity_type": {"type": "string", "minLength": 1, "maxLength": 80},
            "risk_delta": {"type": "integer", "minimum": -100, "maximum": 100},
            "risk_reason": {"type": "string", "minLength": 1, "maxLength": 240},
            "risk_tags": {"type": "array", "items": {"type": "string"}},
            "extracted_slots": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
            "missing_slots": {"type": "array", "items": {"type": "string"}},
            "needs_clarification": {"type": "boolean"},
        },
    }


def _extract_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("output_text"), str):
        return json.loads(data["output_text"])
    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                return json.loads(str(content_item.get("text", "")))
    raise UnderstandingLLMUnavailable("OpenAI response did not include output_text.")
