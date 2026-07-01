from __future__ import annotations

import httpx
import pytest

from backend.app.agents.agent_b import llm_retry


def _make_response(status_code: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        headers=headers or {},
        json={"ok": True},
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
    )


def _patch(monkeypatch, responses, sleeps):
    calls = {"count": 0}

    def fake_post(endpoint, headers=None, json=None, timeout=None):
        result = responses[calls["count"]]
        calls["count"] += 1
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(llm_retry.httpx, "post", fake_post)
    monkeypatch.setattr(llm_retry.time, "sleep", lambda seconds: sleeps.append(seconds))
    return calls


def _call(**overrides):
    kwargs = dict(
        endpoint="https://api.openai.com/v1/responses",
        headers={},
        json_body={},
        timeout_seconds=10.0,
        base_delay_seconds=0.5,
    )
    kwargs.update(overrides)
    return llm_retry.post_json_with_retry(**kwargs)


def test_retries_on_429_then_succeeds(monkeypatch) -> None:
    sleeps: list[float] = []
    calls = _patch(monkeypatch, [_make_response(429), _make_response(200)], sleeps)

    response = _call(max_retries=3)

    assert response.status_code == 200
    assert calls["count"] == 2
    assert len(sleeps) == 1  # 한 번 재시도했으니 한 번 대기


def test_respects_retry_after_header(monkeypatch) -> None:
    sleeps: list[float] = []
    _patch(
        monkeypatch,
        [_make_response(429, {"Retry-After": "2"}), _make_response(200)],
        sleeps,
    )

    _call(max_retries=3, base_delay_seconds=0.0, max_delay_seconds=8.0)

    # Retry-After=2초를 우선 존중 (지터 base_delay=0 이므로 정확히 2.0)
    assert sleeps == [2.0]


def test_raises_after_exhausting_retries_on_429(monkeypatch) -> None:
    sleeps: list[float] = []
    _patch(monkeypatch, [_make_response(429)] * 5, sleeps)

    with pytest.raises(httpx.HTTPStatusError):
        _call(max_retries=2)

    # max_retries=2 → 최초 1회 + 재시도 2회 = 총 3회 요청, 대기는 2회
    assert len(sleeps) == 2


def test_retries_on_transient_transport_error(monkeypatch) -> None:
    sleeps: list[float] = []
    calls = _patch(
        monkeypatch,
        [httpx.ConnectError("boom"), _make_response(200)],
        sleeps,
    )

    response = _call(max_retries=3)

    assert response.status_code == 200
    assert calls["count"] == 2


def test_does_not_retry_on_400(monkeypatch) -> None:
    sleeps: list[float] = []
    calls = _patch(monkeypatch, [_make_response(400)], sleeps)

    with pytest.raises(httpx.HTTPStatusError):
        _call(max_retries=3)

    assert calls["count"] == 1  # 400은 재시도 대상 아님
    assert sleeps == []
