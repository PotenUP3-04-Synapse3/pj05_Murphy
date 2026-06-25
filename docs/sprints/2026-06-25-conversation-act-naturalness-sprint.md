# 2026-06-25 Conversation Act Naturalness Sprint

Goal: reduce phrase-by-phrase dialogue fixes by adding a generalized
conversation-act card that lets C describe the player's social move and lets A/B
respond to that duty without changing branch authority.

## Sprint 1 - RED coverage

- Added C regressions for flight smalltalk self-disclosure and reciprocal
  questions:
  - "I'm going to a wedding" must create a `self_disclosure` card.
  - "What about you?" and "Do you travel often?" must create a
    `reciprocal_question` card with `answer_briefly_then_continue`.
- Added A fallback regressions so LLM failure no longer drops to generic
  "Interesting" or "Good to know" lines when the card says a specific reaction
  or NPC answer is socially required.
- Added B regression so a reciprocal-question card gives A enough
  `length_target` room to answer first and continue.
- Added C LLM schema regression requiring `conversation_act` in strict JSON
  schema.

## Sprint 2 - C conversation-act card

- Added `ConversationActCard` to `UnderstandingOutput`.
- C now attaches the card after pragmatic, incivility, and social-context
  postprocessing in rule, LLM, and LLM-fallback paths.
- The card models generalized player acts:
  `direct_answer`, `self_disclosure`, `reciprocal_question`,
  `belated_obligation_answer`, `social_non_answer`, `clarification_request`,
  `off_topic`, and `threat`.
- C AgentRun summaries now include a compact `conversation_act` object for
  debugging unified logs.

## Sprint 3 - A/B consumers

- A input normalization forwards `conversation_act`.
- A LLM payload and prompts expose:
  `conversation_player_act`, `conversation_npc_social_duty`,
  `conversation_natural_next_move`, `conversation_topic_anchor`, and answer/generic
  avoidance booleans.
- A fallback uses the card before generic smalltalk fallback:
  - self-disclosure -> concrete acknowledgement plus follow-up.
  - reciprocal question -> Arabella answers briefly first.
  - belated obligation answer -> thanks/accepts, then pivots.
- B keeps branch authority unchanged and only adjusts flight smalltalk
  `length_target` when the card says A must answer first or react specifically.

## Sprint 4 - Verification and Test Isolation

- RED confirmed for the new C/A/B/schema regressions.
- Targeted GREEN:
  `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_flight_self_disclosure_marks_social_duty backend/tests/test_understanding_agent.py::test_understanding_agent_flight_reciprocal_question_marks_answer_duty backend/tests/test_developer_a_npc_dialogue.py::test_smalltalk_diagnostic_fallback_responds_to_self_disclosure_context backend/tests/test_developer_a_npc_dialogue.py::test_smalltalk_diagnostic_fallback_answers_reciprocal_question_context backend/tests/test_understanding_llm_client.py::test_understanding_schema_is_openai_strict_compatible -q`
  passed.
- B RED/GREEN:
  `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_reciprocal_question_gives_a_room_to_answer_first -q`
  passed after implementation.
- Related regression suites:
  `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_understanding_llm_client.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/dev_b/test_developer_b_policy_engine.py -q`
  passed, 226 passed, 1 `audioop` deprecation warning.
- Integration:
  `uv run pytest backend/tests/test_preprototype_flow.py -q`
  passed, 48 passed, 1 `audioop` deprecation warning.
- During full verification, `test_multiplayer_baggage_setup_and_respond_flow`
  exposed a pre-existing settings-cache isolation bug: the test set env vars but
  did not clear `get_settings()`, so full-suite runs could reuse an earlier
  LLM/real-TTS settings object. The fixture now clears the cache before and
  after each test.
- Final verification:
  - `uv sync`: passed.
  - `uv run pytest`: passed, 543 passed, 1 `audioop` deprecation warning.
  - `uv run ruff check .`: passed.
  - `uv run mypy .`: passed, no issues found in 149 source files.
