# Dependency Contract

## Package Manager

Use `uv` only. The project must be restorable on another computer with:

```powershell
uv sync
```

Do not use `pip install`, Poetry, Pipenv, Conda, or global manual package
installation.

## Python Version

Preferred Python version: 3.12.

Current `.python-version`:

```text
3.12
```

## Required Runtime Dependencies

- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `pydantic-settings`
- `python-multipart`
- `httpx`
- `websockets`
- `langchain==1.3.2`
- `langgraph==1.2.2`

## Optional Runtime Dependencies

Install optional local STT dependencies only on machines that need real local
Whisper transcription:

```powershell
uv sync --extra local-stt
```

The `local-stt` extra includes:

- `openai-whisper>=20240930`

The local Whisper runtime also requires `ffmpeg` to be available on the host
machine path.

## Environment Configuration

Runtime settings are loaded with `pydantic-settings` from process environment
variables and the repository root `.env` file.

Shared template:

```text
.env.example
```

Local secret file:

```text
.env
```

Rules:

- Commit `.env.example`.
- Do not commit `.env` or `.env.*` secret files.
- Store `OPENAI_API_KEY` and `ELEVENLABS_API_KEY` only in local environment
  variables or `.env`.
- Keep test defaults deterministic and key-free.
- `kokoro`
- `soundfile`
- `torch`
- `espeakng-loader`

## Required Development Dependencies

- `pytest`
- `ruff`
- `mypy`

## AI Framework Version Contract

The following versions are pinned for Developer C agent development:

- `langchain==1.3.2`
- `langgraph==1.2.2`

Do not upgrade or downgrade these packages unless this file,
`docs/handoff.md`, and `docs/portfolio_seanhan.md` are updated together.

## External Provider Policy

Real local STT has been explicitly requested for Developer C and is available
behind the `local-stt` optional extra. API fallback uses the OpenAI
Transcriptions API only when local STT fails and `OPENAI_API_KEY` is present.
Developer C Understanding Agent LLM mode also uses `OPENAI_API_KEY` when
`MURPHY_UNDERSTANDING_MODE=llm`; tests and deterministic demos keep
`MURPHY_UNDERSTANDING_MODE=rule`.

Developer C realtime caption relay may connect to ElevenLabs realtime STT over
WSS with `ELEVENLABS_API_KEY` kept server-side. Unreal must not hold provider
API keys. Tests use fake WebSocket connectors and must pass without ElevenLabs
credentials or network access.

Realtime STT debug mode is local-file logging only. When
`MURPHY_STT_DEBUG_LOG_MODE=debug`, Developer C appends a standalone
`realtime_stt_relay` unified AgentRun record with token counts set to zero and
cost estimated from `ELEVENLABS_REALTIME_ESTIMATED_COST_PER_MINUTE_USD`.

Tests must pass without local model downloads, external API keys, real TTS
providers, real LLM providers, Unreal Engine runtime, or remote OpenKB.

## Approved Local TTS Dependencies

Developer A / kimyonghee received explicit approval on 2026-06-03 to add local
Kokoro TTS dependencies for real wav generation tests.

Approved packages:

- `kokoro>=0.9.4`
- `soundfile>=0.13.1`
- `torch>=2.12.0`
- `espeakng-loader>=0.2.4`

Constraints:

- Tests must still pass without external API keys.
- Real Kokoro generation may download local model assets during smoke tests.
- Runtime audio files are generated under `backend/runtime/`.
- Unreal-facing audio delivery uses `audio_url`; Developer C serves generated
  pre-prototype wav artifacts under `/runtime/audio/...`.
