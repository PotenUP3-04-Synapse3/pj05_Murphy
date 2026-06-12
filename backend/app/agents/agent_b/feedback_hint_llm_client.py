from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Protocol

import httpx


class FeedbackHintLLMClient(Protocol):
    model: str

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class FeedbackHintLLMUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAIFeedbackHintLLMClient:
    api_key: str
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 10.0
    endpoint: str = "https://api.openai.com/v1/responses"

    @classmethod
    def from_environment(cls, env_path: Path | None = None) -> "OpenAIFeedbackHintLLMClient":
        values = _read_env_file(env_path or Path(".env"))
        api_key = os.getenv("OPENAI_API_KEY") or values.get("OPENAI_API_KEY")
        if not api_key:
            raise FeedbackHintLLMUnavailable("OPENAI_API_KEY is not configured.")
        model = os.getenv("DEV_B_FEEDBACK_LLM_MODEL") or values.get(
            "DEV_B_FEEDBACK_LLM_MODEL",
            "gpt-4o-mini",
        )
        timeout = float(
            os.getenv("DEV_B_FEEDBACK_LLM_TIMEOUT_SECONDS")
            or values.get("DEV_B_FEEDBACK_LLM_TIMEOUT_SECONDS", "10")
        )
        return cls(api_key=api_key, model=model, timeout_seconds=timeout)

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
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
                        "name": "developer_b_feedback_hint_result",
                        "strict": True,
                        "schema": _feedback_schema(),
                    }
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return _extract_structured_json(response.json())


def _developer_instructions() -> str:
    return (
        "You are Developer B's English learning feedback and hint assistant for "
        "Murphy's Trippin. Return only JSON matching the schema. Generate short "
        "Korean feedback, a safe English example, and rubric score candidates. "
        "Do not generate NPC dialogue, npc_text, npc_utterance, final dialogue "
        "lines, TTS text, Unreal commands, branch, next_node_id, verdict, "
        "next_action, or state_delta. Do not soften real "
        "immigration risk. Keep feedback supportive and concise for Korean "
        "travel-English learners."
    )


def _feedback_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "hint_kr",
            "feedback_note",
            "report_summary",
            "report_improvement",
            "example_answer",
            "focus_on_form_explanation_kr",
            "rubric_scores",
        ],
        "properties": {
            "hint_kr": {"type": ["string", "null"], "maxLength": 180},
            "feedback_note": {"type": "string", "minLength": 1, "maxLength": 240},
            "report_summary": {"type": "string", "minLength": 1, "maxLength": 240},
            "report_improvement": {"type": "string", "minLength": 1, "maxLength": 300},
            "example_answer": {"type": "string", "minLength": 1, "maxLength": 180},
            "focus_on_form_explanation_kr": {"type": "string", "minLength": 1, "maxLength": 300},
            "rubric_scores": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "comprehension",
                    "fluency",
                    "grammar_accuracy",
                    "vocabulary_range",
                    "clarity",
                    "interaction_problem_solving",
                ],
                "properties": {
                    "comprehension": {"type": "integer", "minimum": 0, "maximum": 2},
                    "fluency": {"type": "integer", "minimum": 0, "maximum": 2},
                    "grammar_accuracy": {"type": "integer", "minimum": 0, "maximum": 2},
                    "vocabulary_range": {"type": "integer", "minimum": 0, "maximum": 2},
                    "clarity": {"type": "integer", "minimum": 0, "maximum": 2},
                    "interaction_problem_solving": {"type": "integer", "minimum": 0, "maximum": 2},
                },
            },
        },
    }


def _extract_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("output_text"), str):
        return json.loads(data["output_text"])
    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                return json.loads(str(content_item.get("text", "")))
    raise FeedbackHintLLMUnavailable("OpenAI response did not include output_text.")


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
