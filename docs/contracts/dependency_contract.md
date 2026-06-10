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

Supported project Python range:

```text
>=3.12,<3.13
```

The upper bound is intentional. `chatterbox-tts==0.1.7` currently pins
`torch==2.6.0`, and dependency resolution should not attempt unsupported
Python 3.13 combinations.

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
- Store `OPENAI_API_KEY` only in local environment variables or `.env`.
- Keep test defaults deterministic and key-free.
- `kokoro`
- `edge-tts`
- `chatterbox-tts`
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

Tests must pass without local model downloads, external API keys, real TTS
providers, real LLM providers, Unreal Engine runtime, or remote OpenKB.

## Approved Local TTS Dependencies

Developer A / kimyonghee received explicit approval on 2026-06-03 to add local
Kokoro TTS dependencies for real wav generation tests.

Approved packages:

- `kokoro>=0.9.4`
- `soundfile>=0.13.1`
- `torch==2.6.0`
- `espeakng-loader>=0.2.4`

Constraints:

- Tests must still pass without external API keys.
- Real Kokoro generation may download local model assets during smoke tests.
- Runtime audio files are generated under `backend/runtime/`.
- Unreal-facing audio delivery uses `audio_url`; Developer C serves generated
  pre-prototype wav artifacts under `/runtime/audio/...`.

## Approved Edge TTS Experiment Dependency

Developer A / kimyonghee added `edge-tts>=7.2.8` on 2026-06-09 as a reversible
TTS provider experiment.

Runtime selection:

- `MURPHY_TTS_PROVIDER=kokoro`: use the existing Kokoro provider.
- `MURPHY_TTS_PROVIDER=edge`: use Edge TTS and convert the generated MP3 to
  PCM WAV with `ffmpeg` when `MURPHY_EDGE_TTS_OUTPUT_FORMAT=wav`.

Constraints:

- Edge TTS is network-dependent and should not be required for automated tests.
- Kokoro remains the rollback provider.
- The host machine must have `ffmpeg` on `PATH` for Edge WAV conversion.

## Approved Chatterbox TTS Experiment Dependency

Developer A / kimyonghee added `chatterbox-tts==0.1.7` on 2026-06-09 as a
reversible emotional TTS provider experiment.

Runtime selection:

- `MURPHY_TTS_PROVIDER=chatterbox`: use Chatterbox TTS.
- `MURPHY_TTS_PROVIDER=kokoro`: rollback to Kokoro.
- `MURPHY_TTS_PROVIDER=edge`: rollback to Edge TTS.

Runtime parameters:

- `MURPHY_CHATTERBOX_REFERENCE_AUDIO`: optional reference wav for Officer
  Miller voice consistency. If the file is missing, Developer A omits
  `audio_prompt_path` and uses the model default voice.
- `MURPHY_CHATTERBOX_EXAGGERATION`: emotion strength.
- `MURPHY_CHATTERBOX_CFG_WEIGHT`: conditioning strength.
- `MURPHY_CHATTERBOX_TEMPERATURE`: sampling variation.
- `MURPHY_CHATTERBOX_DEVICE`: `auto`, `cuda`, or `cpu`.

Constraints:

- `chatterbox-tts==0.1.7` pins `torch==2.6.0`; the project dependency contract
  now follows that pin.
- With `MURPHY_CHATTERBOX_DEVICE=auto`, Developer A uses CUDA only when
  `torch.cuda.is_available()` is true; otherwise it falls back to CPU.
- On Windows/Linux, `pyproject.toml` routes `torch` and `torchaudio` to the
  PyTorch CUDA 12.4 wheel index through `tool.uv.sources`.
- Verified local GPU install on 2026-06-09:
  - NVIDIA driver: `591.74`
  - `nvidia-smi` CUDA capability display: `13.1`
  - GPU: `NVIDIA GeForce RTX 4070 Laptop GPU`
  - PyTorch: `torch==2.6.0+cu124`
  - PyTorch CUDA runtime: `12.4`
  - `torch.cuda.is_available()`: `True`
- Automated tests must not download Chatterbox model weights. Tests monkeypatch
  the provider and verify provider selection, output paths, and AgentRun logs.

## Approved ElevenLabs TTS Provider

Developer A / kimyonghee integrated ElevenLabs TTS on 2026-06-09 as an
official selectable TTS provider. No new Python package is required because the
project already depends on `httpx`.

Runtime selection:

- `MURPHY_TTS_PROVIDER=elevenlabs`: use ElevenLabs TTS.
- `MURPHY_TTS_PROVIDER=edge`: rollback to Edge TTS.
- `MURPHY_TTS_PROVIDER=kokoro`: rollback to Kokoro.
- `MURPHY_TTS_PROVIDER=chatterbox`: use local Chatterbox.

Runtime parameters:

- `MURPHY_ELEVENLABS_API_KEY`: local secret. Do not commit real values.
- `ELEVENLABS_API_KEY`: fallback local secret name.
- `MURPHY_ELEVENLABS_BASE_URL`: defaults to `https://api.elevenlabs.io/v1`.
- `MURPHY_ELEVENLABS_VOICE_ID`: selected Officer Miller voice id.
- `MURPHY_ELEVENLABS_MODEL_ID`: defaults to `eleven_flash_v2_5`.
- `MURPHY_ELEVENLABS_API_OUTPUT_FORMAT`: defaults to `mp3_44100_128`.
- `MURPHY_ELEVENLABS_OUTPUT_FORMAT`: defaults to Unreal-facing `wav`.
- `MURPHY_ELEVENLABS_STABILITY`, `MURPHY_ELEVENLABS_SIMILARITY_BOOST`,
  `MURPHY_ELEVENLABS_STYLE`, and `MURPHY_ELEVENLABS_SPEED`: voice settings.
- `MURPHY_ELEVENLABS_USE_SPEAKER_BOOST`: defaults to `true`.
- `MURPHY_ELEVENLABS_TIMEOUT_SECONDS`: request timeout.

Constraints:

- Automated tests must not call ElevenLabs. Tests monkeypatch the provider and
  verify provider selection, output paths, AgentRun logs, and secret redaction.
- ElevenLabs API keys must not be written to AgentRun logs, generated metadata,
  handoff documents, or committed files.
- ElevenLabs returns MP3 by default. Developer A converts MP3 to 24kHz mono PCM
  WAV with `ffmpeg` for Unreal-facing `audio_url` responses.
