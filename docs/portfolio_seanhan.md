# Portfolio - Sean Han

Updated: 2026-06-21

## Project Title

Murphy's Trippin - AI Travel English Survival Simulator

## Role Summary

Developer C: AI backend safety and orchestration. Sean owns the FastAPI
integration surface, STT pipeline, Understanding Agent, LangGraph orchestration,
OpenKB retrieval, Developer A/B adapters, rule-based validators, Unreal-safe
response assembly, and C-owned AgentRun observability.

The portfolio source of truth is maintained from `docs/handoff.md`. The handoff
file remains the daily implementation ledger; this document distills those
changes into a hiring-ready narrative focused on problem definition, technical
judgment, and follow-up discipline.

## Problem Definition

Murphy's Trippin needs an AI backend that can sit between Unreal Engine and
multiple AI agents without letting nondeterministic model output directly
control gameplay. The player may speak or type English, Korean, or chaotic
Konglish during a JFK immigration scenario, and the game still needs a stable
JSON response with safe NPC dialogue, validated branch transitions, optional
audio, learning feedback, and debug traces.

The difficult part was not simply calling an LLM. The real problem was building
a backend boundary where AI can help interpret messy language while deterministic
rules still own branch safety, Unreal command validity, team ownership, test
repeatability, and provider-key isolation.

## Why This Architecture

- Unreal needs deterministic response JSON, so Developer C validates every
  branch transition and command before returning data to the game.
- Developer A owns NPC dialogue and voice, and Developer B owns learning policy
  and scenario progression. Developer C integrates their outputs through
  adapters instead of rewriting their business logic.
- LLM understanding can be useful for semantic evidence, but it must not own
  scenario branching, scoring, NPC text, or Unreal commands.
- Tests must pass without real API keys, real STT/TTS providers, Unreal runtime,
  or remote OpenKB, so provider-backed paths are environment-controlled and
  deterministic fallbacks stay first-class.
- Debugging AI behavior requires structured runtime evidence, so C writes
  unified AgentRun records instead of relying on ad hoc console output.

## Current Backend Flow

1. Unreal calls `POST /api/game/ai/respond`.
2. Developer C normalizes text input or routes voice input through STT.
3. C loads scenario context from local/OpenKB-backed data.
4. The Understanding Agent extracts semantic evidence from the player turn.
5. C calls the Developer B adapter for level, hint, feedback, and branch policy.
6. C validates B's policy output and B-owned OpenKB write references.
7. C calls the Developer A adapter for NPC dialogue and optional audio.
8. C assembles the Unreal response JSON.
9. C validates branch transitions, commands, audio URLs, and authority
   boundaries.
10. C returns the validated response and appends AgentRun observability data.

## Developer C Technical Detail

### FastAPI Surfaces

- Primary gameplay endpoint: `POST /api/game/ai/respond`.
- Realtime STT endpoint: `/api/game/ai/stt/stream`.
- Result and demo support endpoints expose integrated pre-prototype behavior
  without requiring Unreal during local development.
- Health and diagnostics routes support quick operational checks.

### LangGraph Orchestration and Tool Nodes

Sean refactored the original procedural orchestrator into a LangGraph v1.2.2
workflow. The graph keeps orchestration explicit and inspectable while each step
stays in C-owned graph tools.

The C graph tool sequence is:

- `start_agent_run_tool`
- `transcribe_audio_tool`
- `load_node_context_tool`
- `understand_player_text_tool`
- `evaluate_dev_b_policy_tool`
- `validate_dev_b_policy_tool`
- `record_error_capture_tool`
- `generate_dev_a_dialogue_tool`
- `build_unreal_response_tool`
- `validate_unreal_response_tool`
- `finish_agent_run_tool`

Each graph step is also wrapped as a LangChain `StructuredTool` through
`DeveloperCStructuredToolInput`, which keeps the implementation compatible with
current direct graph invocation and future `ToolNode`/subgraph migration.

### Middleware and AgentRun Observability

Developer C owns `middleware_c` for orchestration-level AgentRun construction.
The middleware records a structured timeline for each backend turn, including
runtime mode, selected tools, STT metadata, Understanding traces, adapter
summaries, validation outcomes, fallback reasons, token/cost estimates, and
safe error details.

The shared log writer appends unified JSONL and Markdown records, but C remains
responsible for constructing C events and for avoiding unsafe data such as API
keys, raw wav payloads, full prompts, or another developer's private business
logic.

### Understanding Agent Guardrails

The Understanding Agent extracts evidence such as intent, language, supported
slots, missing slots, ambiguity, incivility signals, and semantic satisfaction.
It does not choose the next node, rewrite Developer B policy, author NPC
dialogue, or emit Unreal commands.

Real LLM mode uses structured JSON output with repair/fallback behavior. Rule
fallbacks remain available so tests and local demos can run without provider
credentials. Recent updates added open/numeric/closed/system slot policy
handling, `intent_satisfied`, `judgment_reason`, generic immigration slot
evidence, and off-topic/smalltalk safeguards. For the Alpha Flight scene, Sean
also changed the C Understanding layer to treat the seatmate exchange as a
single free smalltalk diagnostic node: the legacy pen-request slot is stripped
from runtime scoring, meaningful follow-up answers can advance, and Developer B
still blocks true abuse and critical-risk cases.

### Adapter Boundaries

The Developer B adapter consumes C understanding evidence and returns policy
output, hint/feedback data, and B-owned write references. C validates the shape,
branch authority, and write-reference namespace before consuming it.

The Developer A adapter receives sanitized context, B transition data, dialogue
seed fields, short-term history previews, challenge metadata, incivility
signals, and TTS mode configuration. C filters private or misleading context so
A can write natural NPC dialogue without taking over branch or state authority.
Recent Flight work added a second adapter guard: free-smalltalk turns arrive at
A with neutralized legacy slots and recent dialogue history, preventing the NPC
from treating the opening pen favor as an unresolved required task.

### Validator and Unreal Guardrails

The validator is deliberately rule-based. It rejects unsafe branch transitions,
invalid command payloads, malformed audio paths, attempts by A output to alter B
state, and response shapes that Unreal should not execute. This keeps the final
game contract stable even when upstream AI output is variable.

### STT and Provider Safety

C supports local/batch STT fallback and a realtime STT WebSocket relay path. The
realtime relay keeps provider keys on the server, records provider metadata in
safe AgentRun debug logs, and leaves deterministic local behavior available for
CI-style verification.

## Process Narrative

### 1. Contract-First Bootstrap

Sean first established `uv`, FastAPI, dependency contracts, ownership rules,
Developer A/B/C onboarding prompts, and bootstrap tests. This made parallel
agent development possible without each developer silently changing another
developer's scope.

### 2. From Harness to Integrated Turn Flow

The initial backend was a minimal health route and target contract. It evolved
into an integrated AI-only pre-prototype that accepts Unreal-style text or
voice input, calls A/B adapters, builds validated JSON, and exposes demo
surfaces for local iteration.

### 3. From Procedural Orchestration to LangGraph

Sean replaced hardcoded orchestration with a C-owned LangGraph workflow. The
reason was traceability: each backend turn now has named stages, explicit state,
structured tool wrappers, and clearer failure boundaries.

### 4. LLM Help Without LLM Authority

The Understanding Agent was expanded to support structured LLM output, semantic
slot evidence, incivility classification, and fallback repair. The important
design choice was limiting the LLM to evidence extraction while B keeps branch
policy and C keeps final validation.

### 5. Natural Dialogue Through Safer Context

As A/B integration matured, C added public node context filtering, dialogue
seed cleanup, short-term history previews, arrival-form state forwarding,
customs challenge scoping, and speaker-mismatch diagnostics. These changes
improved NPC naturalness while preserving A/B/C boundaries.

### 6. Runtime Follow-Up and Debuggability

C added unified AgentRun logging, realtime STT debug records, structured failure
details, result feedback exposure, and session usage summaries. The goal was to
make every AI turn explainable after the fact, not just functional during a
demo.

### 7. Free Smalltalk Repair Under Demo Pressure

When Flight dialogue kept falling into `UNCLEAR/REASK`, Sean traced the unified
AgentRun data flow and found that C was still scoring every seatmate turn
against the first pen-request slot. He refactored C's Flight understanding into
a single-node free-response diagnostic and, with explicit emergency approval,
patched B's policy under demo pressure. A follow-up runtime check then corrected
the design again: refusing the pen is still useful English-level evidence, so
the final behavior lets non-abusive refusals continue while preserving true
abuse and critical-risk guardrails.

A later unified log exposed a subtler follow-up bug: B was rotating through
different diagnostic probes, but A kept returning to the pen because C had
stopped sending dialogue history by default and B/A-facing metadata still named
`polite_response` as the active target. Sean fixed the boundary end to end:
Flight B metadata now carries probe intent instead of pen-slot intent, C sends
recent dialogue history by default, the A adapter neutralizes legacy Flight
slots, and A has a small post-processing guard against repeated pen requests.
The next runtime check caught second-order naturalness issues: form/address
probes were still valid in B's Flight diagnostic pool, and A could ask a new
question on a `COMPLETE_CHAPTER` turn. Sean tightened the Flight probe policy
and added a completion-closing guard so the demo ends with a natural close
instead of a new conversational obligation.

Sean then applied the same follow-up discipline to the Immigration demo path.
Unified logs showed that B's branch decisions were often correct, but C could
underweight a passport handover phrase and A could ask dialogue that did not
match B's next node. Sean added C-side passport handover repair and A-side
Immigration guards so official dialogue follows the canonical next question,
formal retry text stays clean, and current slot evidence wins over stale
dialogue memory. A later runtime pass exposed second-order clearance issues:
prior-visit answers and "good to go" confirmations were valid English evidence
but could still be scored as missing slots. Sean tightened C's deterministic
slot repair and A's final-clearance surface-goal guard so the Immigration scene
can close naturally instead of looping through unclear reasks.

## Reliability and Guardrails

- Rule-based final validator for Unreal-facing safety.
- Environment-controlled runtime modes for STT, TTS, NPC dialogue, and
  Understanding.
- Deterministic mocks and fallbacks for tests without provider credentials.
- Adapter contracts that prevent C from owning A dialogue or B scenario policy.
- Namespace validation for B-owned OpenKB writes.
- C-owned AgentRun summaries with safe redaction and bounded debug detail.
- Change requests and handoff notes when cross-owner changes are needed.

## Testing and Evidence

The project uses `uv run pytest`, `uv run ruff check .`, and `uv run mypy .` as
the required verification baseline. Handoff entries record focused and full-run
results for major C milestones, including LangGraph orchestration, realtime
STT, StructuredTool wrappers, adapter guardrails, slot policy changes, and
integration fixes.

This portfolio is intentionally not a raw changelog. It is updated from the
handoff record so implementation progress can be converted into interview-ready
evidence of architecture, ownership, reliability, and follow-through.

## Demo Coverage

- Happy path immigration turn.
- Retry or hint path when required information is missing.
- Bad ending or rejection path when the policy demands it.
- STT fallback path for voice input.
- Realtime caption/STT relay path.
- Result feedback path for out-game learning summary.

## Resume Bullets

- Designed and implemented the Developer C FastAPI AI backend layer for an
  Unreal Engine travel-English simulator.
- Built a LangGraph v1.2.2 orchestration workflow with named C-owned tool nodes
  for STT, OpenKB context loading, understanding, A/B adapter calls, response
  assembly, validation, and AgentRun completion.
- Wrapped C graph steps as LangChain `StructuredTool` objects to keep the
  current graph stable while preparing for future `ToolNode` or subgraph
  migration.
- Implemented an Understanding Agent that uses structured LLM output, rule
  fallback, semantic slot evidence, incivility signals, and deterministic repair
  without giving the LLM branch or command authority.
- Built rule-based validators that protect Unreal from unsafe branch changes,
  malformed commands, invalid audio URLs, and cross-agent authority leaks.
- Integrated Developer A/B implementations through adapters while preserving
  ownership boundaries for NPC dialogue, TTS, learning policy, and scenario
  progression.
- Added provider-safe STT paths, including local/batch fallback and a realtime
  WebSocket relay that keeps external provider keys server-side.
- Created unified AgentRun observability for C orchestration, including runtime
  modes, tool names, STT metadata, validation outcomes, model usage estimates,
  fallback reasons, and structured error diagnostics.
- Refactored the Alpha Flight seatmate scene from legacy slot gating into a
  free smalltalk diagnostic flow while preserving B-owned branch authority and
  critical social/risk guardrails.
- Used unified runtime logs to correct an over-strict follow-up decision:
  non-abusive pen refusal now continues the level diagnostic instead of stopping
  a natural A-generated question.
- Diagnosed and fixed a Flight pen-loop regression across A/B/C boundaries by
  restoring short-term dialogue history, removing legacy `polite_response`
  metadata from free-smalltalk payloads, and adding an A-side repeat guard.
- Followed unified runtime logs beyond the first fix to remove awkward
  form/address probes from Flight seatmate diagnostics and enforce non-question
  closing dialogue on `COMPLETE_CHAPTER`.
- Tightened the Immigration path by repairing passport handover understanding
  and guarding A dialogue against next-node mismatch, retry hook leakage, and
  stale slot contradictions.
- Followed up on Immigration runtime logs to repair first-visit and final
  clearance acknowledgement slots, stopping end-node `UNCLEAR/REASK` loops and
  preserving a natural demo close.
- Maintained contract-first documentation, handoff records, and portfolio notes
  so rapid daily backend changes remain traceable and reusable for employment
  storytelling.
