# Sprint INC - Developer C Incivility Signal and A Adapter Forward

## Goal

Implement the Developer C side of Developer A's Bad Ending / Profanity Mirror
handoff by producing an `incivility` signal in Understanding and forwarding that
signal to Developer A's existing payload consumer.

## Source Requests

- `docs/handoff.md`: `2026-06-16 Developer A Request: Bad Ending End-to-End`
- `docs/contracts/change_requests.md`: `CR-A1`, `CR-A3`
- `docs/contracts/developer_c_incivility_codex_prompt.md`: C owner prompt for
  incivility signal production and adapter forwarding

## Ownership Boundary

Developer C owns:

- Understanding output schema and C-owned semantic classification.
- C-owned incivility classifier service.
- C-to-A adapter payload forwarding.
- C graph/tool summaries and C-owned tests/docs.

Developer C must not implement:

- Developer A profanity response wording, TTS mirror behavior, or prompt logic.
- Developer B branch, scoring, penalty, or bad-ending routing policy.
- Developer B scenario node data for `*_BAD_END_VERBAL_ABUSE`.

## Sprint Items

| Item | Status | Owner | Notes |
| --- | --- | --- | --- |
| INC-0 Intake and scope audit | Done | C | Reviewed Dev A handoff, CR-A1/A3, and C prompt. Confirmed C only emits and forwards `incivility`; B owns bad-ending branch authority. |
| INC-1 Schema contract | Done | C | Added additive `IncivilityClassification` schema and optional `UnderstandingOutput.incivility`. |
| INC-2 Rule classifier | Done | C | Added C-owned rule classifier for tier 0-3 detection, including common English/Korean profanity and simple obfuscations such as `f*ck` / `fck`. |
| INC-3 Settings and env docs | Done | C | Added `MURPHY_INCIVILITY_CLASSIFIER_MODE=rule` to settings and `.env.example`. |
| INC-4 Understanding integration | Done | C | Attached incivility classification to rule/LLM Understanding outputs without letting it decide branch outcomes. |
| INC-5 C-to-A adapter forward | Done | C | Added top-level `incivility` to `DevANpcDialogueClient` level-design payload with tier 0 default when missing. |
| INC-6 C observability | Done | C | Included `incivility.tier`, `category`, and `source` in C Understanding summaries / AgentRun evidence. |
| INC-7 Regression tests | Done | C | Added C-owned tests for classifier tiers, Understanding output, A adapter forwarding, settings, and AgentRun summary visibility. |
| INC-8 Contract docs and handoff | Done | C | Updated C contract docs, handoff, and CR-A1/A3 status update notes. |
| INC-9 Full verification and commit | Partial | C | `uv run pytest` and `uv run mypy .` pass. Focused C-owned ruff passes. Full `uv run ruff check .` is blocked by A-owned unused imports; change request added. Commit pending. |

## Phase Plan

### Phase 0 - Scope Confirmation

- [x] Confirmed Dev A has already implemented Profanity Mirror/Firm reception.
- [x] Confirmed current C code has no `incivility` schema, classifier, or adapter
  forward.
- [x] Confirmed C must not add bad-ending branch policy; that is CR-A2/B-owned.
- [x] Confirmed C must not add `scenario_nodes.json` verbal-abuse endings; that
  is CR-A4/B-owned.

### Phase 1 - Schema and Classifier

Files:

- Modify: `backend/app/schemas/game_turn.py`
- Create: `backend/app/services/service_c/incivility_classifier.py`
- Modify: `backend/app/services/service_c/settings_service.py`
- Modify: `.env.example`
- Test: `backend/tests/test_understanding_incivility_classifier.py`

Steps:

- [x] Add `IncivilityClassification` with fields:
  `tier`, `detected_terms`, `confidence`, `category`, `source`.
- [x] Add optional `incivility` to `UnderstandingOutput`.
- [x] Add a C-owned rule classifier with Korean beginner docstrings.
- [x] Add `MURPHY_INCIVILITY_CLASSIFIER_MODE=rule` setting.
- [x] Write tests for:
  - normal travel answer -> tier 0
  - `shut up` -> tier 1
  - `you idiot` / `asshole` -> tier 2
  - `fuck you`, `f*ck you`, Korean profanity -> tier 3

### Phase 2 - Understanding Integration

Files:

- Modify: `backend/app/agents/agent_c/understanding_agent.py`
- Modify: `backend/app/agents/agent_c/understanding_llm_client.py`
- Modify: `backend/app/prompts/understanding_prompt.md`
- Test: `backend/tests/test_understanding_agent.py`

Steps:

- [x] Attach rule-mode incivility classification to deterministic Understanding
  outputs.
- [x] Attach incivility classification after LLM output parsing so malformed or
  missing LLM `incivility` cannot erase rule-detected severe profanity.
- [x] If the LLM schema is extended, keep the rule classifier as the final safety
  repair for tier 2-3.
- [x] Keep branch fields unchanged. C only returns semantic evidence.
- [x] Add tests proving `intent_success` and scenario branch semantics are still
  independent from incivility tier.

### Phase 3 - A Adapter Forward

Files:

- Modify: `backend/app/integrations/dev_a_npc_dialogue_client.py`
- Test: `backend/tests/test_preprototype_flow.py` or
  `backend/tests/test_dev_a_adapter_incivility_forward.py`

Steps:

- [x] Add top-level `incivility` to the A-facing level-design payload.
- [x] Default missing incivility to:
  `{"tier": 0, "detected_terms": [], "confidence": 0.0, "category": "none", "source": "none"}`.
- [x] Do not reintroduce B-authored wording fields that were removed from the
  A-facing payload.
- [x] Add tests proving tier 3 reaches the fake A voice-output builder.
- [x] Add tests proving missing incivility still forwards tier 0.

### Phase 4 - C Observability and Runtime QA

Files:

- Modify: `backend/app/tools/tool_c/developer_c_graph_tools.py`
- Modify: C-owned AgentRun summary code only if needed.
- Test: `backend/tests/test_unified_agent_run_log.py`

Steps:

- [x] Include incivility tier/category/source in `_understanding_summary`.
- [x] Ensure AgentRun output summaries show the signal for QA.
- [x] Do not expose bad-ending branch decisions from C.
- [x] Add a focused log test if current AgentRun assertions do not already cover
  Understanding output summaries.

### Phase 5 - Contract Docs, Verification, and Commit

Files:

- Modify: `docs/contracts/developer_c_schema_contract.md`
- Modify: `docs/contracts/developer_c_adapter_contracts.md`
- Modify: `docs/contracts/change_requests.md`
- Modify: `docs/handoff.md`

Steps:

- [x] Document `UnderstandingOutput.incivility` as additive semantic evidence.
- [x] Document C-to-A `incivility` payload forwarding.
- [x] Mark CR-A1 and CR-A3 as implemented with global ruff caveat documented.
- [x] Run:
  - `uv run pytest`
  - `uv run ruff check .`
  - `uv run mypy .`
- [ ] Commit with a message such as
  `feat: add developer c incivility signal`.

Verification note:

- `uv run pytest` passed: 287 passed, 1 warning.
- `uv run mypy .` passed.
- Focused C-owned `uv run ruff check ...` passed.
- Full `uv run ruff check .` is blocked by Developer A-owned unused imports;
  Developer C added a change request instead of editing A-owned implementation
  files.

## Dependency Notes for Developer B

Developer B can start CR-A2/CR-A4 after C exposes
`UnderstandingOutput.incivility`:

- B should consume `understanding.incivility.tier` from C's existing B policy
  input path.
- B owns all `bad_end` / `FAIL_END` routing and score/report penalties.
- B owns `*_BAD_END_VERBAL_ABUSE` scenario nodes.

Until B work lands, C completion should make A's Profanity Mirror/Firm response
audible in AI-only testing, but it should not end the game.

## Acceptance Criteria

- C-owned code produces tier 0-3 incivility evidence for player text.
- `"fuck you"` yields tier 3 with high confidence in rule mode.
- C forwards the incivility object to Developer A payload top-level.
- Existing normal answers remain tier 0 and continue normal scenario flow.
- C does not edit Developer A or Developer B implementation files.
- Full verification passes.
