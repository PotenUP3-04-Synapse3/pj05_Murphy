# Pre-Prototype ABC Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the pre-prototype integration by wiring Developer C adapters to the merged Developer A voice output and Developer B policy/node implementations.

**Architecture:** Keep Developer A and Developer B implementation packages read-only. Developer C-owned adapters translate C schemas into A/B calls, keep validation authority in C, and assemble the final Unreal-safe response including `npc.audio_url`.

**Tech Stack:** FastAPI, Pydantic v2, uv, pytest, ruff, mypy, local filesystem runtime audio artifacts.

---

### Task 1: Wire Developer B Runtime Through C Adapter

**Files:**
- Modify: `backend/app/integrations/dev_b_level_hint_client.py`
- Modify: `backend/app/services/service_c/openkb_service.py`
- Test: `backend/tests/test_preprototype_flow.py`

- [ ] **Step 1: Write failing tests**

Add assertions that `OpenKBService` loads `IMM_003_DURATION` from `backend/app/data/scenario_nodes.json` and that `DevBPolicyClient` records form issues from the real `EnglishLevelHintAgent`.

- [ ] **Step 2: Run the targeted tests and verify RED**

Run: `uv run pytest backend/tests/test_preprototype_flow.py -q`

Expected: FAIL because the C OpenKB service only supports `IMM_002_PURPOSE` and the C B-adapter is still a mock.

- [ ] **Step 3: Implement minimal C integration**

Update the C adapter to delegate to `backend.app.agents.agent_b.EnglishLevelHintAgent`. Update C OpenKB service to parse `backend/app/data/scenario_nodes.json` into `NodeContext`.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run: `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/dev_b/test_developer_b_policy_engine.py -q`

Expected: PASS.

### Task 2: Add Developer A Voice Artifact To C Response

**Files:**
- Modify: `backend/app/schemas/game_turn.py`
- Modify: `backend/app/integrations/dev_a_npc_dialogue_client.py`
- Modify: `backend/app/services/service_c/response_builder.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_preprototype_flow.py`

- [ ] **Step 1: Write failing tests**

Add assertions that multipart `/api/game/ai/respond` returns `npc.audio_url` and that the URL points under `/runtime/audio/kokoro/`.

- [ ] **Step 2: Run the targeted tests and verify RED**

Run: `uv run pytest backend/tests/test_preprototype_flow.py::test_api_accepts_multipart_turn_json_and_sample_wav -q`

Expected: FAIL because `npc.audio_url` is missing from the schema/response.

- [ ] **Step 3: Implement minimal C integration**

Add nullable `audio_url` to `DevADialogueOutput` and `NpcResponse`. Map C `DevADialogueInput` into A's level-design payload and call `build_voice_output_from_level_design` with fake TTS by default and `/runtime/audio` as URL base. Mount `/runtime/audio` as a static route in FastAPI.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run: `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_developer_a_npc_dialogue.py -q`

Expected: PASS.

### Task 3: Harden C Validator Around Real A/B Output

**Files:**
- Modify: `backend/app/services/service_c/validator.py`
- Test: `backend/tests/test_preprototype_flow.py`

- [ ] **Step 1: Write failing tests**

Add validation tests for inconsistent B hint fields and missing NPC audio URL in final pre-prototype response.

- [ ] **Step 2: Run targeted tests and verify RED**

Run: `uv run pytest backend/tests/test_preprototype_flow.py -q`

Expected: FAIL for the new validator expectations.

- [ ] **Step 3: Implement minimal validation**

Add C-owned rule checks for B output invariants and final response audio URL shape.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run: `uv run pytest backend/tests/test_preprototype_flow.py -q`

Expected: PASS.

### Task 4: Verify And Update Handoff Docs

**Files:**
- Modify: `docs/handoff.md`
- Modify: `docs/preprototype_status_demo_plan.md`

- [ ] **Step 1: Run full verification**

Run: `uv run pytest`, `uv run ruff check .`, and `uv run mypy .`.

- [ ] **Step 2: Update docs**

Record changed files, commands run, known issues, and next step in `docs/handoff.md`. Update pre-prototype status so Demo 3 and real A/B integration reflect the new state.

- [ ] **Step 3: Re-run fast checks**

Run: `uv run pytest backend/tests/test_preprototype_flow.py -q`.

Expected: PASS.
