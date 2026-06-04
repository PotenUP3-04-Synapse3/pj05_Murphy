# Pre-Prototype Status and Demo Plan

## Audience

This document is for Developer A, Developer B, and Developer C. It summarizes
the current development phase, the AI-only pre-prototype architecture, and the
planned demo setup before Unreal Engine is connected.

## Current Phase Status

Completed:

- Phase 1: Developer C FastAPI backend harness.
- Phase 2: Developer C-side schemas and mock adapter boundaries.
- Phase 3, pre-prototype version: JSON mock request endpoint and multipart
  `turn` JSON plus wav request handling at `POST /api/game/ai/respond`.
- Phase 4, partial: Developer C Orchestrator, local OpenKB node data, and
  Understanding Agent are connected.
- Phase 5: Developer B deterministic policy engine is connected through the
  C-owned `DevBPolicyClient` adapter and `dev_b_policy.v1` shape.
- Phase 6: Developer A dialogue/voice output service is connected through the
  C-owned `DevANpcDialogueClient` adapter.
- Phase 7: Branch, hint, response, and `npc.audio_url` validation exists for
  the integrated pre-prototype flow.
- Developer C STT runtime: local Whisper large v3 turbo boundary is wired with
  API fallback and deterministic test mode.
- Chapter 0 node context is loaded from `backend/app/data/scenario_nodes.json`
  through the C-owned OpenKB service.
- Demo 3 NPC voice artifact is implemented with deterministic fake Kokoro wav
  generation and `/runtime/audio/...` static serving.

Not completed yet:

- Live local Whisper model download and smoke test on the demo machine.
- Live real Kokoro TTS and OpenAI NPC dialogue mode in the endpoint path.
- Out-game feedback logging and final report flow.
- End-to-end retry, bad-ending, and STT fallback demos.
- Real Unreal multipart bridge validation.

## Pre-Prototype Goal

The pre-prototype goal is to show that the three AI developers can collaborate
through contracts before Unreal integration.

The demo should prove one full turn:

```text
mock turn JSON + player wav
  -> AI backend
  -> STT transcript
  -> Developer C Orchestrator
  -> Developer C Understanding Agent
  -> Developer B policy result
  -> Developer A NPC response
  -> Developer C response builder and validator
  -> Unreal-safe JSON + NPC response wav reference
```

Current implementation proves the same flow with JSON mock audio data and with
a multipart request that sends `turn` JSON plus
`samples/utterance-20260603-163237.wav`. The STT boundary accepts real wav bytes
and can run local Whisper first with API fallback. Automated tests and contract
demos set `MURPHY_STT_MODE=mock`, so they still use deterministic demo
transcription instead of downloading a local model or requiring an API key.

## Current AI-Only Flow

```mermaid
flowchart TD
    REQ["JSON or multipart request<br/>turn + sample wav"] --> API["Developer C API<br/>POST /api/game/ai/respond"]
    API --> STT["Whisper large v3 turbo boundary<br/>local mode or deterministic mock mode"]
    STT --> ORCH["Developer C Orchestrator"]
    ORCH --> KB["OpenKB local data<br/>Chapter 0 node_context"]
    KB --> UA["Understanding Agent<br/>intent, slots, relevance, risk"]
    UA --> B["Developer B Policy Adapter<br/>EnglishLevelHintAgent"]
    B --> A["Developer A Dialogue/Voice Adapter<br/>NPC text, tone, animation, audio_url"]
    A --> RB["Response Builder"]
    RB --> V["Rule-based Validator"]
    V --> OUT["dev_c_unreal_response.v1 JSON"]
```

## Target Demo Flow

```mermaid
flowchart TD
    CURL["Demo client<br/>mock JSON + player_input.wav"] --> API["AI Backend<br/>multipart/form-data"]
    API --> STT["STT Service<br/>local Whisper large v3 turbo<br/>API fallback"]
    STT --> C["Developer C Orchestrator"]
    C --> U["Understanding Agent"]
    U --> B["Developer B<br/>Policy / Level / Hint / Feedback"]
    B --> A["Developer A<br/>NPC Dialogue + Voice Output"]
    A --> VOICE["NPC wav artifact<br/>fixture first, live TTS later"]
    VOICE --> C
    C --> RESP["Unreal-safe JSON<br/>includes npc.audio_url"]
```

## Demo Request Shape

Target demo transport:

```text
POST /api/game/ai/respond
Content-Type: multipart/form-data
```

Parts:

| Part | Type | Owner | Purpose |
| --- | --- | --- | --- |
| `turn` | JSON | Demo client / Developer C | Mock Unreal turn state |
| `audio` | `audio/wav` file | Demo client | Player voice answer |

Example command:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/game/ai/respond `
  -F "turn=<demo/input/imm_002_purpose.json;type=application/json" `
  -F "audio=@samples/utterance-20260603-163237.wav;type=audio/wav"
```

## STT Runtime Setup

Runtime settings are loaded from `.env`. Start from the shared template:

```powershell
Copy-Item .env.example .env
```

For automated tests and contract demos, set deterministic mode in `.env`:

```text
MURPHY_STT_MODE=mock
```

For real local transcription mode, set:

```powershell
uv sync --extra local-stt
```

```text
MURPHY_STT_MODE=local
MURPHY_STT_LOCAL_MODEL=turbo
```

The local runtime uses `openai-whisper` and the `turbo` model alias for Whisper
large-v3-turbo. The first real local run may download the model weights, and
the host machine must have `ffmpeg` available.

Optional API fallback settings in `.env`:

```text
OPENAI_API_KEY=<your-api-key>
MURPHY_STT_API_MODEL=whisper-1
```

The fallback calls the OpenAI Transcriptions API only when the local runtime
fails. `MURPHY_STT_API_MODEL` can be changed to another supported
Transcriptions API model.

Suggested demo fixture layout:

```text
samples/
  utterance-20260603-163237.wav

demo/
  input/
    imm_002_purpose.json
  npc_voice/
    officer_miller_imm_003_duration.wav

artifacts/
  demo/
    session_001/
      turn_2_officer_miller.wav
```

## Demo Response Shape

The demo response should keep the existing `dev_c_unreal_response.v1` contract
and add an NPC audio reference when voice output is available.

Target demo response excerpt:

```json
{
  "contract_version": "dev_c_unreal_response.v1",
  "request_id": "req_imm_0001",
  "current_node_id": "IMM_002_PURPOSE",
  "next_node_id": "IMM_003_DURATION",
  "next_action": "ADVANCE",
  "stt": {
    "model": "whisper-large-v3-turbo",
    "primary_runtime": "local",
    "fallback_runtime": "api",
    "runtime_used": "local",
    "player_text": "I'm here for tourism.",
    "confidence": 0.87
  },
  "npc": {
    "speaker": "Officer Miller",
    "text": "You're here for tourism. How long will you stay?",
    "tone": "formal_neutral",
    "animation": "officer_check_passport",
    "audio_url": "/artifacts/demo/session_001/turn_2_officer_miller.wav"
  },
  "ui": {
    "recommended_expression": "I'm here for tourism.",
    "in_game_feedback": {
      "show": true,
      "feedback_strategy": "recast"
    }
  },
  "evaluation": {
    "verdict": "SUCCESS"
  }
}
```

The current implementation includes `stt.player_text` and `npc.audio_url`.
The automated endpoint path uses deterministic fake Kokoro wav output so tests
do not require real TTS credentials or model downloads.

## Developer A Responsibilities for Demo

Developer A owns NPC dialogue and voice output.

For the first stable demo, Developer A should provide:

- Officer Miller NPC line for `IMM_002_PURPOSE` success:
  `"You're here for tourism. How long will you stay?"`
- NPC tone metadata, such as `formal_neutral`.
- NPC animation hint, such as `officer_check_passport`.
- A fixture wav file for the NPC response, or a voice output adapter that can
  return one.

Recommended first demo mode:

```text
fixture mode
```

Fixture mode means the backend returns a prepared wav artifact path. It avoids
TTS provider latency and credential risk during the first pre-prototype demo.

Later demo mode:

```text
live TTS mode
```

Live TTS mode can replace the fixture while keeping the same `npc.audio_url`
response contract.

## Developer B Responsibilities for Demo

Developer B owns policy, level, hint, feedback, state delta, and branch
recommendation.

For the first stable demo, Developer B should provide or confirm:

- `dev_b_policy.v1` output for `IMM_002_PURPOSE` success.
- `evaluation.verdict = "SUCCESS"`.
- `branch.next_action = "ADVANCE"`.
- `branch.next_node_id = "IMM_003_DURATION"`.
- `level_hint.recommended_expression = "I'm here for tourism."`.
- `in_game_feedback.feedback_strategy = "recast"`.
- `state_delta` values for success.

Developer B should not generate NPC final text, Unreal commands, animation
commands, or final API response envelopes.

## Developer C Responsibilities for Demo

Developer C owns orchestration, STT boundary, validation, response assembly,
and demo backend transport.

For the next demo milestone, Developer C should implement:

- Multipart request support for `turn` JSON plus `audio` wav.
- Live local Whisper smoke test on the demo machine.
- Deterministic STT mock path for tests.
- API-level retry, clarify, warning, and bad-end demo tests.
- Out-game feedback and final report flow.
- Real Unreal bridge validation after the backend demo path is stable.

Developer C should keep tests passing without local model downloads or real API
credentials by using mocks and fixtures.

## Demo Milestones

### Demo 1: Contract Flow, Already Implemented

Input:

- JSON mock request.
- Mock audio metadata and transcript shortcut.

Output:

- Unreal-safe JSON response.
- STT model name in debug.
- Developer B mock success branch.
- Developer A mock NPC text.

Status:

```text
implemented
```

### Demo 2: Mock JSON + Real wav Boundary

Input:

- `turn` JSON.
- `samples/utterance-20260603-163237.wav`.

Output:

- Transcript from the Whisper large v3 turbo boundary.
- STT runtime metadata showing local primary and API fallback.
- Unreal-safe JSON response.
- NPC text from Developer A adapter.

Status:

```text
implemented with real local/API fallback boundary and deterministic test mode
```

### Demo 3: NPC Voice Artifact

Input:

- Same as Demo 2.

Output:

- Unreal-safe JSON response.
- `npc.audio_url` pointing to an Officer Miller wav artifact.

Status:

```text
implemented with deterministic fake Kokoro artifact generation
```

### Demo 4: Real A/B Integration

Input:

- Same as Demo 2.

Output:

- Developer B deterministic policy result.
- Developer A dialogue and voice output.
- Developer C validated response.

Status:

```text
implemented for deterministic pre-prototype mode; live provider mode remains future work
```

## Success Criteria

The pre-prototype demo is ready when:

- A single command can send mock turn JSON plus wav to the backend.
- The backend returns the recognized player text or STT debug info, including
  local primary and API fallback metadata.
- The backend returns `next_node_id = "IMM_003_DURATION"` for the tourism
  success case.
- The backend returns Officer Miller NPC text.
- The backend returns or serves an NPC response wav artifact.
- Tests still pass without local Whisper model downloads, real API keys, Unreal
  Engine runtime, remote OpenKB, or real A/B provider dependencies.
