# Dev B NPC Metadata Contract Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Developer B away from NPC wording authority by replacing A-facing dialogue text hints with compact NPC generation metadata.

**Architecture:** Developer B owns difficulty and emotion policy, but Developer A owns final NPC utterance generation and TTS wording. Developer C owns the schema, validator, and adapter payload that carries B metadata to A. This plan is executable only after Developer C removes or relaxes the current schema fields that force B/C to pass NPC text-like values.

**Tech Stack:** Python 3.12, uv, pytest, Pydantic schemas, B-owned policy services, C-owned adapter/schema handoff.

---

## Scope Decision

This plan is B-owned only where it changes Developer B policy outputs after the C-owned schema accepts the new contract. It does not authorize Developer B to edit Developer A dialogue generation, Developer C adapter code, Developer C schemas, Developer C validators, or Unreal response assembly.

## Required C/A Precondition

Developer C must first support the handoff in `docs/contracts/change_requests.md`:

- C must stop passing `node_context.npc_question` to Developer A as candidate dialogue.
- C must stop writing next-node question text into `in_game_feedback.npc_recast_line_candidate`.
- C must remove or make non-required `dialogue_directive.do_not_generate_npc_text` so Developer B does not send it to C.
- C must accept numeric `npc_speech_speed` and `question_complexity` values on a 0-10 scale.
- C must accept word-only `emotion_change`: `positive`, `neutral`, or `negative`.
- Developer A must generate final NPC utterances from goal/slot/difficulty/emotion metadata.

## Metadata Contract

No JSON comment keys should be added to runtime payloads. Use this table in contract docs and plans instead.

| Key | Value | Meaning |
| --- | --- | --- |
| `npc_speech_speed` | integer `0-10` | `0` = very slow and learner-friendly, `10` = near-native fast |
| `question_complexity` | integer `0-10` | `0` = very simple one-part question, `10` = complex multi-part question |
| `emotion_change` | `positive`, `neutral`, `negative` | NPC emotional/tone direction caused by the current turn |

`hint_frequency` is intentionally excluded from the A-facing NPC generation metadata. Hint timing remains B-owned feedback policy, not Developer A dialogue-generation input.

`pressure_level` is replaced by `emotion_change` for A/Unreal-facing tone and facial-expression direction.

## Target A-Facing Payload Shape

The C-to-A internal payload should remove NPC wording seeds:

```diff
node_context:
-  npc_question: "How long will you be staying?"
   npc_question_goal: "ask_stay_duration"
   required_slots: ["stay_duration"]

in_game_feedback:
-  npc_recast_line_candidate: "You're here for tourism. How long will you be staying?"

dialogue_directive:
   purpose: "continue_to_next_question"
   tone_hint: "formal_stern"
   target_slot: "stay_duration"
-  do_not_generate_npc_text: false

difficulty_profile:
-  npc_speech_speed: "natural"
-  question_complexity: "complex"
-  hint_frequency: "low"
-  pressure_level: "high"
+  npc_speech_speed: 8
+  question_complexity: 7
+  emotion_change: "negative"
```

---

### Task 1: Update Dev B Difficulty Policy Tests

**Files:**
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`

- [ ] **Step 1: Write failing expectations for numeric difficulty metadata**

After C updates `backend/app/schemas/game_turn.py`, replace current string assertions for `npc_speech_speed`, `question_complexity`, and `pressure_level` with numeric and word-only assertions:

```python
def test_difficulty_profile_changes_by_tier_and_tsl() -> None:
    controller = TierDifficultyController()

    bronze = controller.from_score_values(0, 0, 1, 0, 1, 0, tier="Bronze")
    gold = controller.from_score_values(2, 2, 2, 2, 2, 2, tier="Gold")

    assert bronze.difficulty_profile.npc_speech_speed <= 3
    assert bronze.difficulty_profile.question_complexity <= 3
    assert bronze.difficulty_profile.emotion_change == "neutral"
    assert gold.difficulty_profile.npc_speech_speed >= 8
    assert gold.difficulty_profile.question_complexity >= 8
    assert gold.difficulty_profile.emotion_change in {"neutral", "negative"}
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_difficulty_profile_changes_by_tier_and_tsl -q
```

Expected before implementation: fail because the current schema still exposes string speed/complexity, `hint_frequency`, and `pressure_level`.

---

### Task 2: Update Dev B Difficulty Policy Output

**Files:**
- Modify: `backend/app/services/service_b/tier_difficulty_controller.py`

- [ ] **Step 1: Implement numeric difficulty mapping**

Update `difficulty_profile_for(...)` so B maps current tier/TSL evidence into the new values:

```python
def _speech_speed_10(total: int, tier: str) -> int:
    if tier == "Gold":
        return 8 if total >= 10 else 7
    if tier == "Silver":
        return 5
    return 2


def _question_complexity_10(total: int, tier: str) -> int:
    if tier == "Gold":
        return 8 if total >= 10 else 7
    if tier == "Silver":
        return 5
    return 2


def _emotion_change(total: int, tier: str) -> str:
    if tier == "Gold" and total < 8:
        return "negative"
    return "neutral"
```

Do not include `hint_frequency` in the A-facing difficulty metadata. Do not output `pressure_level`.

- [ ] **Step 2: Verify GREEN**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_difficulty_profile_changes_by_tier_and_tsl -q
```

Expected: the updated test passes.

---

### Task 3: Stop Sending B-Controlled NPC Generation Flags

**Files:**
- Modify: `backend/app/agents/agent_b/english_level_hint_agent.py`
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`

- [ ] **Step 1: Remove `do_not_generate_npc_text` expectations from Dev B tests**

Replace assertions like:

```python
assert result.dialogue_directive.do_not_generate_npc_text is True
```

with:

```python
assert result.dialogue_directive is not None
assert result.dialogue_directive.purpose == "continue_to_next_question"
assert result.dialogue_directive.target_slot == "visit_purpose"
```

- [ ] **Step 2: Update Dev B directive construction**

After C makes the field optional or removes it from the schema, update `_build_dialogue_directive(...)` so it returns only purpose, tone, and target-slot metadata:

```python
return DialogueDirective(
    purpose=purpose,
    tone_hint=tone_hint,
    target_slot=target_slot,
)
```

Developer B must not send a field that controls whether Developer A generates NPC text.

- [ ] **Step 3: Verify Dev B tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q
```

Expected: all Dev B policy-engine tests pass.

---

### Task 4: Contract And Handoff Refresh

**Files:**
- Modify: `docs/contracts/change_requests.md`
- Modify: `docs/handoff.md`

- [ ] **Step 1: Confirm the cross-owner request remains open**

Ensure the change request states:

```text
Developer B must not author final NPC dialogue. Developer C must not pass
`npc_question` or generated next-question text to Developer A as
`candidate_text` / `npc_recast_line_candidate`. Developer A owns final NPC
utterance generation.
```

- [ ] **Step 2: Record verification**

Append the actual commands and results to `docs/handoff.md` after implementation:

```markdown
Verification:

- `uv run pytest backend/tests/dev_b -q`
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q`
- `uv run pytest -q`
- `uv run ruff check .`
- `uv run mypy .`
```

---

## Acceptance Criteria

- Developer B no longer sends `do_not_generate_npc_text` after C removes or relaxes that schema field.
- Developer B difficulty output uses numeric `npc_speech_speed` and `question_complexity` on a 0-10 scale.
- Developer B uses word-only `emotion_change`: `positive`, `neutral`, or `negative`.
- `hint_frequency` is not part of the A-facing NPC generation metadata.
- `pressure_level` is not part of the A-facing NPC generation metadata.
- Developer C owns removing `npc_question` / `npc_recast_line_candidate` from C-to-A candidate dialogue flow.
- Developer A remains the sole owner of final NPC utterance and TTS wording.
