import json
from typing import Any

import httpx

from backend.app.agents.agent_a.npc_llm_client import (
    FallbackNPCDialogueLLMClient,
    NPCDialogueLLMUnavailable,
    OpenAICompatibleNPCDialogueLLMClient,
    build_npc_dialogue_llm_client_from_environment,
)


def test_openai_compatible_npc_dialogue_client_calls_vllm_chat_completions(
    monkeypatch,
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
                                    "speaker": "Officer Miller",
                                    "npc_text": "Please answer clearly.",
                                    "tts_text": "Please answer clearly.",
                                    "feedback_kr": "짧고 분명하게 다시 말해보세요.",
                                    "tone": "formal_firm",
                                    "animation": "officer_check_passport",
                                    "llm_reason": "retry branch needs clear answer",
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
    client = OpenAICompatibleNPCDialogueLLMClient(
        api_key="dummy",
        model="google/gemma-4-26B-A4B-it",
        base_url="http://100.95.34.69:8001/v1",
    )

    result = client.generate({"fallback_candidate": {"speaker": "Officer Miller"}})

    assert result["npc_text"] == "Please answer clearly."
    assert result["__llm_usage"] == {
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
    }
    assert calls[0]["args"][0] == "http://100.95.34.69:8001/v1/chat/completions"
    assert calls[0]["kwargs"]["headers"]["Authorization"] == "Bearer dummy"
    assert calls[0]["kwargs"]["json"]["model"] == "google/gemma-4-26B-A4B-it"


class _UnavailableNPCDialogueClient:
    model = "primary"

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NPCDialogueLLMUnavailable("primary unavailable")


class _SuccessfulNPCDialogueClient:
    model = "google/gemma-4-26B-A4B-it"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {
            "speaker": "Officer Miller",
            "npc_text": "Please answer clearly.",
            "tts_text": "Please answer clearly.",
            "feedback_kr": "짧고 분명하게 다시 말해보세요.",
            "tone": "formal_firm",
            "animation": "officer_check_passport",
            "llm_reason": "retry branch needs clear answer",
            "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }


def test_fallback_npc_dialogue_client_uses_gemma4_after_primary_failure() -> None:
    fallback = _SuccessfulNPCDialogueClient()
    client = FallbackNPCDialogueLLMClient(
        primary=_UnavailableNPCDialogueClient(),
        fallback=fallback,
    )

    result = client.generate({"fallback_candidate": {"speaker": "Officer Miller"}})

    assert result["npc_text"] == "Please answer clearly."
    assert result["__fallback_model"] == "google/gemma-4-26B-A4B-it"
    assert fallback.calls == [{"fallback_candidate": {"speaker": "Officer Miller"}}]


def test_npc_dialogue_llm_factory_uses_gemma4_fallback_when_openai_key_is_missing(
    tmp_path,
    monkeypatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "NPC_DIALOGUE_LLM_PROVIDER=openai",
                "NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm",
                "GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1",
                "GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it",
                "GEMMA4_VLLM_API_KEY=dummy",
                "NPC_DIALOGUE_LLM_TIMEOUT_SECONDS=12",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NPC_DIALOGUE_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("NPC_DIALOGUE_LLM_FALLBACK", raising=False)
    monkeypatch.delenv("GEMMA4_VLLM_BASE_URL", raising=False)
    monkeypatch.delenv("GEMMA4_VLLM_MODEL", raising=False)
    monkeypatch.delenv("GEMMA4_VLLM_API_KEY", raising=False)
    monkeypatch.delenv("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS", raising=False)

    client = build_npc_dialogue_llm_client_from_environment(env_file)

    assert isinstance(client, FallbackNPCDialogueLLMClient)
    assert isinstance(client.fallback, OpenAICompatibleNPCDialogueLLMClient)
    assert client.fallback.api_key == "dummy"
    assert client.fallback.model == "google/gemma-4-26B-A4B-it"
    assert client.fallback.base_url == "http://100.95.34.69:8001/v1"
    assert client.fallback.timeout_seconds == 12
