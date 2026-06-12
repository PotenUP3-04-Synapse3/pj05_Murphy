# Portfolio - Sean Han

## Project Title

Murphy's Trippin - AI Travel English Survival Simulator

## My Role

Developer C: STT, Understanding Agent, Orchestrator, OpenKB Retrieval,
Validator, Unreal Response JSON.

## Problem

The game needs a backend that can safely interpret messy multilingual player
input from Unreal Engine and return deterministic, validated commands that the
game can execute.

## Technical Contribution

Sean Han bootstrapped the Developer C backend harness, dependency contract, team
guardrails, documentation foundation, minimal FastAPI app, and bootstrap test
for a contract-first AI backend. He also prepared shared A/B/C agent guidance
and onboarding prompts so parallel developers can work without crossing
ownership boundaries.

## Architecture

The Phase 1 backend exposes a minimal FastAPI health route. The planned backend
flow receives Unreal input, normalizes text or voice input, loads local OpenKB
context, creates structured understanding data, calls replaceable Developer A/B
adapters, builds Unreal-safe JSON, and validates the result before returning it.
The current pre-prototype endpoint can run local Whisper STT and Developer A's
real Kokoro TTS through environment-controlled runtime modes while preserving
deterministic defaults for CI-style tests.
Sean also added an optional real AI mode for the Developer C Understanding
Agent, using structured JSON output with deterministic rule fallback so branch
authority remains with Developer B and final safety remains with Developer C
validation.
For Alpha realtime captions, Sean added a C-owned ElevenLabs WebSocket relay
with the existing local Whisper runtime kept as a batch fallback on committed
audio chunks, plus unified AgentRun debug logs for STT metadata, token counts,
and estimated cost.
Sean also refactored the Developer C turn orchestrator into a LangGraph v1.2.2
workflow with explicit state, C-owned graph tools, transition handling, and
unified AgentRun runtime metadata while preserving Developer A/B adapter
boundaries.

## Main Modules

- STT Pipeline
- Understanding Agent
- LangGraph Developer C Workflow
- Orchestrator
- OpenKB Retrieval
- Validator
- Response Assembler
- Developer A/B Integration Adapters

## API Contract

The target primary endpoint is `POST /api/game/ai/respond`. Phase 1 only
prepares the harness; the full endpoint contract is scheduled for a later phase.

## Agent Design

The Understanding Agent will use structured input/output and deterministic
fallback behavior so tests can pass without external LLM keys.

## Reliability Design

The backend will use rule-based validation, replaceable adapter mocks, local
OpenKB fallback data, and explicit ownership guardrails to prevent unsafe
cross-team changes. Shared `AGENTS.md` instructions and Developer A/B start
prompts make those boundaries visible to each agent before implementation
begins.

## Testing

Phase 1 establishes `pytest`, `ruff`, and `mypy` as required checks and includes
a bootstrap test for the FastAPI app. Later phases will add contract and flow
tests for the API, STT, OpenKB, understanding, validation, and full text/voice
paths.

## Demo Scenarios

- Happy path
- Retry path
- Bad ending path
- STT fallback path

## Resume Bullets

- Bootstrapped a contract-first FastAPI AI backend harness for an Unreal Engine
  language-learning game prototype.
- Defined team ownership guardrails separating orchestration, NPC dialogue,
  level/hint logic, and scenario branching responsibilities.
- Pinned and documented the AI framework dependency contract with `uv`,
  `langchain==1.3.2`, and `langgraph==1.2.2`.
- Added a minimal FastAPI health route with a pytest bootstrap check.
- Prepared shared A/B/C collaboration instructions and Developer A/B onboarding
  prompts for contract-first parallel work.
- Established a portfolio-ready documentation structure for backend
  architecture, reliability, and integration boundaries.
- Added a realtime STT relay/debug path that keeps provider keys server-side,
  preserves local STT fallback, and records audio/cost metadata in unified
  AgentRun logs.
- Replaced hardcoded C orchestration with a LangGraph state graph and C-owned
  graph tool wrappers without editing Developer A/B implementation files.
