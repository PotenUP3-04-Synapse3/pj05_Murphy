# 2026-06-26 BAG_001 Service Boundary Repair Sprint

## Goal

Make Brielle sound like a real baggage service agent when the player gives a
social or meta non-answer at the first baggage desk node. This sprint avoids a
`hello`-specific fix by adding a semantic `meta_non_answer` conversation move
and by teaching A to produce a service-boundary repair instead of another
slot-loop line.

## Problem Observed

Latest live run:

- Brielle: `Hi. How can I help you?`
- Player: `Hello.`
- Brielle: `Sorry, I still need the bag problem. What happened with your bag?`
- Player: `What? I just had... I just said... Hello.`
- Brielle: `I still need the bag issue. What happened with your bag?`

The previous sprint fixed the claim-tag jump, but the line still felt like a
slot machine: it did not acknowledge the player's meta/social move, and it
repeated "I still need..." instead of behaving like a service-desk person.

## Root Cause

- C could label the second turn only as generic `off_topic`, so A lost the
  distinction between "random topic change" and "the player is objecting to or
  describing the conversation itself."
- B correctly kept the branch on the current BAG_001 obligation, but the
  lifecycle signal still arrived at A as a generic social repair.
- A's service-recovery fallback used generic "I need a response" / "I'm not
  sure you heard me" wording. For BAG_001 this sounded repetitive and did not
  establish the baggage-desk boundary.

## Sprint Changes

### C - Conversation Understanding

- Added `meta_non_answer` to `SocialContextCard.conversation_move`,
  `SocialContextCard.social_pattern`, and `ConversationActCard.player_act`.
- Added rule-mode detection for broad meta conversation moves such as "I just
  said...", "I only wanted to...", "I'm just here to...", and similar
  conversation-about-the-conversation utterances.
- Updated the Understanding LLM output schema so the LLM path can emit
  `meta_non_answer` too.

### B - Social Obligation Lifecycle

- Treated `meta_non_answer` as a social stall move in
  `SocialObligationLifecyclePolicy`, so existing service-recovery lifecycle
  progression still works.

### A - NPC Dialogue

- Updated the BAG_001 fallback surface question to `What happened with your
  bag?` in A's fallback service, matching the dialogue policy service.
- Added BAG_001-specific service-boundary repair wording:
  - first social non-answer: `Hi. This is the baggage desk...`
  - repeated/meta non-answer: `I understand. I can help if there's a baggage
    problem...`
- Updated A long/short prompts and runtime LLM instructions so LLM-generated
  lines follow the same behavior and do not ask for claim tags before the bag
  problem is reported.

## Expected Behavior

Example shape:

```text
You: Hello.
Brielle: Hi. This is the baggage desk. If you need help with a bag, tell me what happened.

You: What? I just said hello.
Brielle: I understand. I can help if there's a baggage problem. Is your bag missing, delayed, or damaged?
```

## RED / GREEN

RED command:

```powershell
uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_baggage_meta_greeting_objection_marks_meta_non_answer backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_greeting_fallback_sets_service_boundary_without_slot_loop backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_meta_non_answer_fallback_acknowledges_then_names_bag_options -q
```

RED result:

- 3 failed.
- C returned `off_topic` instead of `meta_non_answer`.
- A returned `I need a response so we can continue...` and
  `I'm not sure you heard me...`.

GREEN result after implementation:

- Same command passed: 3 passed, 1 warning (`audioop` deprecation).

Additional focused check:

```powershell
uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_baggage_meta_greeting_objection_marks_meta_non_answer backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_greeting_fallback_sets_service_boundary_without_slot_loop backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_meta_non_answer_fallback_acknowledges_then_names_bag_options backend/tests/test_developer_a_prompt_rendering.py -q
```

Result:

- 6 passed, 1 warning (`audioop` deprecation).

## Files Changed

- `backend/app/schemas/game_turn.py`
- `backend/app/agents/agent_c/understanding_agent.py`
- `backend/app/agents/agent_c/understanding_llm_client.py`
- `backend/app/services/service_b/social_obligation_lifecycle_policy.py`
- `backend/app/services/service_a/developer_a_fallback_service.py`
- `backend/app/agents/agent_a/npc_llm_client.py`
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/prompts/npc_dialogue_prompt.short.md`
- `backend/tests/test_understanding_agent.py`
- `backend/tests/test_developer_a_npc_dialogue.py`
- `backend/tests/dev_b/test_developer_b_policy_engine.py`

## Next Checks

Additional verification:

```powershell
uv run pytest backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_understanding_agent.py backend/tests/dev_b/test_developer_b_policy_engine.py::test_customs_hold_social_stall_lifecycle_uses_repair_not_hint_loop backend/tests/test_preprototype_flow.py::test_orchestrator_advances_baggage_report_to_claim_tag_node backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata -q
```

Result:

- 119 passed, 1 warning (`audioop` deprecation).

Full-suite verification initially caught a regression where the new
`meta_non_answer` category was too broad for flight pen-loop recovery:

- `Why do you keep asking me about my pen? I already gave it to you.` was being
  treated as a meta non-answer even though the turn also addressed the prior pen
  obligation.

Follow-up fix:

- `meta_non_answer` no longer overrides already-satisfied understanding output.
- Flight pen-obligation answers such as `already gave` / `gave it to you` now
  take priority over reciprocal-question handling.

Regression command:

```powershell
uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_flight_meta_pen_objection_keeps_belated_answer_priority backend/tests/test_preprototype_flow.py::test_orchestrator_forwards_flight_history_and_neutral_slots_to_prevent_pen_loop_legacy backend/tests/test_preprototype_flow.py::test_orchestrator_prevents_pen_loop_in_default_memory_mode -q
```

Result:

- 3 passed, 1 warning (`audioop` deprecation).

Full suite:

- `uv run pytest -q`: 566 passed, 1 warning (`audioop` deprecation).

Static checks:

- `uv run ruff check .`: passed.
- `uv run mypy .`: passed with no issues in 149 source files.
- `git diff --check`: passed. Git printed Windows LF-to-CRLF working-copy
  warnings only.
