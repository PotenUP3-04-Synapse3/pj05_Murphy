# Real Understanding Agent Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Developer C-owned `rule|llm` runtime mode for the Understanding Agent while keeping deterministic tests key-free.

**Architecture:** Keep the current rule analyzer as the default and fallback path. Add a C-owned OpenAI Responses API client that returns only the `UnderstandingOutput` schema, then make `UnderstandingAgent` call it when `MURPHY_UNDERSTANDING_MODE=llm`; failures or invalid output fall back to the rule analyzer. Tool-call/data-flow logging is intentionally left out until Developer A finalizes the shared log file location.

**Tech Stack:** Python 3.12, Pydantic, httpx, OpenAI Responses API-compatible JSON schema payloads, uv, pytest.

---

### Task 1: Runtime Settings

**Files:**
- Modify: `backend/tests/test_settings_service.py`
- Modify: `backend/app/services/service_c/settings_service.py`
- Modify: `.env.example`

- [ ] **Step 1: Write the failing test**

Extend `test_app_settings_reads_values_from_env_file` with:

```text
MURPHY_UNDERSTANDING_MODE=llm
MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini
MURPHY_UNDERSTANDING_LLM_TIMEOUT_SECONDS=10
```

Assert the new `AppSettings` fields are read.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q`

Expected: FAIL because the settings fields do not exist.

- [ ] **Step 3: Implement minimal settings**

Add:

```python
murphy_understanding_mode: Literal["rule", "llm"] = "rule"
murphy_understanding_llm_model: str = "gpt-4o-mini"
murphy_understanding_llm_timeout_seconds: float = 10.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_settings_service.py -q`

Expected: PASS.

### Task 2: LLM Understanding Client and Agent Mode

**Files:**
- Create: `backend/app/agents/agent_c/understanding_llm_client.py`
- Modify: `backend/app/agents/agent_c/understanding_agent.py`
- Create: `backend/tests/test_understanding_agent.py`

- [ ] **Step 1: Write failing tests**

Add tests that instantiate `UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="llm"), llm_client=fake_client)`.

Assert:

- A valid fake LLM response is converted into `UnderstandingOutput`.
- Invalid or forbidden fake LLM output falls back to the rule analyzer.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_understanding_agent.py -q`

Expected: FAIL because `UnderstandingAgent` does not accept settings or an LLM client.

- [ ] **Step 3: Implement minimal LLM mode**

Create a C-owned OpenAI client mirroring A/B's existing httpx pattern and structured JSON extraction. Update `UnderstandingAgent` to:

- Use rule mode by default.
- Call the injected or default LLM client only in `llm` mode.
- Reject forbidden branch/state/hint/NPC fields.
- Validate with `UnderstandingOutput.model_validate`.
- Fall back to rule output on client, HTTP, JSON, or schema failure.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py -q`

Expected: PASS.

### Task 3: Docs and Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/contracts/developer_c_adapter_contracts.md`
- Modify: `docs/contracts/developer_c_schema_contract.md`
- Modify: `docs/contracts/dependency_contract.md`
- Modify: `docs/handoff.md`
- Modify: `docs/portfolio_seanhan.md`
- Modify: `docs/preprototype_status_demo_plan.md`

- [ ] **Step 1: Document runtime mode**

Document deterministic default:

```text
MURPHY_UNDERSTANDING_MODE=rule
```

and real AI mode:

```text
OPENAI_API_KEY=...
MURPHY_UNDERSTANDING_MODE=llm
MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini
MURPHY_UNDERSTANDING_LLM_TIMEOUT_SECONDS=10
```

- [ ] **Step 2: Document logging deferral**

State that C data-flow debug logging is planned after Developer A finalizes the shared log file directory.

- [ ] **Step 3: Run full verification**

Run:

```powershell
uv run pytest
uv run ruff check .
uv run mypy .
git diff --check
```

Expected: PASS, with existing non-blocking warnings only if present.
