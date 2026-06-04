# Real STT Kokoro Endpoint Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable `POST /api/game/ai/respond` to run the existing real STT boundary and Developer A real Kokoro TTS path through local environment toggles.

**Architecture:** Keep Developer A implementation read-only and call its existing `build_voice_output_from_level_design()` service through the C-owned `DevANpcDialogueClient`. Add settings fields that default to deterministic demo mode, then let the adapter pass `use_real_tts` and `use_llm_dialogue` from env-loaded settings.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, uv, pytest, Kokoro, openai-whisper optional extra.

---

### Task 1: Settings Contract

**Files:**
- Modify: `backend/tests/test_settings_service.py`
- Modify: `backend/app/services/service_c/settings_service.py`
- Modify: `.env.example`

- [ ] **Step 1: Write the failing test**

Add assertions that `.env` can set:

```text
MURPHY_TTS_MODE=real
MURPHY_NPC_DIALOGUE_MODE=llm
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q`

Expected: FAIL because `AppSettings` has no TTS or NPC dialogue mode fields.

- [ ] **Step 3: Write minimal implementation**

Add these fields to `AppSettings`:

```python
murphy_tts_mode: Literal["fake", "real"] = "fake"
murphy_npc_dialogue_mode: Literal["rule", "llm"] = "rule"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_settings_service.py -q`

Expected: PASS.

### Task 2: Developer A Adapter Env Toggle

**Files:**
- Modify: `backend/tests/test_preprototype_flow.py`
- Modify: `backend/app/integrations/dev_a_npc_dialogue_client.py`

- [ ] **Step 1: Write the failing test**

Add a fake voice-output builder and instantiate:

```python
DevANpcDialogueClient(
    settings=AppSettings(murphy_tts_mode="real", murphy_npc_dialogue_mode="llm"),
    voice_output_builder=fake_builder,
)
```

Assert that the fake builder receives `use_real_tts=True` and `use_llm_dialogue=True`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_real_tts_and_llm_modes_from_settings -q`

Expected: FAIL because `DevANpcDialogueClient` does not accept `settings` or builder injection.

- [ ] **Step 3: Write minimal implementation**

Let `DevANpcDialogueClient` accept optional `settings`, optional explicit bool overrides, and a `voice_output_builder` callable. Resolve defaults from settings only when explicit bools are omitted.

- [ ] **Step 4: Run tests to verify it passes**

Run: `uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_real_tts_and_llm_modes_from_settings -q`

Expected: PASS.

### Task 3: Demo Usability Docs and Fixture

**Files:**
- Create: `demo/input/imm_002_purpose.json`
- Modify: `README.md`
- Modify: `docs/preprototype_status_demo_plan.md`
- Modify: `docs/contracts/developer_c_adapter_contracts.md`
- Modify: `docs/handoff.md`

- [ ] **Step 1: Add demo fixture**

Create a turn JSON fixture matching the existing test payload so users can run multipart curl without extracting JSON from tests.

- [ ] **Step 2: Document real endpoint mode**

Document:

```text
MURPHY_STT_MODE=local
MURPHY_TTS_MODE=real
MURPHY_NPC_DIALOGUE_MODE=rule
```

and the optional `MURPHY_NPC_DIALOGUE_MODE=llm` OpenAI dialogue mode.

- [ ] **Step 3: Verify**

Run:

```powershell
uv run pytest
uv run ruff check .
uv run mypy .
git diff --check
```

Expected: PASS, with existing non-blocking warnings only if present.
