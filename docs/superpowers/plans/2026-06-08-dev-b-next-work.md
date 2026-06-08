# Dev B Next Work Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Developer B implementation into a stronger Chapter 0 policy/reporting package by cleaning stale docs, expanding node coverage, adding B-owned output checks, building Focus-on-Form report v1, and improving optional LLM feedback logging.

**Architecture:** Developer B remains a rule-authority policy layer behind Developer C's adapter. Branch, verdict, next node, and state delta stay deterministic; LLM paths may only improve learning feedback, report wording, and rubric candidates. Cross-owner API or response changes must be requested through contract docs instead of editing Developer A or Developer C implementation directly.

**Tech Stack:** Python 3.12, uv, FastAPI/Pydantic schemas, pytest, ruff, mypy, local JSON/OpenKB runtime records.

---

## Current Status

- Developer B policy is already connected through `backend/app/integrations/dev_b_level_hint_client.py`.
- Current verification from inspection:
  - `uv run pytest backend/tests/dev_b -q`: 30 passed
  - `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q`: 26 passed
  - `uv run pytest -q`: 110 passed
  - `uv run ruff check .`: passed
  - `uv run mypy .`: passed after rerun with the known uv cache permission workaround
- Do not modify Developer A or Developer C implementation files while executing Dev B tasks. If a C-owned schema/API change is needed, append a change request to `docs/contracts/change_requests.md`.

## Execution Order

1. Documentation cleanup.
2. Chapter 0 full-node Dev B test expansion.
3. Dev B output self-check guard.
4. Out-game Focus-on-Form report v1.
5. LLM feedback/logging improvements.
6. Final verification and handoff update.

---

## Alpha Scenario Addendum

The Alpha scenario documents created on 2026-06-08 extend this plan instead of replacing it:

- `docs/superpowers/plans/2026-06-08-alpha-flight-seatmate-smalltalk.md`
- `docs/superpowers/plans/2026-06-08-alpha-immigration.md`
- `docs/superpowers/plans/2026-06-08-alpha-baggage-missing.md`

Dev B's highest-priority Alpha work is `IMMIGRATION_ALPHA` because it extends the already implemented immigration prototype and can be improved mostly inside B-owned policy files. The original plan workstreams still apply:

- Documentation cleanup should include Alpha scenario ownership and cross-owner change requests.
- Chapter 0 full-node test expansion should cover the current immigration route before adding new Alpha nodes.
- Dev B output self-check guard should protect tier difficulty, report seeds, and branch authority before OpenKB writes.
- Out-game Focus-on-Form report v1 should consume immigration and baggage learning records; flight small talk must not show immediate out-game feedback.
- LLM feedback/logging improvements should support hint/report wording only and must not affect branch, verdict, next node, state delta, NPC final dialogue, TTS, or Unreal commands.

Priority for Alpha execution:

1. Extend `IMMIGRATION_ALPHA` tier policy and Gold challenge selection inside B-owned files.
2. Build or preserve final-report seed capture for immigration turns.
3. Implement Focus-on-Form report v1 as the B-owned final report service.
4. Add the flight small-talk diagnostic policy without visible post-scene feedback.
5. Add `BAGGAGE_MISSING` nodes and final-report learning targets.

---

### Task 1: Documentation Cleanup

**Files:**
- Modify: `docs/portfolio_dev_b.md`
- Modify: `docs/contracts/change_requests.md`
- Modify: `docs/handoff.md`

- [ ] **Step 1: Inspect stale Dev B integration claims**

Run:

```powershell
rg -n "mock|not connected|current runtime still calls|change request|Developer B" docs/portfolio_dev_b.md docs/contracts/change_requests.md docs/handoff.md
```

Expected: Find old statements that imply the Dev B adapter is still mock-only or not wired.

- [ ] **Step 2: Update `docs/portfolio_dev_b.md`**

Replace stale integration wording with this current-state wording:

```markdown
The C-owned adapter now delegates to Developer B's `EnglishLevelHintAgent`, so
the integrated pre-prototype uses the real deterministic `dev_b_policy.v1`
engine. Developer B still treats the C adapter, response envelope, validator,
STT, TTS, and Unreal transport as outside B ownership.
```

- [ ] **Step 3: Mark resolved Dev B change requests**

In `docs/contracts/change_requests.md`, add a short status line to the completed Dev B requests:

```markdown
Status: Resolved in the integrated pre-prototype. Keep this entry for contract history.
```

Apply that status to these completed items:

- `Wire Developer B Policy Engine`
- `Consume Developer B OpenKB Write References`
- `Consume Developer B LLM Feedback Metadata`

Leave `Expose OpenKB objective_kr to Unreal UI` open unless Developer C has exposed it in the final Unreal response.

- [ ] **Step 4: Add Dev B handoff note**

Append a concise Dev B note to `docs/handoff.md`:

```markdown
## Developer B Next Work Plan - 2026-06-08

Developer B's integrated policy path is passing current automated checks. The
next Dev B work should focus on Chapter 0 full-node policy coverage, B-owned
output self-checks, out-game Focus-on-Form report v1, and optional LLM feedback
usage logging. Developer B should not edit A/C implementation files directly;
schema or response-surface changes should be requested through
`docs/contracts/change_requests.md`.
```

- [ ] **Step 5: Verify documentation-only changes**

Run:

```powershell
git diff -- docs/portfolio_dev_b.md docs/contracts/change_requests.md docs/handoff.md
```

Expected: Only documentation wording changed; no implementation files changed.

---

### Task 2: Chapter 0 Full-Node Dev B Test Expansion

**Files:**
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`
- Read-only reference: `backend/app/data/scenario_nodes.json`
- Read-only reference: `backend/app/agents/agent_b/english_level_hint_agent.py`

- [ ] **Step 1: Add node-specific success cases**

Add parametrized tests for all playable Chapter 0 nodes after `IMM_002_PURPOSE`:

```python
@pytest.mark.parametrize(
    ("node_id", "slot_name", "slot_value", "success_next_node"),
    [
        ("IMM_003_DURATION", "stay_duration", "days", "IMM_004_STAY_LOCATION"),
        ("IMM_004_STAY_LOCATION", "stay_location", "hotel", "IMM_005_RETURN_TICKET"),
        ("IMM_005_RETURN_TICKET", "return_ticket_status", "has_return_ticket", "IMM_006_DECLARATION_CHECK"),
        ("IMM_006_DECLARATION_CHECK", "item_purpose", "personal_recreation", "IMM_006B_PACKED_BAG_CHECK"),
        ("IMM_006B_PACKED_BAG_CHECK", "packed_by_self", "yes_self_packed", "IMM_007_FINAL_DECISION"),
    ],
)
def test_chapter_zero_success_nodes_advance(
    node_id: str,
    slot_name: str,
    slot_value: str,
    success_next_node: str,
    tmp_path: Path,
) -> None:
    context = _node_context(node_id)
    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text=context.recommended_expression,
            intent_success=True,
            confidence=0.9,
            extracted_slots={slot_name: slot_value},
            missing_slots=[],
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.branch_type == "success"
    assert result.branch.next_action == "ADVANCE"
    assert result.branch.next_node_id == success_next_node
    assert result.branch.next_node_id in context.allowed_next_nodes
```

- [ ] **Step 2: Add node-specific missing-slot retry cases**

Add:

```python
@pytest.mark.parametrize(
    ("node_id", "missing_slot", "retry_next_node"),
    [
        ("IMM_003_DURATION", "stay_duration", "IMM_003_RETRY_DURATION"),
        ("IMM_004_STAY_LOCATION", "stay_location", "IMM_004_RETRY_LOCATION"),
        ("IMM_005_RETURN_TICKET", "return_ticket_status", "IMM_005_RETRY_RETURN_TICKET"),
        ("IMM_006_DECLARATION_CHECK", "item_purpose", "IMM_006_RETRY_DECLARATION"),
        ("IMM_006B_PACKED_BAG_CHECK", "packed_by_self", "IMM_006B_RETRY_PACKED_BAG"),
    ],
)
def test_chapter_zero_missing_slot_retries(
    node_id: str,
    missing_slot: str,
    retry_next_node: str,
    tmp_path: Path,
) -> None:
    context = _node_context(node_id)
    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="I am not sure.",
            intent_success=False,
            confidence=0.65,
            extracted_slots={},
            missing_slots=[missing_slot],
            tier="Silver",
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.evaluation.verdict == "FAIL"
    assert result.branch.branch_type == "retry"
    assert result.branch.next_action == "REASK"
    assert result.branch.next_node_id == retry_next_node
    assert result.state_delta.retry_count_delta == 1
```

- [ ] **Step 3: Add final node branch case**

Add:

```python
def test_final_decision_node_returns_final_branch(tmp_path: Path) -> None:
    context = _node_context("IMM_007_FINAL_DECISION")
    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text="Thank you, officer.",
            intent_success=True,
            confidence=0.9,
            extracted_slots={"final_recommendation": "PASS"},
            missing_slots=[],
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.branch_type == "final"
    assert result.branch.next_action == "FINAL_DECISION"
    assert result.branch.next_node_id == "END_PASS"
```

- [ ] **Step 4: Run expanded Dev B tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q
```

Expected: Pass.

---

### Task 3: Dev B Output Self-Check Guard

**Files:**
- Modify: `backend/app/agents/agent_b/english_level_hint_agent.py`
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`

- [ ] **Step 1: Write tests for invalid B output invariants**

Add focused tests that construct outputs through injectable fake services where practical. Cover:

```python
def test_dev_b_output_has_no_hint_payload_when_hint_is_not_needed(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(_policy_input())

    assert result.level_hint.needs_hint is False
    assert result.level_hint.hint_type is None
    assert result.level_hint.hint_kr is None
```

```python
def test_dev_b_output_recast_has_candidate_text(tmp_path: Path) -> None:
    result = _agent(tmp_path).evaluate_turn(_policy_input())

    assert result.in_game_feedback.feedback_strategy == "recast"
    assert result.in_game_feedback.npc_recast_line_candidate
```

- [ ] **Step 2: Add B-owned self-check helper**

In `english_level_hint_agent.py`, add a private helper near the bottom:

```python
def _validate_b_policy_output(payload: DevBPolicyInput, output: DevBPolicyOutput) -> None:
    if output.node_id != payload.current_node_id:
        raise ValueError("DevBPolicyOutput.node_id must match input current_node_id")
    if output.branch.next_node_id not in payload.node_context.allowed_next_nodes:
        raise ValueError("DevB branch.next_node_id is outside node_context.allowed_next_nodes")
    if payload.client_allowed_next_nodes and output.branch.next_node_id not in payload.client_allowed_next_nodes:
        raise ValueError("DevB branch.next_node_id is outside client_allowed_next_nodes")
    if not output.level_hint.needs_hint and (
        output.level_hint.hint_type is not None or output.level_hint.hint_kr is not None
    ):
        raise ValueError("DevB hint payload must be empty when needs_hint is false")
    if output.in_game_feedback.feedback_strategy == "recast" and not output.in_game_feedback.npc_recast_line_candidate:
        raise ValueError("DevB recast feedback requires npc_recast_line_candidate")
    if (
        output.in_game_feedback.feedback_strategy == "clarification_request"
        and not output.in_game_feedback.clarification_prompt_candidate
    ):
        raise ValueError("DevB clarification feedback requires clarification_prompt_candidate")
    if output.error_capture.should_record is False and (
        output.error_capture.error_items or output.error_capture.markdown_entry is not None
    ):
        raise ValueError("DevB error capture must be empty when should_record is false")
    if output.out_game_feedback_seed.include_in_final_report and not output.out_game_feedback_seed.focus_on_form_targets:
        raise ValueError("DevB final-report seed requires focus_on_form_targets")
    if output.rubric_scores is not None and not 0 <= output.rubric_scores.total <= 12:
        raise ValueError("DevB rubric_scores.total must be between 0 and 12")
```

- [ ] **Step 3: Call self-check before OpenKB write**

In `EnglishLevelHintAgent.evaluate_turn()`, call:

```python
_validate_b_policy_output(payload, output)
```

Call it after LLM feedback/rubric updates and before `openkb_writer.write_policy_output(...)`.

- [ ] **Step 4: Run Dev B tests**

Run:

```powershell
uv run pytest backend/tests/dev_b -q
```

Expected: Pass.

---

### Task 4: Out-Game Focus-on-Form Report v1

**Files:**
- Create: `backend/app/services/service_b/focus_on_form_report_policy.py`
- Create: `backend/tests/dev_b/test_focus_on_form_report_policy.py`
- Create or modify: `backend/app/kb/dev_b/focus_on_form_cards.json`
- Modify: `backend/app/services/service_b/__init__.py`
- Modify: `docs/contracts/change_requests.md`

- [ ] **Step 1: Add static Focus-on-Form card seeds**

Create `backend/app/kb/dev_b/focus_on_form_cards.json`:

```json
{
  "contract_version": "dev_b_focus_on_form_cards.v1",
  "cards": {
    "sentence_completion": {
      "title_kr": "완전한 문장으로 답하기",
      "rule_summary_kr": "입국심사에서는 단어만 말하기보다 주어와 동사를 포함한 짧은 문장이 더 안전합니다.",
      "good_examples": ["I'm here for tourism.", "I'll stay for five days."],
      "practice_prompt_kr": "방문 목적을 완전한 영어 문장으로 말해보세요.",
      "answer_example": "I'm here for tourism."
    }
  }
}
```

- [ ] **Step 2: Write failing report policy tests**

In `backend/tests/dev_b/test_focus_on_form_report_policy.py`, add tests for:

- repeated focus target selection
- original utterance and suggested expression preservation
- empty-record fallback
- card lookup fallback when a target has no static card

- [ ] **Step 3: Implement `FocusOnFormReportPolicy`**

Create a B-owned service that exposes:

```python
class FocusOnFormReportPolicy:
    def __init__(self, card_path: Path | None = None) -> None: ...

    def build_report(self, records: list[dict[str, Any]]) -> dict[str, Any]: ...
```

Output shape:

```python
{
    "report_mode": "focus_on_form",
    "overall_summary_kr": "...",
    "focus_on_form_items": [...],
    "personalized_next_step": {...},
}
```

- [ ] **Step 4: Export the service**

Add `FocusOnFormReportPolicy` to `backend/app/services/service_b/__init__.py`.

- [ ] **Step 5: Add C integration change request**

Append to `docs/contracts/change_requests.md`:

```markdown
## Change Request - 2026-06-08 - Expose Developer B Focus-on-Form Report v1

### Requested By
Developer B

### Affected Owner
Developer C / Sean Han

### Reason
Developer B can build an out-game Focus-on-Form report from B-owned OpenKB
runtime records and static B learning card seeds, but Developer C owns final API
response assembly and result endpoint shape.

### Proposed Contract Change
Add an optional `out_game_feedback` object to the final result response or a
C-owned result detail endpoint. The payload should be treated as learning
feedback metadata and must not affect branch, verdict, or scoring authority.

### Compatibility Impact
Additive optional field only.

### Temporary Workaround
Developer B will keep the report builder as a B-owned service and test it
directly until C exposes it.
```

- [ ] **Step 6: Run report policy tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_focus_on_form_report_policy.py -q
```

Expected: Pass.

---

### Task 5: LLM Feedback and Logging Improvements

**Files:**
- Modify: `backend/app/services/service_b/feedback_hint_generator.py`
- Modify: `backend/app/agents/agent_b/feedback_hint_llm_client.py`
- Modify: `backend/app/services/service_b/developer_b_agent_run_logger.py`
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`
- Modify: `backend/tests/dev_b/test_developer_b_agent_run_log.py`

- [ ] **Step 1: Add forbidden-key fallback test**

Add a fake LLM client that returns valid feedback fields plus forbidden keys:

```python
class _ForbiddenFeedbackLLMClient:
    model = "fake-forbidden-model"

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "hint_kr": "힌트입니다.",
            "feedback_note": "피드백입니다.",
            "report_summary": "요약입니다.",
            "report_improvement": "개선점입니다.",
            "example_answer": "I'm here for tourism.",
            "focus_on_form_explanation_kr": "설명입니다.",
            "rubric_scores": {
                "comprehension": 2,
                "fluency": 1,
                "grammar_accuracy": 1,
                "vocabulary_range": 1,
                "clarity": 2,
                "interaction_problem_solving": 2,
            },
            "branch": {"next_node_id": "END_SECONDARY_INSPECTION"},
            "state_delta": {"suspicion_delta": 99},
        }
```

Expected result: `feedback_generation.mode == "fallback"` and branch/state remain rule-based.

- [ ] **Step 2: Add forbidden-key detection**

In `feedback_hint_generator.py`, define:

```python
FORBIDDEN_FEEDBACK_LLM_KEYS = {
    "branch",
    "next_node_id",
    "next_action",
    "state_delta",
    "verdict",
    "evaluation",
    "npc_dialogue",
    "npc_text",
    "tts",
    "audio_url",
    "unreal_command",
    "unreal_commands",
}
```

Before validating `_LLMFeedbackPayload`, reject if any forbidden key is present:

```python
forbidden_keys = FORBIDDEN_FEEDBACK_LLM_KEYS.intersection(raw_result)
if forbidden_keys:
    raise ValueError(f"Feedback LLM returned forbidden keys: {', '.join(sorted(forbidden_keys))}")
```

- [ ] **Step 3: Preserve optional provider usage**

Allow the LLM client result to include `__llm_usage`, but exclude it from Pydantic validation. Store normalized usage in the feedback trace only if schema changes are approved. If no schema change is made, record usage in AgentRun event output summary instead of public `DevBPolicyOutput`.

- [ ] **Step 4: Add AgentRun event assertion**

In `test_developer_b_agent_run_log.py`, assert the feedback generator event includes model/mode and does not include forbidden authority fields.

- [ ] **Step 5: Run LLM-related tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py backend/tests/dev_b/test_developer_b_agent_run_log.py -q
```

Expected: Pass.

---

### Task 6: Final Verification

**Files:**
- Modify: `docs/handoff.md`

- [ ] **Step 1: Run Dev B focused tests**

Run:

```powershell
uv run pytest backend/tests/dev_b -q
```

Expected: Pass.

- [ ] **Step 2: Run integration tests that consume Dev B**

Run:

```powershell
uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q
```

Expected: Pass.

- [ ] **Step 3: Run full suite**

Run:

```powershell
uv run pytest -q
```

Expected: Pass.

- [ ] **Step 4: Run static checks**

Run:

```powershell
uv run ruff check .
uv run mypy .
```

Expected: Both pass. If `uv run mypy .` fails with user-cache access denied, rerun with approved escalation and document that it was the known environment workaround.

- [ ] **Step 5: Update handoff**

Add a final note to `docs/handoff.md` with:

- changed Dev B files
- commands run
- pass/fail status
- any remaining C-owned change requests

---

## Acceptance Criteria

- Dev B policy behavior remains deterministic for branch, verdict, next node, and state delta.
- Chapter 0 playable nodes have direct Dev B success and retry coverage.
- B-owned output self-check catches malformed policy output before OpenKB write.
- Focus-on-Form report v1 exists as a B-owned tested service.
- Optional LLM feedback cannot smuggle branch/state/verdict authority into B output.
- No Developer A or Developer C implementation file is modified directly for B-owned work.
- Required verification commands pass or documented environment-only failures are recorded in handoff.
