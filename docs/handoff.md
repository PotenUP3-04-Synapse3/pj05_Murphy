# Handoff

## Current Status

Phase 1 bootstrap is complete, Phase 2 contracts exist, and the AI-only
pre-prototype turn flow is now implemented. The repository has a Developer C
FastAPI backend package, C-side schemas, deterministic mock adapters, a
Whisper-large-v3-turbo STT wrapper, an orchestrator, a minimal validator, and
tests for JSON mock and multipart sample-wav turn flows. The STT contract is
local-first with API fallback. Automated tests keep deterministic STT through
`MURPHY_STT_MODE=mock`.

## Last Completed Task

Implemented the Developer C real STT boundary. The endpoint still accepts both
the existing JSON mock request and multipart `turn` JSON plus sample wav
requests. In `local` mode, STT calls local Whisper first and falls back to the
OpenAI Transcriptions API when local transcription fails. The response includes
`stt.player_text`, `stt.primary_runtime = "local"`,
`stt.fallback_runtime = "api"`, `stt.runtime_used`, `next_node_id`, and
`npc.text`.

## Changed Files

- `docs/preprototype_status_demo_plan.md`
- `pyproject.toml`
- `uv.lock`
- `backend/app/schemas/game_turn.py`
- `backend/app/services/response_builder.py`
- `backend/app/services/stt_service.py`
- `backend/tests/test_preprototype_flow.py`
- `backend/tests/test_stt_service.py`
- `docs/contracts/dependency_contract.md`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/contracts/developer_c_schema_contract.md`
- `docs/handoff.md`

## Commands Run

- `git status --short --branch`
- `Get-Content -Path backend\tests\test_preprototype_flow.py`
- `Get-Content -Path backend\app\schemas\game_turn.py`
- `Get-Content -Path backend\app\services\stt_service.py`
- `Get-Content -Path backend\app\services\response_builder.py`
- `Get-Content -Path docs\contracts\developer_c_schema_contract.md`
- `Get-Content -Path docs\preprototype_status_demo_plan.md`
- `Get-Content -Path docs\handoff.md`
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (RED: STT runtime metadata fields were not implemented)
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (GREEN: 4 passed, 1 warning)
- `uv run pytest backend/tests/test_stt_service.py -q` (RED: local/API runtime injection was not implemented)
- `uv run pytest backend/tests/test_stt_service.py -q` (GREEN: 2 passed)
- `uv lock` (first sandboxed attempt failed on user-level uv cache initialization)
- `uv lock` (rerun with approved escalation: resolved 93 packages)
- `rg -n "provider|Whisper|STT|fallback|runtime" docs\contracts\developer_c_schema_contract.md docs\preprototype_status_demo_plan.md docs\handoff.md`
- `git diff -- docs\contracts\developer_c_schema_contract.md docs\preprototype_status_demo_plan.md docs\handoff.md`
- `git diff --stat`
- `uv sync` (first sandboxed attempt failed on user-level uv cache initialization)
- `uv sync` (rerun with approved escalation: resolved 93 packages, audited 55 packages)
- `uv run pytest` (7 passed, 1 warning)
- `uv run ruff check .` (passed)
- `uv run mypy .` (initially failed on optional `whisper` import typing and endpoint URL typing)
- `uv run mypy .` (passed)
- `git diff --check` (passed)

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
  -> Whisper-large-v3-turbo STT boundary (mock mode in tests, local mode in demo)
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
  -> Developer C local STT, with API fallback
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
  `whisper-large-v3-turbo` model name with real local Whisper transcription,
  OpenAI Transcriptions API fallback, and deterministic mock mode for tests.
- `backend/app/services/orchestrator.py` wires STT, OpenKB, Understanding,
  Developer B, Developer A, logging, response building, and validation.
- `backend/app/services/validator.py` enforces minimal branch and response
  invariants.

## Dependency State

Package management uses `uv`. Python is set to 3.12. Required runtime and dev
dependencies are recorded in `pyproject.toml` and `uv.lock`, including
`langchain==1.3.2` and `langgraph==1.2.2`.

Local STT dependencies are optional:

```powershell
uv sync --extra local-stt
```

Runtime STT settings:

- `MURPHY_STT_MODE=local` runs local Whisper first.
- `MURPHY_STT_MODE=mock` uses deterministic transcription for tests.
- `MURPHY_STT_LOCAL_MODEL=turbo` uses the local Whisper large-v3-turbo alias.
- `MURPHY_STT_API_MODEL=whisper-1` controls API fallback.
- `OPENAI_API_KEY` is required only if API fallback is needed.

The sandboxed `uv sync` and `uv lock` attempts failed while initializing the
user-level uv cache. Both passed when rerun with approved escalation. The
latest `uv run pytest` passed with 7 tests and 1 warning.
`uv run ruff check .` and `uv run mypy .` passed. `git diff --check` passed.

## Known Issues

The pre-prototype uses deterministic mocks for Developer A, Developer B, and
OpenKB. STT can now execute real local Whisper in `local` mode, but automated
tests intentionally use fake runtimes or `mock` mode and do not download model
weights. The first real local run needs `uv sync --extra local-stt`, `ffmpeg`,
and time to download/load the Whisper model. Developer A and Developer B real
implementation files are still absent. The response does not yet include
`npc.audio_url`.

## Next Recommended Step

Next, run a live local Whisper smoke test on the demo machine with
`MURPHY_STT_MODE=local`. After that, implement Demo 3 by adding an NPC voice
artifact fixture or Developer A voice output adapter and returning
`npc.audio_url`.

## Resume Instructions

Run `uv sync` from the repository root, then run `uv run pytest`,
`uv run ruff check .`, and `uv run mypy .`. Continue with Phase 2 only after
Phase 1 is verified.
