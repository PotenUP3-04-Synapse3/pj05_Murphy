# 2026-06-26 BAG_001 Service Intent Check Sprint

## Goal

Stop Brielle from treating a greeting-only player turn at the baggage desk as
an immediate missing-bag detail request. For BAG_001 social non-answers, the
natural repair should first check service intent:

```text
Are you here about a baggage problem?
```

not:

```text
What happened with your bag?
```

## Problem Observed

Latest live run:

- Player: `Hello.`
- Brielle: `Hi. What happened with your bag?`
- Player: `Hello.`
- Brielle: `I can help with baggage. What happened with your bag?`

The branch was correct, and A used the LLM path, but A's output still collapsed
back into a required-slot question. This sounded like a form-filling loop rather
than a human service-desk exchange.

## Root Cause

- BAG_001 starts with `Hi. How can I help you?`, which is closer to a service
  intent check than a hard demand for `missing_bag_statement`.
- A's fallback seed and non-ADVANCE post-processing still treated
  `report_missing_bag_at_service_desk` as "ask the missing-bag detail now."
- The LLM prompt told A to acknowledge social/meta turns but then ask what
  happened with the bag, so the LLM followed the slot objective instead of the
  social repair.

## Changes

### A - Fallback and LLM Guard

- Changed BAG_001 social repair fallback wording:
  - first greeting/social non-answer: `Hi. Are you here about a baggage problem?`
  - repeated/meta non-answer: `I understand. Are you trying to report a baggage
    issue, or just saying hello?`
- Added a BAG_001 service-intent repair helper in A's LLM post-processing.
  When the social context says the player is greeting/stalling/meta-talking at
  the baggage desk, A now uses the social fallback text instead of appending the
  generic `What happened with your bag?` surface-goal question.
- Updated A long prompt, short prompt, and runtime LLM instruction so LLM output
  is asked to check service intent before asking for bag details.

## Expected Behavior

```text
You: Hello.
Brielle: Hi. Are you here about a baggage problem?

You: Hello.
Brielle: Hi again. Are you here about a baggage problem, or just saying hello?
```

After the player confirms they need baggage help, the system can ask for the
actual bag problem detail.

## RED / GREEN

RED command:

```powershell
uv run pytest backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_desk_rejects_claim_tag_question_before_problem_report backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_greeting_fallback_sets_service_boundary_without_slot_loop backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_meta_non_answer_fallback_acknowledges_then_names_bag_options backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_social_llm_slot_question_is_rewritten_to_service_intent_check -q
```

RED result:

- 4 failed.
- Existing fallback and LLM guard still produced `What happened with your bag?`.

GREEN result:

- Same command passed: 4 passed, 1 warning (`audioop` deprecation).

Related regression:

```powershell
uv run pytest backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_prompt_rendering.py backend/tests/test_preprototype_flow.py::test_orchestrator_advances_baggage_report_to_claim_tag_node backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata -q
```

Result:

- 79 passed, 1 warning (`audioop` deprecation).

Full suite:

- `uv run pytest -q`: 567 passed, 1 warning (`audioop` deprecation).

Static checks:

- `uv run ruff check .`: passed.
- `uv run mypy .`: passed with no issues in 149 source files.
- `git diff --check`: passed. Git printed Windows LF-to-CRLF working-copy
  warnings only.

## Files Changed

- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/agents/agent_a/npc_llm_client.py`
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/prompts/npc_dialogue_prompt.short.md`
- `backend/app/services/service_a/developer_a_fallback_service.py`
- `backend/tests/test_developer_a_npc_dialogue.py`
- `docs/sprints/2026-06-26-baggage-service-intent-check-sprint.md`
- `docs/handoff.md`
