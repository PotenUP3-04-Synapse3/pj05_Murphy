# 2026-06-25 Flight Completion Social Closure Sprint

## Goal

Prevent flight smalltalk from ending while Arabella still owes a natural
conversation answer, and make chapter-completion lines explain why the scene is
ending instead of dropping a generic goodbye.

## Sprint 1 - RED Coverage

- Added a B policy regression for the observed `Yes, what about you?` case.
- The test confirms that even when diagnostic evidence is sufficient for early
  completion, `conversation_act` duties such as `answer_briefly_then_continue`
  must keep the flight node on `ADVANCE`.
- Added A fallback regressions that reject abrupt `Enjoy your trip!`-only
  completion lines and require a scene-grounded reason.

## Sprint 2 - Completion Deferral

- `FlightSmallTalkDiagnosticPolicy` now treats `ConversationActCard` as a
  completion veto for early diagnostic exits.
- If the player asks a reciprocal question or C marks
  `should_answer_player_question`, B returns:
  `flight_smalltalk_answer_social_duty_before_complete`.
- The hard `MAX_TURNS` cap remains a cap; the deferral only blocks premature
  confidence-based completion.

## Sprint 3 - Closure Reason Card

- `DialogueSeed` now carries:
  - `completion_closure_reason`
  - `completion_closure_style`
  - `completion_do_not_ask_new_question`
- B fills this metadata for normal chapter completion:
  - flight: `landing_soon_and_arrival_form`
  - immigration: `immigration_cleared_to_baggage_claim`
  - baggage: `baggage_case_resolved`

## Sprint 4 - A Dialogue Consumption

- A fallback now turns completion metadata into natural closing lines.
- Flight completion now sounds like:
  `I should finish this form before we land, but it was nice talking with you. Enjoy your trip.`
- Immigration completion now says the player is cleared and can head to baggage
  claim.
- A LLM prompts now instruct the model to use `completion_closure_reason` and
  not ask new questions on completion turns.

## Verification

- RED confirmed:
  - `test_reciprocal_question_defers_completion_even_when_evidence_is_enough`
  - A completion fallback tests for abrupt closing text
- GREEN targeted:
  - `uv run pytest backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py::test_reciprocal_question_defers_completion_even_when_evidence_is_enough backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_reciprocal_question_gives_a_room_to_answer_first backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_completion_seed_explains_closure_reason -q`
  - `uv run pytest backend/tests/test_developer_a_npc_dialogue.py::test_complete_chapter_transition_returns_closing_phrase_for_each_role backend/tests/test_developer_a_npc_dialogue.py::test_flight_complete_chapter_fallback_uses_structured_closure_reason backend/tests/test_developer_a_npc_dialogue.py::test_smalltalk_complete_chapter_llm_question_falls_back_to_closing -q`
- Related suites:
  - `uv run pytest backend/tests/test_developer_a_npc_dialogue.py backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py backend/tests/dev_b/test_developer_b_policy_engine.py -q`
  - `uv run pytest backend/tests/test_preprototype_flow.py -q`
- Full verification:
  - `uv sync`: PASS
  - `uv run pytest`: PASS, 546 passed, 1 warning (`audioop` deprecation)
  - `uv run ruff check .`: PASS
  - `uv run mypy .`: PASS
