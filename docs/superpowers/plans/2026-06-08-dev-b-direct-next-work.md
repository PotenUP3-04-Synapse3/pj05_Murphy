# Dev B Direct Next Work Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the next Developer B-owned Alpha/Chapter 0 policy package without editing Developer A or Developer C implementation files.

**Architecture:** Developer B remains the deterministic authority for scenario node rules, level/hint policy, final-report seeds, B-owned OpenKB records, and B-only report building. Developer A still owns final NPC dialogue/TTS, and Developer C still owns orchestration, response assembly, endpoint surface, and non-B OpenKB retrieval.

**Tech Stack:** Python 3.12, uv, Pydantic schemas, pytest, ruff, mypy, B-owned JSON scenario data, B-owned OpenKB runtime records.

---

## Current Baseline

- `IMMIGRATION_ALPHA` tier policy and Gold bag-content challenge have been started in B-owned files.
- `backend/tests/dev_b` is allowed for this Dev B work even though `backend/tests/` is generally C-owned.
- Continue to avoid direct edits to Developer A/C implementation files.
- If C-owned endpoint/schema/UI exposure is required, append a request to `docs/contracts/change_requests.md` and summarize it in `docs/handoff.md`.

## Execution Order

1. Expand Chapter 0 node tests.
2. Strengthen Dev B output self-check coverage.
3. Build Focus-on-Form report v1.
4. Add B-owned learning card seeds.
5. Improve B-owned OpenKB record structure.
6. Improve LLM feedback guard/logging.
7. Add `BAGGAGE_MISSING` scenario nodes and policy seeds.
8. Final verification and handoff update.

---

### Task 1: Chapter 0 Remaining Node Test Expansion

**Files:**
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`
- Read: `backend/app/data/scenario_nodes.json`

- [ ] **Step 1: Add success-route coverage for every playable immigration node**

Add a parametrized test that covers:

```python
@pytest.mark.parametrize(
    ("node_id", "slot_name", "slot_value", "success_next_node"),
    [
        ("IMM_001_PASSPORT", "passport_submission_status", "submitted", "IMM_002_PURPOSE"),
        ("IMM_002_PURPOSE", "visit_purpose", "tourism", "IMM_003_DURATION"),
        ("IMM_003_DURATION", "stay_duration", "days", "IMM_004_STAY_LOCATION"),
        ("IMM_004_STAY_LOCATION", "stay_location", "hotel", "IMM_005_RETURN_TICKET"),
        ("IMM_006_DECLARATION_CHECK", "item_purpose", "personal_recreation", "IMM_006B_PACKED_BAG_CHECK"),
        ("IMM_006B_PACKED_BAG_CHECK", "packed_by_self", "yes_self_packed", "IMM_007_FINAL_DECISION"),
        ("IMM_ALPHA_GOLD_BAG_CONTENT_CHECK", "bag_contents_summary", "mixed_personal_items", "IMM_006_DECLARATION_CHECK"),
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
            confidence=0.92,
            extracted_slots={slot_name: slot_value},
            missing_slots=[],
            tier="Silver",
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.next_action == "ADVANCE"
    assert result.branch.next_node_id == success_next_node
    assert result.branch.next_node_id in context.allowed_next_nodes
```

- [ ] **Step 2: Add retry coverage for every playable immigration node**

Add:

```python
@pytest.mark.parametrize(
    ("node_id", "missing_slot", "retry_next_node"),
    [
        ("IMM_001_PASSPORT", "passport_submission_status", "IMM_001_RETRY_PASSPORT"),
        ("IMM_002_PURPOSE", "visit_purpose", "IMM_002_RETRY_PURPOSE"),
        ("IMM_003_DURATION", "stay_duration", "IMM_003_RETRY_DURATION"),
        ("IMM_004_STAY_LOCATION", "stay_location", "IMM_004_RETRY_LOCATION"),
        ("IMM_005_RETURN_TICKET", "return_ticket_status", "IMM_005_RETRY_RETURN_TICKET"),
        ("IMM_006_DECLARATION_CHECK", "item_purpose", "IMM_006_RETRY_DECLARATION"),
        ("IMM_006B_PACKED_BAG_CHECK", "packed_by_self", "IMM_006B_RETRY_PACKED_BAG"),
        ("IMM_ALPHA_GOLD_BAG_CONTENT_CHECK", "bag_contents_summary", "IMM_ALPHA_GOLD_RETRY_BAG_CONTENT_CHECK"),
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
```

- [ ] **Step 3: Run RED/GREEN verification**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q
```

Expected after implementation: pass.

---

### Task 2: Dev B Output Self-Check Guard Expansion

**Files:**
- Modify: `backend/app/agents/agent_b/english_level_hint_agent.py`
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`

- [ ] **Step 1: Add self-check tests**

Add tests for these invalid outputs:

- `level_hint.needs_hint is False` with non-empty `hint_kr`
- `feedback_strategy == "recast"` with no `npc_recast_line_candidate`
- `out_game_feedback_seed.include_in_final_report is True` with empty `focus_on_form_targets`
- `rubric_scores.total` outside `0..12`

Use fake injected services where needed. Expected result: each case raises `ValueError` before OpenKB write.

- [ ] **Step 2: Add or extend `_validate_b_policy_output`**

The guard must enforce:

```text
output.node_id == payload.current_node_id
branch.next_node_id in node_context.allowed_next_nodes
branch.next_node_id in client_allowed_next_nodes when client list is present
no hint payload when needs_hint is false
recast feedback requires npc_recast_line_candidate
clarification feedback requires clarification_prompt_candidate
empty error payload when should_record is false
final-report seed requires focus_on_form_targets when included
rubric total stays within 0..12
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q
```

Expected: pass.

---

### Task 3: Focus-on-Form Report v1 Builder

**Files:**
- Create: `backend/app/services/service_b/focus_on_form_report_policy.py`
- Create: `backend/tests/dev_b/test_focus_on_form_report_policy.py`
- Modify: `backend/app/services/service_b/__init__.py`

- [ ] **Step 1: Write report builder tests**

Create tests that verify:

- repeated targets are grouped and ranked
- original utterance and suggested expression are preserved
- empty input returns a valid empty report
- unknown target uses fallback card text
- report output never changes branch, verdict, or score

Expected output shape:

```python
{
    "report_mode": "focus_on_form",
    "overall_summary_kr": "...",
    "focus_on_form_items": [
        {
            "focus_on_form_target": "sentence_completion",
            "title_kr": "...",
            "original_utterances": ["Travel. New York."],
            "suggested_expressions": ["I'm here for tourism."],
            "practice_prompt_kr": "...",
            "answer_example": "I'm here for tourism.",
            "priority": "medium",
            "source_node_ids": ["IMM_002_PURPOSE"],
        }
    ],
    "personalized_next_step": {
        "target": "sentence_completion",
        "practice_prompt_kr": "...",
        "answer_example": "I'm here for tourism.",
    },
}
```

- [ ] **Step 2: Implement `FocusOnFormReportPolicy`**

Expose:

```python
class FocusOnFormReportPolicy:
    def __init__(self, card_path: Path | None = None) -> None: ...

    def build_report(self, records: list[dict[str, Any]]) -> dict[str, Any]: ...
```

Input records should be B-owned OpenKB record dictionaries from `OpenKBFeedbackWriter`.

- [ ] **Step 3: Export the service**

Update `backend/app/services/service_b/__init__.py`:

```python
from backend.app.services.service_b.focus_on_form_report_policy import FocusOnFormReportPolicy
```

and add it to `__all__`.

- [ ] **Step 4: Run report tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_focus_on_form_report_policy.py -q
```

Expected: pass.

---

### Task 4: B-Owned Learning Cards / Seeds

**Files:**
- Create: `backend/app/kb/dev_b/focus_on_form_cards.json`
- Modify: `backend/tests/dev_b/test_focus_on_form_report_policy.py`

- [ ] **Step 1: Add static card seeds**

Create:

```json
{
  "contract_version": "dev_b_focus_on_form_cards.v1",
  "cards": {
    "sentence_completion": {
      "title_kr": "완전한 문장으로 답하기",
      "rule_summary_kr": "입국심사와 공항 문제 해결에서는 단어만 말하기보다 주어와 동사를 포함한 짧은 문장이 더 안전합니다.",
      "good_examples": ["I'm here for tourism.", "My suitcase didn't arrive."],
      "practice_prompt_kr": "상황을 완전한 영어 문장으로 말해보세요.",
      "answer_example": "I'm here for tourism."
    },
    "return_ticket_statement": {
      "title_kr": "귀국 항공권을 명확히 말하기",
      "rule_summary_kr": "귀국 계획은 yes/no 뒤에 날짜나 항공편 정보를 짧게 붙이면 더 신뢰도가 높습니다.",
      "good_examples": ["Yes, I do. My return flight is next Friday."],
      "practice_prompt_kr": "귀국 항공권이 있다는 것을 날짜와 함께 말해보세요.",
      "answer_example": "Yes, I do. My return flight is next Friday."
    },
    "bag_content_explanation": {
      "title_kr": "짐 내용물 설명하기",
      "rule_summary_kr": "짐 내용물 질문에는 주요 물건을 구체적으로 말하고 신고할 물건이 있는지 분명히 답해야 합니다.",
      "good_examples": ["I packed clothes, toiletries, and my laptop. I have nothing else to declare."],
      "practice_prompt_kr": "짐 안의 주요 물건과 신고 여부를 한 문장으로 말해보세요.",
      "answer_example": "I packed clothes, toiletries, and my laptop. I have nothing else to declare."
    },
    "problem_statement": {
      "title_kr": "문제 상황을 직접 말하기",
      "rule_summary_kr": "공항 직원에게는 문제가 무엇인지 짧고 직접적으로 말하는 것이 좋습니다.",
      "good_examples": ["My suitcase didn't arrive."],
      "practice_prompt_kr": "수화물이 도착하지 않았다는 문제를 말해보세요.",
      "answer_example": "My suitcase didn't arrive."
    },
    "bag_description": {
      "title_kr": "수화물 외형 설명하기",
      "rule_summary_kr": "색, 크기, 종류, 태그 같은 식별 정보를 함께 말하면 직원이 찾기 쉽습니다.",
      "good_examples": ["It's a black medium-sized suitcase with a red luggage tag."],
      "practice_prompt_kr": "가방의 색, 크기, 특징을 말해보세요.",
      "answer_example": "It's a black medium-sized suitcase with a red luggage tag."
    }
  }
}
```

- [ ] **Step 2: Test card loading**

Report tests must assert that card text is used for known targets and fallback text is used for unknown targets.

---

### Task 5: B-Owned OpenKB Record Structure Improvement

**Files:**
- Modify: `backend/app/services/service_b/openkb_feedback_writer.py`
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`

- [ ] **Step 1: Add record schema assertions**

Assert each B OpenKB record includes:

```text
record_schema_version: dev_b_openkb_record.v2
record_kind: policy_turn_feedback
scene_id
node_id
turn_index
focus_on_form_targets
report_item
rubric_scores
difficulty_profile
feedback_generation
branch
state_delta
```

- [ ] **Step 2: Implement additive record fields**

Keep existing keys for compatibility. Add only new fields; do not remove or rename current record keys.

- [ ] **Step 3: Update Markdown record heading**

Markdown should include:

```text
- Record Schema: dev_b_openkb_record.v2
- Record Kind: policy_turn_feedback
```

- [ ] **Step 4: Run OpenKB writer tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q
```

Expected: pass.

---

### Task 6: LLM Feedback Guard / Logging Improvement

**Files:**
- Modify: `backend/app/services/service_b/feedback_hint_generator.py`
- Modify: `backend/app/agents/agent_b/english_level_hint_agent.py`
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`
- Modify: `backend/tests/dev_b/test_developer_b_agent_run_log.py`

- [ ] **Step 1: Add LLM usage test**

Add a fake LLM client returning:

```python
"__llm_usage": {
    "input_tokens": 100,
    "output_tokens": 50,
    "total_tokens": 150,
}
```

Assert usage is recorded in AgentRun event output summary, not in public `DevBPolicyOutput`.

- [ ] **Step 2: Extend forbidden-key logging**

When forbidden keys force fallback, AgentRun should include:

```text
feedback_generation.mode == "fallback"
fallback_reason contains "forbidden keys"
```

Do not add branch/verdict/state authority to public LLM output.

- [ ] **Step 3: Run logging tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py backend/tests/dev_b/test_developer_b_agent_run_log.py -q
```

Expected: pass.

---

### Task 7: BAGGAGE_MISSING Scenario Nodes And Seeds

**Files:**
- Modify: `backend/app/data/scenario_nodes.json`
- Modify: `backend/app/agents/agent_b/english_level_hint_agent.py`
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`
- Read: `docs/superpowers/plans/2026-06-08-alpha-baggage-missing.md`

- [ ] **Step 1: Add baggage node tests first**

Add tests for these nodes:

```text
BAG_002_FIND_STAFF
BAG_003_REPORT_MISSING_BAG
BAG_004_DESCRIBE_BAG
BAG_005_PROVIDE_FLIGHT_OR_TAG
BAG_006_CONTACT_AND_DELIVERY
BAG_007_RESOLUTION
```

Required behavior:

- success advances to the next baggage node
- missing required slot retries or clarifies
- Bronze broken English can still create a report seed without hard fail
- Gold missing details are stricter and produce final-report seeds

- [ ] **Step 2: Add baggage nodes to `scenario_nodes.json`**

Use the existing `NodeContext` shape. Keep `chapter_id` as `CH0_IMMIGRATION` until Developer C introduces a broader airport-arrival chapter/scene contract.

Minimum node mapping:

```text
BAG_002_FIND_STAFF -> BAG_003_REPORT_MISSING_BAG
BAG_003_REPORT_MISSING_BAG -> BAG_004_DESCRIBE_BAG
BAG_004_DESCRIBE_BAG -> BAG_005_PROVIDE_FLIGHT_OR_TAG
BAG_005_PROVIDE_FLIGHT_OR_TAG -> BAG_006_CONTACT_AND_DELIVERY
BAG_006_CONTACT_AND_DELIVERY -> BAG_007_RESOLUTION
BAG_007_RESOLUTION -> END_BAGGAGE_REPORT_FILED
```

Use required slots:

```text
missing_bag_status
missing_bag_report
bag_description
baggage_tag_or_flight_info
delivery_contact
resolution_acknowledgement
```

- [ ] **Step 3: Add baggage Focus-on-Form target mapping**

In Dev B focus target mapping, add:

```text
BAG_003_REPORT_MISSING_BAG -> problem_statement
BAG_004_DESCRIBE_BAG -> bag_description
BAG_005_PROVIDE_FLIGHT_OR_TAG -> flight_or_tag_statement
BAG_006_CONTACT_AND_DELIVERY -> delivery_request
BAG_007_RESOLUTION -> follow_up_question
```

- [ ] **Step 4: Run baggage tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q
```

Expected: pass.

---

### Task 8: Handoff And Verification

**Files:**
- Modify: `docs/handoff.md`
- Modify only if needed: `docs/contracts/change_requests.md`

- [ ] **Step 1: Add handoff entry**

Append a Dev B handoff entry listing:

- changed B files
- tests run
- B-owned behavior added
- any C/A change requests

- [ ] **Step 2: Add C change request only if endpoint exposure is required**

If Focus-on-Form report v1 needs API exposure, add a C change request for optional final-result `out_game_feedback`. Do not edit C implementation.

- [ ] **Step 3: Run final verification**

Run:

```powershell
uv run pytest backend/tests/dev_b -q
uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q
uv run pytest -q
uv run ruff check .
uv run mypy .
```

Expected:

- Dev B tests pass.
- Integration tests pass.
- Full suite passes.
- Ruff passes.
- Mypy passes. If mypy fails with uv cache permission error, rerun the same command with approved escalation and document the environment workaround.

---

## Acceptance Criteria

- Chapter 0 playable immigration nodes have success and retry coverage.
- Dev B output self-checks protect branch, hint, feedback, report seed, and rubric invariants.
- Focus-on-Form report v1 exists as a B-owned service and is tested directly.
- B-owned learning cards exist under `backend/app/kb/dev_b/`.
- B OpenKB runtime records have additive v2 structure while preserving current compatibility keys.
- LLM feedback cannot smuggle authority fields and logs fallback reason/usage safely.
- `BAGGAGE_MISSING` has B-owned scenario nodes, required slots, hint policy, and final-report seed mapping.
- No Developer A or Developer C implementation file is modified directly.
