# NPC Roster Extensibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NPC가 추가될 때 `officer_miller` 하드코딩을 반복 수정하지 않고, NPC 프로필(Profile) 한 곳만 추가하면 대사(Dialogue), 음성(Voice), TTS, 로그(Log)가 같은 방식으로 동작하게 만든다.

**Architecture:** Developer A 영역에 NPC roster registry를 만들고, 기존 `voice_output_service`, `voice_profile_service`, `tts_service`, `npc_dialogue_agent`가 `npc_id`로 registry를 조회하도록 바꾼다. Developer C adapter는 기존 Unreal turn payload의 `npc` 정보를 Developer A payload로 전달만 하며, NPC 대사 생성 권한은 계속 Developer A에 둔다. 알 수 없는 NPC는 안전한 기본값 `officer_miller`로 fallback한다.
AgentRun 로그에는 `dialogue_source_trace`를 추가해 node context, player text preview, Developer B feedback/directive, branch, NPC profile, voice profile 중 어떤 데이터가 다음 대사 생성에 사용됐는지 요약한다.

**Tech Stack:** Python 3.12, uv, FastAPI adapter boundary, Pydantic schemas, pytest, ruff, mypy.

---

## File Structure

- Create: `backend/app/services/service_a/npc_roster_service.py`
  - Developer A 소유. NPC별 이름, 역할(Role), voice 후보, 기본 animation, fallback line, mock voice id를 제공한다.
- Modify: `backend/app/services/service_a/voice_profile_service.py`
  - `officer_miller` 전용 voice 선택 함수를 registry 기반 voice 선택으로 교체한다.
- Modify: `backend/app/services/service_a/tts_service.py`
  - `speaker == "Officer Miller"` 분기 대신 `speaker_id` 또는 registry speaker 이름 기준으로 mock voice를 고른다.
- Modify: `backend/app/services/service_a/voice_output_service.py`
  - payload에서 `npc_id`를 추출하고, voice profile/TTS request/log metadata에 같은 `npc_id`를 사용한다.
  - AgentRun metadata에 다음 대사 생성에 사용한 입력 데이터와 활용 방식을 `dialogue_source_trace`로 기록한다.
- Modify: `backend/app/agents/agent_a/npc_dialogue_agent.py`
  - 대사 결과의 `speaker`, fallback text, animation 기본값을 registry에서 가져온다.
- Modify: `backend/app/integrations/dev_a_npc_dialogue_client.py`
  - Developer C 소유 adapter. `DevADialogueInput.npc`를 Developer A level design payload의 `npc` 필드로 전달한다.
- Test: `backend/tests/test_developer_a_npc_roster.py`
  - registry, unknown NPC fallback, voice profile selection을 검증한다.
- Test: `backend/tests/test_developer_a_agent_run_logging.py`
  - unified AgentRun metadata가 요청 NPC를 기록하는지 검증한다.
  - unified AgentRun metadata가 다음 대사 생성 입력 출처와 활용 목적을 기록하는지 검증한다.
- Test: `backend/tests/test_preprototype_flow.py`
  - C adapter가 `npc` payload를 A builder로 넘기는지 검증한다.
- Modify: `docs/contracts/developer_a_agent_spec.md`
  - `npc` input 필드와 fallback 규칙을 계약에 추가한다.
- Modify: `docs/handoff.md`
  - 변경 파일, 검증 명령, 다음 단계 기록.
- Modify: `docs/implementation_logs/developer_a_implementation_log_kimyonghee.md`
  - Developer A 구현 로그에 NPC roster 구조화 내역 기록.

---

### Task 1: NPC Roster Registry 추가

**Files:**
- Create: `backend/app/services/service_a/npc_roster_service.py`
- Test: `backend/tests/test_developer_a_npc_roster.py`

- [ ] **Step 1: Write the failing test**

```python
from backend.app.services.service_a.npc_roster_service import (
    NPCProfile,
    resolve_npc_profile,
)


def test_resolve_known_npc_profile_for_officer_miller() -> None:
    profile = resolve_npc_profile("OFFICER_MILLER")

    assert profile == NPCProfile(
        npc_id="officer_miller",
        display_name="Officer Miller",
        role="immigration_officer",
        default_animation="officer_check_passport",
        fallback_text="Okay. Please continue.",
        mock_voice_id="officer_miller_mock_baritone",
        kokoro_voices=("am_michael",),
    )
    assert profile.kokoro_voices == ("am_michael",)


def test_resolve_unknown_npc_profile_falls_back_to_officer_miller() -> None:
    profile = resolve_npc_profile("UNKNOWN_NPC")

    assert profile.npc_id == "officer_miller"
    assert profile.display_name == "Officer Miller"
    assert profile.mock_voice_id == "officer_miller_mock_baritone"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_roster.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.services.service_a.npc_roster_service'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/service_a/npc_roster_service.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class NPCProfile:
    npc_id: str
    display_name: str
    role: str
    default_animation: str
    fallback_text: str
    mock_voice_id: str
    # Kokoro 모델에서 지원하는 voice id 중 이 NPC에 배정할 후보 목록이다.
    # 새 NPC를 추가할 때는 Kokoro가 실제 지원하는 voice id만 여기에 넣는다.
    kokoro_voices: tuple[str, ...]


_DEFAULT_NPC_ID = "officer_miller"

_NPC_ROSTER: dict[str, NPCProfile] = {
    "officer_miller": NPCProfile(
        npc_id="officer_miller",
        display_name="Officer Miller",
        role="immigration_officer",
        default_animation="officer_check_passport",
        fallback_text="Okay. Please continue.",
        mock_voice_id="officer_miller_mock_baritone",
        # Officer Miller의 기본 Kokoro voice 후보. NPC별로 이 tuple만 바꾸면 된다.
        kokoro_voices=("am_michael",),
    )
}


def resolve_npc_profile(npc_id: str | None) -> NPCProfile:
    normalized_id = _normalize_npc_id(npc_id)
    return _NPC_ROSTER.get(normalized_id, _NPC_ROSTER[_DEFAULT_NPC_ID])


def _normalize_npc_id(npc_id: str | None) -> str:
    if not npc_id:
        return _DEFAULT_NPC_ID
    return npc_id.strip().lower()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_roster.py -q
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/service_a/npc_roster_service.py backend/tests/test_developer_a_npc_roster.py
git commit -m "feat: add developer a npc roster registry"
```

---

### Task 2: Voice Profile을 NPC Registry 기반으로 변경

**Files:**
- Modify: `backend/app/services/service_a/voice_profile_service.py`
- Test: `backend/tests/test_developer_a_npc_roster.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_developer_a_npc_roster.py`:

```python
from backend.app.services.service_a.voice_profile_service import resolve_voice_profile


def test_resolve_voice_profile_uses_normalized_npc_id_and_roster_voice() -> None:
    profile = resolve_voice_profile(user_id="session_1", npc_id="OFFICER_MILLER")

    assert profile.user_id == "session_1"
    assert profile.npc_id == "officer_miller"
    assert profile.voice_profile_id == "session_1:officer_miller"
    assert profile.provider == "kokoro"
    assert profile.voice_id == "am_michael"


def test_resolve_voice_profile_unknown_npc_uses_default_roster_profile() -> None:
    profile = resolve_voice_profile(user_id="session_1", npc_id="UNKNOWN_NPC")

    assert profile.npc_id == "officer_miller"
    assert profile.voice_profile_id == "session_1:officer_miller"
    assert profile.voice_id == "am_michael"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_roster.py::test_resolve_voice_profile_uses_normalized_npc_id_and_roster_voice backend/tests/test_developer_a_npc_roster.py::test_resolve_voice_profile_unknown_npc_uses_default_roster_profile -q
```

Expected: FAIL because current `resolve_voice_profile()` keeps `OFFICER_MILLER` as-is and uses the old officer-specific selector.

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/services/service_a/voice_profile_service.py`:

```python
from dataclasses import dataclass
import hashlib

from backend.app.services.service_a.npc_roster_service import resolve_npc_profile


@dataclass(frozen=True)
class VoiceProfile:
    user_id: str
    npc_id: str
    voice_profile_id: str
    provider: str
    voice_id: str


def resolve_voice_profile(user_id: str, npc_id: str) -> VoiceProfile:
    """동일 user+npc 조합에는 항상 같은 voice profile을 반환한다."""
    safe_user_id = user_id or "user_unknown"
    npc_profile = resolve_npc_profile(npc_id)
    digest = hashlib.sha256(f"{safe_user_id}:{npc_profile.npc_id}".encode("utf-8")).hexdigest()[:12]
    return VoiceProfile(
        user_id=safe_user_id,
        npc_id=npc_profile.npc_id,
        voice_profile_id=f"{safe_user_id}:{npc_profile.npc_id}",
        provider="kokoro",
        voice_id=_select_voice(digest, npc_profile.kokoro_voices),
    )


def _select_voice(digest: str, voices: tuple[str, ...]) -> str:
    index = int(digest[:4], 16) % len(voices)
    return voices[index]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_roster.py -q
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/service_a/voice_profile_service.py backend/tests/test_developer_a_npc_roster.py
git commit -m "refactor: resolve voice profiles from npc roster"
```

---

### Task 3: Developer C Adapter가 NPC Payload를 Developer A로 전달

**Files:**
- Modify: `backend/app/integrations/dev_a_npc_dialogue_client.py`
- Test: `backend/tests/test_preprototype_flow.py`

- [ ] **Step 1: Write the failing test**

Add or update an adapter test in `backend/tests/test_preprototype_flow.py`:

```python
def test_dev_a_adapter_forwards_npc_context_to_voice_builder() -> None:
    builder_calls = []

    def fake_builder(payload: dict, **kwargs) -> dict:
        builder_calls.append(payload)
        return {
            "speaker": "Officer Miller",
            "npc_text": "Okay. How long will you stay?",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "feedback_kr": "좋아요.",
            "tts": {"audio_url": "/runtime/audio/kokoro/test.wav"},
        }

    request = PrePrototypeRequest(turn=UnrealTurnRequest.model_validate(_turn_payload()), audio=MockAudioInput())
    node_context = OpenKBService().get_node_context("CH0_IMMIGRATION", "IMM_002_PURPOSE")
    client = DevANpcDialogueClient(voice_output_builder=fake_builder)

    client.generate_dialogue(
        DevADialogueInput(
            contract_version="dev_a_dialogue.v1",
            request_id=request.turn.request_id,
            session_id=request.turn.session.session_id,
            current_node_id=request.turn.session.current_node_id,
            player_text="I'm here for tourism.",
            npc=request.turn.npc,
            node_context=node_context,
            understanding=_understanding_output(intent_success=True),
            developer_b_policy=_success_policy_output(),
        )
    )

    assert builder_calls[0]["npc"] == {
        "npc_id": "OFFICER_MILLER",
        "npc_role": "immigration_officer",
        "last_npc_message": "What is the purpose of your visit?",
    }
```

If `_understanding_output()` or `_success_policy_output()` does not exist, reuse the existing helper objects already used by `test_preprototype_flow.py` for `DevADialogueInput`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_npc_context_to_voice_builder -q
```

Expected: FAIL because `_build_level_design_payload()` currently omits `npc`.

- [ ] **Step 3: Write minimal implementation**

Modify `DevANpcDialogueClient._build_level_design_payload()` return dict:

```python
        return {
            "node_id": payload.current_node_id,
            "player_text": payload.player_text,
            "npc": payload.npc.model_dump(),
            "node_context": payload.node_context.model_dump(),
            "understanding": payload.understanding.model_dump(),
            "evaluation_summary": {
                "feedback_note": evaluation.feedback_note or "",
                "main_feedback_tag": evaluation.feedback_tags[0] if evaluation.feedback_tags else "",
                "task_success": evaluation.scores.task_success,
                "clarity": evaluation.scores.clarity,
            },
            "level_hint": policy.level_hint.model_dump(),
            "in_game_feedback": feedback,
            "branch": branch,
            "dialogue_directive": dialogue_directive,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_npc_context_to_voice_builder -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/integrations/dev_a_npc_dialogue_client.py backend/tests/test_preprototype_flow.py
git commit -m "feat: forward npc context to developer a adapter"
```

---

### Task 4: Voice Output Service에서 NPC ID 하드코딩 제거

**Files:**
- Modify: `backend/app/services/service_a/voice_output_service.py`
- Test: `backend/tests/test_developer_a_agent_run_logging.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_developer_a_agent_run_logging.py`:

```python
def test_voice_output_uses_npc_id_from_payload_for_voice_profile_and_log(tmp_path) -> None:
    payload = {
        "chapter_id": "chapter_0_immigration",
        "turn_id": "turn_003",
        "node_id": "IMM_003_DURATION",
        "npc": {"npc_id": "OFFICER_MILLER", "npc_role": "immigration_officer"},
        "player": {"utterance": "I will stay five days", "language_level": "beginner"},
        "evaluation": {"branch_type": "success", "target_slot": "stay_address"},
    }

    output = build_voice_output_from_level_design(
        payload,
        runtime_root=tmp_path / "runtime",
        request_id="req_1",
        session_id="session_1",
        use_llm_dialogue=False,
        use_real_tts=False,
        agent_run_root=tmp_path,
    )

    record = json.loads((tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert output["tts"]["voice_profile_id"] == "session_1:officer_miller"
    assert record["metadata"]["npc_context"]["npc_id"] == "officer_miller"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_uses_npc_id_from_payload_for_voice_profile_and_log -q
```

Expected: FAIL because current code passes hardcoded `officer_miller` to `resolve_voice_profile()` and TTS request.

- [ ] **Step 3: Write minimal implementation**

Modify the voice profile block in `backend/app/services/service_a/voice_output_service.py`:

```python
        npc_id = _npc_id(payload)
        voice_profile = resolve_voice_profile(
            user_id=user_id or str(payload.get("user_id", "")),
            npc_id=npc_id,
        )
        agent_run_middleware.record_event(
            evidence_metadata,
            event="tool_call",
            status="completed",
            tool_name="voice_profile_service.resolve_voice_profile",
            data_loaded={
                "npc_id": voice_profile.npc_id,
                "voice_profile_id": voice_profile.voice_profile_id,
                "voice_id": voice_profile.voice_id,
            },
        )
        tts_request = build_kokoro_provider_request(
            text=str(dialogue.get("tts_text") or dialogue["npc_text"]),
            speaker_id=voice_profile.npc_id,
            voice_profile_id=voice_profile.voice_profile_id,
            kokoro_voice=voice_profile.voice_id,
            tone=str(dialogue["tone"]),
            english_level=str(normalized["english_level"]),
            emotion=str(
                dialogue.get("generation_profile", {})
                .get("npc_emotion", {})
                .get("emotion", "calm_official")
            ),
            emotion_intensity=float(
                dialogue.get("generation_profile", {})
                .get("npc_emotion", {})
                .get("intensity", 0.35)
            ),
        )
```

Update `_npc_id()`:

```python
def _npc_id(payload: dict[str, Any]) -> str:
    npc = _as_dict(payload.get("npc"))
    return resolve_npc_profile(_optional_str(npc.get("npc_id") or npc.get("id"))).npc_id
```

Add import:

```python
from backend.app.services.service_a.npc_roster_service import resolve_npc_profile
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_uses_npc_id_from_payload_for_voice_profile_and_log -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/service_a/voice_output_service.py backend/tests/test_developer_a_agent_run_logging.py
git commit -m "refactor: use npc id from payload in voice output"
```

---

### Task 5: AgentRun 로그에 대사 생성 데이터 활용 내역 추가

**Files:**
- Modify: `backend/app/services/service_a/voice_output_service.py`
- Test: `backend/tests/test_developer_a_agent_run_logging.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_developer_a_agent_run_logging.py`:

```python
def test_voice_output_logs_dialogue_source_trace_for_next_line_generation(tmp_path) -> None:
    payload = {
        "chapter_id": "chapter_0_immigration",
        "turn_id": "turn_003",
        "node_id": "IMM_003_DURATION",
        "npc": {"npc_id": "OFFICER_MILLER", "npc_role": "immigration_officer"},
        "player_text": "I will stay five days",
        "node_context": {
            "npc_question": "How long will you stay?",
            "npc_question_goal": "ask_stay_duration",
            "recommended_expression": "I will stay for five days.",
        },
        "evaluation_summary": {
            "feedback_note": "Duration was understood.",
            "task_success": True,
            "clarity": 0.9,
        },
        "level_hint": {
            "english_level": "beginner",
            "needs_hint": False,
            "recommended_expression": "I will stay for five days.",
        },
        "in_game_feedback": {
            "npc_recast_line_candidate": "You'll stay for five days. Where are you staying?",
            "feedback_strategy": "recast",
        },
        "branch": {"branch_type": "success", "next_node_id": "IMM_004_ADDRESS"},
        "dialogue_directive": {"do_not_generate_npc_text": False},
    }

    build_voice_output_from_level_design(
        payload,
        runtime_root=tmp_path / "runtime",
        request_id="req_1",
        session_id="session_1",
        use_llm_dialogue=False,
        use_real_tts=False,
        agent_run_root=tmp_path,
    )

    record = json.loads((tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    trace = record["metadata"]["dialogue_source_trace"]

    assert trace["npc_profile"]["npc_id"] == "officer_miller"
    assert trace["used_inputs"]["node_context"] == {
        "used_for": "next_question_and_goal",
        "node_id": "IMM_003_DURATION",
        "npc_question_goal": "ask_stay_duration",
    }
    assert trace["used_inputs"]["player_text"]["used_for"] == "dialogue_evidence_preview"
    assert trace["used_inputs"]["developer_b_feedback"]["used_for"] == "recast_candidate_and_feedback_note"
    assert trace["used_inputs"]["branch"]["next_node_id"] == "IMM_004_ADDRESS"
    assert trace["output_decision"]["npc_text_source"] == "developer_b_recast_candidate"
    assert trace["output_decision"]["tts_text_source"] == "tts_text_polisher_service"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_logs_dialogue_source_trace_for_next_line_generation -q
```

Expected: FAIL because current AgentRun metadata has `npc_context`, `tts_summary`, and `fallback`, but no `dialogue_source_trace`.

- [ ] **Step 3: Write minimal implementation**

Add helper to `backend/app/services/service_a/voice_output_service.py`:

```python
def _dialogue_source_trace(
    *,
    payload: dict[str, Any],
    normalized: dict[str, Any],
    dialogue: dict[str, Any],
    tts: dict[str, Any],
) -> dict[str, Any]:
    npc_profile = resolve_npc_profile(_optional_str(_as_dict(payload.get("npc")).get("npc_id")))
    node_context = _as_dict(payload.get("node_context"))
    feedback = _as_dict(payload.get("in_game_feedback"))
    evaluation = _as_dict(payload.get("evaluation_summary"))
    branch = _as_dict(payload.get("branch"))
    candidate_text = str(normalized.get("candidate_text", "")).strip()
    return {
        "npc_profile": {
            "npc_id": npc_profile.npc_id,
            "display_name": npc_profile.display_name,
            "role": npc_profile.role,
        },
        "used_inputs": {
            "node_context": {
                "used_for": "next_question_and_goal",
                "node_id": normalized.get("node_id") or payload.get("node_id"),
                "npc_question_goal": node_context.get("npc_question_goal"),
            },
            "player_text": {
                "used_for": "dialogue_evidence_preview",
                "preview": _preview_text(str(payload.get("player_text") or _as_dict(payload.get("player")).get("utterance") or "")),
            },
            "developer_b_feedback": {
                "used_for": "recast_candidate_and_feedback_note",
                "feedback_strategy": feedback.get("feedback_strategy"),
                "has_candidate_text": bool(candidate_text),
                "feedback_note": evaluation.get("feedback_note"),
            },
            "branch": {
                "used_for": "next_dialogue_direction",
                "branch_type": branch.get("branch_type"),
                "next_node_id": branch.get("next_node_id"),
            },
            "voice_profile": {
                "used_for": "tts_voice_selection",
                "voice_profile_id": tts.get("voice_profile_id"),
                "voice_id": tts.get("voice_id"),
            },
        },
        "output_decision": {
            "npc_text_source": "developer_b_recast_candidate" if candidate_text else "developer_a_fallback",
            "tts_text_source": "tts_text_polisher_service",
            "npc_text_preview": _preview_text(str(dialogue.get("npc_text") or dialogue.get("text") or "")),
            "audio_url": tts.get("audio_url"),
        },
    }


def _preview_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
```

Update `_record_agent_run()` before `middleware.start_run()`:

```python
    evidence_metadata["dialogue_source_trace"] = _dialogue_source_trace(
        payload=payload,
        normalized=normalized,
        dialogue=dialogue,
        tts=tts,
    )
```

Update `_record_failed_agent_run()` with a smaller failure trace:

```python
    evidence_metadata["dialogue_source_trace"] = {
        "npc_profile": {"npc_id": _npc_id(payload)},
        "used_inputs": {
            "player_text": {
                "used_for": "fallback_error_context",
                "preview": _preview_text(str(payload.get("player_text") or _as_dict(payload.get("player")).get("utterance") or "")),
            }
        },
        "output_decision": {
            "npc_text_source": "developer_a_error_fallback",
            "tts_text_source": "developer_a_audio_fallback",
            "audio_url": fallback_tts.get("audio_url"),
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_logs_dialogue_source_trace_for_next_line_generation -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/service_a/voice_output_service.py backend/tests/test_developer_a_agent_run_logging.py
git commit -m "feat: log npc dialogue source trace"
```

---

### Task 6: Dialogue Agent의 Speaker와 Animation을 Registry 기반으로 변경

**Files:**
- Modify: `backend/app/agents/agent_a/npc_dialogue_agent.py`
- Test: `backend/tests/test_developer_a_npc_dialogue.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_developer_a_npc_dialogue.py`:

```python
def test_generate_dialogue_from_level_design_uses_npc_profile_defaults() -> None:
    payload = {
        "node_id": "IMM_002_PURPOSE",
        "npc": {"npc_id": "OFFICER_MILLER"},
        "player_text": "I'm here for tourism.",
        "node_context": {
            "npc_question": "What is the purpose of your visit?",
            "recommended_expression": "I'm here for tourism.",
        },
        "evaluation_summary": {"task_success": True, "clarity": 0.9, "feedback_note": "Good."},
        "level_hint": {"english_level": "beginner", "needs_hint": False, "recommended_expression": "I'm here for tourism."},
        "in_game_feedback": {"npc_recast_line_candidate": "You're here for tourism. How long will you stay?"},
        "branch": {"branch_type": "success", "next_node_id": "IMM_003_DURATION"},
        "dialogue_directive": {"do_not_generate_npc_text": False},
    }

    result = generate_npc_dialogue_from_level_design(payload, use_llm=False)

    assert result["speaker"] == "Officer Miller"
    assert result["animation"] == "officer_check_passport"
```

- [ ] **Step 2: Run test to verify it fails if registry is not used**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue.py::test_generate_dialogue_from_level_design_uses_npc_profile_defaults -q
```

Expected: PASS may occur because existing hardcoding matches Officer Miller. If it passes immediately, add this second assertion to make the test prove fallback normalization:

```python
    payload["npc"] = {"npc_id": "UNKNOWN_NPC"}
    fallback_result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
    assert fallback_result["speaker"] == "Officer Miller"
    assert fallback_result["animation"] == "officer_check_passport"
```

- [ ] **Step 3: Write minimal implementation**

Modify `generate_npc_dialogue_from_level_design()`:

```python
    npc_profile = resolve_npc_profile(_npc_id_from_payload(payload))
```

Use `npc_profile` in result:

```python
    result = {
        "speaker": npc_profile.display_name,
        "npc_text": npc_text,
        "text": npc_text,
        "tts_text": tts_text,
        "feedback_kr": feedback_kr,
        "tone": policy.tone,
        "animation": npc_profile.default_animation,
        "fallback": {"used": False, "reason": None},
    }
```

Add helper:

```python
def _npc_id_from_payload(payload: dict[str, Any]) -> str | None:
    npc = payload.get("npc")
    if isinstance(npc, dict):
        value = npc.get("npc_id") or npc.get("id")
        return str(value) if value else None
    return None
```

Add import:

```python
from backend.app.services.service_a.npc_roster_service import resolve_npc_profile
```

- [ ] **Step 4: Run tests**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_npc_roster.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/agents/agent_a/npc_dialogue_agent.py backend/tests/test_developer_a_npc_dialogue.py
git commit -m "refactor: use npc roster in dialogue generation"
```

---

### Task 7: TTS Mock Voice도 Registry 기반으로 변경

**Files:**
- Modify: `backend/app/services/service_a/tts_service.py`
- Test: `backend/tests/test_developer_a_npc_roster.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_developer_a_npc_roster.py`:

```python
from backend.app.services.service_a.tts_service import TTSRequest, synthesize_speech


def test_mock_tts_uses_roster_mock_voice_for_known_speaker() -> None:
    audio = synthesize_speech(
        TTSRequest(
            text="Passport, please.",
            speaker="Officer Miller",
            tone="formal_neutral",
        )
    )

    assert audio.voice_id == "officer_miller_mock_baritone"
```

- [ ] **Step 2: Run test**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_roster.py::test_mock_tts_uses_roster_mock_voice_for_known_speaker -q
```

Expected: PASS currently, but it still proves backward compatibility. The implementation step removes the hardcoded speaker branch without changing behavior.

- [ ] **Step 3: Write minimal implementation**

Modify `_voice_id()` in `backend/app/services/service_a/tts_service.py`:

```python
from backend.app.services.service_a.npc_roster_service import resolve_npc_profile


def _voice_id(speaker: str) -> str:
    if speaker == "Officer Miller":
        return resolve_npc_profile("officer_miller").mock_voice_id
    return "generic_mock_voice"
```

This is intentionally conservative. Full display-name lookup can be added after a second NPC profile exists.

- [ ] **Step 4: Run tests**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_roster.py backend/tests/test_developer_a_npc_dialogue.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/service_a/tts_service.py backend/tests/test_developer_a_npc_roster.py
git commit -m "refactor: read mock tts voice from npc roster"
```

---

### Task 8: Contract와 Handoff 문서 업데이트

**Files:**
- Modify: `docs/contracts/developer_a_agent_spec.md`
- Modify: `docs/handoff.md`
- Modify: `docs/implementation_logs/developer_a_implementation_log_kimyonghee.md`

- [ ] **Step 1: Update Developer A contract**

Add this section to `docs/contracts/developer_a_agent_spec.md`:

```markdown
## NPC Roster Contract

Developer A resolves NPC presentation through `backend/app/services/service_a/npc_roster_service.py`.

Input payload may include:

```json
{
  "npc": {
    "npc_id": "OFFICER_MILLER",
    "npc_role": "immigration_officer",
    "last_npc_message": "What is the purpose of your visit?"
  }
}
```

Rules:

- `npc.npc_id` is normalized to lowercase internally, for example `OFFICER_MILLER` becomes `officer_miller`.
- Unknown or missing `npc_id` falls back to `officer_miller`.
- NPC-specific speaker display name, default animation, mock voice id, and Kokoro voice candidates come from the roster.
- `kokoro_voices` must contain voice ids supported by the installed Kokoro model. Add a short Korean code comment beside each NPC's `kokoro_voices` tuple explaining why that voice was selected.
- Developer A unified AgentRun metadata includes `dialogue_source_trace`, which explains which input data was used for the next NPC line and how it influenced the output.
- Developer C may pass NPC context through the adapter, but Developer A owns final NPC dialogue text and voice style.
```

- [ ] **Step 2: Update handoff**

Add:

```markdown
## Developer A NPC Roster Extensibility Update - 2026-06-05

Developer A now resolves NPC speaker, voice profile, default animation, and fallback metadata through `npc_roster_service.py`. The current roster contains `officer_miller`; unknown NPC ids fall back to that profile. Kokoro voice ids are configured per NPC through `kokoro_voices`, and comments in the roster mark that these must be selected from the installed Kokoro model's supported voice list. Developer C adapter forwards Unreal `npc` context into Developer A level-design payload, but final NPC dialogue and voice style remain Developer A-owned. Developer A AgentRun metadata now includes `dialogue_source_trace` so reviewers can see which node context, player text, Developer B feedback/directive, branch, NPC profile, and voice profile data shaped the next NPC line.

Verification:

- `uv run pytest backend/tests/test_developer_a_npc_roster.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py -q`
- `uv run pytest backend/tests/test_preprototype_flow.py -q`
- `uv run ruff check .`
- `uv run mypy .`
```

- [ ] **Step 3: Update Developer A implementation log**

Append:

```markdown
## 2026-06-05 00:00:00 +09:00

- 향후 NPC 추가를 쉽게 하기 위해 `npc_roster_service.py`를 추가했다.
- `officer_miller` 하드코딩을 voice profile, dialogue result, TTS mock voice, AgentRun metadata에서 registry 조회 방식으로 줄였다.
- Kokoro voice는 모델에서 지원하는 voice id 중 NPC별 후보를 `kokoro_voices`에 명시하고, 주석으로 선택 의도를 남기도록 했다.
- AgentRun metadata에 `dialogue_source_trace`를 추가해 다음 대사 생성에 사용한 데이터와 활용 목적을 남기도록 했다.
- 새 NPC를 추가할 때는 roster에 `NPCProfile`을 추가하고, 필요한 경우 테스트 fixture만 확장하면 된다.
- 검증:
  - `uv run pytest backend/tests/test_developer_a_npc_roster.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py -q`: PASS
```

- [ ] **Step 4: Run docs diff check**

Run:

```powershell
git diff --check
```

Expected: exit code 0.

- [ ] **Step 5: Commit**

```powershell
git add docs/contracts/developer_a_agent_spec.md docs/handoff.md docs/implementation_logs/developer_a_implementation_log_kimyonghee.md
git commit -m "docs: document npc roster contract"
```

---

### Task 9: Final Verification

**Files:**
- No new code files.
- Verify all files changed in Tasks 1-8.

- [ ] **Step 1: Run focused Developer A tests**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_developer_a_npc_roster.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py -q
```

Expected: PASS.

- [ ] **Step 2: Run C adapter flow tests**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_unified_agent_run_log.py -q
```

Expected: PASS. If local environment enables real LLM mode, set deterministic modes for CI-equivalent verification:

```powershell
$env:MURPHY_STT_MODE='mock'
$env:MURPHY_TTS_MODE='fake'
$env:MURPHY_NPC_DIALOGUE_MODE='rule'
$env:MURPHY_UNDERSTANDING_MODE='rule'
$env:DEV_B_FEEDBACK_LLM_MODE='rule'
```

- [ ] **Step 3: Run static checks**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run ruff check .
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run mypy .
git diff --check
```

Expected: all pass.

- [ ] **Step 4: Run full test suite**

Run:

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'; uv run pytest -q
```

Expected: PASS. If the user's local environment intentionally enables real API LLM tests, record that in `docs/handoff.md` as an environment-specific verification note rather than making CI depend on real API keys.

- [ ] **Step 5: Final commit**

```powershell
git status --short
git add backend/app/services/service_a/npc_roster_service.py backend/app/services/service_a/voice_profile_service.py backend/app/services/service_a/tts_service.py backend/app/services/service_a/voice_output_service.py backend/app/agents/agent_a/npc_dialogue_agent.py backend/app/integrations/dev_a_npc_dialogue_client.py backend/tests/test_developer_a_npc_roster.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py backend/tests/test_preprototype_flow.py docs/contracts/developer_a_agent_spec.md docs/handoff.md docs/implementation_logs/developer_a_implementation_log_kimyonghee.md
git commit -m "feat: structure developer a npc roster"
```

Expected: commit succeeds with only intended files staged.

---

## Self-Review

- Spec coverage: The plan covers adding future NPCs through one roster service, removing `officer_miller` hardcoding from voice profile, TTS request, dialogue output, adapter payload, logs, and contracts.
- Ownership check: Most implementation is Developer A-owned. `backend/app/integrations/dev_a_npc_dialogue_client.py` and `backend/tests/` are Developer C-owned by AGENTS.md, so Task 3 must be treated as a coordinated adapter/verification change.
- Test strategy: Tests are TDD-first and keep real API calls opt-in only. Default verification remains deterministic and restorable with `uv sync`.
- Placeholder scan: 모든 작업 단계가 구체적인 파일, 코드, 명령, 기대 결과를 포함한다.
