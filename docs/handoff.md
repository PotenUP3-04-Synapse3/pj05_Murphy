# Handoff

## Current Status

Phase 1 bootstrap is complete, and Phase 2 contract planning has started. The
repository now has a Developer C FastAPI backend package, initial contracts,
handoff and portfolio docs, dependency pins, a bootstrap health-route test,
shared A/B/C collaboration guidance, and C-side schema/adapter contract docs
for wav-only Unreal input.

## Last Completed Task

Created Developer C schema and adapter contract documentation aligned with the
Developer B `dev_b_policy.v1` JSON contract. The new C architecture assumes
Unreal always sends wav audio, Developer C always runs STT first, and Developer
C maps normalized voice input into downstream adapter payloads.

## Changed Files

- `docs/contracts/developer_c_contract.md`
- `docs/contracts/developer_c_schema_contract.md`
- `docs/contracts/developer_c_adapter_contracts.md`
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
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy .`

## Current Architecture

The current Phase 1 architecture is a minimal FastAPI app at
`backend/app/main.py` with `GET /health`.

The target Developer C architecture is a FastAPI backend that receives wav
audio from Unreal, runs STT, retrieves OpenKB context, runs a deterministic
Understanding Agent, calls replaceable Developer B and Developer A adapters,
records validated error-capture markdown, assembles Unreal response JSON, and
validates all responses before returning them.

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

## Dependency State

Package management uses `uv`. Python is set to 3.12. Required runtime and dev
dependencies are recorded in `pyproject.toml` and `uv.lock`, including
`langchain==1.3.2` and `langgraph==1.2.2`.

The sandboxed `uv sync` attempt failed while initializing the user-level uv
cache. It passed when rerun with approved escalation. `uv run pytest`,
`uv run ruff check .`, and `uv run mypy .` passed.

## Known Issues

No Phase 1 check failures remain. Phase 2 implementation is not started yet.
The primary `POST /api/game/ai/respond` endpoint, C-side Pydantic schemas,
adapter mocks, orchestration services, and validator are not implemented yet.
Developer A and Developer B real implementation files are still absent.

## Next Recommended Step

Implement Phase 2 Developer C Pydantic schemas and deterministic adapter mocks
from the new C-side schema and adapter contract docs. The first implementation
target should be the wav-only request schema, mock STT normalized input,
Developer B policy input builder, and rule-based branch validator.

## Resume Instructions

Run `uv sync` from the repository root, then run `uv run pytest`,
`uv run ruff check .`, and `uv run mypy .`. Continue with Phase 2 only after
Phase 1 is verified.
