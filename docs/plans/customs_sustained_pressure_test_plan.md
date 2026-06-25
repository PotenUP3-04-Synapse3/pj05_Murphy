# 작업계획서: 억까 세관 물품 "지속 압박" 다회차 테스트

## Context (배경)

[customs_pressure_fix_plan.md](customs_pressure_fix_plan.md)의 수정이 구현·검증 완료됨
(Part 1 배선 / Part 2 LLM 프롬프트 / Part 3 rule 게이트 + critical 일반화 모두 적용, end-to-end
배선 확인). 단일 턴 probe로 다음을 확인함:

- 고난이도(diff≥7) 불충분 답변 → 누출 0 (clarify 압박 / valuable·luxury는 critical)
- 저난이도(diff<7) → 통과 유지(과잉 압박 없음), 충분 답변 24/24 통과

**그러나 현재 probe는 단일 턴(retry_count=0, patience=100 고정)만 본다.** 검증되지 않은 것:
**연속으로 불충분하게 답하면 시스템이 압박을 유지하는가, 아니면 몇 번 뒤 그냥 통과시키는가?**

### 의도한 결과

억까 물품(diff≥7)에 대해 **연속 불충분 답변을 하는 한 어떤 턴에서도 success가 나오지 않는다**
(압박 → 힌트 → 실패 종료로 이어지되 결코 통과되지 않음). 단, 중간에 **충분한 답변을 하면
즉시 통과**되어 막다른 길이 아님을 함께 보장한다.

## 검증 시나리오 (사용자 요구 정리)

물품마다 다음 다회차 흐름을 시뮬레이션:

1. 턴1: 불충분 답변 A → **압박(clarify/retry/hint) 또는 critical, success 아님** 확인
2. 턴2: 불충분 답변 B(살짝 다름) → **여전히 success 아님** 확인
3. 턴3: 불충분 답변 C(살짝 다름) → **여전히 success 아님** 확인
4. … N턴까지(또는 종료 분기까지) 반복
5. **불변식**: insufficient가 계속되는 한 모든 턴에서 `branch_type != "success"`
6. **탈출 제어(positive)**: 중간 턴에 충분한 답변 → `branch_type == "success"` (압박이 막다른 길 아님)

각 턴 답변은 **모두 약간씩 다르게**, 억까 물품 **전체(24종)** 에 대해 진행.

## 구현

### 1. 다회차 하네스 (로그용, rule + llm)

[customs_pressure_probe.py](../../backend/tests/eval_harness/customs_pressure_probe.py)에
`run_multiturn(mode)` + 리포트 추가.

- **답변 풀(변형 ≥ 6종, 턴마다 순환)** — 의도적으로 generic·의심사유 미해소:
  ```
  "It's a gift for my friend."
  "It's just a personal item."
  "I bought it as a souvenir."
  "It's something I brought from home."
  "It's mine, nothing special."
  "I just have it for myself, honestly."
  ```
- **상태 threading**: 각 턴 `ScenarioStateMachine.decide()` 결과의 delta를 다음 턴
  `ScenarioState`에 적용:
  - `patience += patience_delta`, `retry_count += retry_count_delta`,
    `hint_count += hint_count_delta`, `suspicion += suspicion_delta`
  - `previous_fail_count += 0 if success else 1`
  - (라이브 상태 갱신 로직과 동일하게 맞춤 — 갱신 규칙이 다르면 그 출처를 따른다)
- **시작 상태**: 실게임에 가까운 patience(예: 30)로 설정해 escalation(clarify −5 / retry −8 /
  hint −10)이 몇 턴 내 hint→bad_end로 수렴하는지 관찰. 종료 분기(bad_end/critical) 도달 또는
  최대 N(예: 8)턴에서 중단.
- **턴별 기록**: item_id, difficulty, turn_index, answer, verdict, branch_type, next_action,
  patience/retry/hint 스냅샷.
- **물품별 판정**: 불충분 시퀀스 동안 success가 한 번이라도 나오면 "leak"(실패), 0이면 "held".

### 2. 결정적 단위 테스트 (CI 게이트, rule 모드)

[test_scenario_state_machine_loop_exit.py](../../backend/tests/dev_b/test_scenario_state_machine_loop_exit.py)
또는 신규 `test_customs_sustained_pressure.py`에:

- `test_high_difficulty_item_never_passes_on_consecutive_insufficient`:
  diff≥7 물품 전체에 대해 연속 불충분 답변 N턴 시뮬 → 매 턴 `branch_type != "success"` 단언.
  종료는 hint/bad_end/critical 중 하나로 끝남(통과 아님)을 단언.
- `test_low_difficulty_item_passes_generic`(대조군):
  diff<7 물품은 generic 첫 답변에 success(과잉 압박 없음) 단언.
- `test_sufficient_answer_escapes_pressure`(탈출 제어):
  몇 턴 압박 후 충분 답변(물품명 토큰 포함) → success 단언.
- valuable/luxury 미신고는 첫 턴 critical(bad_end)로 분리 단언.

### 3. llm 모드 (진단 로그만)

`run_multiturn("llm")`로 동일 흐름 1회 실행, 턴별 arc를 리포트. 비결정적이므로 CI 게이트화하지
않고 경향(고위험 물품이 연속 압박을 유지하는지) 관찰용으로만 사용.

## 측정·기대치

| 항목 | rule 기대 | llm 기대 |
|---|---|---|
| diff≥7 연속 불충분 → success 발생 | **0건** | 0~소수(경향) |
| 종료 분기 | hint→bad_end 또는 critical | 동일 경향 |
| diff<7 generic 첫 답변 | success | success |
| 충분 답변 탈출 | success | success(대체로) |

## 범위 밖 / 주의

- 이 작업은 **검증/테스트만**. 판정 로직·프롬프트·노드 데이터 변경 없음.
  (만약 다회차에서 누출이 발견되면 별도 수정 계획으로 분리)
- 상태 threading은 라이브 orchestrator의 상태 갱신과 일치시켜야 의미가 있음 — 갱신 규칙
  출처를 확인해 동일하게 적용.
- 저난이도 과잉 압박 금지 불변식(대조군)을 함께 둬서 과교정 회귀를 막는다.
```
실행:
.venv/Scripts/python.exe -m backend.tests.eval_harness.customs_pressure_probe --multiturn
.venv/Scripts/python.exe -m pytest backend/tests/dev_b/test_customs_sustained_pressure.py -q
```
