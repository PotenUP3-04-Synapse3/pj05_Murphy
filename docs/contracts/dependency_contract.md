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

Tests must pass without local model downloads, external API keys, real TTS
providers, real LLM providers, Unreal Engine runtime, or remote OpenKB.
