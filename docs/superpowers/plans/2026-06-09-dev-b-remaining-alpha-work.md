# Dev B Remaining Alpha Work Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining Developer B-owned Alpha policy, scoring, and scenario-end feedback work after the 2026-06-08 plan implementation and 2026-06-09 code review.

**Architecture:** Developer B owns Travel Speaking Level rubric policy, difficulty profile policy, result score policy, and out-game feedback seed records. Developer B provides score/report payloads that Developer C validates and assembles into Unreal-safe JSON; Developer C still owns orchestration, response shape, UI delivery, cutscene/skip flow, and non-B OpenKB runtime coordination. Developer A owns final NPC dialogue/TTS and consumes B difficulty metadata when C passes it through.

**Tech Stack:** Python 3.12, uv, pytest, ruff, mypy, Pydantic schemas, B-owned scenario JSON, B-owned OpenKB JSONL records.

---

## Updated Product Decisions

These decisions supersede the earlier small-talk no-report language:

- `FLIGHT_001_SEATMATE_SMALLTALK` must create an external-facing `out_game_feedback_seed`.
- The player still must not see feedback immediately after flight small talk.
- `out_game_feedback` is generated and shown only after the full Alpha scenario ends.
- When the full scenario ends, the UI should show both `evaluation` and `out_game_feedback`.
- `evaluation` is B-owned score policy output:
  - each rubric dimension is converted from 0..2 to 0..100,
  - each scene first produces its own dimension averages so scenes with more turns do not dominate the result,
  - default Alpha scene weights are `FLIGHT_001_SEATMATE_SMALLTALK` 20%, `IMMIGRATION_ALPHA` 50%, and `BAGGAGE_MISSING` 30%,
  - optional events are feature-gated and do not affect numeric scoring unless an explicit weight is added later,
  - overall score is the average of the weighted dimension scores,
  - Developer C validates and assembles this payload into Unreal-safe JSON.

## Current Status From 2026-06-08 Plans

Completed or implemented in B-owned code:

- `IMMIGRATION_ALPHA` extends the prototype through tier policy and the Gold-only `IMM_ALPHA_GOLD_BAG_CONTENT_CHECK` challenge.
- Chapter 0 success/retry tests cover playable immigration nodes, the Gold challenge node, and baggage nodes.
- Dev B output self-checks validate branch, hint, feedback, error capture, final-report seed, and rubric invariants before OpenKB writes.
- `FinalResultScorePolicy` exists as the B-owned result score policy and returns 0..100 final score metadata.
- `FocusOnFormReportPolicy` exists as a B-owned report builder and is tested directly.
- `backend/app/kb/dev_b/focus_on_form_cards.json` covers the current Dev B Focus-on-Form target set for immigration, Gold challenge, and baggage.
- B OpenKB runtime records include additive `dev_b_openkb_record.v2` metadata while preserving compatibility keys.
- LLM feedback guard rejects forbidden authority keys and logs provider usage in AgentRun event summaries without exposing usage on public `DevBPolicyOutput`.
- `BAGGAGE_MISSING` has B-owned node definitions from `BAG_002_FIND_STAFF` through `BAG_007_RESOLUTION`.

Still unimplemented in Dev B-owned work:

- `FLIGHT_001_SEATMATE_SMALLTALK` has a scenario document but no B-owned diagnostic policy or B-owned node data.
- Flight small talk does not yet emit a deferred `out_game_feedback_seed`.
- Current score policy must be made explicit that scenario-end `overall` is the average of scene-normalized rubric dimension scores, not a raw per-turn average or hidden score.
- B-owned `out_game_feedback` building is direct-record only; there is no B-owned session-level reader/helper for C to call at scenario end.
- Optional post-baggage event seeds such as customs trouble, stolen passport, and seatmate reunion are not represented as B-owned scenario seed documents. Alpha should enable at most one optional event initially, with seatmate reunion as the lowest-risk first candidate.

Blocked outside Dev B ownership:

- C-owned runtime does not yet orchestrate `FLIGHT_001_SEATMATE_SMALLTALK -> IMMIGRATION_ALPHA -> BAGGAGE_MISSING -> scenario_end`.
- C-owned Understanding rule mode still focuses on visit-purpose classification and does not cover flight/baggage slots.
- A/C dialogue integration currently looks up next-node questions only for `IMM_` node ids.
- C-owned response/result payload does not yet expose scenario-end `evaluation` plus B `out_game_feedback`.
- A-owned dialogue/TTS still needs to consume B difficulty metadata for tier-aware speed, strictness, and scene roles.

---

## File Structure

- `backend/app/services/service_b/flight_smalltalk_diagnostic_policy.py`
  - B-owned minimum-turn, skip-eligibility, fallback-question, and deferred feedback-seed policy for flight small talk.
- `backend/app/agents/agent_b/english_level_hint_agent.py`
  - Existing B policy entry point. Add flight-specific out-game feedback seed behavior.
- `backend/app/services/service_b/final_result_score_policy.py`
  - Existing B result score policy. Make overall score equal to the average of scene-normalized weighted rubric dimension scores.
- `backend/app/services/service_b/focus_on_form_report_policy.py`
  - Existing B report builder. Add session-level report construction for scenario-end `out_game_feedback`.
- `backend/app/data/scenario_nodes.json`
  - Existing B scenario node data. Add `FLIGHT_001_SEATMATE_SMALLTALK`.
- `backend/app/kb/dev_b/focus_on_form_cards.json`
  - Existing B learning cards. Add a small-talk card for final out-game feedback.
- `backend/tests/dev_b/`
  - Allowed Dev B test location by user instruction. Add/extend focused tests.
- `docs/contracts/change_requests.md`
  - Add or update C-facing request for scenario-end UI payload with `evaluation` and `out_game_feedback`.
- `docs/handoff.md`
  - Record changed files, verification, and remaining A/C tasks.

---

## Execution Order

1. Add a B-owned flight small-talk diagnostic policy.
2. Add `FLIGHT_001_SEATMATE_SMALLTALK` node data and deferred feedback seed behavior.
3. Align scenario-end evaluation score policy with 0..100 scene-normalized dimension averages.
4. Add B-owned scenario-end `out_game_feedback` session builder.
5. Add optional Alpha event seed documents for later scenario expansion.
6. Refresh C-facing contract and handoff notes.
7. Run Dev B, integration, full, lint, and type checks.

---

### Task 1: Flight Small-Talk Diagnostic Policy

**Files:**
- Create: `backend/app/services/service_b/flight_smalltalk_diagnostic_policy.py`
- Create: `backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py`
- Modify: `backend/app/services/service_b/__init__.py`

- [ ] **Step 1: Write the failing diagnostic policy tests**

Create `backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py`:

```python
from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import (
    FlightSmallTalkDiagnosticPolicy,
)


def test_smalltalk_requires_three_player_turns_before_normal_exit() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=2)

    assert decision.scene_id == "FLIGHT_001_SEATMATE_SMALLTALK"
    assert decision.diagnostic_only is True
    assert decision.minimum_turns_met is False
    assert decision.required_more_turns == 1
    assert decision.skip_eligible is False
    assert decision.should_emit_out_game_feedback_seed is True
    assert decision.should_show_out_game_feedback_now is False


def test_smalltalk_allows_normal_exit_after_three_player_turns() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=3)

    assert decision.minimum_turns_met is True
    assert decision.required_more_turns == 0
    assert decision.skip_eligible is False
    assert decision.should_emit_out_game_feedback_seed is True
    assert decision.should_show_out_game_feedback_now is False


def test_smalltalk_skip_becomes_eligible_after_five_player_turns() -> None:
    decision = FlightSmallTalkDiagnosticPolicy().evaluate(player_turn_count=5)

    assert decision.minimum_turns_met is True
    assert decision.required_more_turns == 0
    assert decision.skip_eligible is True
    assert decision.should_emit_out_game_feedback_seed is True
    assert decision.should_show_out_game_feedback_now is False


def test_smalltalk_fallback_questions_are_available_when_flow_stalls() -> None:
    policy = FlightSmallTalkDiagnosticPolicy()

    assert policy.fallback_question(0) == "Is this your first time flying to New York?"
    assert policy.fallback_question(1) == "What are you most excited to do after you land?"
    assert policy.fallback_question(4) == "Do you usually like window seats or aisle seats?"
```

- [ ] **Step 2: Run the diagnostic policy tests and verify RED**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py -q
```

Expected: fail with `ModuleNotFoundError` for `flight_smalltalk_diagnostic_policy`.

- [ ] **Step 3: Implement the diagnostic policy**

Create `backend/app/services/service_b/flight_smalltalk_diagnostic_policy.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


SCENE_ID = "FLIGHT_001_SEATMATE_SMALLTALK"
MINIMUM_PLAYER_TURNS = 3
SKIP_ELIGIBLE_PLAYER_TURNS = 5
FALLBACK_QUESTIONS = [
    "Is this your first time flying to New York?",
    "What are you most excited to do after you land?",
    "Are you traveling alone or with someone?",
    "How long will you stay in the United States?",
    "Do you usually like window seats or aisle seats?",
]


@dataclass(frozen=True)
class FlightSmallTalkDiagnosticDecision:
    scene_id: str
    diagnostic_only: bool
    minimum_turns_met: bool
    required_more_turns: int
    skip_eligible: bool
    should_emit_out_game_feedback_seed: bool
    should_show_out_game_feedback_now: bool


class FlightSmallTalkDiagnosticPolicy:
    def evaluate(self, *, player_turn_count: int) -> FlightSmallTalkDiagnosticDecision:
        safe_turn_count = max(0, player_turn_count)
        required_more_turns = max(0, MINIMUM_PLAYER_TURNS - safe_turn_count)
        return FlightSmallTalkDiagnosticDecision(
            scene_id=SCENE_ID,
            diagnostic_only=True,
            minimum_turns_met=required_more_turns == 0,
            required_more_turns=required_more_turns,
            skip_eligible=safe_turn_count >= SKIP_ELIGIBLE_PLAYER_TURNS,
            should_emit_out_game_feedback_seed=True,
            should_show_out_game_feedback_now=False,
        )

    def fallback_question(self, player_turn_count: int) -> str:
        safe_turn_count = max(0, player_turn_count)
        index = min(safe_turn_count, len(FALLBACK_QUESTIONS) - 1)
        return FALLBACK_QUESTIONS[index]
```

- [ ] **Step 4: Export the diagnostic policy**

Update `backend/app/services/service_b/__init__.py`:

```python
if TYPE_CHECKING:
    from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import FlightSmallTalkDiagnosticPolicy
```

Add `"FlightSmallTalkDiagnosticPolicy"` to `__all__`, and add this branch in `__getattr__`:

```python
if name == "FlightSmallTalkDiagnosticPolicy":
    from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import FlightSmallTalkDiagnosticPolicy

    return FlightSmallTalkDiagnosticPolicy
```

- [ ] **Step 5: Run the diagnostic policy tests and verify GREEN**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py -q
```

Expected: `4 passed`.

---

### Task 2: Flight Node Data And Deferred Feedback Seed

**Files:**
- Modify: `backend/app/data/scenario_nodes.json`
- Modify: `backend/app/agents/agent_b/english_level_hint_agent.py`
- Modify: `backend/app/kb/dev_b/focus_on_form_cards.json`
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`
- Modify: `backend/tests/dev_b/test_focus_on_form_report_policy.py`

- [ ] **Step 1: Add failing tests for flight node data and deferred feedback seed behavior**

Append to `backend/tests/dev_b/test_developer_b_policy_engine.py`:

```python
def test_flight_smalltalk_node_exists_as_alpha_diagnostic_node() -> None:
    context = _node_context("FLIGHT_001_SEATMATE_SMALLTALK")

    assert context.node_id == "FLIGHT_001_SEATMATE_SMALLTALK"
    assert context.npc_question_goal == "friendly_seatmate_smalltalk"
    assert context.required_intents == ["respond_to_smalltalk"]
    assert context.required_slots == ["smalltalk_response"]
    assert "FLIGHT_001_SEATMATE_SMALLTALK" in context.allowed_next_nodes
    assert "IMM_001_PASSPORT" in context.allowed_next_nodes


def test_flight_smalltalk_creates_deferred_out_game_feedback_seed(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_001_SEATMATE_SMALLTALK")
    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="I go New York. First time.",
            intent_success=True,
            confidence=0.88,
            extracted_slots={"smalltalk_response": "answered"},
            missing_slots=[],
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.out_game_feedback_seed.include_in_final_report is True
    assert result.out_game_feedback_seed.focus_on_form_targets == ["smalltalk_response_clarity"]
    assert "deferred_out_game_feedback" in result.out_game_feedback_seed.openkb_query_tags
    assert result.branch.next_node_id in context.allowed_next_nodes
```

- [ ] **Step 2: Run the flight node tests and verify RED**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_node_exists_as_alpha_diagnostic_node backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_creates_deferred_out_game_feedback_seed -q
```

Expected: fail because `FLIGHT_001_SEATMATE_SMALLTALK` is not in `scenario_nodes.json`.

- [ ] **Step 3: Add `FLIGHT_001_SEATMATE_SMALLTALK` to B scenario data**

Add this node to `backend/app/data/scenario_nodes.json` under `nodes`:

```json
"FLIGHT_001_SEATMATE_SMALLTALK": {
  "node_id": "FLIGHT_001_SEATMATE_SMALLTALK",
  "chapter_id": "CH0_IMMIGRATION",
  "npc_question": "Hi, I'm Emily. Are you heading to New York too?",
  "npc_question_goal": "friendly_seatmate_smalltalk",
  "objective_kr": "Talk with the passenger next to you.",
  "required_intents": ["respond_to_smalltalk"],
  "required_slots": ["smalltalk_response"],
  "optional_slots": ["travel_reason", "first_time_visit", "interest", "duration"],
  "critical_slots": [],
  "allowed_slot_values": {
    "smalltalk_response": ["answered", "short_answer", "asked_back", "shared_travel_detail"]
  },
  "risk_keywords": [],
  "recommended_expression": "Yes, I'm going to New York for a short trip.",
  "base_hint_kr": "Answer in a friendly short sentence, then add one travel detail if you can.",
  "hint_policy": {
    "keyword": ["yes", "New York", "trip"],
    "sentence_pattern": "Yes, I'm going to New York for ___.",
    "situation_hint": "The seatmate is making friendly small talk.",
    "action_hint": "Answer briefly and ask a simple question back if you can."
  },
  "branch_candidates": {
    "success": "FLIGHT_001_SEATMATE_SMALLTALK",
    "retry": "FLIGHT_001_RETRY_SMALLTALK",
    "clarify": "FLIGHT_001_CLARIFY_SMALLTALK",
    "hint": "FLIGHT_001_RETRY_SMALLTALK",
    "warning": "FLIGHT_001_SEATMATE_SMALLTALK",
    "bad_end": "FLIGHT_001_SEATMATE_SMALLTALK"
  },
  "allowed_next_nodes": [
    "FLIGHT_001_SEATMATE_SMALLTALK",
    "FLIGHT_001_RETRY_SMALLTALK",
    "FLIGHT_001_CLARIFY_SMALLTALK",
    "IMM_001_PASSPORT"
  ]
}
```

- [ ] **Step 4: Add a flight-specific out-game seed**

In `backend/app/agents/agent_b/english_level_hint_agent.py`, update `_build_out_game_feedback_seed(...)` before the generic `should_include` logic:

```python
if payload.current_node_id.startswith("FLIGHT_"):
    return OutGameFeedbackSeed(
        include_in_final_report=True,
        openkb_query_tags=[
            "smalltalk_response_clarity",
            "diagnostic_level_sample",
            "deferred_out_game_feedback",
        ],
        focus_on_form_targets=["smalltalk_response_clarity"],
        report_priority="low",
    )
```

Also update `_focus_on_form_target(...)`:

```python
if payload.current_node_id.startswith("FLIGHT_"):
    return "smalltalk_response_clarity"
```

- [ ] **Step 5: Add a small-talk learning card**

Add this card to `backend/app/kb/dev_b/focus_on_form_cards.json`:

```json
"smalltalk_response_clarity": {
  "title_kr": "스몰토크에 자연스럽게 답하기",
  "rule_summary_kr": "스몰토크에서는 짧게 답한 뒤 한 가지 정보를 덧붙이면 대화가 자연스럽게 이어집니다.",
  "good_examples": ["Yes, I'm going to New York for a short trip.", "It's my first time visiting the United States."],
  "practice_prompt_kr": "옆자리 승객에게 여행 이유나 기대하는 점을 한 문장으로 말해보세요.",
  "answer_example": "Yes, I'm going to New York for a short trip."
}
```

In `backend/tests/dev_b/test_focus_on_form_report_policy.py`, add `"smalltalk_response_clarity"` to `CURRENT_DEV_B_FOCUS_TARGETS`.

- [ ] **Step 6: Run the flight seed tests and verify GREEN**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_node_exists_as_alpha_diagnostic_node backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_creates_deferred_out_game_feedback_seed backend/tests/dev_b/test_focus_on_form_report_policy.py::test_static_cards_cover_current_dev_b_focus_targets -q
```

Expected: `3 passed`.

---

### Task 3: Scenario-End Scene-Normalized Evaluation Score Policy

**Files:**
- Modify: `backend/app/services/service_b/final_result_score_policy.py`
- Modify: `backend/tests/dev_b/test_final_result_score_policy.py`

- [ ] **Step 1: Write the failing score policy test**

Add this helper and test to `backend/tests/dev_b/test_final_result_score_policy.py`:

```python
def _record_with_rubric(
    *,
    node_id: str,
    rubric: dict[str, int],
    verdict: str = "SUCCESS",
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "evaluation": {"verdict": verdict, "feedback_tags": ["intent_matched"]},
        "rubric_scores": {**rubric, "total": sum(rubric.values())},
        "out_game_feedback_seed": {
            "include_in_final_report": False,
            "focus_on_form_targets": [],
            "report_priority": "low",
        },
        "report_item": {
            "summary": f"{node_id} was evaluated.",
            "improvement": "Keep answers concise and polite.",
            "example_answer": "Thank you.",
            "score_tags": ["task_success_good"],
        },
        "branch": {"branch_type": "success", "next_node_id": "NEXT"},
        "state_delta": {
            "patience_delta": 0,
            "suspicion_delta": 0,
            "retry_count_delta": 0,
            "hint_count_delta": 0,
        },
    }


def test_final_score_uses_scene_normalized_dimension_averages_not_turn_counts() -> None:
    result = FinalResultScorePolicy().build_result(
        [
            *[
                _record_with_rubric(
                    node_id="FLIGHT_001_SEATMATE_SMALLTALK",
                    rubric={
                        "comprehension": 0,
                        "fluency": 0,
                        "grammar_accuracy": 0,
                        "vocabulary_range": 0,
                        "clarity": 0,
                        "interaction_problem_solving": 0,
                    },
                )
                for _ in range(5)
            ],
            _record_with_rubric(
                node_id="IMM_002_PURPOSE",
                rubric={
                    "comprehension": 2,
                    "fluency": 2,
                    "grammar_accuracy": 2,
                    "vocabulary_range": 2,
                    "clarity": 2,
                    "interaction_problem_solving": 2,
                },
            ),
            _record_with_rubric(
                node_id="BAG_003_REPORT_MISSING_BAG",
                rubric={
                    "comprehension": 2,
                    "fluency": 2,
                    "grammar_accuracy": 2,
                    "vocabulary_range": 2,
                    "clarity": 2,
                    "interaction_problem_solving": 2,
                },
            ),
        ],
        final_state=FinalScoreState(patience=100, suspicion=0, retry_count=0, hint_count=0),
    )

    assert result.quantitative_scores.comprehension == 80
    assert result.quantitative_scores.fluency == 80
    assert result.quantitative_scores.grammar_accuracy == 80
    assert result.quantitative_scores.vocabulary_range == 80
    assert result.quantitative_scores.clarity == 80
    assert result.quantitative_scores.interaction_problem_solving == 80
    assert result.quantitative_scores.overall == 80
    assert result.final_score_100 == 80
    assert result.quantitative_scores.scoring_policy == "scene_normalized_dimension_average"
```

- [ ] **Step 2: Run the score policy test and verify RED**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_final_result_score_policy.py::test_final_score_uses_scene_normalized_dimension_averages_not_turn_counts -q
```

Expected: fail because the current implementation computes `overall` from averaged per-turn total scores, causing a long small-talk scene to dominate the result.

- [ ] **Step 3: Update final score computation**

In `backend/app/services/service_b/final_result_score_policy.py`, add scene weights and use only scored scenes that are present in the session:

```python
SCENE_SCORE_WEIGHTS = {
    "flight": 20,
    "immigration": 50,
    "baggage": 30,
}
```

Optional events should be feature-gated and excluded from numeric scoring unless a later plan adds an explicit weight.

Change `build_result(...)` so `final_score` comes from the scene-normalized dimension scores:

```python
quantitative_scores = self._quantitative_scores(included_records)
final_score = quantitative_scores.overall
per_turn_scores = [self._rubric_total_to_100(record["rubric_scores"]["total"]) for record in included_records]
recommendation, reason_tags = self._recommendation(included_records, final_score, state)
```

Update `_quantitative_scores(...)` to compute scene-level dimension averages first, then combine them using the weights for scenes present in the session:

```python
def _quantitative_scores(self, included_records: list[dict[str, Any]]) -> QuantitativeScores:
    scene_records: dict[str, list[dict[str, Any]]] = {}
    for record in included_records:
        scene_key = self._scene_key(record)
        if scene_key not in SCENE_SCORE_WEIGHTS:
            continue
        scene_records.setdefault(scene_key, []).append(record)

    if not scene_records:
        scene_records = {"immigration": included_records}

    weight_total = sum(SCENE_SCORE_WEIGHTS.get(scene_key, 0) for scene_key in scene_records)
    if weight_total <= 0:
        weight_total = len(scene_records)

    averages = {}
    for field in RUBRIC_FIELDS:
        weighted_sum = 0
        for scene_key, records in scene_records.items():
            scene_average = _average_int(
                [self._rubric_dimension_to_100(record["rubric_scores"][field]) for record in records]
            )
            weighted_sum += scene_average * SCENE_SCORE_WEIGHTS.get(scene_key, 1)
        averages[field] = _round_half_up(weighted_sum / weight_total)

    overall = _average_int([averages[field] for field in RUBRIC_FIELDS])
    return QuantitativeScores(
        overall=overall,
        comprehension=averages["comprehension"],
        fluency=averages["fluency"],
        grammar_accuracy=averages["grammar_accuracy"],
        vocabulary_range=averages["vocabulary_range"],
        clarity=averages["clarity"],
        interaction_problem_solving=averages["interaction_problem_solving"],
        # Temporary C-schema compatibility: C currently accepts only
        # "simple_average" in QuantitativeScores.scoring_policy. Keep the
        # field compatible until C widens the schema/validator, and expose the
        # new numeric policy through reason tags and documented contract change.
        scoring_policy="simple_average",
    )
```

Add a helper that maps current node IDs to the scoring scene:

```python
def _scene_key(self, record: dict[str, Any]) -> str:
    node_id = str(record.get("node_id", ""))
    if node_id.startswith("FLIGHT_"):
        return "flight"
    if node_id.startswith("IMM_"):
        return "immigration"
    if node_id.startswith("BAG_"):
        return "baggage"
    return "optional"
```

Update reason tags from `simple_average_policy` to `scene_normalized_dimension_average_policy`.

Because C validator still requires `simple_average`, add a change request in Task 6 and keep the runtime field compatible. Do not edit C validator from Dev B work unless the user explicitly asks for implementation across owners.

- [ ] **Step 4: Run score policy tests and verify GREEN**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_final_result_score_policy.py -q
```

Expected: all final score policy tests pass after assertions verify scene-normalized numeric behavior and `scene_normalized_dimension_average_policy` reason tags. The `scoring_policy` field remains `simple_average` until C widens the schema/validator.

---

### Task 4: Scenario-End Out-Game Feedback Session Builder

**Files:**
- Modify: `backend/app/services/service_b/focus_on_form_report_policy.py`
- Modify: `backend/tests/dev_b/test_focus_on_form_report_policy.py`

- [ ] **Step 1: Write the failing session helper test**

Append to `backend/tests/dev_b/test_focus_on_form_report_policy.py`:

```python
def test_focus_on_form_report_can_be_built_from_full_scenario_session_jsonl(tmp_path: Path) -> None:
    runtime_root = tmp_path / "openkb" / "dev_b"
    runtime_root.mkdir(parents=True)
    session_path = runtime_root / "session_alpha.jsonl"
    session_path.write_text(
        "\n".join(
            [
                json.dumps(_record(node_id="FLIGHT_001_SEATMATE_SMALLTALK", focus_targets=["smalltalk_response_clarity"]), ensure_ascii=False),
                json.dumps(_record(node_id="IMM_002_PURPOSE", focus_targets=["purpose_statement"]), ensure_ascii=False),
                json.dumps(_record(node_id="BAG_003_REPORT_MISSING_BAG", focus_targets=["problem_statement"]), ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = FocusOnFormReportPolicy(runtime_root=runtime_root).build_session_report("session_alpha")

    assert report["report_mode"] == "focus_on_form"
    assert [item["focus_on_form_target"] for item in report["focus_on_form_items"]] == [
        "smalltalk_response_clarity",
        "purpose_statement",
        "problem_statement",
    ]
    assert report["personalized_next_step"]["target"] == "smalltalk_response_clarity"
```

- [ ] **Step 2: Run the session helper test and verify RED**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_focus_on_form_report_policy.py::test_focus_on_form_report_can_be_built_from_full_scenario_session_jsonl -q
```

Expected: fail because `FocusOnFormReportPolicy.__init__` does not accept `runtime_root`.

- [ ] **Step 3: Extend `FocusOnFormReportPolicy`**

In `backend/app/services/service_b/focus_on_form_report_policy.py`, update the constructor and add a session helper:

```python
def __init__(self, card_path: Path | None = None, runtime_root: Path | None = None) -> None:
    self.card_path = card_path or DEFAULT_CARD_PATH
    self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_b")

def build_session_report(self, session_id: str) -> dict[str, Any]:
    jsonl_path = self.runtime_root / f"{session_id}.jsonl"
    if not jsonl_path.exists():
        return self.build_report([])

    records: list[dict[str, Any]] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return self.build_report(records)
```

- [ ] **Step 4: Run report policy tests and verify GREEN**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_focus_on_form_report_policy.py -q
```

Expected: all report policy tests pass.

---

### Task 5: Optional Alpha Event Seed Documents

**Files:**
- Create: `docs/superpowers/plans/2026-06-09-alpha-optional-events-dev-b-seeds.md`

- [ ] **Step 1: Create the optional event seed document**

Create `docs/superpowers/plans/2026-06-09-alpha-optional-events-dev-b-seeds.md`:

```markdown
# Alpha Optional Events Dev B Seed Plan

## Scope

This document records B-owned scenario policy seeds for optional Alpha events
after `BAGGAGE_MISSING`. It does not authorize Developer B to edit A/C runtime
or response code.

Alpha should enable at most one optional event at first. The recommended first
candidate is `SEATMATE_REUNION` because it reuses the opening flight
relationship, has low safety/orchestration risk, and can compare casual English
from the beginning and end of the Alpha flow.

Optional events do not affect numeric `evaluation` by default. They may create
deferred `out_game_feedback_seed` records, but numeric scoring requires a later
explicit scene weight decision.

## Candidate Events

### CUSTOMS_DECLARATION_PROBLEM

- Initial Alpha status: later candidate, not first optional event.
- Trigger: after baggage resolution when the player is routed to customs.
- B-owned required intent: `explain_customs_item`
- B-owned required slot: `customs_item_purpose`
- Focus-on-Form target: `customs_explanation`
- Risk slots: `undeclared_restricted_item`, `commercial_resale`, `unknown_item_owner`

### PASSPORT_STOLEN

- Initial Alpha status: later candidate because it requires higher C-owned
  orchestration and recovery-state support.
- Trigger: after baggage or optional public-area transition.
- B-owned required intent: `report_lost_passport`
- B-owned required slot: `passport_loss_report`
- Focus-on-Form target: `lost_document_report`
- Risk slots: `cannot_identify_self`, `panic_no_details`, `refuse_police_report`

### SEATMATE_REUNION

- Initial Alpha status: recommended first optional event behind a feature flag.
- Trigger: after baggage resolution in arrivals hall.
- B-owned required intent: `continue_casual_conversation`
- B-owned required slot: `reunion_response`
- Focus-on-Form target: `smalltalk_follow_up`
- Feedback policy: this event can produce a deferred final `out_game_feedback_seed` if the product owner enables the event.

## Verification

No tests are required for this design-only seed document. When implementation starts, add B-owned scenario-node tests before editing `backend/app/data/scenario_nodes.json`.
```

- [ ] **Step 2: Confirm the seed document has no placeholder markers**

Run:

```powershell
rg -n "TB[D]|TO[D]O|implement[ ]later|fill[ ]in" docs/superpowers/plans/2026-06-09-alpha-optional-events-dev-b-seeds.md
```

Expected: no matches.

---

### Task 6: C-Facing Contract And Handoff Refresh

**Files:**
- Modify: `docs/contracts/change_requests.md`
- Modify: `docs/handoff.md`

- [ ] **Step 1: Add or update the C-facing scenario-end UI change request**

Append this to `docs/contracts/change_requests.md` unless an equivalent entry already exists:

```markdown
## Change Request - 2026-06-09 - Expose Scenario-End Evaluation And Out-Game Feedback

Status: Open.

### Requested By
Developer B

### Affected Owner
Developer C / Sean Han

### Reason
Developer B owns Travel Speaking Level rubric policy, difficulty profile policy,
result score policy, and out-game feedback seed records. At full Alpha scenario
end, the player should see a UI window containing B-owned `evaluation` and
`out_game_feedback`, but Developer C owns response assembly and Unreal-safe JSON.

### Proposed Contract Change
At scenario end, add a C-owned result response or final turn response shape that
includes:

- `evaluation`: B-owned scenario-wide score payload with rubric dimensions
  converted to 0..100, scene-normalized dimension averages using the default
  Alpha scene weights, and `overall` as the average of those weighted dimension
  scores.
- `out_game_feedback`: B-owned final learning report generated from all
  included `out_game_feedback_seed` records, including flight small talk,
  immigration, and baggage.

Developer C should validate the B payload and assemble it without changing B
score authority.

### Compatibility Impact
Additive scenario-end response fields. Existing per-turn response clients can
ignore these fields until the final UI is ready.

### Temporary Workaround
Developer B keeps `FinalResultScorePolicy` and `FocusOnFormReportPolicy` tested
directly. C may continue returning the current `report.final_result` until the
scenario-end UI response is added.
```

- [ ] **Step 2: Append a Dev B remaining-work completion note**

Append this section to `docs/handoff.md` after the latest Dev B entry:

```markdown
## 2026-06-09 Developer B Remaining Alpha Work Execution

Developer B completed the B-owned remaining Alpha policy/reporting tasks from
`docs/superpowers/plans/2026-06-09-dev-b-remaining-alpha-work.md`.

Changed:

- Added B-owned flight small-talk diagnostic policy and tests.
- Added `FLIGHT_001_SEATMATE_SMALLTALK` node data with deferred
  `out_game_feedback_seed` behavior.
- Updated scenario-end evaluation scoring so each rubric dimension is averaged
  inside each scene first, combined with default Alpha scene weights on a 0..100
  scale, and reported with overall as the average of those dimension scores.
- Added B-owned session helper for `out_game_feedback` report building from
  local `dev_b` OpenKB JSONL records.
- Added optional Alpha event seed document for customs, stolen passport, and
  seatmate reunion, with seatmate reunion recommended as the first
  feature-flagged optional event.

Still A/C-owned:

- C scene orchestration, cutscene/skip, and silent level carryover.
- C Understanding coverage for flight/baggage slots.
- A tier-aware scene-specific dialogue/TTS.
- C scenario-end UI response with `evaluation` and `out_game_feedback`.
```

- [ ] **Step 3: Run a docs consistency scan**

Run:

```powershell
$patterns = @(
    'no' + ' out-game feedback',
    'never' + ' creates visible' + ' out_game_feedback',
    'No' + ' cross-owner change requests',
    'replace the current' + ' mock',
    'full out-game practice-card generation from Focus-on-Form records is still' + ' not implemented'
)
$patterns | ForEach-Object { rg -n $_ docs }
```

Expected: no stale current-state matches in Dev B-owned current plans or handoff. Historical context in older dated plans can remain only if superseded by this plan.

---

### Task 7: Verification

**Files:**
- No new files beyond prior tasks.

- [ ] **Step 1: Run Dev B focused tests**

Run:

```powershell
uv run pytest backend/tests/dev_b -q
```

Expected: all Dev B tests pass.

- [ ] **Step 2: Run integration tests that consume Dev B**

Run:

```powershell
uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q
```

Expected: pass if Developer C has accepted `scene_normalized_dimension_average` scenario-end evaluation. If the only failure is C-owned validation or response assembly still expecting `simple_average` or lacking scenario-end `evaluation` / `out_game_feedback`, document that blocker in `docs/handoff.md` and do not edit C-owned implementation files from this Dev B plan.

- [ ] **Step 3: Run full suite**

Run:

```powershell
uv run pytest -q
```

Expected: full pytest suite passes after the C-owned scenario-end contract is updated. If the only failures are the C-owned blockers documented above, record the failing command and owner handoff in `docs/handoff.md`.

- [ ] **Step 4: Run static checks**

Run:

```powershell
uv run ruff check .
uv run mypy .
```

Expected: both pass.

---

## Acceptance Criteria

- `FLIGHT_001_SEATMATE_SMALLTALK` has a B-owned diagnostic policy with minimum-turn and skip-eligibility decisions.
- Flight small talk creates a deferred `out_game_feedback_seed`.
- Flight small talk does not display feedback immediately after the scene.
- B scenario-end evaluation converts 0..2 rubric dimensions to 0..100, averages each dimension inside each scene, combines present scenes using the default Alpha weights, and computes overall as the average of dimension scores.
- B scenario-end `out_game_feedback` can be built by session id using local `dev_b` OpenKB records.
- C-facing contract docs request scenario-end UI fields: `evaluation` and `out_game_feedback`.
- Optional Alpha event seeds are documented without editing A/C runtime code, and Alpha enables at most one optional event initially.
- Dev B, ruff, and mypy verification pass. Integration/full-suite failures are acceptable only when they are documented C-owned scenario-end contract blockers.
