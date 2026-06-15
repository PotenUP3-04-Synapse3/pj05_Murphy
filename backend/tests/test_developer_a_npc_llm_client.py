from langchain_core.runnables import Runnable

from backend.app.agents.agent_a.npc_llm_client import build_npc_dialogue_llm_client_from_environment


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

    assert isinstance(client, Runnable)
    assert hasattr(client, "fallbacks")
    assert len(client.fallbacks) == 1
