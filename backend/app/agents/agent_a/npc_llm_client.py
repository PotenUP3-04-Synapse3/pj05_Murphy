from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import json
import os

import httpx


class NPCDialogueLLMClient(Protocol):
    @property
    def model(self) -> str:
        ...

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class NPCDialogueLLMUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class _UnavailableNPCDialogueLLMClient:
    reason: str
    model: str = "openai_unavailable"

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NPCDialogueLLMUnavailable(self.reason)


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
        """OpenAI Responses API로 NPC 대사를 구조화 JSON으로 생성한다."""
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


@dataclass(frozen=True)
class OpenAICompatibleNPCDialogueLLMClient:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 10.0

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """vLLM처럼 OpenAI chat/completions 호환 서버에서 NPC 대사를 생성한다."""
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _developer_instructions()},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "temperature": 0.2,
                "max_tokens": 500,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return _extract_chat_completion_structured_json(data)


@dataclass(frozen=True)
class FallbackNPCDialogueLLMClient:
    primary: NPCDialogueLLMClient
    fallback: NPCDialogueLLMClient

    @property
    def model(self) -> str:
        return self.primary.model

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.primary.generate(payload)
        except (NPCDialogueLLMUnavailable, httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError):
            result = self.fallback.generate(payload)
            result["__fallback_model"] = self.fallback.model
            return result


def build_npc_dialogue_llm_client_from_environment(
    env_path: Path | None = None,
) -> NPCDialogueLLMClient:
    values = _read_env_file(env_path or Path(".env"))
    provider = (
        os.getenv("NPC_DIALOGUE_LLM_PROVIDER")
        or values.get("NPC_DIALOGUE_LLM_PROVIDER")
        or "openai"
    ).strip().lower()
    if provider != "openai":
        raise NPCDialogueLLMUnavailable(f"Unsupported NPC_DIALOGUE_LLM_PROVIDER: {provider}")

    fallback_name = (
        os.getenv("NPC_DIALOGUE_LLM_FALLBACK")
        or values.get("NPC_DIALOGUE_LLM_FALLBACK")
        or "none"
    ).strip().lower()
    fallback = _build_gemma4_vllm_client(values) if fallback_name == "gemma4_vllm" else None

    try:
        primary = OpenAINPCDialogueLLMClient.from_environment(env_path)
    except NPCDialogueLLMUnavailable as exc:
        if fallback is not None:
            return FallbackNPCDialogueLLMClient(
                primary=_UnavailableNPCDialogueLLMClient(reason=str(exc)),
                fallback=fallback,
            )
        raise

    if fallback is not None:
        return FallbackNPCDialogueLLMClient(primary=primary, fallback=fallback)
    return primary


def _build_gemma4_vllm_client(values: dict[str, str]) -> OpenAICompatibleNPCDialogueLLMClient:
    timeout = float(
        os.getenv("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS")
        or values.get("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS", "10")
    )
    return OpenAICompatibleNPCDialogueLLMClient(
        api_key=os.getenv("GEMMA4_VLLM_API_KEY") or values.get("GEMMA4_VLLM_API_KEY", "dummy"),
        model=(
            os.getenv("GEMMA4_VLLM_MODEL")
            or values.get("GEMMA4_VLLM_MODEL", "google/gemma-4-26B-A4B-it")
        ),
        base_url=(
            os.getenv("GEMMA4_VLLM_BASE_URL")
            or values.get("GEMMA4_VLLM_BASE_URL", "http://100.95.34.69:8001/v1")
        ),
        timeout_seconds=timeout,
    )


def _developer_instructions() -> str:
    return (
        "You are Developer A's NPC Dialogue Agent for Murphy's Trippin. "
        "Generate only JSON that matches the schema. Use the Level Design JSON, "
        "player language profile, NPC emotion state, and dialogue policy. "
        "Do not change branch, next_node_id, commands, validation, or scores. "
        "Use fallback_candidate.speaker as the NPC speaker and keep the NPC concise, "
        "official, calm, not overly friendly, and suitable for a beginner Korean traveler. "
        "Use fallback_candidate.animation unless the caller later overrides it from the NPC roster. "
        "npc_text and tts_text must be English-only ASCII NPC dialogue. Do not put Korean, "
        "mojibake, translation notes, or mixed-language text in npc_text or tts_text. "
        "npc_text is the line displayed to the player. tts_text is a slightly "
        "more speakable version for Kokoro, using short pauses like '...' only "
        "where it improves natural timing. feedback_kr is the only field that may contain Korean, "
        "and it must be short Korean feedback."
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
            "speaker": {"type": "string", "minLength": 1, "maxLength": 80},
            "npc_text": {"type": "string", "minLength": 1, "maxLength": 180},
            "tts_text": {"type": "string", "minLength": 1, "maxLength": 220},
            "feedback_kr": {"type": "string", "minLength": 1, "maxLength": 180},
            "tone": {
                "type": "string",
                "enum": [
                    "formal_neutral",
                    "formal_firm",
                    "formal_stern",
                    "formal_warning",
                    "formal_supportive",
                ],
            },
            "animation": {"type": "string"},
            "llm_reason": {"type": "string", "maxLength": 240},
        },
    }


def _extract_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("output_text"), str):
        result = json.loads(data["output_text"])
        result["__llm_usage"] = _extract_usage(data)
        return result
    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                result = json.loads(str(content_item.get("text", "")))
                result["__llm_usage"] = _extract_usage(data)
                return result
    raise NPCDialogueLLMUnavailable("OpenAI response did not include output_text.")


def _extract_chat_completion_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices")
    if not isinstance(choices, list):
        raise NPCDialogueLLMUnavailable("OpenAI-compatible response did not include choices.")
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        text = str(message.get("content") or "").strip()
        if text:
            result = json.loads(_strip_json_fence(text))
            result["__llm_usage"] = _extract_chat_completion_usage(data)
            return result
    raise NPCDialogueLLMUnavailable(
        "OpenAI-compatible response did not include message content."
    )


def _strip_json_fence(text: str) -> str:
    if text.startswith("```json"):
        return text.removeprefix("```json").removesuffix("```").strip()
    if text.startswith("```"):
        return text.removeprefix("```").removesuffix("```").strip()
    return text


def _extract_usage(data: dict[str, Any]) -> dict[str, int]:
    # OpenAI usage 필드는 응답 형식에 따라 없을 수 있으므로 0으로 안전하게 보정한다.
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    input_tokens = _int_value(usage.get("input_tokens"))
    output_tokens = _int_value(usage.get("output_tokens"))
    total_tokens = _int_value(usage.get("total_tokens")) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _extract_chat_completion_usage(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    input_tokens = _int_value(usage.get("prompt_tokens"))
    output_tokens = _int_value(usage.get("completion_tokens"))
    total_tokens = _int_value(usage.get("total_tokens")) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _int_value(value: Any) -> int:
    return value if isinstance(value, int) else 0


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
