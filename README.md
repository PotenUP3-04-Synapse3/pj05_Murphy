# Murphy's Trippin - Developer C Backend Harness

This repository is the Developer C backend harness for the Chapter 0
Immigration Check prototype of Murphy's Trippin, a Chaos Travel English
Simulator.

The backend will receive Unreal Engine player input and return validated,
Unreal-safe JSON commands through:

```text
POST /api/game/ai/respond
```

The current pre-prototype wires Developer C orchestration to merged Developer B
policy logic and Developer A dialogue/voice output through C-owned adapters.
Automated tests still use deterministic STT and fake Kokoro output, so the
project remains restorable and testable without provider credentials.

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

Current scope: integrated AI-only pre-prototype for Chapter 0 Immigration
Check.

## Implemented Backend Checks

The FastAPI backend exposes:

```text
GET /health
POST /api/game/ai/respond
GET /runtime/audio/{artifact}
```

`POST /api/game/ai/respond` accepts JSON mock input or multipart `turn` JSON
plus `audio/wav` input and returns Unreal-safe JSON, including STT transcript
metadata and `npc.audio_url` for generated demo voice artifacts.

## Collaboration Prompts

All developer agents should start with [AGENTS.md](AGENTS.md).

Developer-specific start prompts:

- Developer A: [docs/prompts/developer_a_start_prompt.md](docs/prompts/developer_a_start_prompt.md)
- Developer B: [docs/prompts/developer_b_start_prompt.md](docs/prompts/developer_b_start_prompt.md)
