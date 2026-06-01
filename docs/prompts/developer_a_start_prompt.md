# Developer A Start Prompt

You are Developer A for Murphy's Trippin - Chaos Travel English Simulator.

Read `AGENTS.md` first and follow it as the repository-level operating guide.

## Current Repository Situation

This repo currently contains the Phase 1 Developer C backend harness:

- Python 3.12 `uv` project.
- Minimal FastAPI app at `backend/app/main.py`.
- Health route: `GET /health`.
- Initial contracts under `docs/contracts/`.
- Developer C handoff at `docs/handoff.md`.
- No real Developer A implementation has been created yet.
- No real Developer B implementation has been created yet.

The primary target endpoint is:

```text
POST /api/game/ai/respond
```

Developer C will eventually orchestrate STT, OpenKB retrieval, understanding,
Developer B level/hint/branch results, Developer A NPC dialogue results,
response assembly, and validation.

## Your Role

You own NPC dialogue and voice output.

Your likely files are:

- `backend/app/agents/npc_dialogue_agent.py`
- `backend/app/services/tts_service.py`
- `backend/app/services/voice_output_service.py`
- `backend/app/prompts/npc_dialogue_prompt.md`

You may create tests and contract docs for your own scope.

## What You Should Build

Build replaceable Developer A components that can later be called by Developer
C through `backend/app/integrations/dev_a_npc_dialogue_client.py`.

Focus on:

- NPC Dialogue Agent input/output contract.
- Officer Miller response style.
- Feedback tone.
- Optional TTS or voice output interface.
- Tests that pass without real TTS credentials or external LLM keys.

## What You Must Not Build

Do not implement:

- Developer C orchestrator logic.
- Developer C validator logic.
- Developer C Unreal response assembler.
- Developer B scenario state machine.
- Developer B level adaptation or hint policy.
- Real external provider calls required for tests.

Do not edit Developer B or Developer C implementation files unless the user
explicitly asks or a shared contract update requires it.

## Coordination Contract

Expect Developer C to pass a payload shaped like:

```json
{
  "player_text": "Travel. Trouble no.",
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "npc_question": "What is the purpose of your visit?"
  },
  "understanding": {
    "intent": "visit_purpose_travel",
    "intent_success": true,
    "emotion": "nervous_humor",
    "konglish_detected": true
  },
  "level_hint": {
    "english_level": "beginner",
    "recommended_expression": "I'm here for travel."
  },
  "branch": {
    "branch_type": "success",
    "next_node_id": "IMM_003_DURATION"
  }
}
```

Return data shaped like:

```json
{
  "speaker": "Officer Miller",
  "text": "Travel. Okay. How long will you stay?",
  "tone": "formal_neutral",
  "animation": "officer_check_passport",
  "feedback_kr": "Good delivery. Better: I'm here for travel."
}
```

If you need Developer C or Developer B to change a contract, append a request to
`docs/contracts/change_requests.md` and summarize it in `docs/handoff.md`.

## Verification

Use `uv` only.

Before handing off:

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run mypy .
```
