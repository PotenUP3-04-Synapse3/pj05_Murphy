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

For a non-deterministic endpoint demo with real STT and real Kokoro TTS, set
these values in `.env`:

```text
MURPHY_STT_MODE=local
MURPHY_STT_LOCAL_MODEL=turbo
MURPHY_UNDERSTANDING_MODE=llm
MURPHY_UNDERSTANDING_LLM_PROVIDER=openai
MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini
MURPHY_UNDERSTANDING_LLM_TIMEOUT_SECONDS=10
MURPHY_TTS_MODE=real
MURPHY_NPC_DIALOGUE_MODE=rule
```

`MURPHY_UNDERSTANDING_MODE=rule` keeps Developer C semantic analysis
deterministic. `MURPHY_UNDERSTANDING_MODE=llm` enables LLM-assisted
Understanding Agent output with rule fallback. `MURPHY_NPC_DIALOGUE_MODE=llm`
can be used for optional LLM NPC dialogue generation. OpenAI remains the
primary provider. When the GPT key is unavailable, enable the academy Gemma4
vLLM fallback:

```text
OPENAI_API_KEY=...

GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1
GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it
GEMMA4_VLLM_API_KEY=dummy

MURPHY_UNDERSTANDING_LLM_PROVIDER=openai
MURPHY_UNDERSTANDING_LLM_FALLBACK=gemma4_vllm
MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini

NPC_DIALOGUE_LLM_PROVIDER=openai
NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm
NPC_DIALOGUE_LLM_MODEL=gpt-4o-mini
```

Run the development server after the backend endpoint exists:

```powershell
uv run uvicorn backend.app.main:app --reload
```

Send the demo turn JSON and wav as multipart form data:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/game/ai/respond `
  -F "turn=<demo/input/imm_002_purpose.json;type=application/json" `
  -F "audio=@samples/utterance-20260603-163237.wav;type=audio/wav"
```

The response includes `stt.player_text`, STT runtime metadata, Officer Miller's
NPC text, and `npc.audio_url`. The audio URL is served by the same FastAPI app
under `/runtime/audio/...`.

To capture incoming Unreal multipart requests for debugging, enable:

```powershell
$env:MURPHY_UNREAL_REQUEST_CAPTURE_MODE="debug"
$env:MURPHY_UNREAL_REQUEST_CAPTURE_ROOT="backend/runtime/generated/unreal_requests"
```

When enabled, each multipart request stores `turn.json`, `audio.wav`, and
`metadata.json` under the capture root before turn validation/orchestration.

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
