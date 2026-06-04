# NPC Dialogue Tool Middleware Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NPC Dialogue Agent 전용 tool/middleware를 추가해 “어디서 어떤 데이터를 받아서, 어떻게 정제하고, 어떤 출력이 나왔는지”를 사람이 설명 가능한 trace JSON으로 남긴다.

**Architecture:** FastAPI 전역 middleware는 건드리지 않고 Developer A 내부 pipeline middleware만 추가한다. `tool_a`는 입력/정제/출력 snapshot을 만드는 순수 도구로 두고, `middleware_a`는 실행 단계 시작/종료/실패를 기록하는 trace 조립 계층으로 둔다.

**Tech Stack:** Python 3.12, dataclasses, pathlib, json, 기존 Developer A agent/service 구조, uv.

---

## 1. 설계 기준

이번 변경은 NPC Dialogue Agent 내부에서만 사용한다.

- Developer A 소유 경로만 새로 추가/수정한다.
- Developer C의 FastAPI 전역 middleware, orchestrator 동작 방식은 변경하지 않는다.
- 루트 `tools/__init__.py`, `middleware/__init__.py`는 import/export 없이 공용 설명만 둔다.
- 추적 결과(trace)는 디버깅과 발표 설명용이며, Unreal 응답 계약을 직접 바꾸지 않는다.
- API key, 원본 음성 파일, 민감한 파일 경로는 trace에 저장하지 않는다.

## 2. 최종 파일 구조

```text
backend/app/
  tools/
    __init__.py
    tool_a/
      __init__.py
      npc_dialogue_trace_tool.py

  middleware/
    __init__.py
    middleware_a/
      __init__.py
      npc_dialogue_trace_middleware.py

  agents/
    agent_a/
      npc_dialogue_agent.py

  services/
    service_a/
      voice_output_service.py

backend/tests/
  test_developer_a_npc_dialogue_trace.py

docs/implementation_logs/
  developer_a_implementation_log_kimyonghee.md
```

## 3. Trace JSON 목표 형태

최종 metadata 또는 별도 trace 파일에 아래 구조를 남긴다.

```json
{
  "trace_id": "npcdlg_20260604_000000_IMM_003_DURATION",
  "agent": "npc_dialogue_agent",
  "owner": "developer_a",
  "input_source": {
    "source_agent": "level_design_agent",
    "node_id": "IMM_003_DURATION",
    "npc_id": "officer_miller",
    "player_text": "I will stay five days"
  },
  "steps": [
    {
      "name": "receive_level_design_json",
      "status": "success",
      "input_keys": ["node_id", "npc", "player", "evaluation"],
      "output_summary": "Level Design Agent JSON 수신"
    },
    {
      "name": "normalize_level_design_payload",
      "status": "success",
      "input_summary": "원본 Level Design JSON",
      "output_summary": "NPCDialogueInput 생성"
    },
    {
      "name": "build_dialogue_policy",
      "status": "success",
      "output": {
        "tone": "formal_supportive",
        "branch_type": "success",
        "target_slot": "stay_address"
      }
    },
    {
      "name": "generate_npc_dialogue",
      "status": "success",
      "output": {
        "npc_text": "Alright. You'll stay for five days. Where will you be staying?",
        "tts_text": "Alright. You'll stay for five days. ... Where will you be staying?"
      }
    },
    {
      "name": "build_tts_request",
      "status": "success",
      "output": {
        "voice_id": "am_michael",
        "speed": 0.92,
        "lang_code": "a"
      }
    },
    {
      "name": "synthesize_voice_output",
      "status": "success",
      "output": {
        "audio_url": "http://localhost:8000/runtime/audio/kokoro/IMM_003_DURATION_stay_address_success_am_michael_02160baf.wav",
        "duration_ms": 4625
      }
    }
  ],
  "final_output": {
    "npc_text": "Alright. You'll stay for five days. Where will you be staying?",
    "audio_url": "http://localhost:8000/runtime/audio/kokoro/IMM_003_DURATION_stay_address_success_am_michael_02160baf.wav",
    "fallback_used": false
  }
}
```

## 4. Task 1: Tool/Middleware 패키지 생성

**Files:**
- Create: `backend/app/tools/__init__.py`
- Create: `backend/app/tools/tool_a/__init__.py`
- Create: `backend/app/middleware/__init__.py`
- Create: `backend/app/middleware/middleware_a/__init__.py`

- [ ] **Step 1: 패키지 초기화 파일 작성**

```python
# backend/app/tools/__init__.py
"""개발자별 내부 실행 도구 패키지."""
```

```python
# backend/app/tools/tool_a/__init__.py
"""Developer A NPC dialogue 전용 tool 패키지."""
```

```python
# backend/app/middleware/__init__.py
"""개발자별 내부 pipeline middleware 패키지."""
```

```python
# backend/app/middleware/middleware_a/__init__.py
"""Developer A NPC dialogue 전용 middleware 패키지."""
```

- [ ] **Step 2: 경로 확인**

Run:

```powershell
rg --files backend/app/tools backend/app/middleware
```

Expected:

```text
backend/app/tools/__init__.py
backend/app/tools/tool_a/__init__.py
backend/app/middleware/__init__.py
backend/app/middleware/middleware_a/__init__.py
```

## 5. Task 2: NPC Dialogue Trace Tool 추가

**Files:**
- Create: `backend/app/tools/tool_a/npc_dialogue_trace_tool.py`
- Test: `backend/tests/test_developer_a_npc_dialogue_trace.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
from backend.app.tools.tool_a.npc_dialogue_trace_tool import (
    summarize_level_design_input,
    summarize_tts_request,
)


def test_summarize_level_design_input_exposes_source_data_without_api_secrets() -> None:
    payload = {
        "node_id": "IMM_003_DURATION",
        "npc": {"npc_id": "officer_miller", "emotion": "neutral"},
        "player": {"utterance": "I will stay five days", "language_level": "beginner"},
        "evaluation": {"branch_type": "success", "target_slot": "stay_address"},
        "OPENAI_API_KEY": "should_not_appear",
    }

    summary = summarize_level_design_input(payload)

    assert summary == {
        "source_agent": "level_design_agent",
        "node_id": "IMM_003_DURATION",
        "npc_id": "officer_miller",
        "player_text": "I will stay five days",
        "language_level": "beginner",
        "npc_emotion": "neutral",
        "branch_type": "success",
        "target_slot": "stay_address",
    }
    assert "OPENAI_API_KEY" not in str(summary)


def test_summarize_tts_request_exposes_kokoro_variables() -> None:
    summary = summarize_tts_request(
        {
            "voice": "am_michael",
            "speed": 0.92,
            "lang_code": "a",
            "text": "Where will you be staying?",
        }
    )

    assert summary == {
        "voice_id": "am_michael",
        "speed": 0.92,
        "lang_code": "a",
        "text_length": 27,
    }
```

- [ ] **Step 2: 실패 확인**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue_trace.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'backend.app.tools.tool_a.npc_dialogue_trace_tool'
```

- [ ] **Step 3: tool 구현**

```python
from typing import Any


SENSITIVE_KEYS = {"api_key", "openai_api_key", "authorization", "token", "password"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def summarize_level_design_input(payload: dict[str, Any]) -> dict[str, Any]:
    # 발표용 trace에는 원본 JSON 전체가 아니라 의사결정에 필요한 핵심 값만 남긴다.
    npc = _as_dict(payload.get("npc"))
    player = _as_dict(payload.get("player"))
    evaluation = _as_dict(payload.get("evaluation"))

    return {
        "source_agent": "level_design_agent",
        "node_id": _first_text(payload.get("node_id")),
        "npc_id": _first_text(npc.get("npc_id"), npc.get("id")),
        "player_text": _first_text(player.get("utterance"), player.get("text"), payload.get("player_text")),
        "language_level": _first_text(player.get("language_level"), player.get("level")),
        "npc_emotion": _first_text(npc.get("emotion"), npc.get("emotion_state")),
        "branch_type": _first_text(evaluation.get("branch_type"), payload.get("branch_type")),
        "target_slot": _first_text(evaluation.get("target_slot"), payload.get("target_slot")),
    }


def summarize_tts_request(request: dict[str, Any]) -> dict[str, Any]:
    # Kokoro 실행 변수 중 사람이 디버깅할 수 있는 값만 노출한다.
    text = _first_text(request.get("text"))
    return {
        "voice_id": _first_text(request.get("voice"), request.get("voice_id")),
        "speed": request.get("speed"),
        "lang_code": _first_text(request.get("lang_code")),
        "text_length": len(text),
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue_trace.py -q
```

Expected:

```text
2 passed
```

## 6. Task 3: NPC Dialogue Trace Middleware 추가

**Files:**
- Create: `backend/app/middleware/middleware_a/npc_dialogue_trace_middleware.py`
- Modify: `backend/tests/test_developer_a_npc_dialogue_trace.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from backend.app.middleware.middleware_a.npc_dialogue_trace_middleware import (
    NPCDialogueTraceMiddleware,
)


def test_trace_middleware_records_step_order_and_final_output() -> None:
    middleware = NPCDialogueTraceMiddleware()

    trace = middleware.start(
        trace_id="npcdlg_test",
        input_source={"node_id": "IMM_003_DURATION"},
    )
    middleware.record_step(
        trace,
        name="normalize_level_design_payload",
        status="success",
        input_summary="원본 JSON",
        output_summary="NPCDialogueInput",
    )
    finished = middleware.finish(
        trace,
        final_output={"npc_text": "Where will you be staying?", "fallback_used": False},
    )

    assert finished["trace_id"] == "npcdlg_test"
    assert finished["agent"] == "npc_dialogue_agent"
    assert finished["steps"][0]["name"] == "normalize_level_design_payload"
    assert finished["final_output"]["npc_text"] == "Where will you be staying?"
```

- [ ] **Step 2: 실패 확인**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue_trace.py::test_trace_middleware_records_step_order_and_final_output -q
```

Expected:

```text
ModuleNotFoundError: No module named 'backend.app.middleware.middleware_a.npc_dialogue_trace_middleware'
```

- [ ] **Step 3: middleware 구현**

```python
from datetime import UTC, datetime
from typing import Any


class NPCDialogueTraceMiddleware:
    """NPC Dialogue Agent 내부 실행 단계를 사람이 읽을 수 있는 trace로 조립한다."""

    def start(self, *, trace_id: str, input_source: dict[str, Any]) -> dict[str, Any]:
        return {
            "trace_id": trace_id,
            "agent": "npc_dialogue_agent",
            "owner": "developer_a",
            "started_at": datetime.now(UTC).isoformat(),
            "input_source": input_source,
            "steps": [],
        }

    def record_step(
        self,
        trace: dict[str, Any],
        *,
        name: str,
        status: str,
        input_summary: str | None = None,
        output_summary: str | None = None,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        step = {
            "name": name,
            "status": status,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        if input_summary is not None:
            step["input_summary"] = input_summary
        if output_summary is not None:
            step["output_summary"] = output_summary
        if output is not None:
            step["output"] = output
        if error is not None:
            step["error"] = error
        trace["steps"].append(step)

    def finish(self, trace: dict[str, Any], *, final_output: dict[str, Any]) -> dict[str, Any]:
        trace["finished_at"] = datetime.now(UTC).isoformat()
        trace["final_output"] = final_output
        return trace
```

- [ ] **Step 4: 테스트 통과 확인**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue_trace.py -q
```

Expected:

```text
3 passed
```

## 7. Task 4: NPC Dialogue Agent에 trace 연결

**Files:**
- Modify: `backend/app/agents/agent_a/npc_dialogue_agent.py`
- Modify: `backend/app/services/service_a/voice_output_service.py`
- Modify: `backend/tests/test_developer_a_npc_dialogue_trace.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from backend.app.services.service_a.voice_output_service import build_voice_output_from_level_design


def test_voice_output_from_level_design_contains_explainable_trace() -> None:
    payload = {
        "node_id": "IMM_003_DURATION",
        "npc": {"npc_id": "officer_miller", "emotion": "neutral"},
        "player": {"utterance": "I will stay five days", "language_level": "beginner"},
        "evaluation": {"branch_type": "success", "target_slot": "stay_address"},
    }

    output = build_voice_output_from_level_design(payload, use_llm_dialogue=False, use_real_tts=False)

    assert output.trace is not None
    assert output.trace["input_source"]["node_id"] == "IMM_003_DURATION"
    step_names = [step["name"] for step in output.trace["steps"]]
    assert "receive_level_design_json" in step_names
    assert "normalize_level_design_payload" in step_names
    assert "generate_npc_dialogue" in step_names
    assert "build_tts_request" in step_names
    assert output.trace["final_output"]["npc_text"] == output.dialogue.npc_text
```

- [ ] **Step 2: 실패 확인**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue_trace.py::test_voice_output_from_level_design_contains_explainable_trace -q
```

Expected:

```text
AttributeError: 'VoiceOutput' object has no attribute 'trace'
```

- [ ] **Step 3: `VoiceOutput`에 trace 필드 추가**

`backend/app/services/service_a/voice_output_service.py`의 `VoiceOutput` dataclass에 아래 필드를 추가한다.

```python
trace: dict[str, Any] | None = None
```

기존 `build_voice_output(dialogue)`는 호환성을 위해 `trace=None`으로 둔다.

- [ ] **Step 4: `build_voice_output_from_level_design`에서 trace 생성**

함수 시작부에 아래 흐름을 추가한다.

```python
trace_middleware = NPCDialogueTraceMiddleware()
input_source = summarize_level_design_input(payload)
trace = trace_middleware.start(
    trace_id=f"npcdlg_{input_source.get('node_id', 'unknown')}",
    input_source=input_source,
)
trace_middleware.record_step(
    trace,
    name="receive_level_design_json",
    status="success",
    output={"input_source": input_source},
)
```

정규화 직후:

```python
trace_middleware.record_step(
    trace,
    name="normalize_level_design_payload",
    status="success",
    input_summary="Level Design Agent JSON",
    output_summary="NPCDialogueInput",
)
```

대사 생성 직후:

```python
trace_middleware.record_step(
    trace,
    name="generate_npc_dialogue",
    status="success",
    output={
        "npc_text": dialogue.npc_text,
        "tts_text": dialogue.tts_text,
        "tone": dialogue.tone,
        "animation": dialogue.animation,
    },
)
```

TTS request 생성 직후:

```python
trace_middleware.record_step(
    trace,
    name="build_tts_request",
    status="success",
    output=summarize_tts_request(tts_request.__dict__),
)
```

최종 반환 직전:

```python
trace = trace_middleware.finish(
    trace,
    final_output={
        "npc_text": dialogue.npc_text,
        "audio_url": audio.audio_url,
        "fallback_used": fallback_used,
    },
)
```

- [ ] **Step 5: 테스트 통과 확인**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue_trace.py -q
```

Expected:

```text
4 passed
```

## 8. Task 5: trace 파일 저장 옵션 추가

**Files:**
- Modify: `backend/app/services/service_a/voice_output_service.py`
- Modify: `backend/tests/test_developer_a_npc_dialogue_trace.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
import json


def test_voice_output_writes_trace_file_when_trace_dir_is_provided(tmp_path) -> None:
    payload = {
        "node_id": "IMM_003_DURATION",
        "npc": {"npc_id": "officer_miller"},
        "player": {"utterance": "I will stay five days"},
        "evaluation": {"branch_type": "success", "target_slot": "stay_address"},
    }

    output = build_voice_output_from_level_design(
        payload,
        use_llm_dialogue=False,
        use_real_tts=False,
        trace_dir=tmp_path,
    )

    assert output.trace_path is not None
    trace_data = json.loads(output.trace_path.read_text(encoding="utf-8"))
    assert trace_data["trace_id"] == output.trace["trace_id"]
    assert trace_data["final_output"]["npc_text"] == output.dialogue.npc_text
```

- [ ] **Step 2: 실패 확인**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue_trace.py::test_voice_output_writes_trace_file_when_trace_dir_is_provided -q
```

Expected:

```text
TypeError: build_voice_output_from_level_design() got an unexpected keyword argument 'trace_dir'
```

- [ ] **Step 3: trace 저장 구현**

`VoiceOutput`에 추가:

```python
trace_path: Path | None = None
```

`build_voice_output_from_level_design` 인자에 추가:

```python
trace_dir: Path | None = None
```

저장 로직:

```python
trace_path = None
if trace_dir is not None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"{trace['trace_id']}.json"
    trace_path.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue_trace.py -q
```

Expected:

```text
5 passed
```

## 9. Task 6: 문서와 작업 로그 갱신

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/implementation_logs/developer_a_implementation_log_kimyonghee.md`

- [ ] **Step 1: `AGENTS.md`에 Developer A tool/middleware 소유 경로 추가**

Developer A owned files에 추가:

```markdown
- `backend/app/tools/tool_a/`
- `backend/app/middleware/middleware_a/`
```

공용 규칙에 추가:

```markdown
- `backend/app/tools/__init__.py`와 `backend/app/middleware/__init__.py`는 공용 패키지 marker로만 사용하고 하위 모듈을 import/export하지 않는다.
- Developer A middleware는 FastAPI 전역 middleware가 아니라 NPC Dialogue Agent 내부 pipeline middleware로 제한한다.
```

- [ ] **Step 2: 구현 로그 추가**

`docs/implementation_logs/developer_a_implementation_log_kimyonghee.md` 끝에 추가:

```markdown
## 2026-06-04 HH:MM:SS +09:00

- NPC Dialogue Agent 전용 `tool_a`, `middleware_a` 설계를 구현했다.
- `tool_a`는 Level Design JSON과 TTS request를 발표 가능한 summary로 정리한다.
- `middleware_a`는 receive/normalize/policy/dialogue/tts/final output 단계를 trace JSON으로 기록한다.
- FastAPI 전역 middleware와 Developer C orchestration은 수정하지 않았다.
```

## 10. Task 7: 최종 검증

**Files:**
- No code changes.

- [ ] **Step 1: conflict marker 확인**

Run:

```powershell
rg "<<<<<<<|=======|>>>>>>>" .
```

Expected:

```text
no output
```

- [ ] **Step 2: ruff 실행**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run ruff check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: pytest 실행**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 4: mypy 실행**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run mypy .
```

Expected:

```text
Success: no issues found
```

## 11. 현재 예상 리스크

- 현재 repo는 `uv.lock`의 `numpy` 중복/source 누락 문제로 `uv run` 검증이 실패할 수 있다. 이 경우 이번 구현 문제가 아니라 lock file 복구 이슈로 분리해 기록한다.
- `backend/tests/`는 AGENTS 기준 Developer C 소유다. 이번 요청에서 Developer A 전용 trace 검증이 필요하므로 테스트 추가가 필요하지만, 팀 규칙상 최종 병합 전 Developer C와 테스트 위치 합의를 확인한다.
- `trace`를 Unreal 응답에 바로 포함할지는 아직 결정하지 않는다. 1차 구현은 Python object와 선택적 trace file 저장까지만 제공한다.

## 12. Self-Review

- Spec coverage: tool/middleware 추가, NPC Dialogue Agent 전용 제한, 데이터 수신/정제/출력 가시화, 설명 가능한 trace 산출물을 모두 포함했다.
- Placeholder scan: TBD/TODO 없이 경로, 함수명, 테스트 기대값을 명시했다.
- Type consistency: `VoiceOutput.trace`, `VoiceOutput.trace_path`, `trace_dir`, `NPCDialogueTraceMiddleware`, `summarize_level_design_input`, `summarize_tts_request` 이름을 전 task에서 일관되게 사용했다.

## 13. 실행 방식

권장 실행 방식은 **Inline Execution**이다. 이번 작업은 Developer A 내부 파일 중심이고, 병합 중인 repo 상태라 subagent 병렬화보다 한 세션에서 단계별 검증하는 편이 안전하다.
