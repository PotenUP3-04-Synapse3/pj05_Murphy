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
- Moved `visa_work_authorization_clarification` before the cumulative
  critical-risk gate and set its `suspicion_delta` to 0. Repeated medium
  work-authorization clarifications should remain procedural clarification, not
  build up to automatic secondary inspection.
- Preserved the existing B authority: C provides evidence, B still chooses the
  clarify, warning, or secondary-inspection branch.

## Sprint D - A Dialogue Naturalness

- Extended A dialogue validation so LLM outputs that re-ask generic visit
  purpose are rejected on work-authorization clarification branches.
- Follow-up live run showed the phrase `Could you tell me why you're here`
  still passed as too-vague LLM dialogue. A now rejects work-authorization
  clarification output unless it contains concrete visa/authorization/employer
  or business-meeting specificity.
- Added fallback wording that asks the real procedural follow-up:
  whether the player means business meetings/short business travel or work for
  an employer, and whether a work visa or authorization can be verified.
- Updated long and short NPC dialogue prompts so the LLM is instructed to
  avoid generic purpose re-asks, avoid "work issue", and avoid secondary
  inspection unless the card is truly high/critical risk.

## Sprint E - Close The Work-Visa Clarification

- Reproduced the follow-up loop where the player answered
  `I said, I'm here to work. Check my visa. I have a work visa.` but C still
  preserved the LLM's `visa_work_mismatch` card, so B kept routing back to
  `IMM_EXTRA_001_CLARIFY_PURPOSE`.
- Added a C semantic repair for explicit work authorization confirmations:
  work visa, work permit, employment authorization, or authorized-to-work
  language now closes the clarification as `visit_purpose=work` plus
  `work_authorization_status=confirmed`.
- Kept `I'm here to work.` as a clarification case. The repair is only for a
  direct authorization confirmation, so ambiguous work is not silently accepted
  and explicit no-authorization / illegal-work language still remains eligible
  for risk handling.
- Updated Understanding LLM instructions and the documented prompt so the LLM
  should produce the same outcome before C's repair has to intervene.
- Added an orchestrator regression proving the whole response advances to
  `IMM_003_DURATION` instead of repeating a purpose question.

## Sprint F - Preserve The Work-Authorization Fallback Text

- Reproduced the remaining live `/respond-dialog` symptom where
  `I'm here to work.` correctly triggered
  `branch_reason=visa_work_authorization_clarification`, A correctly rejected
  the generic LLM output with `work_authorization_reask_violation`, but the
  fallback still ended as `Could you tell me why you're here?` or
  `What brings you to the United States?`.
- Root cause: A built the correct work-authorization fallback first, then
  retry variation / non-ADVANCE generic question override saw
  `surface_goal=ask_visit_purpose` and overwrote the specialized fallback with
  a generic visit-purpose paraphrase.
- A now excludes work-authorization clarification branches from those generic
  retry variation and non-ADVANCE override paths, preserving the concrete
  visa/work authorization question.

## Verification

- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_llm_mode_closes_work_authorization_when_work_visa_is_confirmed -q`
  - RED first: 1 failed because C kept `intent_success=false`,
    `visa_work_authorization_unclear`, and the `visa_work_mismatch` card.
- `uv run pytest backend/tests/test_preprototype_flow.py::test_orchestrator_advances_work_purpose_after_work_visa_confirmation -q`
  - RED first: 1 failed because the integrated response was still `REASK`.
- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_llm_mode_closes_work_authorization_when_work_visa_is_confirmed backend/tests/test_preprototype_flow.py::test_orchestrator_advances_work_purpose_after_work_visa_confirmation -q`
  - GREEN after correction: 2 passed, 1 warning (`audioop` deprecation).
- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_llm_pragmatic_card_clarifies_work_authorization backend/tests/dev_b/test_developer_b_policy_engine.py::test_llm_pragmatic_work_purpose_routes_to_authorization_clarification backend/tests/dev_b/test_developer_b_policy_engine.py::test_repeated_work_authorization_clarification_does_not_escalate_to_secondary backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_fallback_asks_authorization_not_secondary backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_llm_output_is_not_accepted_as_generic_purpose_reask backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_llm_output_rejects_vague_why_here_reask backend/tests/test_preprototype_flow.py::test_orchestrator_routes_work_purpose_to_authorization_clarification_not_secondary -q`
  - GREEN: 7 passed, 1 warning (`audioop` deprecation).
- `uv run pytest backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_fallback_is_not_overwritten_by_retry_variation -q`
  - RED first: 1 failed because the fallback was overwritten to
    `What brings you to the United States?`.
  - GREEN after correction: 1 passed, 1 warning (`audioop` deprecation).
- `uv run pytest backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_fallback_asks_authorization_not_secondary backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_llm_output_is_not_accepted_as_generic_purpose_reask backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_llm_output_rejects_vague_why_here_reask backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_fallback_is_not_overwritten_by_retry_variation backend/tests/test_preprototype_flow.py::test_orchestrator_routes_work_purpose_to_authorization_clarification_not_secondary -q`
  - GREEN: 5 passed, 1 warning (`audioop` deprecation).
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/dev_b/test_developer_b_policy_engine.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_preprototype_flow.py -q`
  - GREEN: 278 passed, 1 warning (`audioop` deprecation).
- `uv run pytest -q`
  - GREEN: 556 passed, 1 warning (`audioop` deprecation).
- `uv run ruff check .`
  - GREEN: all checks passed.
- `uv run mypy .`
  - GREEN: no issues found in 149 source files.
- `git diff --check`
  - GREEN: no whitespace errors; Git printed Windows LF-to-CRLF conversion warnings only.
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/dev_b/test_developer_b_policy_engine.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_preprototype_flow.py -q`
  - GREEN: 277 passed, 1 warning (`audioop` deprecation).
- `uv run pytest -q`
  - GREEN: 555 passed, 1 warning (`audioop` deprecation).
- `uv run ruff check .`
  - GREEN: all checks passed.
- `uv run mypy .`
  - GREEN: no issues found in 149 source files.
- `git diff --check`
  - GREEN: no whitespace errors; Git printed Windows LF-to-CRLF conversion warnings only.
- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_llm_pragmatic_card_clarifies_work_authorization backend/tests/dev_b/test_developer_b_policy_engine.py::test_llm_pragmatic_work_purpose_routes_to_authorization_clarification backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_fallback_asks_authorization_not_secondary backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_llm_output_is_not_accepted_as_generic_purpose_reask backend/tests/test_preprototype_flow.py::test_orchestrator_routes_work_purpose_to_authorization_clarification_not_secondary -q`
  - RED first: 5 failed for over-escalation / generic purpose re-ask.
  - GREEN after correction: 5 passed.
- `uv run pytest backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_llm_output_rejects_vague_why_here_reask -q`
  - RED first: 1 failed because `Could you tell me why you're here` was
    accepted as valid LLM dialogue.
  - GREEN after A specificity guard: 1 passed.
- `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_llm_pragmatic_work_purpose_routes_to_authorization_clarification backend/tests/dev_b/test_developer_b_policy_engine.py::test_repeated_work_authorization_clarification_does_not_escalate_to_secondary -q`
  - RED first: 2 failed because clarification still added suspicion and
    repeated clarification escalated to `CRITICAL_FAIL`.
  - GREEN after B ordering/state-delta fix: 2 passed.
- `uv run pytest backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_fallback_asks_authorization_not_secondary backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_llm_output_is_not_accepted_as_generic_purpose_reask backend/tests/test_developer_a_npc_dialogue.py::test_work_purpose_clarification_llm_output_rejects_vague_why_here_reask backend/tests/test_preprototype_flow.py::test_orchestrator_routes_work_purpose_to_authorization_clarification_not_secondary backend/tests/test_understanding_agent.py::test_understanding_agent_llm_pragmatic_card_clarifies_work_authorization backend/tests/dev_b/test_developer_b_policy_engine.py::test_llm_pragmatic_work_purpose_routes_to_authorization_clarification -q`
  - GREEN: 6 passed.
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/dev_b/test_developer_b_policy_engine.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_preprototype_flow.py -q`
  - GREEN: 275 passed.
- `uv run pytest -q`
  - GREEN: 553 passed.
- `uv run ruff check .`
  - GREEN: all checks passed.
- `uv run mypy .`
  - GREEN: no issues found in 149 source files.
- `git diff --check`
  - GREEN: no whitespace errors; Git printed Windows LF-to-CRLF conversion warnings only.
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
