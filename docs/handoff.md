# Handoff

## Current Status

Phase 1 bootstrap is complete, Phase 2 contracts exist, and the AI-only
pre-prototype turn flow is now implemented. The repository has a Developer C
FastAPI backend package, C-side schemas, deterministic mock adapters, a
Whisper-large-v3-turbo STT wrapper, an orchestrator, a minimal validator, and
tests for the mock wav turn flow.

## Last Completed Task

Implemented the pre-prototype AI turn flow without Unreal. A JSON mock request
represents Unreal wav input, Developer C runs the Whisper-large-v3-turbo STT
wrapper, OpenKB lookup, Understanding Agent, Developer B policy adapter,
Developer A dialogue adapter, response builder, and rule-based validator.

## Changed Files

- `docs/contracts/developer_c_contract.md`
- `docs/contracts/developer_c_schema_contract.md`
- `docs/contracts/developer_c_adapter_contracts.md`
- `backend/app/api/__init__.py`
- `backend/app/api/ai_respond.py`
- `backend/app/agents/__init__.py`
- `backend/app/agents/understanding_agent.py`
- `backend/app/integrations/__init__.py`
- `backend/app/integrations/dev_a_npc_dialogue_client.py`
- `backend/app/integrations/dev_b_level_hint_client.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/game_turn.py`
- `backend/app/services/__init__.py`
- `backend/app/services/logging_service.py`
- `backend/app/services/openkb_service.py`
- `backend/app/services/orchestrator.py`
- `backend/app/services/response_builder.py`
- `backend/app/services/stt_service.py`
- `backend/app/services/validator.py`
- `backend/app/main.py`
- `backend/tests/test_preprototype_flow.py`
- `docs/handoff.md`

## Commands Run

- `git status --short`
- `rg --files`
- `Get-Content -LiteralPath 'AGENTS.md'`
- `Get-Content -LiteralPath 'docs\contracts\developer_c_contract.md'`
- `Get-Content -LiteralPath 'docs\handoff.md'`
- `Get-Content -Encoding UTF8 -LiteralPath 'C:\Users\hanvv\Downloads\developer_b_json_final_v1.md'`
- `Get-Content -Encoding UTF8 -LiteralPath 'C:\Users\hanvv\Downloads\developer_b_json_key_value_contract_v1.md'`
- `Get-Content -LiteralPath 'docs\contracts\developer_c_schema_contract.md'`
- `Get-Content -LiteralPath 'docs\contracts\developer_c_adapter_contracts.md'`
- `git diff -- docs\contracts\developer_c_contract.md docs\handoff.md docs\contracts\developer_c_schema_contract.md docs\contracts\developer_c_adapter_contracts.md`
- `uv sync` (first sandboxed attempt failed on user-level uv cache initialization)
- `uv sync` (rerun with approved escalation)
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (RED: failed because `backend.app.schemas` did not exist)
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (GREEN: 3 passed, 1 warning)
- `uv run pytest`
- `uv run ruff check .` (first run caught one F541 lint issue)
- `uv run mypy .` (first run caught Literal typing issues)
- `uv run ruff check .` (passed after fixes)
- `uv run mypy .` (passed after fixes)
- `uv run pytest` (4 passed, 1 warning)

## Current Architecture

The current implementation exposes `GET /health` and
`POST /api/game/ai/respond`. The pre-prototype endpoint accepts JSON mock input
instead of real Unreal multipart data.

The target Developer C architecture is a FastAPI backend that receives wav
audio from Unreal, runs STT, retrieves OpenKB context, runs a deterministic
Understanding Agent, calls replaceable Developer B and Developer A adapters,
records validated error-capture markdown, assembles Unreal response JSON, and
validates all responses before returning them.

Current pre-prototype flow:

```text
Mock Unreal wav JSON
  -> Whisper-large-v3-turbo STT wrapper
  -> Developer C Orchestrator
  -> Developer C OpenKB node_context
  -> Developer C Understanding Agent
  -> Developer B Policy Adapter mock
  -> Developer A NPC Dialogue Adapter mock
  -> Developer C Response Builder
  -> Developer C Validator
  -> Unreal-safe JSON
```

Canonical turn flow:

```text
Unreal wav
  -> Developer C STT
  -> Developer C Orchestrator
  -> Developer C OpenKB node_context
  -> Developer C Understanding Agent
  -> Developer B Policy / Level / Hint / Feedback Adapter
  -> Developer C Orchestrator
  -> Developer A NPC Dialogue Adapter
  -> Developer C Response Builder
  -> Developer C Validator
  -> Unreal
```

## Contracts / Interfaces

Initial Phase 1 team guardrail, Developer C ownership, dependency, and change
request contracts exist under `docs/contracts/`. `AGENTS.md` now explains
Developer A, B, and C ownership boundaries. Developer A and B start prompts now
exist under `docs/prompts/`. No Developer A or Developer B implementation files
existed in this repository, and none were modified.

New Developer C contract docs:

- `docs/contracts/developer_c_schema_contract.md` defines
  `dev_c_unreal_turn.v1`, STT normalized input, OpenKB node context,
  Understanding output, Developer B policy input mapping, internal turn context,
  and `dev_c_unreal_response.v1`.
- `docs/contracts/developer_c_adapter_contracts.md` defines the STT, OpenKB,
  Understanding, Developer B policy, Developer B final feedback, Developer A
  dialogue, logging, response builder, and validator adapter boundaries.

The Developer B adapter now consumes the broader `dev_b_policy.v1` policy
contract, not only level/hint/branch fields.

Implemented C-owned modules:

- `backend/app/schemas/game_turn.py` contains the pre-prototype Pydantic
  schemas for mock Unreal input, STT normalized input, OpenKB node context,
  Understanding output, Developer A/B adapter payloads, and final response.
- `backend/app/services/stt_service.py` wraps the configured
  `whisper-large-v3-turbo` model name with deterministic mock transcription.
- `backend/app/services/orchestrator.py` wires STT, OpenKB, Understanding,
  Developer B, Developer A, logging, response building, and validation.
- `backend/app/services/validator.py` enforces minimal branch and response
  invariants.

## Dependency State

Package management uses `uv`. Python is set to 3.12. Required runtime and dev
dependencies are recorded in `pyproject.toml` and `uv.lock`, including
`langchain==1.3.2` and `langgraph==1.2.2`.

The sandboxed `uv sync` attempt failed while initializing the user-level uv
cache. It passed when rerun with approved escalation. The latest `uv run
pytest`, `uv run ruff check .`, and `uv run mypy .` passed.

## Known Issues

The pre-prototype uses deterministic mocks for Developer A, Developer B, OpenKB,
and STT transcription content. It does not yet process real wav bytes through a
remote or local Whisper provider. The primary endpoint currently accepts JSON
mock input, not real Unreal multipart upload. Developer A and Developer B real
implementation files are still absent.

## Next Recommended Step

Next, replace the deterministic STT transcript shortcut with a real
Whisper-large-v3-turbo provider boundary while keeping tests on the mock path.
After that, expand scenario coverage beyond `IMM_002_PURPOSE` and connect real
Developer A/B implementations behind the existing adapters.

## Resume Instructions

Run `uv sync` from the repository root, then run `uv run pytest`,
`uv run ruff check .`, and `uv run mypy .`. Continue with Phase 2 only after
Phase 1 is verified.
