from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import json
import os

import httpx


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


# OpenAI Responses API를 사용하여 NPC 대사를 생성하는 공식 클라이언트 클래스(Class)입니다.
@dataclass(frozen=True)
class OpenAINPCDialogueLLMClient:
    api_key: str
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 10.0
    endpoint: str = "https://api.openai.com/v1/responses"

    @classmethod
    def from_environment(cls, env_path: Path | None = None) -> "OpenAINPCDialogueLLMClient":
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

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """OpenAI Responses API를 호출하여 NPC 대사 결과를 정규화된 스키마(Schema) 형태의 JSON으로 획득합니다."""
        persona = str(payload.get("persona_instruction", "concise, official, calm, and dry immigration officer.")).strip()
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "instructions": _developer_instructions(persona),
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
        # API 응답 결과에서 구조화된 대사 데이터를 추출하여 반환합니다.
        return _extract_structured_json(data)


# vLLM 또는 Ollama처럼 OpenAI의 Chat Completions API와 호환되는 로컬 서버(Local Server) 연동을 위한 클라이언트 클래스(Class)입니다.
@dataclass(frozen=True)
class OpenAICompatibleNPCDialogueLLMClient:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 10.0

    @property
    def endpoint(self) -> str:
        # Chat Completions 호환 규격에 맞춰 엔드포인트(Endpoint) URL을 조립합니다.
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """OpenAI 호환 Chat Completions API 엔드포인트를 호출하여 NPC 대사를 생성합니다."""
        persona = str(payload.get("persona_instruction", "concise, official, calm, and dry immigration officer.")).strip()
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _developer_instructions(persona)},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "temperature": 0.2,
                "max_tokens": 500,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        # Chat Completion 응답 형식에 맞춰 구조화된 결과를 추출합니다.
        return _extract_chat_completion_structured_json(data)


# 메인(Primary) LLM 클라이언트가 실패하거나 예외가 발생하면 대체(Fallback) LLM 클라이언트를 실행하는 데코레이터(Decorator) 형태의 클라이언트 클래스(Class)입니다.
@dataclass(frozen=True)
class FallbackNPCDialogueLLMClient:
    primary: NPCDialogueLLMClient
    fallback: NPCDialogueLLMClient

    @property
    def model(self) -> str:
        # 기본적으로 메인 클라이언트의 모델명을 반환합니다.
        return self.primary.model

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            # 1단계로 메인 클라이언트 생성을 시도합니다.
            return self.primary.generate(payload)
        except (NPCDialogueLLMUnavailable, httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError):
            # 2단계로 실패 시 대체 클라이언트를 통해 생성하고, 호출 메타데이터에 대체 모델이 사용되었음을 기록합니다.
            result = self.fallback.generate(payload)
            result["__fallback_model"] = self.fallback.model
            return result


def build_npc_dialogue_llm_client_from_environment(
    env_path: Path | None = None,
) -> NPCDialogueLLMClient:
    """환경 변수 설정을 바탕으로 Primary 클라이언트와 Fallback 클라이언트를 자동 조립하여 제공하는 팩토리 함수(Factory Function)입니다."""
    values = _read_env_file(env_path or Path(".env"))
    provider = (
        os.getenv("NPC_DIALOGUE_LLM_PROVIDER")
        or values.get("NPC_DIALOGUE_LLM_PROVIDER")
        or "openai"
    ).strip().lower()

    # 1차 프로토타입 범위에서는 오직 openai 계열 프로바이더(Provider)만을 지원합니다.
    if provider != "openai":
        raise NPCDialogueLLMUnavailable(f"Unsupported NPC_DIALOGUE_LLM_PROVIDER: {provider}")

    fallback_name = (
        os.getenv("NPC_DIALOGUE_LLM_FALLBACK")
        or values.get("NPC_DIALOGUE_LLM_FALLBACK")
        or "none"
    ).strip().lower()

    # 대체 모델 설정이 vLLM 상의 gemma4_vllm인 경우 해당 호환 클라이언트를 빌드합니다.
    fallback = _build_gemma4_vllm_client(values) if fallback_name == "gemma4_vllm" else None

    try:
        primary = OpenAINPCDialogueLLMClient.from_environment(env_path)
    except NPCDialogueLLMUnavailable as exc:
        # 만약 메인 OpenAI 클라이언트 빌드가 실패했더라도 대체 클라이언트가 정의되어 있다면 안전하게 연동해 줍니다.
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
    """vLLM 기반으로 실행 중인 로컬 Gemma 모델용 클라이언트를 빌드합니다."""
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


def _dialogue_schema() -> dict[str, Any]:
    """LLM 출력 형식을 제한하고 강제(Strict Schema Matching)하기 위한 JSON 스키마 명세를 정의합니다."""
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
            "npc_emotion",
            "stability",
            "style",
            "speed",
            "similarity_boost",
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
            "npc_emotion": {
                "type": "string",
                "enum": [
                    "joy",
                    "panic",
                    "sad",
                    "suspicion",
                    "disgust",
                    "fear",
                    "smirk",
                    "normal",
                    "anger",
                    "surprise",
                    "pain",
                    "confusion",
                    "boredom",
                ],
            },
            "stability": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "style": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0},
            "similarity_boost": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "llm_reason": {"type": "string", "maxLength": 240},
        },
    }


def _extract_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    """OpenAI Responses API 응답 본문에서 구조화된 대사 JSON과 사용한 토큰 통계(Usage)를 추출합니다."""
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
    """OpenAI 호환 Chat Completions API 응답 본문에서 대사 JSON과 사용한 토큰 통계(Usage)를 추출합니다."""
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
    """마크다운(Markdown) 형식의 JSON 코드 블록 기호(```json ... ```)를 파싱하기 편하게 제거합니다."""
    if text.startswith("```json"):
        return text.removeprefix("```json").removesuffix("```").strip()
    if text.startswith("```"):
        return text.removeprefix("```").removesuffix("```").strip()
    return text


def _extract_usage(data: dict[str, Any]) -> dict[str, int]:
    """OpenAI API가 보고한 입력, 출력, 총 토큰 사용량 데이터를 파싱합니다."""
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
    """OpenAI 호환 Chat Completions API의 토큰 사용량 데이터(prompt/completion tokens)를 파싱합니다."""
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
    """안전하게 값을 정수(Integer)형으로 변환합니다."""
    return value if isinstance(value, int) else 0


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
