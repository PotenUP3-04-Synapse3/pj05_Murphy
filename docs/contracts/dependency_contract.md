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

No real STT, TTS, or LLM provider dependency should be added until explicitly
requested. Tests must pass without external API keys.
