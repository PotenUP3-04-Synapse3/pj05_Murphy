# 작업계획서: BAG_002·BAG_005 인텐트 인식 실패 수정

## 배경 (Context)

플레이테스트에서 발견한 두 개의 연속 버그. 세관 수하물 챕터 초입부터 비정상 종료까지
이어지는 치명적 경로다.

```
BAG_002: "here it is"         → REASK | UNCLEAR   ← 버그
BAG_005: "yeah I checked now" → REASK | UNCLEAR   ← 버그 (×3회 반복 후 FAIL)
BAG_005: "yeah, I did."       → REASK | UNCLEAR   ← 버그
BAG_005: "I did"              → END_BAGGAGE_REPORT_INCOMPLETE | FAIL ← 버그
```

---

## 진단 요약

### BUG #1 — BAG_002 `provide_claim_tag`: 물리 제출 표현 미인식

| 항목 | 내용 |
|---|---|
| 노드 | `BAG_002_PROVIDE_CLAIM_TAG` (+ RETRY, CLARIFY 변형) |
| NPC 질문 | "May I see your baggage claim tag?" |
| 유저 입력 | "here it is" |
| 기대 결과 | `claim_tag_status: has_claim_tag` → ADVANCE |
| 실제 결과 | `intent_success=false`, `needs_clarification=true` → REASK |

**근본 원인**: `_developer_instructions()`의 특별처리 규칙이 `confirm_*` 인텐트만 커버한다.
`provide_claim_tag`는 `provide_*` 인텐트라 이 규칙에 해당하지 않는다. "here it is", "here
you go", "take it" 같은 물리 제출(physical handover) 표현은 LLM이 슬롯 값으로 매핑하지
못하고 `needs_clarification=true`를 반환한다. `_is_unclear()` 조건을 충족시켜 REASK로
빠진다.

**변경 범위**: prompt 계층만 수정. `allowed_slot_values`는 이미 올바름
(`has_claim_tag` / `has_ticket` / `has_boarding_pass`).

---

### BUG #2 — BAG_005 `acknowledge_customs_hold_explanation`: 과거형 이행 확인 미인식

| 항목 | 내용 |
|---|---|
| 노드 | `BAG_005_CUSTOMS_HOLD_EXPLANATION` (+ RETRY, CLARIFY 변형 포함 **3종 동일 구조**) |
| NPC 질문 | "I'll unlock it, so please check the contents." |
| 유저 입력 | "yeah I checked now" / "yeah, I did." / "I did" |
| 기대 결과 | `customs_hold_acknowledgement: already_checked` → ADVANCE |
| 실제 결과 | `intent_success=false`, `needs_clarification=true` → REASK × 3 → FAIL |

**근본 원인 (두 곳)**:

1. **`allowed_slot_values` 설계 누락**: 현재 값은 `["will_unlock_and_check",
   "understands_inspection", "confirms_owner"]`로 모두 미래형 동의 표현이다. "I did", "I
   checked now", "yeah I did"처럼 이미 행동을 완료했다는 **과거형 이행 확인** 응답이 매핑될
   슬롯 값이 없다. LLM이 어떤 값에도 매핑 못해 슬롯을 missing으로 둔다.

2. **prompt 규칙 누락**: `confirm_*` / `acknowledge_*` 인텐트 특별처리 규칙이 없어, 과거형
   compliance 표현을 LLM이 `intent_success=false`로 판정한다.

**변경 범위**: prompt 계층 + `scenario_nodes.json` BAG_005 3종 노드.

---

## 수정 대상 파일

| 파일 | 변경 이유 |
|---|---|
| `backend/app/agents/agent_c/understanding_llm_client.py` | `_developer_instructions()` 규칙 추가 |
| `backend/app/prompts/understanding_prompt.md` | 위 규칙 동기화 |
| `backend/app/data/scenario_nodes.json` | BAG_005 3종 `allowed_slot_values` 확장 |

---

## 수정 명세

### Step 1 — `understanding_llm_client.py`: 인텐트별 특별처리 규칙 확장

**위치**: [`backend/app/agents/agent_c/understanding_llm_client.py:218`](../../backend/app/agents/agent_c/understanding_llm_client.py)
`_developer_instructions()` 문자열 내 기존 `confirm_*` 규칙 다음에 두 블록 추가.

**추가 규칙 1 — `provide_*` 인텐트: 물리 제출 표현 인식**

```
 For provide_* required intents (e.g. provide_claim_tag), if the player
 uses a physical-handover expression ("here it is", "here you go",
 "take it", "there you go", "this one", "here", combined with context
 of presenting an item), canonicalize to the most appropriate
 allowed_slot_value (e.g. has_claim_tag) and set intent_success=true.
 Do not require an explicit verbal "yes I have it" when the phrasing
 clearly indicates a physical act of submission.
```

**추가 규칙 2 — `acknowledge_*` 인텐트: 과거형 이행 확인 인식**

```
 For acknowledge_* required intents (e.g. acknowledge_customs_hold_explanation),
 if the player uses a past-tense compliance expression confirming they have
 already performed the requested action ("I did", "I checked", "yeah I did",
 "I already did it", "done", "I looked", "yeah I checked now"), canonicalize
 to the most appropriate allowed_slot_value (e.g. already_checked) and set
 intent_success=true. Past-tense compliance is as valid as future-tense
 agreement — do not mark it as unclear or missing intent.
```

---

### Step 2 — `understanding_prompt.md`: Step 1과 동기화

**위치**: [`backend/app/prompts/understanding_prompt.md:39`](../../backend/app/prompts/understanding_prompt.md)
기존 `### Confirmation Intents` 섹션 다음에 두 섹션 추가.

```markdown
### Physical Handover Intents

For `provide_*` required intents (e.g. `provide_claim_tag`), physical-handover
expressions ("here it is", "here you go", "take it", "there you go", "this one",
"here") indicate the player is physically submitting the requested item.
Canonicalize to the most appropriate `allowed_slot_value` (e.g. `has_claim_tag`)
and return `intent_success = true`. Do not require an explicit "yes I have it."

### Acknowledgement Intents

For `acknowledge_*` required intents (e.g. `acknowledge_customs_hold_explanation`),
past-tense compliance expressions ("I did", "I checked", "yeah I did", "I already
did it", "done", "I looked", "yeah I checked now") confirm the player has already
performed the requested action. Canonicalize to the most appropriate
`allowed_slot_value` (e.g. `already_checked`) and return `intent_success = true`.
Past-tense compliance is as valid as future-tense agreement — do not return
`needs_clarification = true` for these expressions.
```

---

### Step 3 — `scenario_nodes.json`: BAG_005 3종 노드 `allowed_slot_values` 확장

대상 노드 (3개, 동일 구조):
- `BAG_005_CUSTOMS_HOLD_EXPLANATION` (line ~844)
- `BAG_005_RETRY_CUSTOMS_HOLD_EXPLANATION` (line ~2638)
- `BAG_005_CLARIFY_CUSTOMS_HOLD_EXPLANATION` (line ~2720)

각 노드의 `allowed_slot_values.customs_hold_acknowledgement` 배열에
`"already_checked"` 추가:

```json
"allowed_slot_values": {
  "customs_hold_acknowledgement": [
    "will_unlock_and_check",
    "understands_inspection",
    "confirms_owner",
    "already_checked"
  ]
}
```

> **주의**: 세 노드 모두 동일하게 수정해야 한다. RETRY와 CLARIFY 노드를 빠뜨리면
> retry 루프에서 여전히 FAIL이 발생한다.

---

## 검증 기준

### 수동 플레이 체크리스트

| 시나리오 | 입력 | 기대 결과 |
|---|---|---|
| BAG_002 물리 제출 | "here it is" | ADVANCE → BAG_003 |
| BAG_002 물리 제출 변형 | "here you go" | ADVANCE → BAG_003 |
| BAG_002 명시 답변 (회귀) | "Yes, here is my baggage claim tag." | ADVANCE → BAG_003 |
| BAG_005 과거형 이행 | "yeah I checked now" | ADVANCE → BAG_006 |
| BAG_005 과거형 이행 | "I did" | ADVANCE → BAG_006 |
| BAG_005 과거형 이행 | "yeah, I did." | ADVANCE → BAG_006 |
| BAG_005 미래형 동의 (회귀) | "Okay, I'll open it and check." | ADVANCE → BAG_006 |
| BAG_005 거부 (회귀) | "I refuse to open it" | CRITICAL_FAIL |
| BAG_005 부정 (회귀) | "not my bag" | CRITICAL_FAIL 또는 REASK |

### 단위 테스트

- `backend/tests/dev_b/test_baggage_chapter_flow.py`에 BAG_002 물리 제출 케이스 추가
- `backend/tests/dev_b/test_baggage_chapter_flow.py`에 BAG_005 과거형 이행 케이스 추가
- `backend/tests/test_llm_acceptance.py`에 두 노드에 대한 acceptance 케이스 추가

---

## 작업 순서

```
Step 1  understanding_llm_client.py _developer_instructions() 수정
Step 2  understanding_prompt.md 동기화
Step 3  scenario_nodes.json BAG_005 3종 allowed_slot_values 수정
Step 4  수동 플레이 검증 (위 체크리스트)
Step 5  테스트 케이스 추가
```

Step 3은 Step 1·2와 독립적으로 진행 가능. Step 1·2는 함께 진행.

---

## 영향 범위

- **BAG_001 ~ BAG_004**: 변경 없음. `provide_*` 규칙은 `provide_claim_tag` 문맥에서만
  활성화되며 다른 인텐트에 영향 없음.
- **BAG_006 이후**: 변경 없음. BAG_005 통과 이후 경로는 기존 로직 유지.
- **IMM 챕터**: 변경 없음. `acknowledge_*` / `provide_*` 인텐트 처리는 해당 인텐트가
  선언된 노드에서만 동작.
- **customs_pressure 수정 (별도 브랜치)**: BAG_005의 `allowed_slot_values` 확장은
  `customs_item_context` 주입 로직과 충돌 없음. BAG_005는 BAG_006 진입 게이트이며
  물품 컨텍스트 판정은 BAG_006에서 이루어짐.
