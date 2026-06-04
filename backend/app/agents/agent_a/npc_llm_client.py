from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import json
import os

import httpx


class NPCDialogueLLMClient(Protocol):
    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class NPCDialogueLLMUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAINPCDialogueLLMClient:
    api_key: str
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 10.0
    endpoint: str = "https://api.openai.com/v1/responses"

    @classmethod
    def from_environment(cls, env_path: Path | None = None) -> "OpenAINPCDialogueLLMClient":
        """환경변수 또는 .env 파일에서 OpenAI 설정을 읽어 client를 만든다."""
        values = _read_env_file(env_path or Path(".env"))
        api_key = os.getenv("OPENAI_API_KEY") or values.get("OPENAI_API_KEY")
        if not api_key:
            raise NPCDialogueLLMUnavailable("OPENAI_API_KEY is not configured.")
        model = os.getenv("NPC_DIALOGUE_LLM_MODEL") or values.get(
            "NPC_DIALOGUE_LLM_MODEL",
            "gpt-4o-mini",
        )
        timeout = float(
            os.getenv("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS")
            or values.get("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS", "10")
        )
        return cls(api_key=api_key, model=model, timeout_seconds=timeout)

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """OpenAI Responses API로 Officer Miller 대사를 구조화 JSON으로 생성한다."""
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
                        "name": "npc_dialogue_result",
                        "strict": True,
                        "schema": _dialogue_schema(),
                    }
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return _extract_structured_json(data)


def _developer_instructions() -> str:
    return (
        "You are Developer A's NPC Dialogue Agent for Murphy's Trippin. "
        "Generate only JSON that matches the schema. Use the Level Design JSON, "
        "player language profile, NPC emotion state, and dialogue policy. "
        "Do not change branch, next_node_id, commands, validation, or scores. "
        "Officer Miller is a JFK immigration officer: concise, official, calm, "
        "not overly friendly, and suitable for a beginner Korean traveler. "
        "npc_text is the line displayed to the player. tts_text is a slightly "
        "more speakable version for Kokoro, using short pauses like '...' only "
        "where it improves natural timing. feedback_kr must be short Korean feedback."
    )


def _dialogue_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "speaker",
            "npc_text",
            "tts_text",
            "feedback_kr",
            "tone",
            "animation",
            "llm_reason",
        ],
        "properties": {
            "speaker": {"type": "string", "enum": ["Officer Miller"]},
            "npc_text": {"type": "string", "minLength": 1, "maxLength": 180},
            "tts_text": {"type": "string", "minLength": 1, "maxLength": 220},
            "feedback_kr": {"type": "string", "minLength": 1, "maxLength": 180},
            "tone": {
                "type": "string",
                "enum": ["formal_neutral", "formal_firm", "formal_supportive"],
            },
            "animation": {"type": "string"},
            "llm_reason": {"type": "string", "maxLength": 240},
        },
    }


def _extract_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("output_text"), str):
        return json.loads(data["output_text"])
    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                return json.loads(str(content_item.get("text", "")))
    raise NPCDialogueLLMUnavailable("OpenAI response did not include output_text.")


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
