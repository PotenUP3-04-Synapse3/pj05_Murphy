# 2026-06-26 Immigration Work-Purpose Pragmatics Sprint

## Goal

Make immigration purpose answers such as "I'm here to work" behave like a
human procedural officer would handle them: not as a generic unclear visit
purpose, not as a hardcoded keyword branch, and not as automatic secondary
inspection. The LLM should provide the situation-level judgment, while C/B/A
carry that judgment through their normal contracts.

## Sprint A - Reproduce The Failure

- Added C coverage showing an LLM `pragmatic_context` card for an ambiguous
  work-purpose answer must become a work-authorization clarification, not an
  illegal-work accusation.
- Added B coverage showing the same evidence must route to a `clarify` branch
  with branch reason `visa_work_authorization_clarification`, not warning or
  generic retry.
- Added A coverage showing dialogue must not re-ask "What is the purpose of
  your visit?", must not say "work issue", and must not send the player to
  secondary inspection for ambiguous legal work.
- Added an orchestrator regression showing the whole response stays `REASK` /
  `UNCLEAR` and asks about work visa or authorization.

## Sprint B - C Understanding Evidence

- Extended `PragmaticContextCard.player_move` with `visa_work_mismatch`.
- Updated the active Understanding LLM instructions and documented prompt to
  ask the model for visa/work-authorization pragmatic judgment instead of
  collapsing work claims into ordinary business visits.
- Merged `risk_evidence` tags and deltas from LLM output into the internal
  `risk_tags` / `risk_delta` fields.
- Added a generic postprocessing bridge that trusts an LLM
  `visa_work_mismatch` card and preserves its strength:
  `clarify` / `medium` becomes `visa_work_authorization_unclear` with
  `risk_delta < 20`, while high/critical warning cards can still become
  procedural risk.

## Sprint C - B Policy Routing

- Taught the scenario state machine to treat LLM pragmatic
  work-purpose mismatch evidence as either clarification or procedural risk
  based on the card strength.
- Removed `visa_work_mismatch` from the unconditional critical risk tags so
  ambiguous legal work is not punished as illegal work.
- Preserved the existing B authority: C provides evidence, B still chooses the
  clarify, warning, or secondary-inspection branch.

## Sprint D - A Dialogue Naturalness

- Extended A dialogue validation so LLM outputs that re-ask generic visit
  purpose are rejected on work-authorization clarification branches.
- Added fallback wording that asks the real procedural follow-up:
  whether the player means business meetings/short business travel or work for
  an employer, and whether a work visa or authorization can be verified.
- Updated long and short NPC dialogue prompts so the LLM is instructed to
  avoid generic purpose re-asks, avoid "work issue", and avoid secondary
  inspection unless the card is truly high/critical risk.

## Verification

- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_llm_pragmatic_card_clarifies_work_authorization backend/tests/dev_b/test_developer_b_policy_engine.py::test_llm_pragmatic_work_purpose_routes_to_authorization_clarification backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_fallback_asks_authorization_not_secondary backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_llm_output_is_not_accepted_as_generic_purpose_reask backend/tests/test_preprototype_flow.py::test_orchestrator_routes_work_purpose_to_authorization_clarification_not_secondary -q`
  - RED first: 5 failed for over-escalation / generic purpose re-ask.
  - GREEN after correction: 5 passed.
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/dev_b/test_developer_b_policy_engine.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_preprototype_flow.py -q`
  - GREEN: 273 passed, 1 warning (`audioop` deprecation).
- `uv run pytest -q`
  - GREEN: 551 passed, 1 warning (`audioop` deprecation).
- `uv run ruff check .`
  - GREEN: all checks passed.
- `uv run mypy .`
  - GREEN: no issues found in 149 source files.
- `git diff --check`
  - GREEN: no whitespace errors; Git printed Windows LF-to-CRLF conversion warnings only.

## Next Recommended Step

Run a live `/respond-dialog` immigration pass with LLM understanding enabled and
try variants such as "I'm here to work", "I'm here to work as a software
engineer", "I'll help my uncle's shop", "I have a work visa", and "I have
business meetings" to make sure the LLM separates ambiguous employment,
lawful authorization, explicit illegal work, and ordinary business visits.
