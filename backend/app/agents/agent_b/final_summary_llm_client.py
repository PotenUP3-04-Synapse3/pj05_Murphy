from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)


class FinalSummaryLLMClient(Protocol):
    model: str

    def generate(self, payload: dict[str, Any]) -> str:
        """세션 성과 데이터를 받아 한국어 총평 문자열을 반환합니다."""
        ...


class FinalSummaryLLMUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAIFinalSummaryLLMClient:
    api_key: str
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 15.0
    endpoint: str = "https://api.openai.com/v1/responses"

    @classmethod
    def from_environment(cls, env_path: Path | None = None) -> "OpenAIFinalSummaryLLMClient":
        values = _read_env_file(env_path or Path(".env"))
        api_key = os.getenv("OPENAI_API_KEY") or values.get("OPENAI_API_KEY")
        if not api_key:
            raise FinalSummaryLLMUnavailable("OPENAI_API_KEY is not configured.")
        model = (
            os.getenv("DEV_B_FINAL_SUMMARY_LLM_MODEL")
            or values.get("DEV_B_FINAL_SUMMARY_LLM_MODEL")
            or os.getenv("DEV_B_FEEDBACK_LLM_MODEL")
            or values.get("DEV_B_FEEDBACK_LLM_MODEL", "gpt-4o-mini")
        )
        timeout = float(
            os.getenv("DEV_B_FINAL_SUMMARY_LLM_TIMEOUT_SECONDS")
            or values.get("DEV_B_FINAL_SUMMARY_LLM_TIMEOUT_SECONDS", "15")
        )
        return cls(api_key=api_key, model=model, timeout_seconds=timeout)

    def generate(self, payload: dict[str, Any]) -> str:
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "instructions": _system_instructions(),
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
                        "name": "final_summary_result",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["overall_summary"],
                            "properties": {
                                "overall_summary": {
                                    "type": "string",
                                    "minLength": 10,
                                    "maxLength": 200,
                                }
                            },
                        },
                    }
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        result = _extract_json(response.json())
        summary = result.get("overall_summary", "")
        if not isinstance(summary, str) or not summary.strip():
            raise FinalSummaryLLMUnavailable("LLM returned empty overall_summary.")
        return summary.strip()


def _system_instructions() -> str:
    return (
        "You are Murphy's Trippin의 최종 성적 총평 작성 AI입니다. "
        "여행 영어 게임의 세션 성과 데이터를 JSON으로 받아, "
        "한국어로 된 총평 한 단락(2~3문장, 최대 200자)을 JSON 형태로 반환하세요. "
        "총평은 실제로 수행한 챕터(scenes_covered)만 언급해야 합니다. "
        "수행하지 않은 챕터(예: 입국 심사를 하지 않았는데 '입국 심사를 통과했습니다' 같은 표현)는 절대 쓰지 마세요. "
        "점수가 낮은 영역(weakest_dimension)을 언급하고 구체적인 개선 방향을 제시하세요. "
        "응원하는 어조이되 과장하지 말고, 실제 성과에 기반해 솔직하게 쓰세요. "
        "recommendation이 PASS면 긍정적으로, CONDITIONAL_PASS면 아쉬운 점 포함, "
        "SECONDARY_ROOM/COMIC_FAIL이면 솔직하게 부족한 점을 지적하세요. "
        'Return only JSON: {"overall_summary": "..."}. No markdown, no extra keys.'
    )


def _extract_json(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("output_text"), str):
        return json.loads(data["output_text"])
    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                return json.loads(str(content_item.get("text", "")))
    raise FinalSummaryLLMUnavailable("OpenAI response did not include output_text.")


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
