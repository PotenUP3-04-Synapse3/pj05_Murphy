# Developer C Contract

## Mission

Developer C converts player input into structured understanding data, attaches
scenario context from local OpenKB sources, coordinates backend flow, validates
outputs, and returns Unreal-safe JSON.

Developer C is responsible for the backend entry point and safety layer.
Developer C is not responsible for real NPC dialogue generation or real
level/hint/scenario branch logic.

## Owned Areas

- `backend/app/main.py`
- `backend/app/api/ai_respond.py`
- `backend/app/schemas/`
- `backend/app/services/`
- `backend/app/agents/understanding_agent.py`
- `backend/app/prompts/understanding_prompt.md`
- `backend/app/graphs/developer_c_graph.py`
- `backend/app/integrations/`
- `backend/app/kb/`
- `backend/tests/`
- `docs/handoff.md`
- `docs/portfolio_seanhan.md`
- `docs/contracts/`

## Backend Flow

The target Developer C flow is:

1. Normalize Unreal request input.
2. Bypass STT for text or use mock/provider STT for voice.
3. Load OpenKB node context.
4. Run the Understanding Agent.
5. Call the Developer B adapter for level, hint, and branch mock/contract data.
6. Call the Developer A adapter for NPC response mock/contract data.
7. Build Unreal response JSON.
8. Validate the response with rule-based checks.
9. Return the validated response.

## Guardrails

The validator must be rule-based. Tests must pass without real API keys, real
STT, real TTS, Unreal Engine runtime, remote OpenKB, or real Developer A/B
agents.

LangGraph may orchestrate Developer C-owned workflow nodes only. It must not
replace the Developer B scenario state machine, rule-based branch control, or
the validator.
