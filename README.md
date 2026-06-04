# Murphy's Trippin - Developer C Backend Harness

This repository is the Developer C backend harness for the Chapter 0
Immigration Check prototype of Murphy's Trippin, a Chaos Travel English
Simulator.

The backend will receive Unreal Engine player input and return validated,
Unreal-safe JSON commands through:

```text
POST /api/game/ai/respond
```

Phase 1 bootstraps the Developer C project only. It does not implement real
Developer A NPC dialogue logic, real Developer B scenario logic, real STT
providers, or external LLM calls.

## Developer C Responsibilities

- STT pipeline interface and mock behavior
- Understanding Agent contract and deterministic fallback
- OpenKB retrieval
- Backend orchestrator
- Validator
- Unreal response JSON assembler
- Developer A/B integration adapters
- Developer C tests, contracts, handoff, and portfolio docs

## Setup

Use `uv` only:

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run mypy .
```

Create local runtime settings from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Fill `.env` locally for API keys and STT settings. The real `.env` file is
ignored by git and must not be committed.

For real local Whisper STT:

```powershell
uv sync --extra local-stt
```

Run the development server after the backend endpoint exists:

```powershell
uv run uvicorn backend.app.main:app --reload
```

## Current Phase

Current scope: Phase 1 - Developer C harness bootstrap.

## Bootstrap Health Check

The Phase 1 FastAPI skeleton exposes:

```text
GET /health
```

This route confirms the Developer C backend package imports and the app starts.

## Collaboration Prompts

All developer agents should start with [AGENTS.md](AGENTS.md).

Developer-specific start prompts:

- Developer A: [docs/prompts/developer_a_start_prompt.md](docs/prompts/developer_a_start_prompt.md)
- Developer B: [docs/prompts/developer_b_start_prompt.md](docs/prompts/developer_b_start_prompt.md)
