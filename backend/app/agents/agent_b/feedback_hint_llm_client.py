from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Protocol

import httpx


class FeedbackHintLLMClient(Protocol):
    """
    학습자 피드백 및 힌트를 생성하는 LLM 클라이언트의 공통 규격(인터페이스)입니다.
    
    초보자 가이드: 이 프로토콜을 구현하는 클래스는 반드시 `model` 변수와 `generate` 메서드를 가지고 있어야 합니다.
    """
    model: str

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        사용자의 입력 데이터(payload)를 바탕으로 피드백과 힌트 데이터가 담긴 JSON 객체를 생성합니다.
        
        Args:
            payload: 학습자의 발화 및 현재 게임 상황 정보가 포함된 딕셔너리
            
        Returns:
            피드백, 모범 예문, 루브릭 점수 등이 포함된 JSON 형식의 딕셔너리
        """
        ...


class FeedbackHintLLMUnavailable(RuntimeError):
    """
    피드백 힌트 생성을 위한 LLM 서비스를 사용할 수 없을 때(예: API 키 누락 등) 발생하는 에러입니다.
    """
    pass


@dataclass(frozen=True)
class OpenAIFeedbackHintLLMClient:
    """
    OpenAI API를 사용하여 영어 학습용 피드백과 힌트를 생성하는 실제 구현체입니다.
    
    초보자 가이드: OpenAI의 GPT 모델을 호출하여, 학생의 영어 답변에 대해 한국어로 된 힌트와 피드백, 모범 답안 등을 받아옵니다.
    """
    api_key: str
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 10.0
    endpoint: str = "https://api.openai.com/v1/responses"

    @classmethod
    def from_environment(cls, env_path: Path | None = None) -> "OpenAIFeedbackHintLLMClient":
        """
        환경 변수나 설정 파일(.env)에서 설정 값을 읽어와 OpenAI 피드백 LLM 클라이언트를 생성합니다.
        
        Args:
            env_path: 설정 값을 읽어올 .env 파일의 경로 (전달하지 않으면 기본적으로 루트 폴더의 .env 사용)
            
        Returns:
            설정이 완료된 OpenAIFeedbackHintLLMClient 인스턴스
            
        Raises:
            FeedbackHintLLMUnavailable: OPENAI_API_KEY 설정이 없을 경우 발생
        """
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
        """
        OpenAI API를 직접 호출하여, 주어진 대화 컨텍스트(payload)에 부합하는 한국어 피드백 및 루브릭 평가 결과를 받아옵니다.
        
        Args:
            payload: 학습자의 대화 상태, 정답 여부, 현재 챕터 노드 등의 메타데이터가 담긴 딕셔너리
            
        Returns:
            JSON 스키마에 정의된 형태의 한글 피드백, 모범 예문, 영역별 평가 점수가 포함된 딕셔너리
            
        Raises:
            HTTPError: OpenAI API 통신에 실패했을 때 발생
            FeedbackHintLLMUnavailable: 반환된 결과가 올바른 JSON 형식이 아닐 때 발생
        """
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
    """
    OpenAI API 호출 시 전달할 개발자 시스템 안내문(Instructions)을 반환합니다.
    이 안내문은 LLM에게 입국 위험을 미화하지 말고, 한국어 피드백과 모범 답안 등을 JSON 형태로 출력하도록 지시합니다.
    """
    return (
        "You are Developer B's English learning feedback and hint assistant for "
        "Murphy's Trippin. Return only JSON matching the schema. Generate short "
        "Korean feedback (feedback_note, report_summary, and report_improvement must be in Korean), a safe English example, and rubric score candidates. "
        "Do not generate NPC dialogue, npc_text, npc_utterance, final dialogue "
        "lines, TTS text, Unreal commands, branch, next_node_id, verdict, "
        "next_action, or state_delta. Do not soften real "
        "immigration risk. Keep feedback supportive and concise for Korean "
        "travel-English learners."
    )



def _feedback_schema() -> dict[str, Any]:
    """
    OpenAI가 반환해야 하는 JSON 응답의 구조(스키마)를 정의하여 반환합니다.
    한글 힌트, 피드백 노트, 종합 리포트 요약, 개선 방향, 모범 답안, 루브릭 점수 등의 필드를 강제합니다.
    """
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
    """
    OpenAI 응답 데이터에서 최종 텍스트 결과(JSON 형식)를 추출하여 파이썬 딕셔너리로 파싱합니다.
    
    Args:
        data: OpenAI API의 응답 JSON 데이터
        
    Returns:
        파싱되어 구조화된 피드백 결과 딕셔너리
    """
    if isinstance(data.get("output_text"), str):
        return json.loads(data["output_text"])
    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                return json.loads(str(content_item.get("text", "")))
    raise FeedbackHintLLMUnavailable("OpenAI response did not include output_text.")


def _read_env_file(path: Path) -> dict[str, str]:
    """
    지정된 경로의 설정 파일(.env)을 읽어 키-값 쌍의 딕셔너리로 반환합니다.
    
    Args:
        path: 읽어올 파일의 경로 객체
        
    Returns:
        설정 정보 키와 값이 담긴 딕셔너리
    """
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
