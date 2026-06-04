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

1. Receive an Unreal turn request with a required wav audio file and turn
   metadata.
2. Run STT with a deterministic mock or provider implementation and create
   normalized player text.
3. Load OpenKB node context for the current scenario node.
4. Run the Understanding Agent to produce semantic evidence only. The
   Understanding Agent may use deterministic rule mode or optional real AI mode,
   but it must not produce branch, score, hint, NPC dialogue, or Unreal command
   fields.
5. Call the Developer B policy adapter for evaluation, level, hint, in-game
   feedback strategy, error capture, out-game feedback seed, state delta, and
   branch recommendation.
6. Record Developer B error capture markdown when validation allows it.
7. Call the Developer A dialogue adapter for NPC response text and presentation
   hints.
8. Build Unreal response JSON from validated Developer A and B outputs.
9. Validate the response with rule-based checks, including branch transition
   safety.
10. Append a Developer C unified AgentRun record with orchestration events and
    safe data-flow summaries.
11. Return the validated response.

Developer C currently assumes all Unreal player input is wav audio. The public
Unreal request does not need an `input_type` field. Developer C sets
`input_source.input_type` to `voice` internally when building downstream
adapter payloads.

Detailed C-side schema and adapter contracts:

- `docs/contracts/developer_c_schema_contract.md`
- `docs/contracts/developer_c_adapter_contracts.md`

## Guardrails

The validator must be rule-based. Tests must pass without real API keys, real
STT, real TTS, Unreal Engine runtime, remote OpenKB, or real Developer A/B
agents.

LangGraph may orchestrate Developer C-owned workflow nodes only. It must not
replace the Developer B scenario state machine, rule-based branch control, or
the validator.
