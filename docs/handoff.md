# Handoff

## Current Status

Phase 1 bootstrap is complete, Phase 2 contracts exist, and the AI-only
pre-prototype turn flow is now implemented. The repository has a Developer C
FastAPI backend package, C-side schemas, deterministic mock adapters, a
Whisper-large-v3-turbo STT wrapper, an orchestrator, a minimal validator, and
tests for JSON mock and multipart sample-wav turn flows.

## Last Completed Task

Implemented the Developer C Demo 2 baseline. The endpoint now accepts both the
existing JSON mock request and multipart `turn` JSON plus sample wav requests.
The response includes `stt.player_text`, `next_node_id`, and `npc.text`.

## Changed Files

- `docs/preprototype_status_demo_plan.md`
- `backend/app/api/ai_respond.py`
- `backend/app/schemas/game_turn.py`
- `backend/app/services/response_builder.py`
- `backend/app/services/stt_service.py`
- `backend/tests/test_preprototype_flow.py`
- `docs/contracts/developer_c_schema_contract.md`
- `docs/handoff.md`

## Commands Run

- `git status --short`
- `rg --files docs`
- `Get-Content -LiteralPath 'docs\handoff.md'`
- `Get-Content -LiteralPath 'docs\contracts\developer_c_schema_contract.md'`
- `Get-Content -LiteralPath 'docs\contracts\developer_c_adapter_contracts.md'`
- `Get-Content -LiteralPath 'docs\preprototype_status_demo_plan.md'`
- `Get-ChildItem -Recurse -File -LiteralPath 'samples'`
- `git diff --stat`
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (RED: multipart request and `stt` response fields were not implemented)
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (GREEN: 4 passed, 1 warning)
- `uv sync` (first sandboxed attempt failed on user-level uv cache initialization)
- `uv sync` (rerun with approved escalation)
- `uv run pytest` (5 passed, 1 warning)
- `uv run ruff check .`
- `uv run mypy .`

## Current Architecture

The current implementation exposes `GET /health` and
`POST /api/game/ai/respond`. The pre-prototype endpoint accepts JSON mock input
and multipart `turn` JSON plus wav input.

The target Developer C architecture is a FastAPI backend that receives wav
audio from Unreal, runs STT, retrieves OpenKB context, runs a deterministic
Understanding Agent, calls replaceable Developer B and Developer A adapters,
records validated error-capture markdown, assembles Unreal response JSON, and
validates all responses before returning them.

Current pre-prototype flow:

```text
Mock Unreal JSON or multipart sample wav
  -> Whisper-large-v3-turbo STT boundary
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

- `docs/preprototype_status_demo_plan.md` summarizes the current phase status,
  AI-only pre-prototype architecture, target demo request/response plan,
  Developer A/B/C demo responsibilities, and demo readiness criteria.
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
  `whisper-large-v3-turbo` model name with deterministic mock and sample-wav
  transcription.
- `backend/app/services/orchestrator.py` wires STT, OpenKB, Understanding,
  Developer B, Developer A, logging, response building, and validation.
- `backend/app/services/validator.py` enforces minimal branch and response
  invariants.

## Dependency State

Package management uses `uv`. Python is set to 3.12. Required runtime and dev
dependencies are recorded in `pyproject.toml` and `uv.lock`, including
`langchain==1.3.2` and `langgraph==1.2.2`.

The sandboxed `uv sync` attempt failed while initializing the user-level uv
cache. It passed when rerun with approved escalation. The latest
`uv run pytest` passed with 5 tests and 1 warning. `uv run ruff check .` and
`uv run mypy .` passed.

## Known Issues

The pre-prototype uses deterministic mocks for Developer A, Developer B, OpenKB,
and STT transcription content. It accepts wav bytes for the demo path but does
not yet process them through a remote or local Whisper provider. Developer A
and Developer B real implementation files are still absent. The response does
not yet include `npc.audio_url`.

## Next Recommended Step

Next, implement Demo 3 by adding an NPC voice artifact fixture or Developer A
voice output adapter and returning `npc.audio_url`. After that, replace the
deterministic STT transcript shortcut with a real Whisper-large-v3-turbo
provider boundary while keeping tests on the mock path.

## Resume Instructions

Run `uv sync` from the repository root, then run `uv run pytest`,
`uv run ruff check .`, and `uv run mypy .`. Continue with Phase 2 only after
Phase 1 is verified.
