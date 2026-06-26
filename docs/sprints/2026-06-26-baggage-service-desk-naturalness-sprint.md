# 2026-06-26 Baggage Service Desk Naturalness Sprint

## Problem

In the latest BAG_001 run, the player only greeted Brielle or said they were
just there to say hello. The backend correctly kept the turn at
`BAG_001_REPORT_MISSING_AT_DESK` with required slot `missing_bag_statement`,
but Developer A's final line jumped ahead to:

> Do you have your baggage claim tag or ticket?

That question belongs to `BAG_002_PROVIDE_CLAIM_TAG`, after the player has
reported the baggage problem. Asking it before the problem statement makes the
desk interaction feel mechanical and out of order.

## Sprint Steps

1. Red tests
   - Added a fallback synthesis regression proving
     `report_missing_bag_at_service_desk` must ask what happened with the bag,
     not ask for claim tag or ticket.
   - Added an LLM-path regression where the LLM prematurely asks for the claim
     tag. The expected behavior is to keep the LLM call alive but align the
     final question with the current BAG_001 slot.

2. Surface-goal alignment
   - Updated the Developer A `SURFACE_GOAL_QUESTIONS` entry for
     `report_missing_bag_at_service_desk` to ask:
     `What happened with your bag?`
   - This keeps BAG_001 retry/clarify turns on the current social/service
     obligation: first hear the baggage problem, then move to claim-tag
     collection on BAG_002.

3. LLM instruction alignment
   - Updated Developer A's runtime LLM instructions so
     `surface_goal=report_missing_bag_at_service_desk` means asking what
     happened with the bag or what baggage problem needs help.
   - The prompt now explicitly says not to ask for claim tag, baggage ticket,
     or boarding pass until `surface_goal=ask_claim_tag_or_ticket`.

## Verification

- RED:
  `uv run pytest backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_desk_fallback_dialogue backend/tests/test_developer_a_npc_dialogue.py::test_baggage_service_desk_rejects_claim_tag_question_before_problem_report -q`
  failed: 2 failed.

- GREEN:
  same command passed: 2 passed, 1 warning (`audioop` deprecation).

- Broader A dialogue regression:
  `uv run pytest backend/tests/test_developer_a_npc_dialogue.py -q`
  passed: 71 passed, 1 warning (`audioop` deprecation).

- Related preprototype checks:
  `uv run pytest backend/tests/test_preprototype_flow.py::test_orchestrator_advances_baggage_report_to_claim_tag_node backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata -q`
  passed: 2 passed, 1 warning (`audioop` deprecation).

## Next Direction

The next naturalness layer should be a small service-recovery dialogue corpus:

- greeting-only player turns,
- off-topic social turns,
- rude but non-abusive turns such as `What's your problem?`,
- valid missing-bag reports,
- premature claim-tag answers before the problem is known.

Each case should assert the current slot, allowed next move, and whether A
should preserve the LLM reaction or override only the next question.
