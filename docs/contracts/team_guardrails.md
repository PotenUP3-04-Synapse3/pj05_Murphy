# Team Guardrails Contract

## Purpose

This contract protects the boundaries between Developer A, Developer B, and
Developer C while the Chapter 0 Immigration Check prototype is built in phases.

All developer agents should read `AGENTS.md` before editing. Developer A and B
also have start prompts under `docs/prompts/`.

## Developer A Ownership

Developer A owns NPC dialogue generation, TTS, NPC voice style, NPC feedback
tone, and related prompts or services.

Developer C must not modify Developer A implementation files. Developer C may
create adapters, mocks, interfaces, and contract tests that call or simulate
Developer A outputs.

Developer A start prompt:

- `docs/prompts/developer_a_start_prompt.md`

## Developer B Ownership

Developer B owns English level and hint logic, scenario state machine behavior,
level adaptation, scenario node rules, hint policy, OpenKB content design, and
result score policy.

Developer C must not modify Developer B implementation files. Developer C may
create adapters, mocks, schemas, and contract docs that call or simulate
Developer B outputs.

Developer B start prompt:

- `docs/prompts/developer_b_start_prompt.md`

## Developer C Ownership

Developer C owns the backend entry point, STT interface, understanding agent,
OpenKB retrieval, orchestrator, validator, Unreal-safe response builder,
Developer A/B adapters, Developer C tests, contracts, handoff notes, and
portfolio documentation.

## File Classification Rule

Before editing a file, classify it as one of:

- Developer C owned
- Shared contract
- Developer A owned
- Developer B owned
- Unknown

Developer C owned files may be edited. Shared contracts may be edited carefully
and documented. Developer A, Developer B, and unknown implementation files are
read-only unless the user explicitly approves a change.

## Change Requests

If Developer C needs a change from Developer A or Developer B, append the
request to `docs/contracts/change_requests.md` and summarize it in
`docs/handoff.md`.
