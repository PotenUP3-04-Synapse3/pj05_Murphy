from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import json
import os
import jinja2

import httpx


from langchain_core.messages import BaseMessage, AIMessage, SystemMessage, HumanMessage
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

    def on_chain_start(self, serialized: dict[str, Any], inputs: Any, **kwargs: Any) -> None:
        """LCEL 체인 실행이 시작될 때 실행됩니다.

        주의: LCEL 파이프라인 내부 Runnable 단계에 따라 inputs 가 dict / list[BaseMessage] /
        ChatPromptValue / BaseMessage 등 다양한 타입으로 전달될 수 있으므로 타입별 안전 요약을 사용합니다.
        """
        if self.recorder and self.metadata:
            self.recorder.record_event(
                self.metadata,
                event="langchain_chain_start",
                status="started",
                input_summary=_summarize_runnable_io(inputs),
            )

    def on_chain_end(self, outputs: Any, **kwargs: Any) -> None:
        """LCEL 체인 실행이 정상적으로 완료될 때 실행됩니다.

        주의: 단계별 Runnable 출력은 dict 가 아닌 BaseMessage / list[BaseMessage] / 임의 객체일 수 있습니다.
        """
        if self.recorder and self.metadata:
            self.recorder.record_event(
                self.metadata,
                event="langchain_chain_end",
                status="completed",
                output_summary=_summarize_runnable_io(outputs),
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
        # api_key: OpenAI 인증을 위한 API 키(Secret Key)입니다.
        self.api_key = api_key
        # _model: 호출할 OpenAI 모델 식별자(예: gpt-4o-mini)입니다.
        self._model = model
        # timeout_seconds: HTTP 통신 제한 시간(초)입니다.
        self.timeout_seconds = timeout_seconds
        
        # [초기화] 표준 ChatOpenAI 모델에 structured output 스키마를 강제하는 설정입니다.
        self._chat_model = ChatOpenAI(
            model=model,
            api_key=SecretStr(api_key),
            timeout=timeout_seconds,
        ).with_structured_output(NPCDialogueLLMResult, method="json_schema", strict=True, include_raw=True)

    @property
    def model(self) -> str:
        """현재 사용 중인 모델의 이름을 반환합니다."""
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
        system_prompt = _render_developer_instructions(payload, use_short=False)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
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
        # api_key: 로컬 서버 인증용 API 키(필요 시 사용)입니다.
        self.api_key = api_key
        # model: vLLM 또는 Ollama에 탑재된 모델명(예: google/gemma-4-26B-it)입니다.
        self.model = model
        # base_url: OpenAI 규격 호환 API Endpoint 주소(URL)입니다.
        self.base_url = base_url
        # timeout_seconds: HTTP 통신 제한 시간(초)입니다.
        self.timeout_seconds = timeout_seconds
        
        # [초기화] vLLM의 json_schema 미지원 가능성을 감안해, JSON Mode 출력을 유도하고 구조화 모델을 구성합니다.
        self._chat_model = ChatOpenAI(
            model=model,
            api_key=SecretStr(api_key) if api_key else None,
            base_url=base_url,
            timeout=timeout_seconds,
        ).with_structured_output(NPCDialogueLLMResult, method="json_mode", include_raw=True)

    def generate(self, payload: dict[str, Any], callbacks: list[Any] | None = None) -> dict[str, Any]:
        """LangChain의 ChatPromptTemplate과 LCEL 체인을 결합하여 NPC 대사를 생성합니다."""
        system_prompt = _render_developer_instructions(payload, use_short=True)
        input_payload_str = json.dumps(payload, ensure_ascii=False)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=input_payload_str)
        ]
        
        # include_raw=True 방식에 의해 동일한 출력을 얻습니다.
        output = self._chat_model.invoke(
            messages,
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
    # [1단계] 로컬 .env 파일과 OS 환경 변수에서 구동 옵션을 로드합니다.
    values = _read_env_file(env_path or Path(".env"))
    
    # [2단계] 사용할 LLM의 핵심 프로바이더(Provider) 명칭을 결정합니다.
    provider = (
        os.getenv("NPC_DIALOGUE_LLM_PROVIDER")
        or values.get("NPC_DIALOGUE_LLM_PROVIDER")
        or "openai"
    ).strip().lower()

    # 현재는 openai 프로바이더만 공식 지원하고 있으므로 예외 처리를 둡니다.
    if provider != "openai":
        raise NPCDialogueLLMUnavailable(f"Unsupported NPC_DIALOGUE_LLM_PROVIDER: {provider}")

    # [3단계] 기본 모델 에러 시 예외 복구를 위해 활용할 Fallback 모델명을 결정합니다.
    fallback_name = (
        os.getenv("NPC_DIALOGUE_LLM_FALLBACK")
        or values.get("NPC_DIALOGUE_LLM_FALLBACK")
        or "none"
    ).strip().lower()

    from langchain_core.runnables import RunnableLambda

    # primary_prompt_runner 정의
    def make_primary_prompt_and_input(payload: dict) -> list[BaseMessage]:
        system_prompt = _render_developer_instructions(payload, use_short=False)
        input_payload_str = json.dumps(payload, ensure_ascii=False)
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=input_payload_str)
        ]

    # fallback_prompt_runner 정의
    def make_fallback_prompt_and_input(payload: dict) -> list[BaseMessage]:
        system_prompt = _render_developer_instructions(payload, use_short=True)
        input_payload_str = json.dumps(payload, ensure_ascii=False)
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=input_payload_str)
        ]

    primary_prompt_runner = RunnableLambda(make_primary_prompt_and_input)
    fallback_prompt_runner = RunnableLambda(make_fallback_prompt_and_input)

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

        fallback_client = fallback_prompt_runner | fallback_model | RunnableLambda(lambda out: format_output(out, fallback_model_name=fb_model))

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

        primary_client = primary_prompt_runner | primary_model | RunnableLambda(lambda out: format_output(out))

    if fallback_client is not None:
        final_chain = primary_client.with_fallbacks(
            fallbacks=[fallback_client],
            exceptions_to_handle=(NPCDialogueLLMUnavailable, httpx.HTTPError, json.JSONDecodeError, ValueError, KeyError)
        )
        return final_chain

    return primary_client



def _render_developer_instructions(context: dict[str, Any], use_short: bool = False) -> str:
    """외부 마크다운 프롬프트 파일을 읽어 Jinja2 템플릿으로 렌더링하는 헬퍼 함수입니다.
    
    use_short가 True일 경우 fallback LLM용 축약본 프롬프트를 렌더링합니다.
    """
    # parents[2]가 C:/5th_project/pj05_Murphy/backend/app 이므로 그 하위 prompts 폴더 설정
    prompt_dir = Path(__file__).resolve().parents[2] / "prompts"
    
    filename = "npc_dialogue_prompt.short.md" if use_short else "npc_dialogue_prompt.md"
    prompt_path = prompt_dir / filename
    few_shots_path = prompt_dir / "npc_dialogue_few_shots.md"
    
    if not prompt_path.exists():
        import logging
        logger = logging.getLogger("backend.app.agents.agent_a")
        logger.warning(f"Prompt template {filename} not found at {prompt_path}. Falling back to default instructions.")
        return _developer_instructions(str(context.get("persona_instruction", "")))
        
    try:
        render_context = context.copy()
        
        for key in ["allowed_mild", "allowed_strong", "non_verbal_palette", "discussed_topics"]:
            if key in render_context:
                val = render_context[key]
                if isinstance(val, (list, set)):
                    render_context[key] = ", ".join(f"'{x}'" for x in sorted(list(val)))
                    
        if "past_player_utterances" in render_context:
            val = render_context["past_player_utterances"]
            if isinstance(val, (list, set)):
                render_context["past_player_utterances"] = ", ".join(f"'{x}'" for x in list(val))
                
        if "allowed_emotions" in render_context:
            val = render_context["allowed_emotions"]
            if isinstance(val, (list, set)):
                render_context["allowed_emotions"] = ", ".join(val)
                
        template_content = prompt_path.read_text(encoding="utf-8")
        template = jinja2.Template(template_content)
        rendered = template.render(render_context)
        
        if few_shots_path.exists():
            few_shots_content = few_shots_path.read_text(encoding="utf-8")
            rendered += "\n\n" + few_shots_content
            
        return rendered
    except Exception as e:
        import logging
        logger = logging.getLogger("backend.app.agents.agent_a")
        logger.error(f"Failed to render prompt template {filename}: {e}. Falling back to default instructions.")
        return _developer_instructions(str(context.get("persona_instruction", "")))


def _developer_instructions(persona_instruction: str) -> str:
    """LLM이 NPC의 성격, 제한조건, 입력 양식 및 언어 규칙(영어만 사용 등)을 철저히 따르도록 지시하는 시스템 프롬프트(System Prompt)입니다."""
    return (
        "You are Developer A's NPC Dialogue Agent for Murphy's Trippin. "
        "Generate only JSON that matches the schema. "
        "Use the input Level Design JSON (player_text, node_context, understanding, evaluation_summary, dialogue_seed) "
        "to generate the final npc_text and tts_text. "
        f"Adopt the following persona style for the NPC dialogue: {persona_instruction} "
        "Always set animation to 'move'. "
        "Do not copy node_context.npc_question verbatim as the final dialogue. "
        "If npc_role is seatmate, use casual, warm, conversational tone. Keep sentences short. Avoid officer-style directives. "
        "If npc_role is baggage_agent or baggage_service_staff, use helpful, bright, polite, and service-oriented tone. "
        "The player utterance comes from the PLAYER, not the NPC. Do NOT echo the player's recommended phrasing or npc_recast_line_candidate as if the NPC said it. "
        "If transition.status is 'complete_chapter' or next_action is 'COMPLETE_CHAPTER', the NPC MUST output a natural closing or goodbye line only, and MUST NOT ask the next chapter's opening question or any other question. "
        "If dialogue_seed.surface_goal is provided (and not complete_chapter), the NPC MUST (a) briefly acknowledge the prior turn AND (b) ask the next question that fulfills surface_goal (e.g., ask_travel_purpose_smalltalk -> ask a travel-purpose follow-up). Do not output reaction-only lines when a surface_goal exists. "
        "Recommended expression (recommended_expression) is a model answer for the player to learn — never insert it into npc_text/tts_text unless paraphrased as the NPC's own question (e.g., 'So, where are you headed?'). "
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
        "feedback_kr must always be set to 'Good.'."
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


def _summarize_runnable_io(value: Any) -> dict[str, Any]:
    """LCEL 단계 입/출력을 타입에 따라 안전하게 요약합니다.

    LCEL Runnable 사이를 흐르는 값은 dict 라고 가정할 수 없습니다.
    - RunnableSequence / ChatPromptTemplate 단계: dict
    - ChatModel 단계 입력: list[BaseMessage] 또는 ChatPromptValue
    - ChatModel 단계 출력 / 후속 단계 입력: BaseMessage(AIMessage)
    on_chain_start 가 inputs.keys() 를 강제 호출하면 위 비-dict 케이스에서 AttributeError 가 발생하므로
    본 헬퍼로 타입별 요약을 만들고 핸들러 예외를 방지합니다.
    """
    if isinstance(value, dict):
        return {"type": "dict", "keys": list(value.keys())}
    if isinstance(value, BaseMessage):
        return {"type": type(value).__name__, "content_len": len(str(value.content))}
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "item_types": sorted({type(item).__name__ for item in value}),
        }
    # ChatPromptValue 등 to_messages() 를 가진 LangChain 표준 객체
    if hasattr(value, "to_messages"):
        try:
            messages = value.to_messages()
            return {"type": type(value).__name__, "messages_count": len(messages)}
        except Exception:  # noqa: BLE001 - 콜백 안에서는 본 실행을 절대 막지 않는다
            return {"type": type(value).__name__}
    return {"type": type(value).__name__}


# 하위 호환성을 위한 별칭(Alias) 정의입니다.
OpenAICompatibleNPCDialogueLLMClient = OpenAICompatibleNPCDialogueChatModel
OpenAINPCDialogueLLMClient = OpenAINPCDialogueChatModel

