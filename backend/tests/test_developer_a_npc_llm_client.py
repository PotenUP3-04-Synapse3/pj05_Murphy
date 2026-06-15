# 테스트용 패키지 임포트


from backend.app.agents.agent_a.npc_llm_client import (
    NPCDialogueLLMUnavailable,
    build_npc_dialogue_llm_client_from_environment,
    OpenAICompatibleNPCDialogueChatModel,
)


def test_openai_compatible_npc_dialogue_client_calls_vllm_chat_completions(
    monkeypatch,
) -> None:
    from langchain_core.messages import AIMessage
    from backend.app.agents.agent_a.schemas import NPCDialogueLLMResult

    client = OpenAICompatibleNPCDialogueChatModel(
        api_key="dummy",
        model="google/gemma-4-26B-A4B-it",
        base_url="http://100.95.34.69:8001/v1",
    )

    from langchain_core.runnables import Runnable

    class FakeChatModel(Runnable):
        def invoke(self, input_payload, config=None):
            raw_msg = AIMessage(
                content="dummy",
                usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
            )
            parsed_obj = NPCDialogueLLMResult(
                speaker="Officer Miller",
                npc_text="Please answer clearly.",
                tts_text="Please answer clearly.",
                feedback_kr="짧고 분명하게 다시 말해보세요.",
                tone="formal_firm",
                animation="move",
                npc_emotion="normal",
                stability=0.5,
                style=0.5,
                speed=1.0,
                similarity_boost=0.5,
                llm_reason="retry branch needs clear answer"
            )
            return {"raw": raw_msg, "parsed": parsed_obj}

    monkeypatch.setattr(client, "_chat_model", FakeChatModel())

    result = client.generate({"fallback_candidate": {"speaker": "Officer Miller"}})



    assert result["npc_text"] == "Please answer clearly."
    assert result["__llm_usage"] == {
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
    }
    assert client.model == "google/gemma-4-26B-A4B-it"
    assert client.base_url == "http://100.95.34.69:8001/v1"


def test_fallback_npc_dialogue_client_uses_gemma4_after_primary_failure() -> None:
    from langchain_core.runnables import RunnableLambda

    def fail_invoke(*args, **kwargs):
        raise NPCDialogueLLMUnavailable("primary unavailable")
    primary = RunnableLambda(fail_invoke)

    def success_invoke(*args, **kwargs):
        return {
            "speaker": "Officer Miller",
            "npc_text": "Please answer clearly.",
            "tts_text": "Please answer clearly.",
            "feedback_kr": "짧고 분명하게 다시 말해보세요.",
            "tone": "formal_firm",
            "animation": "move",
            "llm_reason": "retry branch needs clear answer",
            "__fallback_model": "google/gemma-4-26B-A4B-it"
        }
    fallback = RunnableLambda(success_invoke)

    chain = primary.with_fallbacks([fallback], exceptions_to_handle=(Exception,))

    result = chain.invoke({"some": "input"})
    assert result["npc_text"] == "Please answer clearly."
    assert result["__fallback_model"] == "google/gemma-4-26B-A4B-it"


def test_npc_dialogue_llm_factory_uses_gemma4_fallback_when_openai_key_is_missing(
    tmp_path,
    monkeypatch,
) -> None:
    from langchain_core.runnables import Runnable

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







