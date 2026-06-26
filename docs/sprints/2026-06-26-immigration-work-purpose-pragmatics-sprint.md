# 2026-06-26 Immigration Work-Purpose Pragmatics Sprint

## Goal

Make immigration purpose answers such as "I'm here to work" behave like a
human procedural officer would handle them: not as a generic unclear visit
purpose, and not as a hardcoded keyword branch. The LLM should provide the
situation-level judgment, while C/B/A carry that judgment through their normal
contracts.

## Sprint A - Reproduce The Failure

- Added C coverage showing an LLM `pragmatic_context` card for a work-purpose
  visa mismatch must not fall back to generic rule understanding.
- Added B coverage showing the same evidence must route to a risk-control
  warning branch, not a generic retry.
- Added A coverage showing risk-control dialogue must not re-ask "What is the
  purpose of your visit?"
- Added an orchestrator regression showing the whole response avoids purpose
  re-ask wording and mentions visa / secondary inspection.

## Sprint B - C Understanding Evidence

- Extended `PragmaticContextCard.player_move` with `visa_work_mismatch`.
- Updated the active Understanding LLM instructions and documented prompt to
  ask the model for visa/work-authorization pragmatic judgment instead of
  collapsing work claims into ordinary business visits.
- Merged `risk_evidence` tags and deltas from LLM output into the internal
  `risk_tags` / `risk_delta` fields.
- Added a generic postprocessing bridge that trusts an LLM
  `visa_work_mismatch` card and raises procedural risk evidence without
  inspecting the utterance string directly.

## Sprint C - B Policy Routing

- Taught the scenario state machine to treat high-confidence LLM pragmatic
  work-purpose mismatch evidence as procedural risk.
- Added `visa_work_mismatch` as a critical risk tag.
- Preserved the existing B authority: C provides evidence, B still chooses the
  warning / secondary-inspection branch.

## Sprint D - A Dialogue Naturalness

- Extended A risk-control detection beyond violent threats so LLM outputs that
  re-ask visit purpose are rejected on work-purpose procedural branches.
- Added fallback wording that explains the actual procedural reason:
  visa/work authorization must be verified, so the traveler goes to secondary
  inspection.
- Updated long and short NPC dialogue prompts so the LLM is instructed to
  avoid generic purpose re-asks on this branch.

## Verification

- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_llm_pragmatic_card_escalates_work_purpose_risk backend/tests/dev_b/test_developer_b_policy_engine.py::test_llm_pragmatic_work_purpose_risk_routes_to_warning_not_generic_retry backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_warning_fallback_does_not_reask_visit_purpose backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_llm_output_is_not_accepted_as_generic_purpose_reask -q`
  - RED first: 4 failed for missing schema / policy / dialogue guard.
  - GREEN after implementation: 4 passed.
- `uv run pytest backend/tests/test_preprototype_flow.py::test_orchestrator_routes_work_purpose_pragmatic_risk_to_secondary_not_purpose_reask -q`
  - GREEN: 1 passed.
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
try variants such as "I'm here to work", "I'll help my uncle's shop", and "I
have business meetings" to make sure the LLM separates lawful business visits
from work-authorization mismatch.
