from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import json
import os

import httpx


from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from pydantic import SecretStr
from backend.app.agents.agent_a.schemas import NPCDialogueLLMResult


class NPCDialogueCallbackHandler(BaseCallbackHandler):
    def __init__(
        self,
        middleware: Any = None,
        recorder: Any = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        self.recorder = recorder or middleware
        self.metadata = metadata

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """LLM 호출이 시작될 때 실행되며, 기존 기록기/미들웨어가 제공될 경우 이벤트를 연동 기록합니다."""
        if self.recorder and self.metadata:
            self.recorder.record_event(
                self.metadata,
                event="langchain_llm_start",
                status="started",
                input_summary={"prompts_count": len(prompts)},
            )

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """LLM 호출이 성공적으로 완료될 때 실행되며, 기존 기록기/미들웨어가 제공될 경우 이벤트를 연동 기록합니다."""
        if self.recorder and self.metadata:
            self.recorder.record_event(
                self.metadata,
                event="langchain_llm_end",
                status="completed",
                output_summary={"generations_count": len(response.generations) if response else 0},
            )

    def on_chain_start(self, serialized: dict[str, Any], inputs: dict[str, Any], **kwargs: Any) -> None:
        """LCEL 체인 실행이 시작될 때 실행됩니다."""
        if self.recorder and self.metadata:
            self.recorder.record_event(
                self.metadata,
                event="langchain_chain_start",
                status="started",
                input_summary={"inputs_keys": list(inputs.keys())},
            )

    def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any) -> None:
        """LCEL 체인 실행이 정상적으로 완료될 때 실행됩니다."""
        if self.recorder and self.metadata:
            self.recorder.record_event(
                self.metadata,
                event="langchain_chain_end",
                status="completed",
                output_summary={"outputs_keys": list(outputs.keys()) if isinstance(outputs, dict) else []},
            )



# NPC 대사 생성을 위한 LLM 클라이언트(LLM Client)의 규격을 정의하는 프로토콜(Protocol) 클래스(Class)입니다.
class NPCDialogueLLMClient(Protocol):
    @property
    def model(self) -> str:
        """현재 클라이언트가 사용하는 LLM 모델명(Model Name)을 반환하는 속성(Property)입니다."""
        ...

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """주어진 입력 데이터(Payload)를 바탕으로 구조화된 NPC 대사 사전(Dictionary)을 생성합니다."""
        ...


# LLM 서비스에 연결할 수 없거나 설정 오류가 발생했을 때 발생하는 예외(Exception) 클래스(Class)입니다.
class NPCDialogueLLMUnavailable(RuntimeError):
    pass


# LLM 서비스 비활성화 상태에서 예외를 던지기 위한 더미(Dummy) 클라이언트 클래스(Class)입니다.
@dataclass(frozen=True)
class _UnavailableNPCDialogueLLMClient:
    reason: str
    model: str = "openai_unavailable"

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 사용 가능한 LLM 클라이언트가 없으므로 설정 오류 메시지와 함께 예외를 상위로 전파합니다.
        raise NPCDialogueLLMUnavailable(self.reason)


# OpenAI Responses API를 사용하여 NPC 대사를 생성하는 공식 Chat Model 클래스(Class)입니다.
class OpenAINPCDialogueChatModel:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout_seconds: float = 10.0) -> None:
        self.api_key = api_key
        self._model = model
        self.timeout_seconds = timeout_seconds
        # 표준 ChatOpenAI 모델에 structured output 연결
        self._chat_model = ChatOpenAI(
            model=model,
            api_key=SecretStr(api_key),
            timeout=timeout_seconds,
        ).with_structured_output(NPCDialogueLLMResult, method="json_schema", strict=True, include_raw=True)

    @property
    def model(self) -> str:
        return self._model

    @classmethod
    def from_environment(cls, env_path: Path | None = None) -> "OpenAINPCDialogueChatModel":
        """환경 변수(Environment Variable) 또는 .env 파일에서 OpenAI 설정을 읽어 클라이언트 인스턴스(Instance)를 생성합니다."""
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

    def generate(self, payload: dict[str, Any], callbacks: list[Any] | None = None) -> dict[str, Any]:
        """LangChain의 ChatPromptTemplate과 LCEL 체인을 결합하여 NPC 대사를 생성합니다."""
        persona = str(payload.get("persona_instruction", "concise, official, calm, and dry immigration officer.")).strip()
        prompt = ChatPromptTemplate.from_messages([
            ("system", _developer_instructions(persona)),
            ("user", "{input_payload}")
        ])
        chain = prompt | self._chat_model
        
        # include_raw=True에 의해 output은 {"raw": AIMessage, "parsed": NPCDialogueLLMResult} 형식을 가집니다.
        output = chain.invoke(
            {"input_payload": json.dumps(payload, ensure_ascii=False)},
            config={"callbacks": callbacks}
        )
        
        parsed_obj: NPCDialogueLLMResult = output["parsed"]
        raw_msg: AIMessage = output["raw"]
        
        # Pydantic 모델을 사전(Dictionary)으로 변환
        parsed = parsed_obj.model_dump()
        
        # 토큰 사용량 정보 추출 및 주입
        usage = getattr(raw_msg, "usage_metadata", None) or {}
        parsed["__llm_usage"] = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
        return parsed



# vLLM 또는 Ollama처럼 OpenAI의 Chat Completions API와 호환되는 로컬 서버(Local Server) 연동을 위한 Chat Model 클래스(Class)입니다.
class OpenAICompatibleNPCDialogueChatModel:
    def __init__(self, api_key: str, model: str, base_url: str, timeout_seconds: float = 10.0) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        
        # vLLM의 json_schema 미지원 가능성에 대비해 안전하게 method="json_mode" 사용
        self._chat_model = ChatOpenAI(
            model=model,
            api_key=SecretStr(api_key) if api_key else None,
            base_url=base_url,
            timeout=timeout_seconds,
        ).with_structured_output(NPCDialogueLLMResult, method="json_mode", include_raw=True)

    def generate(self, payload: dict[str, Any], callbacks: list[Any] | None = None) -> dict[str, Any]:
        """LangChain의 ChatPromptTemplate과 LCEL 체인을 결합하여 NPC 대사를 생성합니다."""
        persona = str(payload.get("persona_instruction", "concise, official, calm, and dry immigration officer.")).strip()
        prompt = ChatPromptTemplate.from_messages([
            ("system", _developer_instructions(persona)),
            ("user", "{input_payload}")
        ])
        chain = prompt | self._chat_model
        
        # include_raw=True 방식에 의해 동일한 출력을 얻습니다.
        output = chain.invoke(
            {"input_payload": json.dumps(payload, ensure_ascii=False)},
            config={"callbacks": callbacks}
        )
        
        parsed_obj: NPCDialogueLLMResult = output["parsed"]
        raw_msg: AIMessage = output["raw"]
        
        parsed = parsed_obj.model_dump()
        
        usage = getattr(raw_msg, "usage_metadata", None) or {}
        parsed["__llm_usage"] = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
        return parsed



# 환경 변수 설정을 바탕으로 Primary 체인과 Fallback 체인을 자동 조립하여 제공하는 팩토리 함수입니다.
def build_npc_dialogue_llm_client_from_environment(
    env_path: Path | None = None,
) -> Runnable[dict, dict]:
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

    from langchain_core.runnables import RunnableLambda

    # prompt_runner 정의
    def make_prompt_and_input(payload: dict) -> list[BaseMessage]:
        persona = str(payload.get("persona_instruction", "concise, official, calm, and dry immigration officer.")).strip()
        system_prompt = _developer_instructions(persona)
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{input_payload}")
        ])
        input_payload_str = json.dumps(payload, ensure_ascii=False)
        return prompt_template.format_messages(input_payload=input_payload_str)

    prompt_runner = RunnableLambda(make_prompt_and_input)

    # output_formatter 정의
    def format_output(output: dict, fallback_model_name: str | None = None) -> dict:
        parsed_obj: NPCDialogueLLMResult = output["parsed"]
        raw_msg: AIMessage = output["raw"]
        parsed = parsed_obj.model_dump()
        usage = getattr(raw_msg, "usage_metadata", None) or {}
        parsed["__llm_usage"] = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
        if fallback_model_name:
            parsed["__fallback_model"] = fallback_model_name
        return parsed

    primary_api_key = os.getenv("OPENAI_API_KEY") or values.get("OPENAI_API_KEY")
    primary_model_name = os.getenv("NPC_DIALOGUE_LLM_MODEL") or values.get("NPC_DIALOGUE_LLM_MODEL", "gpt-4o-mini")
    primary_timeout = float(os.getenv("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS") or values.get("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS", "10"))

    fallback_client: Runnable | None = None
    if fallback_name == "gemma4_vllm":
        fb_timeout = float(os.getenv("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS") or values.get("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS", "10"))
        fb_api_key = os.getenv("GEMMA4_VLLM_API_KEY") or values.get("GEMMA4_VLLM_API_KEY", "dummy")
        fb_model = os.getenv("GEMMA4_VLLM_MODEL") or values.get("GEMMA4_VLLM_MODEL", "google/gemma-4-26B-A4B-it")
        fb_base_url = os.getenv("GEMMA4_VLLM_BASE_URL") or values.get("GEMMA4_VLLM_BASE_URL", "http://100.95.34.69:8001/v1")

        fallback_model = ChatOpenAI(
            model=fb_model,
            api_key=SecretStr(fb_api_key) if fb_api_key else None,
            base_url=fb_base_url,
            timeout=fb_timeout,
        ).with_structured_output(NPCDialogueLLMResult, method="json_mode", include_raw=True).with_retry(stop_after_attempt=2)

        fallback_client = prompt_runner | fallback_model | RunnableLambda(lambda out: format_output(out, fallback_model_name=fb_model))

    primary_client: Runnable
    if not primary_api_key:
        exc = NPCDialogueLLMUnavailable("OPENAI_API_KEY is not configured.")
        if fallback_client is not None:
            def throw_exc(*args, **kwargs):
                raise exc
            primary_client = RunnableLambda(throw_exc)
        else:
            raise exc
    else:
        primary_model = ChatOpenAI(
            model=primary_model_name,
            api_key=SecretStr(primary_api_key),
            timeout=primary_timeout,
        ).with_structured_output(NPCDialogueLLMResult, method="json_schema", strict=True, include_raw=True).with_retry(stop_after_attempt=2)

        primary_client = prompt_runner | primary_model | RunnableLambda(lambda out: format_output(out))

    if fallback_client is not None:
        final_chain = primary_client.with_fallbacks(
            fallbacks=[fallback_client],
            exceptions_to_handle=(NPCDialogueLLMUnavailable, httpx.HTTPError, json.JSONDecodeError, ValueError, KeyError)
        )
        return final_chain

    return primary_client



def _developer_instructions(persona_instruction: str) -> str:
    """LLM이 NPC의 성격, 제한조건, 입력 양식 및 언어 규칙(영어만 사용 등)을 철저히 따르도록 지시하는 시스템 프롬프트(System Prompt)입니다."""
    return (
        "You are Developer A's NPC Dialogue Agent for Murphy's Trippin. "
        "Generate only JSON that matches the schema. Use the Level Design JSON, "
        "player language profile, NPC emotion state, and dialogue policy. "
        "Do not change branch, next_node_id, commands, validation, or scores. "
        "Generate final npc_text and tts_text from npc_question_goal, required_slots, "
        "target_slot, question_complexity, npc_speech_speed, emotion_change, player_text, "
        "and understanding.extracted_slots. "
        "Do not copy node_context.npc_question, npc_recast_line_candidate, "
        "fallback_candidate.npc_text, or fallback_candidate.tts_text verbatim as final dialogue. "
        "Use fallback_candidate only as a safety seed when generation metadata is missing. "
        "Use fallback_candidate.speaker as the NPC speaker. "
        f"Adopt the following persona style for the NPC dialogue generation: {persona_instruction} "
        "Always set animation to 'move'. "
        "Evaluate and output the final 'npc_emotion' (selected from: joy, panic, sad, suspicion, disgust, fear, smirk, normal, anger, surprise, pain, confusion, boredom) and 'tone' matching the context. "
        "Based on the resolved emotion, dynamically calculate and adjust ElevenLabs TTS parameters (stability, style, speed, and similarity_boost). "
        "For intense emotions like anger, panic, or fear, lower the stability and increase style/speed. "
        "For flat or low-intensity emotions like boredom or sad, adjust parameters for a slower delivery. "
        "Output them as floating-point numbers in the specified schema ranges. "
        "npc_text and tts_text must be English-only ASCII NPC dialogue. Do not put Korean, "
        "mojibake, translation notes, or mixed-language text in npc_text or tts_text. "
        "npc_text is the line displayed to the player. tts_text is a slightly "
        "more speakable version for ElevenLabs TTS. Make tts_text natural for spoken audio: "
        "use short sentences, conversational rhythm, and brief pauses like '...' only where "
        "they improve timing. "
        "feedback_kr is the only field that may contain Korean, "
        "and it must be short Korean feedback."
    )






def _read_env_file(path: Path) -> dict[str, str]:
    """지정된 경로의 로컬 .env 파일을 파싱하여 키-값 사전(Dictionary)으로 로드합니다."""
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


# 하위 호환성을 위한 별칭(Alias) 정의입니다.
OpenAICompatibleNPCDialogueLLMClient = OpenAICompatibleNPCDialogueChatModel
OpenAINPCDialogueLLMClient = OpenAINPCDialogueChatModel

