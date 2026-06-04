# Murphy's Trippin Agent Guide

This file is the shared operating guide for any coding agent working in this
repository as Developer A, Developer B, or Developer C.

## Project Snapshot

Project: Murphy's Trippin - Chaos Travel English Simulator.

Prototype scope: Chapter 0, Immigration Check. The player is a Korean traveler
going through JFK immigration and may answer in English, Korean, or Chaos
Konglish.

Primary backend endpoint target:

```text
POST /api/game/ai/respond
```

Current repository state:

- Python 3.12 `uv` project.
- Minimal Developer C FastAPI app at `backend/app/main.py`.
- Health route: `GET /health`.
- Initial contract docs under `docs/contracts/`.
- Developer C handoff: `docs/handoff.md`.
- Sean Han portfolio: `docs/portfolio_seanhan.md`.
- Developer A implementation exists under `backend/app/agents/agent_a/` and
  `backend/app/services/service_a/`.
- Developer B implementation exists under `backend/app/agents/agent_b/`,
  `backend/app/services/service_b/`, and `backend/app/data/scenario_nodes.json`.
- Developer C adapters now connect merged A/B implementations for the
  integrated AI-only pre-prototype.

## Package Management

Use `uv` only.

Allowed commands:

- `uv init`
- `uv sync`
- `uv add`
- `uv remove`
- `uv lock`
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy .`
- `uv run uvicorn backend.app.main:app --reload`

Forbidden:

- `pip install`
- Poetry
- Pipenv
- Conda
- Manual global package installation

The project must be restorable on another computer with:

```powershell
uv sync
```

## Dependency Contract

Python version: 3.12.

Pinned AI framework versions:

- `langchain==1.3.2`
- `langgraph==1.2.2`

Do not upgrade or downgrade these without updating:

- `docs/contracts/dependency_contract.md`
- `docs/handoff.md`
- `docs/portfolio_seanhan.md`

Tests must pass without real API keys, real STT providers, real TTS providers,
Unreal Engine runtime, or remote OpenKB.

## Shared Editing Rule

Before editing any file, classify it as one of:

- Developer A owned
- Developer B owned
- Developer C owned
- Shared contract
- Unknown

Rules:

- Edit your own files freely.
- Edit shared contracts carefully and document the change.
- Treat another developer's implementation files as read-only.
- Treat unknown files as read-only unless the user explicitly approves editing.
- Do not reformat the whole repository.
- Do not rename, move, or delete another developer's files silently.
- Do not change public contracts without updating docs and handoff notes.

If you need a change from another developer, append a request to
`docs/contracts/change_requests.md` and summarize it in `docs/handoff.md`.

## Developer A Scope

Developer A owns NPC dialogue and voice output.

Likely owned files:

- `backend/app/agents/agent_a/`
- `backend/app/services/service_a/`
- `backend/app/prompts/npc_dialogue_prompt.md`

Responsibilities:

- NPC Dialogue Agent
- TTS
- NPC voice style
- NPC feedback tone
- NPC dialogue generation

Guardrails:

- Do not implement Developer C orchestration logic.
- Do not implement Developer B scenario state or level/hint policy.
- Keep outputs replaceable behind Developer C integration contracts.
- Coordinate expected input/output with
  `backend/app/integrations/dev_a_npc_dialogue_client.py` once that adapter
  exists.

Start prompt:

- `docs/prompts/developer_a_start_prompt.md`

## Developer B Scope

Developer B owns English level, hints, and scenario progression rules.

Likely owned files:

- `backend/app/agents/agent_b/`
- `backend/app/services/service_b/`
- `backend/app/agents/agent_b/feedback_hint_llm_client.py`
- `backend/app/services/service_b/openkb_feedback_writer.py`
- `backend/app/prompts/english_level_hint_prompt.md`
- `backend/app/data/scenario_nodes.json`
- `backend/app/data/scenario_nodes.yaml`
- `backend/app/kb/dev_b/`
- `backend/runtime/openkb/dev_b/`

Responsibilities:

- English Level and Hint Agent
- Scenario State Machine
- Level Adaptation Controller
- LLM-assisted learning feedback and hint text
- Travel Speaking Level rubric and difficulty profile policy
- Scenario node rules
- Hint policy
- OpenKB content design
- OpenKB content authoring
- OpenKB feedback/error runtime write under the `dev_b` namespace
- Focus-on-Form target records
- Out-game feedback seed records
- Result score policy

Guardrails:

- Do not implement Developer A NPC dialogue or voice logic.
- Do not implement Developer C orchestration, STT, validator, or response
  assembler logic.
- Scenario branch control must remain rule-based.
- LLM-assisted Developer B code may generate hint, feedback, report, and rubric
  candidates only. It must not generate or override branch, next node, verdict,
  state delta, Unreal commands, NPC dialogue, or TTS/audio fields.
- Coordinate expected input/output with
  `backend/app/integrations/dev_b_level_hint_client.py` once that adapter
  exists.

Start prompt:

- `docs/prompts/developer_b_start_prompt.md`

## Developer C Scope

Developer C is Sean Han and owns the backend safety and orchestration layer.

Owned files:

- `backend/app/main.py`
- `backend/app/api/ai_respond.py`
- `backend/app/schemas/`
- `backend/app/services/service_c/`
- `backend/app/agents/agent_c/`
- `backend/app/prompts/understanding_prompt.md`
- `backend/app/graphs/developer_c_graph.py`
- `backend/app/integrations/dev_a_npc_dialogue_client.py`
- `backend/app/integrations/dev_b_level_hint_client.py`
- `backend/app/kb/`, except `backend/app/kb/dev_b/`
- `backend/runtime/openkb/`, except `backend/runtime/openkb/dev_b/`
- `backend/tests/`
- `docs/handoff.md`
- `docs/portfolio_seanhan.md`
- `docs/contracts/`

Responsibilities:

- STT Pipeline
- Understanding Agent
- AI Backend Orchestrator
- OpenKB Retrieval
- OpenKB runtime coordination outside B-owned write namespaces
- Validator
- Unreal Response JSON Assembler
- Developer A/B integration adapters
- Developer C tests, contracts, handoff, and portfolio docs

Guardrails:

- Do not implement real Developer A NPC dialogue logic.
- Do not implement real Developer B level/hint or scenario branch logic.
- Do not create or mutate B-owned OpenKB write records; read and validate them
  through agreed contracts.
- Use deterministic mocks until A/B contracts are ready.
- Validator must stay rule-based.
- LangGraph may orchestrate Developer C workflow nodes only. It must not
  replace Developer B scenario branching or bypass validation.

## Integration Direction

Target backend flow:

1. Unreal sends a request to Developer C.
2. Developer C normalizes text input or routes voice input through STT.
3. Developer C loads current node context from OpenKB.
4. Developer C runs the Understanding Agent.
5. Developer C calls Developer B adapter for level, hint, and branch result.
6. Developer B writes feedback/error/focus-on-form records to its OpenKB
   `dev_b` namespace and returns the write reference in its policy output.
7. Developer C validates and consumes the B write reference.
8. Developer C calls Developer A adapter for NPC dialogue result.
9. Developer C builds Unreal-safe response JSON.
10. Developer C validates commands and branch transitions.
11. Developer C returns the response to Unreal.

Developer A and B should expose contracts that can be consumed by Developer C
adapters. Developer C should not import A/B implementation files unless a
contract explicitly allows it.

## Required Verification

Run the checks that apply before handing off work:

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run mypy .
```

If a check fails:

1. Fix it if it is inside your scope.
2. Do not modify another developer's implementation files to make your check
   pass.
3. Use adapter mocks for missing cross-team modules.
4. Document the failure and workaround in `docs/handoff.md`.

## Documentation Expectations

After meaningful changes, update:

- `docs/handoff.md`
- Your own contract docs, if contracts changed
- `docs/portfolio_seanhan.md`, only when Sean Han / Developer C portfolio
  content changes

Keep handoff entries concrete: changed files, commands run, known issues, and
the next recommended step.
