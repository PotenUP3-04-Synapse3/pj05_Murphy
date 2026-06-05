# Gemma4 vLLM Fallback Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GPT key 장애 시 Gemini가 아니라 학원 서버의 vLLM OpenAI-compatible Gemma4 모델을 LLM fallback으로 사용한다.

**Architecture:** OpenAI provider는 기본 primary로 유지하고, primary LLM client가 key 누락/HTTP 실패/JSON 실패를 내면 rule fallback 전에 Gemma4 vLLM fallback client를 한 번 시도한다. Gemma4 fallback은 공통 서버 설정(`GEMMA4_VLLM_*`)을 쓰고, Developer C Understanding과 Developer A NPC Dialogue가 각각 opt-in env flag로 사용할 수 있게 한다. Gemini 전용 client와 env 문구는 제거한다.

**Tech Stack:** Python 3.12, uv, httpx, FastAPI, Pydantic Settings, pytest, ruff, mypy, vLLM OpenAI-compatible `/v1/chat/completions`.

---

## File Structure

- Modify: `backend/app/services/service_c/settings_service.py`
  - Gemini API key/provider 설정을 제거하고, Gemma4 vLLM fallback 설정을 추가한다.
- Modify: `backend/app/agents/agent_c/understanding_llm_client.py`
  - Gemini client를 제거한다.
  - `OpenAICompatibleUnderstandingLLMClient`와 `FallbackUnderstandingLLMClient`를 추가한다.
  - `build_understanding_llm_client_from_settings()`가 fallback 설정을 보고 primary -> Gemma4 순서 client를 만든다.
- Modify: `backend/app/agents/agent_a/npc_llm_client.py`
  - Gemini client를 제거한다.
  - `OpenAICompatibleNPCDialogueLLMClient`와 `FallbackNPCDialogueLLMClient`를 추가한다.
  - `build_npc_dialogue_llm_client_from_environment()`가 fallback 설정을 보고 primary -> Gemma4 순서 client를 만든다.
- Modify: `backend/app/agents/agent_c/understanding_agent.py`
  - 기존 factory 호출은 유지한다. factory 반환 client가 fallback을 처리한다.
- Modify: `backend/app/agents/agent_a/npc_dialogue_agent.py`
  - 기존 factory 호출은 유지한다. factory 반환 client가 fallback을 처리한다.
- Modify: `.env.example`
  - Gemini 관련 env를 제거하고 Gemma4 vLLM fallback env를 추가한다.
- Modify: `README.md`
  - Gemini 전환 설명을 제거하고 Gemma4 fallback 설정 예시를 추가한다.
- Modify: `docs/contracts/developer_c_adapter_contracts.md`
  - Understanding LLM provider 설명을 Gemma4 fallback 기준으로 갱신한다.
- Modify: `docs/contracts/developer_c_schema_contract.md`
  - C runtime env 표에서 Gemini를 제거하고 Gemma4 vLLM fallback 설정을 추가한다.
- Modify: `docs/handoff.md`
  - GPT key 장애 시 Gemma4 fallback 사용법을 남긴다.
- Modify: `docs/implementation_logs/developer_a_implementation_log_kimyonghee.md`
  - Developer A NPC Dialogue LLM의 Gemma4 fallback 변경을 기록한다.
- Test: `backend/tests/test_settings_service.py`
  - Gemma4 vLLM fallback env 값을 읽는지 검증한다.
- Test: `backend/tests/test_understanding_llm_client.py`
  - vLLM `/v1/chat/completions` 요청 형식, JSON 추출, primary 실패 후 fallback 성공을 검증한다.
- Test: `backend/tests/test_developer_a_npc_llm_client.py`
  - A NPC Dialogue vLLM fallback 요청 형식과 factory 선택을 검증한다.

---

### Task 1: Runtime Settings에서 Gemini 제거 및 Gemma4 Fallback 설정 추가

**Files:**
- Modify: `backend/app/services/service_c/settings_service.py`
- Modify: `backend/tests/test_settings_service.py`

- [ ] **Step 1: Write the failing test**

Add these keys to `_clear_runtime_env()` in `backend/tests/test_settings_service.py`:

```python
"GEMINI_API_KEY",
"GEMMA4_VLLM_BASE_URL",
"GEMMA4_VLLM_MODEL",
"GEMMA4_VLLM_API_KEY",
"MURPHY_UNDERSTANDING_LLM_FALLBACK",
```

In `test_app_settings_reads_values_from_env_file()`, replace Gemini lines with:

```python
"GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1",
"GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it",
"GEMMA4_VLLM_API_KEY=dummy",
"MURPHY_UNDERSTANDING_LLM_PROVIDER=openai",
"MURPHY_UNDERSTANDING_LLM_FALLBACK=gemma4_vllm",
"MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini",
```

And assert:

```python
assert settings.gemma4_vllm_base_url == "http://100.95.34.69:8001/v1"
assert settings.gemma4_vllm_model == "google/gemma-4-26B-A4B-it"
assert settings.gemma4_vllm_api_key == "dummy"
assert settings.murphy_understanding_llm_provider == "openai"
assert settings.murphy_understanding_llm_fallback == "gemma4_vllm"
assert settings.murphy_understanding_llm_model == "gpt-4o-mini"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q
```

Expected: FAIL with missing `gemma4_vllm_*` or `murphy_understanding_llm_fallback` attributes.

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/services/service_c/settings_service.py`:

```python
class AppSettings(BaseSettings):
    ...
    openai_api_key: str | None = None
    gemma4_vllm_base_url: str = "http://100.95.34.69:8001/v1"
    gemma4_vllm_model: str = "google/gemma-4-26B-A4B-it"
    gemma4_vllm_api_key: str = "dummy"
    ...
    murphy_understanding_llm_provider: Literal["openai"] = "openai"
    murphy_understanding_llm_fallback: Literal["none", "gemma4_vllm"] = "none"
    murphy_understanding_llm_model: str = "gpt-4o-mini"
```

Remove this field if it exists:

```python
gemini_api_key: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_settings_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/service_c/settings_service.py backend/tests/test_settings_service.py
git commit -m "feat: add gemma4 vllm fallback settings"
```

---

### Task 2: Developer C Understanding Gemma4 vLLM Fallback Client

**Files:**
- Modify: `backend/app/agents/agent_c/understanding_llm_client.py`
- Test: `backend/tests/test_understanding_llm_client.py`

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_understanding_llm_client.py`, remove imports and tests for `GeminiUnderstandingLLMClient` and `_extract_gemini_structured_json`.

Add imports:

```python
from backend.app.agents.agent_c.understanding_llm_client import (
    FallbackUnderstandingLLMClient,
    OpenAICompatibleUnderstandingLLMClient,
    _extract_chat_completion_structured_json,
)
```

Add this test:

```python
def test_extract_chat_completion_structured_json_preserves_usage() -> None:
    result = _extract_chat_completion_structured_json(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "intent": "state_visit_purpose",
                                "intent_success": True,
                                "confidence": 0.91,
                                "meaning_summary_kr": "방문 목적을 말했다.",
                                "emotion": "calm",
                                "answer_relevance": "on_topic",
                                "ambiguity_type": "none",
                                "risk_delta": 0,
                                "risk_reason": "No risk expression was found.",
                                "risk_tags": [],
                                "extracted_slots": {"visit_purpose": "tourism"},
                                "missing_slots": [],
                                "needs_clarification": False,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        }
    )

    assert result["extracted_slots"] == {"visit_purpose": "tourism"}
    assert result["__llm_usage"] == {
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
    }
```

Add this test:

```python
def test_openai_compatible_understanding_client_calls_vllm_chat_completions(
    monkeypatch: pytest.MonkeyPatch,
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
                                    "intent": "state_visit_purpose",
                                    "intent_success": True,
                                    "confidence": 0.91,
                                    "meaning_summary_kr": "방문 목적을 말했다.",
                                    "emotion": "calm",
                                    "answer_relevance": "on_topic",
                                    "ambiguity_type": "none",
                                    "risk_delta": 0,
                                    "risk_reason": "No risk expression was found.",
                                    "risk_tags": [],
                                    "extracted_slots": {"visit_purpose": "tourism"},
                                    "missing_slots": [],
                                    "needs_clarification": False,
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
    client = OpenAICompatibleUnderstandingLLMClient(
        api_key="dummy",
        model="google/gemma-4-26B-A4B-it",
        base_url="http://100.95.34.69:8001/v1",
    )

    result = client.analyze({"player_text": "I'm here for tourism."})

    assert result["intent"] == "state_visit_purpose"
    assert calls[0]["args"][0] == "http://100.95.34.69:8001/v1/chat/completions"
    assert calls[0]["kwargs"]["headers"]["Authorization"] == "Bearer dummy"
    assert calls[0]["kwargs"]["json"]["model"] == "google/gemma-4-26B-A4B-it"
```

Add this test:

```python
class _UnavailableUnderstandingClient:
    model = "primary"

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise UnderstandingLLMUnavailable("primary unavailable")


class _SuccessfulUnderstandingClient:
    model = "google/gemma-4-26B-A4B-it"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {
            "intent": "state_visit_purpose",
            "intent_success": True,
            "confidence": 0.91,
            "meaning_summary_kr": "방문 목적을 말했다.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "extracted_slots": {"visit_purpose": "tourism"},
            "missing_slots": [],
            "needs_clarification": False,
            "__llm_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }


def test_fallback_understanding_client_uses_gemma4_after_primary_failure() -> None:
    fallback = _SuccessfulUnderstandingClient()
    client = FallbackUnderstandingLLMClient(
        primary=_UnavailableUnderstandingClient(),
        fallback=fallback,
    )

    result = client.analyze({"player_text": "I'm here for tourism."})

    assert result["intent"] == "state_visit_purpose"
    assert result["__fallback_model"] == "google/gemma-4-26B-A4B-it"
    assert fallback.calls == [{"player_text": "I'm here for tourism."}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_understanding_llm_client.py -q
```

Expected: FAIL with missing `OpenAICompatibleUnderstandingLLMClient`, `_extract_chat_completion_structured_json`, or `FallbackUnderstandingLLMClient`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/agents/agent_c/understanding_llm_client.py`, remove `GeminiUnderstandingLLMClient` and `_extract_gemini_structured_json`.

Add:

```python
@dataclass(frozen=True)
class OpenAICompatibleUnderstandingLLMClient:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 10.0

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _developer_instructions()},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 600,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise UnderstandingLLMUnavailable(
                f"OpenAI-compatible Understanding LLM request failed: {_http_status_error_detail(exc)}"
            ) from exc
        except httpx.HTTPError as exc:
            raise UnderstandingLLMUnavailable(
                f"OpenAI-compatible Understanding LLM request failed: {exc}"
            ) from exc
        except ValueError as exc:
            raise UnderstandingLLMUnavailable(
                "OpenAI-compatible Understanding LLM returned non-JSON response."
            ) from exc

        return _extract_chat_completion_structured_json(data)


@dataclass(frozen=True)
class FallbackUnderstandingLLMClient:
    primary: UnderstandingLLMClient
    fallback: UnderstandingLLMClient

    @property
    def model(self) -> str:
        return self.primary.model

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.primary.analyze(payload)
        except UnderstandingLLMUnavailable:
            result = self.fallback.analyze(payload)
            result["__fallback_model"] = self.fallback.model
            return result
```

Update factory:

```python
def build_understanding_llm_client_from_settings(
    settings: AppSettings | None = None,
) -> UnderstandingLLMClient:
    resolved_settings = settings or get_settings()
    primary = OpenAIUnderstandingLLMClient.from_settings(resolved_settings)
    if resolved_settings.murphy_understanding_llm_fallback == "gemma4_vllm":
        fallback = OpenAICompatibleUnderstandingLLMClient(
            api_key=resolved_settings.gemma4_vllm_api_key,
            model=resolved_settings.gemma4_vllm_model,
            base_url=resolved_settings.gemma4_vllm_base_url,
            timeout_seconds=resolved_settings.murphy_understanding_llm_timeout_seconds,
        )
        return FallbackUnderstandingLLMClient(primary=primary, fallback=fallback)
    return primary
```

Add parser:

```python
def _extract_chat_completion_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices")
    if not isinstance(choices, list):
        raise UnderstandingLLMUnavailable("OpenAI-compatible response did not include choices.")
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = str(message.get("content") or "").strip()
        if content:
            result = _normalize_structured_result(json.loads(_strip_json_fence(content)))
            result["__llm_usage"] = _extract_chat_completion_usage(data)
            return result
    raise UnderstandingLLMUnavailable("OpenAI-compatible response did not include message content.")


def _extract_chat_completion_usage(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    input_tokens = _int_or_zero(usage.get("prompt_tokens"))
    output_tokens = _int_or_zero(usage.get("completion_tokens"))
    total_tokens = _int_or_zero(usage.get("total_tokens")) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _strip_json_fence(text: str) -> str:
    if text.startswith("```json"):
        return text.removeprefix("```json").removesuffix("```").strip()
    if text.startswith("```"):
        return text.removeprefix("```").removesuffix("```").strip()
    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_understanding_llm_client.py backend/tests/test_understanding_agent.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/agents/agent_c/understanding_llm_client.py backend/tests/test_understanding_llm_client.py
git commit -m "feat: add gemma4 vllm fallback for understanding"
```

---

### Task 3: Developer A NPC Dialogue Gemma4 vLLM Fallback Client

**Files:**
- Modify: `backend/app/agents/agent_a/npc_llm_client.py`
- Modify: `backend/app/agents/agent_a/npc_dialogue_agent.py`
- Test: `backend/tests/test_developer_a_npc_llm_client.py`

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_developer_a_npc_llm_client.py`, remove Gemini tests and imports.

Add imports:

```python
from backend.app.agents.agent_a.npc_llm_client import (
    FallbackNPCDialogueLLMClient,
    NPCDialogueLLMUnavailable,
    OpenAICompatibleNPCDialogueLLMClient,
    build_npc_dialogue_llm_client_from_environment,
)
```

Add:

```python
def test_openai_compatible_npc_dialogue_client_calls_vllm_chat_completions(monkeypatch) -> None:
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
                                    "feedback_kr": "짧고 분명하게 말해보세요.",
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
```

Add:

```python
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
            "feedback_kr": "짧고 분명하게 말해보세요.",
            "tone": "formal_firm",
            "animation": "officer_check_passport",
            "llm_reason": "fallback success",
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
```

Add:

```python
def test_npc_dialogue_llm_factory_uses_gemma4_fallback(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "NPC_DIALOGUE_LLM_PROVIDER=openai",
                "OPENAI_API_KEY=sk-test",
                "NPC_DIALOGUE_LLM_MODEL=gpt-4o-mini",
                "NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm",
                "GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1",
                "GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it",
                "GEMMA4_VLLM_API_KEY=dummy",
            ]
        ),
        encoding="utf-8",
    )
    for key in [
        "NPC_DIALOGUE_LLM_PROVIDER",
        "OPENAI_API_KEY",
        "NPC_DIALOGUE_LLM_MODEL",
        "NPC_DIALOGUE_LLM_FALLBACK",
        "GEMMA4_VLLM_BASE_URL",
        "GEMMA4_VLLM_MODEL",
        "GEMMA4_VLLM_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    client = build_npc_dialogue_llm_client_from_environment(env_file)

    assert isinstance(client, FallbackNPCDialogueLLMClient)
    assert client.fallback.model == "google/gemma-4-26B-A4B-it"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_llm_client.py -q
```

Expected: FAIL with missing OpenAI-compatible or fallback classes.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/agents/agent_a/npc_llm_client.py`, remove `GeminiNPCDialogueLLMClient`, `_extract_gemini_structured_json`, and Gemini factory branch.

Add:

```python
@dataclass(frozen=True)
class OpenAICompatibleNPCDialogueLLMClient:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 10.0

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _developer_instructions()},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "temperature": 0.2,
                "max_tokens": 500,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return _extract_chat_completion_structured_json(data)


@dataclass(frozen=True)
class FallbackNPCDialogueLLMClient:
    primary: NPCDialogueLLMClient
    fallback: NPCDialogueLLMClient

    @property
    def model(self) -> str:
        return getattr(self.primary, "model", "unknown")

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.primary.generate(payload)
        except (NPCDialogueLLMUnavailable, httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError):
            result = self.fallback.generate(payload)
            result["__fallback_model"] = getattr(self.fallback, "model", "unknown")
            return result
```

Add parser:

```python
def _extract_chat_completion_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices")
    if not isinstance(choices, list):
        raise NPCDialogueLLMUnavailable("OpenAI-compatible response did not include choices.")
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = str(message.get("content") or "").strip()
        if content:
            result = json.loads(_strip_json_fence(content))
            result["__llm_usage"] = _extract_chat_completion_usage(data)
            return result
    raise NPCDialogueLLMUnavailable("OpenAI-compatible response did not include message content.")


def _extract_chat_completion_usage(data: dict[str, Any]) -> dict[str, int]:
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


def _strip_json_fence(text: str) -> str:
    if text.startswith("```json"):
        return text.removeprefix("```json").removesuffix("```").strip()
    if text.startswith("```"):
        return text.removeprefix("```").removesuffix("```").strip()
    return text
```

Update factory:

```python
def build_npc_dialogue_llm_client_from_environment(
    env_path: Path | None = None,
) -> NPCDialogueLLMClient:
    values = _read_env_file(env_path or Path(".env"))
    provider = (
        os.getenv("NPC_DIALOGUE_LLM_PROVIDER")
        or values.get("NPC_DIALOGUE_LLM_PROVIDER")
        or "openai"
    ).strip().lower()
    if provider != "openai":
        raise NPCDialogueLLMUnavailable(f"Unsupported NPC dialogue provider: {provider}")

    primary = OpenAINPCDialogueLLMClient.from_environment(env_path)
    fallback = (
        os.getenv("NPC_DIALOGUE_LLM_FALLBACK")
        or values.get("NPC_DIALOGUE_LLM_FALLBACK")
        or "none"
    ).strip().lower()
    if fallback == "gemma4_vllm":
        return FallbackNPCDialogueLLMClient(
            primary=primary,
            fallback=OpenAICompatibleNPCDialogueLLMClient(
                api_key=os.getenv("GEMMA4_VLLM_API_KEY") or values.get("GEMMA4_VLLM_API_KEY", "dummy"),
                model=os.getenv("GEMMA4_VLLM_MODEL")
                or values.get("GEMMA4_VLLM_MODEL", "google/gemma-4-26B-A4B-it"),
                base_url=os.getenv("GEMMA4_VLLM_BASE_URL")
                or values.get("GEMMA4_VLLM_BASE_URL", "http://100.95.34.69:8001/v1"),
                timeout_seconds=float(
                    os.getenv("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS")
                    or values.get("NPC_DIALOGUE_LLM_TIMEOUT_SECONDS", "10")
                ),
            ),
        )
    return primary
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_llm_client.py backend/tests/test_developer_a_npc_dialogue.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/agents/agent_a/npc_llm_client.py backend/app/agents/agent_a/npc_dialogue_agent.py backend/tests/test_developer_a_npc_llm_client.py
git commit -m "feat: add gemma4 vllm fallback for npc dialogue"
```

---

### Task 4: Runtime Env Docs에서 Gemini 제거 및 Gemma4 Fallback 설정 추가

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/contracts/developer_c_adapter_contracts.md`
- Modify: `docs/contracts/developer_c_schema_contract.md`
- Modify: `docs/handoff.md`
- Modify: `docs/implementation_logs/developer_a_implementation_log_kimyonghee.md`

- [ ] **Step 1: Update `.env.example`**

Remove:

```env
GEMINI_API_KEY=
MURPHY_UNDERSTANDING_LLM_PROVIDER=gemini
NPC_DIALOGUE_LLM_PROVIDER=gemini
```

Add:

```env
# Shared Gemma4 vLLM fallback endpoint.
# This server exposes an OpenAI-compatible /v1/chat/completions API.
GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1
GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it
GEMMA4_VLLM_API_KEY=dummy

MURPHY_UNDERSTANDING_LLM_PROVIDER=openai
MURPHY_UNDERSTANDING_LLM_FALLBACK=none
MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini

NPC_DIALOGUE_LLM_PROVIDER=openai
NPC_DIALOGUE_LLM_FALLBACK=none
NPC_DIALOGUE_LLM_MODEL=gpt-4o-mini
```

For GPT outage local use, document these exact values in comments:

```env
# GPT outage fallback:
# MURPHY_UNDERSTANDING_LLM_FALLBACK=gemma4_vllm
# NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm
```

- [ ] **Step 2: Update `README.md`**

Replace the Gemini section with:

```text
# GPT primary with Gemma4 vLLM fallback
OPENAI_API_KEY=...
GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1
GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it
GEMMA4_VLLM_API_KEY=dummy

MURPHY_UNDERSTANDING_MODE=llm
MURPHY_UNDERSTANDING_LLM_PROVIDER=openai
MURPHY_UNDERSTANDING_LLM_FALLBACK=gemma4_vllm
MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini

MURPHY_NPC_DIALOGUE_MODE=llm
NPC_DIALOGUE_LLM_PROVIDER=openai
NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm
NPC_DIALOGUE_LLM_MODEL=gpt-4o-mini
```

Add this note:

```text
Gemma4 is served by vLLM as an OpenAI-compatible API, so the project calls
`/v1/chat/completions` with `api_key=dummy`. Automated tests still use rule/fake
modes and do not depend on the academy server.
```

- [ ] **Step 3: Update C contract docs**

In `docs/contracts/developer_c_adapter_contracts.md`, replace Gemini wording with:

```markdown
- `MURPHY_UNDERSTANDING_LLM_FALLBACK=gemma4_vllm` tries the academy Gemma4 vLLM
  OpenAI-compatible endpoint after the primary OpenAI client fails.
- Gemma4 fallback settings:
  - `GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1`
  - `GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it`
  - `GEMMA4_VLLM_API_KEY=dummy`
```

In `docs/contracts/developer_c_schema_contract.md`, add rows:

```markdown
| `GEMMA4_VLLM_BASE_URL` | `http://100.95.34.69:8001/v1` | Academy vLLM OpenAI-compatible base URL |
| `GEMMA4_VLLM_MODEL` | `google/gemma-4-26B-A4B-it` | Gemma4 fallback model |
| `GEMMA4_VLLM_API_KEY` | `dummy` | vLLM fallback API key placeholder |
| `MURPHY_UNDERSTANDING_LLM_FALLBACK` | `none` | `none` or `gemma4_vllm` |
```

- [ ] **Step 4: Update handoff and Developer A implementation log**

Append to `docs/handoff.md`:

```markdown
Gemma4 vLLM fallback support replaces the previous temporary Gemini provider plan.
The academy server is OpenAI-compatible vLLM at `http://100.95.34.69:8001/v1`
with model `google/gemma-4-26B-A4B-it` and dummy API key. Enable fallback with
`MURPHY_UNDERSTANDING_LLM_FALLBACK=gemma4_vllm` and
`NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm`.
```

Append to `docs/implementation_logs/developer_a_implementation_log_kimyonghee.md`:

```markdown
## 2026-06-05 01:30:00 +09:00

- Gemini provider 설정을 제거하고 학원 서버 Gemma4 vLLM OpenAI-compatible fallback으로 전환한다.
- Developer A NPC Dialogue LLM은 primary OpenAI 실패 시 `google/gemma-4-26B-A4B-it`를 `/v1/chat/completions`로 호출할 수 있게 한다.
- fallback은 `NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm`일 때만 활성화된다.
```

- [ ] **Step 5: Run docs/config search**

Run:

```powershell
rg -n "GEMINI|gemini|GEMMA4_VLLM|gemma4_vllm|google/gemma-4-26B-A4B-it" .env.example README.md backend docs
```

Expected:

- No active runtime setting named `GEMINI_API_KEY`.
- No Gemini client class remains under `backend/app`.
- Gemma4 settings are present in `.env.example`, README, contracts, handoff, and tests.

- [ ] **Step 6: Commit**

```powershell
git add .env.example README.md docs/contracts/developer_c_adapter_contracts.md docs/contracts/developer_c_schema_contract.md docs/handoff.md docs/implementation_logs/developer_a_implementation_log_kimyonghee.md
git commit -m "docs: document gemma4 vllm fallback mode"
```

---

### Task 5: Local Integration Smoke for Gemma4 and WAV Generation

**Files:**
- No required code files.
- Optional runtime output under `backend/runtime/generated/audio/`.

- [ ] **Step 1: Verify academy vLLM server still responds**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run python -c "import httpx, json; base='http://100.95.34.69:8001/v1'; r=httpx.post(base+'/chat/completions', headers={'Authorization':'Bearer dummy','Content-Type':'application/json'}, json={'model':'google/gemma-4-26B-A4B-it','messages':[{'role':'user','content':'Reply with only OK.'}],'max_tokens':16,'temperature':0}, timeout=30); print(r.status_code); print(r.text[:1000])"
```

Expected:

```text
200
... "content":"OK" ...
```

- [ ] **Step 2: Run focused automated tests**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_understanding_llm_client.py backend/tests/test_developer_a_npc_llm_client.py backend/tests/test_settings_service.py -q
```

Expected: PASS.

- [ ] **Step 3: Run real endpoint WAV smoke with Gemma4 fallback enabled**

Start the API server in one terminal:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'
$env:OPENAI_API_KEY=''
$env:GEMMA4_VLLM_BASE_URL='http://100.95.34.69:8001/v1'
$env:GEMMA4_VLLM_MODEL='google/gemma-4-26B-A4B-it'
$env:GEMMA4_VLLM_API_KEY='dummy'
$env:MURPHY_STT_MODE='mock'
$env:MURPHY_TTS_MODE='real'
$env:MURPHY_UNDERSTANDING_MODE='llm'
$env:MURPHY_UNDERSTANDING_LLM_PROVIDER='openai'
$env:MURPHY_UNDERSTANDING_LLM_FALLBACK='gemma4_vllm'
$env:MURPHY_NPC_DIALOGUE_MODE='llm'
$env:NPC_DIALOGUE_LLM_PROVIDER='openai'
$env:NPC_DIALOGUE_LLM_FALLBACK='gemma4_vllm'
uv run uvicorn backend.app.main:app --reload --port 8000
```

In another terminal, send the demo request:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/game/ai/respond `
  -F "turn=<demo/input/imm_002_purpose.json;type=application/json" `
  -F "audio=@samples/utterance-20260603-163237.wav;type=audio/wav"
```

Expected:

- HTTP 200 response.
- Response contains `npc.audio_url`.
- Generated wav path exists under `backend/runtime/generated/audio/kokoro/`.
- Developer A AgentRun metadata records model name `google/gemma-4-26B-A4B-it` when fallback was used.

- [ ] **Step 4: Run final verification**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest -q
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run ruff check .
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run mypy .
git diff --check
```

Expected:

- `pytest`: PASS.
- `ruff`: PASS.
- `mypy`: PASS.
- `git diff --check`: exit code 0.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/agents/agent_c/understanding_llm_client.py backend/app/agents/agent_a/npc_llm_client.py backend/app/services/service_c/settings_service.py backend/tests/test_understanding_llm_client.py backend/tests/test_developer_a_npc_llm_client.py backend/tests/test_settings_service.py .env.example README.md docs/contracts/developer_c_adapter_contracts.md docs/contracts/developer_c_schema_contract.md docs/handoff.md docs/implementation_logs/developer_a_implementation_log_kimyonghee.md
git commit -m "feat: add gemma4 vllm fallback provider"
```

---

## Self-Review

- Spec coverage: The plan removes the temporary Gemini provider path and replaces it with academy Gemma4 vLLM fallback for Developer C Understanding and Developer A NPC Dialogue. It keeps OpenAI as primary and makes fallback opt-in through env variables, so switching remains easy.
- Ownership check: Developer C-owned files include settings, Understanding client, contracts, handoff, and tests. Developer A-owned files include NPC Dialogue LLM client and implementation log. The plan documents both ownership areas and requires docs updates.
- Test strategy: Tests do not require real API keys or the academy server. Network smoke is isolated in Task 5 and only runs manually after code passes.
- Placeholder scan: All code snippets, commands, expected outputs, paths, env names, and model names are concrete.
- Type consistency: Settings names are consistent across tasks: `GEMMA4_VLLM_BASE_URL`, `GEMMA4_VLLM_MODEL`, `GEMMA4_VLLM_API_KEY`, `MURPHY_UNDERSTANDING_LLM_FALLBACK`, and `NPC_DIALOGUE_LLM_FALLBACK`.
