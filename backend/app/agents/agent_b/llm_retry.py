from __future__ import annotations

import random
import time
from typing import Any

import httpx


# OpenAI가 일시적으로 반환하는, 재시도하면 대부분 성공하는 상태 코드들입니다.
# 429(Too Many Requests)와 5xx(일시적 서버 오류)가 여기에 해당합니다.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def post_json_with_retry(
    *,
    endpoint: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    timeout_seconds: float,
    max_retries: int = 3,
    base_delay_seconds: float = 0.5,
    max_delay_seconds: float = 8.0,
) -> httpx.Response:
    """
    OpenAI 응답 API로 POST 요청을 보내되, 429/5xx나 일시적 네트워크 오류가 나면
    지수 백오프(+지터)로 재시도합니다.

    초보자 가이드: 한 턴에 여러 LLM(이해·NPC 대사·피드백·총평)이 짧은 구간에 몰리면
    순간 요청량이 계정 rate limit을 넘겨 429가 뜹니다. 429는 잠깐 기다렸다 다시 보내면
    대부분 성공하므로, 여기서 짧게 재시도해 규칙 폴백(영어 피드백)으로 떨어지는 것을 막습니다.

    - 429 응답에 `Retry-After` 헤더가 있으면 그 값을 우선 존중합니다.
    - 여러 클라이언트가 동시에 재시도하며 다시 몰리는(thundering herd) 것을 막기 위해 지터를 더합니다.
    - 재시도를 모두 소진하면 마지막 응답에 대해 `raise_for_status()`를 호출해 예외를 전파합니다
      (호출부에서 규칙 폴백으로 자연스럽게 넘어갑니다).
    """
    attempt = 0
    while True:
        try:
            response = httpx.post(
                endpoint,
                headers=headers,
                json=json_body,
                timeout=timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt >= max_retries:
                raise
            time.sleep(_backoff_delay(attempt, base_delay_seconds, max_delay_seconds))
            attempt += 1
            continue

        if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
            time.sleep(
                _retry_after_delay(response, attempt, base_delay_seconds, max_delay_seconds)
            )
            attempt += 1
            continue

        response.raise_for_status()
        return response


def _backoff_delay(attempt: int, base_delay_seconds: float, max_delay_seconds: float) -> float:
    """지수 백오프 대기 시간(초)을 지터와 함께 계산합니다."""
    delay = base_delay_seconds * (2 ** attempt)
    delay = min(delay, max_delay_seconds)
    return delay + random.uniform(0, base_delay_seconds)


def _retry_after_delay(
    response: httpx.Response,
    attempt: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> float:
    """
    `Retry-After` 헤더(초 단위)가 있으면 그 값을 우선 사용하고,
    없으면 지수 백오프로 대기 시간을 계산합니다.
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            seconds = float(retry_after)
        except ValueError:
            seconds = -1.0
        if seconds >= 0:
            return min(seconds, max_delay_seconds) + random.uniform(0, base_delay_seconds)
    return _backoff_delay(attempt, base_delay_seconds, max_delay_seconds)
