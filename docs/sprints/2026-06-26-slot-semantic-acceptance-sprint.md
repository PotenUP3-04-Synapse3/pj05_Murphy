# 2026-06-26 Slot Semantic Acceptance Sprint

## Problem

The latest Immigration run showed two answered questions still looping:

- `I'm gonna stay here for one year.` was treated as missing `stay_duration`.
- `I'm a shopkeeper. I run a cafe.` filled an occupation-like value but still
  remained `intent_success=false`, so B kept reasking.

This felt like another one-off rule fix. The sprint reframes the work as a
slot semantic acceptance problem: C should reliably extract current-node slot
evidence, and B should validate the semantic slot category instead of only a
few example phrases.

## Sprint Steps

1. Red tests
   - Added C Understanding coverage for year-based stay durations.
   - Added C Understanding coverage for `shopkeeper` occupation.
   - Added unified-authority coverage proving C semantic repair is not erased
     by raw LLM `satisfied=false`.
   - Added B policy coverage for converting years to days and routing long
     stays.
   - Added integrated pre-prototype coverage for both user-visible symptoms.

2. C semantic acceptance
   - Extended stay-duration parsing to accept `year` and `years`.
   - Added `shopkeeper` and cafe/self-employment occupation phrases.
   - Added a unified-authority promotion step: if C has filled every required
     slot with safe, on-task evidence, raw LLM retry/clarify flags no longer
     reopen the answered question.

3. B duration policy
   - Extended `_stay_duration_days` to convert years as 365-day units.
   - Allowed `years` as a valid numeric stay-duration category.

4. Prompt and scenario contract alignment
   - Updated Understanding prompt guidance so the LLM treats days/weeks/months
     and years as stay-duration evidence.
   - Updated occupation guidance so open job titles and self-employment
     descriptions satisfy the occupation slot.
   - Updated scenario node allowed values for `years` and `shopkeeper`.

## Verification

- RED:
  `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_repairs_llm_missing_year_stay_duration_slot backend/tests/test_understanding_agent.py::test_understanding_agent_rule_mode_recognizes_stay_duration_values backend/tests/test_understanding_agent.py::test_understanding_agent_rule_mode_recognizes_new_immigration_slot_values backend/tests/test_understanding_agent.py::test_understanding_agent_unified_authority_preserves_semantic_slot_repair backend/tests/dev_b/test_developer_b_policy_engine.py::test_stay_duration_days_parser backend/tests/dev_b/test_developer_b_policy_engine.py::test_year_stay_duration_routes_to_long_stay_reason backend/tests/test_preprototype_flow.py::test_orchestrator_accepts_year_stay_duration_answer backend/tests/test_preprototype_flow.py::test_orchestrator_accepts_shopkeeper_occupation_answer -q`
  failed: 8 failed.

- GREEN:
  same command passed: 8 passed, 1 warning (`audioop` deprecation).

- Broader regression:
  `uv run pytest backend/tests/test_understanding_agent.py backend/tests/dev_b/test_developer_b_policy_engine.py backend/tests/test_preprototype_flow.py -q`
  passed: 213 passed, 1 warning (`audioop` deprecation).

- Static checks:
  `uv run ruff check .` passed.

- Static typing:
  `uv run mypy .` passed: no issues found in 149 source files.

- Whitespace:
  `git diff --check` passed with Windows LF-to-CRLF conversion warnings only.

- Full suite:
  `uv run pytest -q` was not rerun in this sprint because the required
  escalated command was rejected by the Codex usage limit after the targeted
  and broader regression suites had passed.

## Next Direction

The better long-term pattern is not to add a new branch rule for every failed
sentence. Build a small slot acceptance corpus for each required slot:

- examples that must pass,
- examples that must clarify,
- examples that must warning/fail,
- expected canonical slot evidence.

Then C/B changes become "expand slot semantics and evaluate the corpus" rather
than "patch this exact utterance."
