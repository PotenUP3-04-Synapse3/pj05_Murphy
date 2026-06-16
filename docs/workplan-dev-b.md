# Developer B 작업계획서 — 슬롯 값 유효성 검증으로 SUCCESS 오판정 차단

- 작성일: 2026-06-16
- 작성자: Developer B
- 대상 버그: "펜을 빌려달라"는 질문에 "Um,"이라고만 답했는데 SUCCESS(ADVANCE)로
  판정되어 잘못된 다음 대사가 생성되는 현상

## 1. 배경 및 문제 정의

플레이어가 단순 망설임("Um,")을 발화했을 때 다음 연쇄가 발생했다.

1. Understanding Agent(Dev C 소유)가 `intent_success=True`로 오인식하고,
   필수 슬롯 `polite_response`에 `"short acknowledgement / hesitant start"`라는
   임의의 자유 텍스트 값을 채워 넣음.
2. **Dev B의 `ScenarioStateMachine`가 슬롯에 채워진 값이
   `allowed_slot_values`(예: `offered_help`, `declined_politely`,
   `short_acknowledgement`)에 실재하는 후보인지 검증하지 않고**,
   `intent_success == True`이며 `missing_slots`가 비어 있다는 조건만으로
   해당 턴을 SUCCESS(ADVANCE)로 판정함.
3. 시나리오가 성공으로 판정됨에 따라 Dev A의 Dialogue Agent가 잘못된 상황
   대사를 생성(화자 역할 혼동/환각, 다음 질문 누락)함.

본 계획서는 **2번(Dev B 소유 영역)** 만을 다룬다. 1번/3번은 Dev C/Dev A 소유라
별도 변경 요청으로 전달한다(`docs/contracts/change_requests.md`,
`docs/handoff.md` 참조).

### 이 수정이 중요한 이유

Dev B가 슬롯 값 유효성을 검증하면 "Um,"이 SUCCESS로 판정되어 ADVANCE되는
연쇄의 출발점이 차단된다. 잘못된 SUCCESS가 Dev A로 전달되지 않으므로, Dev A
측 환각·다음 질문 누락 현상의 **발현 조건 자체가 사라진다.** 즉 본 수정은 이
버그 체인에서 Dev B 소유 영역만으로 가능한 가장 효과적인 단일 차단점이다.

## 2. 범위

### 포함 (Dev B 소유)

- `backend/app/services/service_b/scenario_state_machine.py`
- `backend/app/agents/agent_b/english_level_hint_agent.py` (보조, 선택)
- `backend/tests/dev_b/test_developer_b_policy_engine.py`

### 제외

- env 수정 전체 (수작업 예정)
- `voice_output_service.py` / TTS 폴백 (Dev A 소유)
- Understanding Agent / 통합 어댑터 / Dialogue Agent 코드 직접 수정
  (Dev C·Dev A 소유 → 변경 요청으로만 전달)

## 3. 현재 코드 분석

`scenario_state_machine.py`의 `_is_success`:

```python
def _is_success(self, payload: DevBPolicyInput) -> bool:
    return payload.understanding.intent_success and not payload.understanding.missing_slots
```

- 검증 대상 데이터는 이미 스키마에 존재한다.
  - `NodeContext.allowed_slot_values: dict[str, list[str]]`
    (`backend/app/schemas/game_turn.py`)
  - `UnderstandingOutput.extracted_slots: dict[str, str]`
  - `NodeContext.required_slots: list[str]`
- 따라서 추가 스키마/계약 변경 없이 규칙 검증만 보강하면 된다.

## 4. 작업 항목

### 작업 1 — 슬롯 값 검증 헬퍼 추가 (`scenario_state_machine.py`)

`required_slots` 중 `allowed_slot_values`가 정의된 슬롯의 추출값이 허용
후보군에 실재하는지 검사하는 헬퍼를 추가한다. 허용값이 정의되지 않은 자유
텍스트 슬롯은 검증을 생략한다(기존 동작 보존).

```python
def _has_invalid_required_slot_value(self, payload: DevBPolicyInput) -> bool:
    """required_slots 중 allowed_slot_values가 정의된 슬롯의 추출값이
    허용 후보군에 실재하지 않으면 True. 허용값이 정의되지 않은(자유 텍스트)
    슬롯은 검증을 생략한다."""
    allowed = payload.node_context.allowed_slot_values
    extracted = payload.understanding.extracted_slots
    for slot in payload.node_context.required_slots:
        candidates = allowed.get(slot)
        if not candidates:
            continue
        value = extracted.get(slot)
        if value is None or value not in candidates:
            return True
    return False
```

### 작업 2 — `_is_success`에 검증 조건 추가

```python
def _is_success(self, payload: DevBPolicyInput) -> bool:
    return (
        payload.understanding.intent_success
        and not payload.understanding.missing_slots
        and not self._has_invalid_required_slot_value(payload)
    )
```

### 작업 3 — 유효하지 않은 값은 clarify(REASK)로 라우팅

`_is_unclear`에 동일 조건을 추가하여, 허용 후보로 매핑되지 않는 모호 응답이
SUCCESS가 아니라 되묻기(REASK)로 흐르도록 한다.

```python
def _is_unclear(self, payload: DevBPolicyInput) -> bool:
    return (
        payload.input_source.needs_repeat
        or payload.understanding.needs_clarification
        or payload.understanding.confidence < 0.5
        or payload.understanding.answer_relevance == "partially_related"
        or self._has_invalid_required_slot_value(payload)
    )
```

설계 근거: 슬롯 값이 허용 후보에 매핑되지 않는다는 것은 "의도는 비슷하나
명확하지 않다"는 의미이므로 retry(FAIL)보다 clarify(REASK)가 학습 흐름상
적합하다. `decide()`는 success → unclear 순으로 검사하므로, 작업 2에서
`_is_success`가 False가 되면 자연스럽게 clarify로 진입한다.

가드레일 준수: 분기 제어는 규칙 기반을 유지하며, NPC 대사·다음 노드·verdict를
LLM으로 생성하지 않는다. 본 수정은 순수 규칙 검증이므로 Dev B 가드레일에
부합한다.

### 작업 4 (보조, 선택) — 평가 출력 정합성

`english_level_hint_agent.py`의 평가 구성에서
`filled_slots=payload.understanding.extracted_slots`를 그대로 복사하므로,
유효하지 않은 값도 "채워진 슬롯"으로 리포트된다. 분기 버그는 작업 1~3으로
해결되지만, 다운스트림(Dev A 대사·리포트) 정합성을 위해 유효하지 않은 required
슬롯은 `filled_slots`에서 제외하고 `missing_slots`에 반영하도록 재도출하는 것을
권장한다.

우선순위: 분기 차단이 목적이면 작업 1~3만으로 충분하다. 작업 4는 리포트
품질용 선택 작업이며 별도 PR로 분리해도 된다.

## 5. 테스트 계획 (`test_developer_b_policy_engine.py`)

기존 헬퍼 `_policy_input` / `_node_context`를 재사용한다.

- `test_invalid_required_slot_value_does_not_advance`:
  `FLIGHT_A_001_SEATMATE_SMALLTALK` 노드 + `intent_success=True`,
  `extracted_slots={"polite_response": "short acknowledgement / hesitant start"}`,
  `missing_slots=[]` → `verdict != "SUCCESS"`, `branch_type == "clarify"`,
  `next_action == "REASK"` 검증 (회귀 버그 재현).
- `test_valid_slot_value_still_advances`:
  동일 노드 + `extracted_slots={"polite_response": "offered_help"}` →
  `SUCCESS`/`ADVANCE` 유지 (정상 케이스가 깨지지 않음 확인).
- `test_freeform_slot_without_allowed_values_skips_validation`:
  `allowed_slot_values`에 정의되지 않은 슬롯은 검증을 생략하여 기존대로
  통과하는지 확인.
- 회귀 가드: 기존 `test_chapter_zero_success_nodes_advance`,
  `test_flight_smalltalk_*` 등은 모두 유효한 슬롯 값을 사용하므로 그대로
  통과해야 한다.

## 6. 검증 명령

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py
uv run pytest
uv run ruff check .
uv run mypy .
```

## 7. 타 팀 의존 작업

본 수정은 2차 방어선이며 근본 원인(Understanding Agent의 오인식)은 Dev C
영역이다. 다음 변경 요청을 함께 전달한다.

- Dev C: Understanding Agent의 슬롯 값 정규화 / 매핑 실패 처리, 통합 어댑터의
  다음 질문 후보 필터링 점검.
- Dev A: Dialogue Agent의 화자 역할 혼동·환각 및 다음 질문 작문 누락 보강.

자세한 내용은 `docs/contracts/change_requests.md`(2026-06-16 항목)와
`docs/handoff.md`(2026-06-16 항목) 참조.
