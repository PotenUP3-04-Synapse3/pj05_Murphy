# Portfolio - Developer B

## Project Title

Murphy's Trippin - AI Travel English Survival Simulator

## My Role

Developer B: English level, hint policy, scenario progression rules, Chapter 0
immigration node design, result scoring policy, and rule-based branch
recommendations.

## Problem

The game needs a deterministic policy layer that can turn messy travel English,
Korean-influenced English, or short broken answers into safe learning feedback
and scenario progression. Developer C owns the orchestration and validator, so
Developer B must provide a replaceable policy engine that is strict about JSON
contracts and never generates NPC dialogue, TTS, Unreal commands, or backend
response envelopes.

## Technical Contribution

Developer B aligned the source planning documents under `data/assets/dev-b`
with the repository ownership rules in `AGENTS.md`, then implemented a
contract-compatible `dev_b_policy.v1` engine under the new owner-specific
package structure. The implementation consumes C-provided `DevBPolicyInput`
and returns `DevBPolicyOutput` with evaluation, level/hint decisions,
in-game feedback strategy, branch recommendations, state deltas, error capture,
out-game feedback seeds, dialogue directives, and report items.

Developer B also defined the full Chapter 0 immigration node context in
`backend/app/data/scenario_nodes.json`, including `IMM_001_PASSPORT` through
`IMM_007_FINAL_DECISION`, each with allowed next nodes and retry, clarify,
hint, warning, and bad-end branch candidates.

## Architecture

The Developer B implementation is split into a small public agent and focused
services:

- `backend/app/agents/agent_b/english_level_hint_agent.py` is the policy entry
  point for C adapter integration.
- `backend/app/services/service_b/scenario_state_machine.py` owns deterministic
  verdict, branch, next-action, next-node, and state-delta decisions.
- `backend/app/services/service_b/level_adaptation_controller.py` owns English
  level, CEFR estimate, hint strength, hint type, and in-game feedback strategy.
- `backend/app/data/scenario_nodes.json` defines Chapter 0 immigration node
  content and branch candidates.

The C-owned adapter is intentionally left untouched. A change request documents
that Developer C should replace the current mock body of
`DevBPolicyClient.evaluate_turn()` with a delegation to
`EnglishLevelHintAgent.evaluate_turn()`.

## Main Modules

- English Level and Hint Agent
- Scenario State Machine
- Level Adaptation Controller
- Chapter 0 Immigration Node Specs
- Rule-based Branch Policy
- Error Capture Candidate Builder
- Out-game Feedback Seed Builder
- Dialogue Directive Metadata
- Developer B pytest suite

## Contract Design

Developer B uses the existing C-owned Pydantic schemas:

- Input: `DevBPolicyInput`
- Output: `DevBPolicyOutput`
- Contract version: `dev_b_policy.v1`

The implementation does not add fields such as `in_game_feedback.ui_hint` that
are absent from the stricter key-value contract. It keeps
`dialogue_directive.do_not_generate_npc_text` set to `true` because Developer A
owns final NPC dialogue and voice.

## Rule-based Policy

The branch policy is deterministic:

- Success advances only when required intent and required slots are satisfied.
- Clarify handles low confidence, STT repeat needs, or semantic ambiguity.
- Retry handles missing task intent or slot on early attempts.
- Hint handles repeated failure and Bronze/beginner support conditions.
- Warning and bad-end handle critical immigration risk expressions.
- Every `branch.next_node_id` is checked against `node_context.allowed_next_nodes`
  and, when present, `client_allowed_next_nodes`.

## Node Design

The Chapter 0 immigration flow now covers:

- `IMM_001_PASSPORT`
- `IMM_002_PURPOSE`
- `IMM_003_DURATION`
- `IMM_004_STAY_LOCATION`
- `IMM_005_RETURN_TICKET`
- `IMM_006_DECLARATION_CHECK`
- `IMM_006B_PACKED_BAG_CHECK`
- `IMM_007_FINAL_DECISION`

Each node defines required intents, required slots, optional slots, critical
slots, allowed slot values, risk keywords, a recommended expression, Korean hint
base text, hint policy candidates, branch candidates, and allowed next nodes.

## Reliability Design

The policy engine has no external API dependency and does not require LLM keys,
STT providers, TTS providers, Unreal runtime, or remote OpenKB. It is designed
for C to call through an adapter, and for C's validator to remain the final
safety gate.

Developer B coordination requests are recorded in
`docs/contracts/change_requests.md`:

- C should wire `dev_b_level_hint_client.py` to the B engine.
- C should sync or consume `backend/app/data/scenario_nodes.json` in the
  C-owned OpenKB runtime.

## Testing

Developer B added `backend/tests/dev_b/test_developer_b_policy_engine.py`.

Covered scenarios:

- Clear purpose answer advances from `IMM_002_PURPOSE` to `IMM_003_DURATION`.
- Broken English such as `Travel. New York.` and `I go travel five days` records
  form feedback without immediate bad-end failure.
- Unclear answers trigger clarify.
- Repeated failures trigger hint.
- Risky immigration answers trigger warning or bad-end behavior.
- Branch recommendations stay inside allowed next nodes.
- Empty allowed-next-node context raises `ValueError`.
- All Chapter 0 nodes define branch candidates and allowed next nodes.
- Report items, feedback tags, error capture, and out-game feedback seeds are
  returned.

Latest verification:

- `uv run pytest backend/tests/dev_b -q`: 10 passed
- `uv run pytest`: 23 passed, 2 warnings
- `uv run ruff check .`: passed
- `uv run mypy .`: passed, 51 source files

## Demo Scenarios

- Happy path: clear tourism purpose answer advances to the stay-duration node.
- Broken English support: short or Korean-influenced English stays playable and
  produces form-focused feedback.
- Retry path: missing slot or off-target answer reasks without unsafe branch
  movement.
- Hint path: repeated failure gives a sentence-pattern hint.
- Warning or bad-end path: illegal work, overstay, unknown item, or unsafe bag
  content expressions raise suspicion and branch to C-validated warning/fail
  outcomes.

## Resume Bullets

- Implemented a deterministic Developer B policy engine for an Unreal Engine
  travel-English game prototype using contract-first Pydantic input/output.
- Designed Chapter 0 immigration scenario node specs covering passport,
  purpose, duration, stay location, return ticket, declaration, bag check, and
  final decision flows.
- Built a rule-based scenario state machine for success, retry, clarify, hint,
  warning, bad-end, and final branch recommendations.
- Added English level and hint adaptation logic for beginner/Bronze,
  intermediate/Silver, and advanced/Gold player profiles.
- Generated structured `state_delta`, `error_capture`,
  `out_game_feedback_seed`, `dialogue_directive`, and `report_item` payloads
  without crossing into NPC dialogue, TTS, STT, validator, or Unreal response
  ownership.
- Added focused pytest coverage for broken English, branch safety, risk
  handling, node spec completeness, and feedback/report payload generation.
- Documented cross-owner integration requirements so Developer C can replace
  the mock adapter with the real B policy engine without changing schemas.
