# 작업계획서: Baggage Claim 챕터(CH0_04) 대화 테스트 전략

## Context (배경)

목표는 개별 버그 땜질이 아니라 **baggage claim 챕터 전체 대화 품질 개선**이다. 그런데 현재
테스트는 한 노드(BAG_006 세관 물품 압박)에만 과집중돼 있고 나머지는 얕다.

### 현 커버리지 실측

| 노드 | 판정 테스트 | NPC 대사(eval) |
|---|---|---|
| BAG_001 보고 | 일부 | baggage_brielle.yaml |
| BAG_002 클레임태그 | 일부 | — |
| **BAG_003 캐러셀** | **거의 없음**(과거 B-1 버그 지점) | — |
| BAG_004 리디렉트 | 거의 없음 | — |
| BAG_005 검사동의 | 일부(critical 미검증) | — |
| **BAG_006 물품설명** | **매우 깊음** | customs_dan.yaml |
| BAG_007 통관 | 일부 | — |
| **풀 플로우** | **없음**(immigration엔 `immigration_hale_full_flow.yaml` 존재) | — |

- `baggage_brielle.yaml`은 **단 2케이스(BAG_001만)** → NPC 대사 자연스러움 커버리지 사실상 공백.
- 앞선 진단에서 customs probe **metric 버그(저난이도 오집계)** 와 **LLM 저난이도 과잉압박**
  (cash_envelopes diff 5)도 발견 → 측정 신뢰성부터 회복 필요.

### 의도한 결과

7개 주요 노드 + 풀 플로우 + NPC 자연스러움 + 엣지 입력을 아우르는 **챕터 회귀 베이스라인**을
확보해, 한 곳을 고쳐도 다른 곳이 깨지지 않게 한다.

## 테스트 차원 (5축)

- **A. 노드별 판정 일관성** — 7개 전 노드에서 "불충분→압박 / 충분→통과 / 무효값→reask".
  특히 BAG_003(캐러셀) 회귀: "yes/정황 확인 통과, 모호 답변 압박".
- **B. 챕터 풀 플로우(다회차 end-to-end)** — *최대 공백*. 정상(BAG_001→…→`BAG_999_COMPLETE`),
  실패(지속 불충분→`END_BAGGAGE_REPORT_INCOMPLETE`), critical(미신고 고가품/밀수→bad_end),
  욕설(→`BAG_BAD_END_VERBAL_ABUSE`). 루프/오라우팅/조기통과·조기실패 검출.
- **C. NPC 대사 자연스러움(Dev A)** — 직전 답변 인지, 다음 질문 정확성, 되물음 무시/확정사실
  재질문 금지, 모순 문장 금지. `immigration_hale_full_flow.yaml`의 `must_not_include_any`
  패턴 차용.
- **D. 엣지 입력 robustness** — 되물음("왜 또 물어요?"), off-topic, 거부, 초단답,
  needs_repeat("다시요?") — 노드 횡단.
- **E. 측정 신뢰성 + 모드 일관성** — probe metric 버그 수정, rule vs llm 일치, CI(결정적) vs
  harness(진단) 역할 분리.

## 단계별 실행 (권장 순서 E → B → A → C → D)

### Phase 1 — E: 측정 신뢰성 회복 (선행, 차단요소)
- [customs_pressure_probe.py](../../backend/tests/eval_harness/customs_pressure_probe.py)
  `report_multiturn`의 `passed_low` 집계를 `helds` 리스트가 아니라 `held` 속성 기준으로 수정
  (저난이도가 압박당해 success 못 받으면 "passed"로 세지 않도록).
- LLM 전수 1회 재실행으로 **저난이도 과잉압박 건수 정량화**(cash_envelopes 외 몇 건인지).
- 산출: 신뢰 가능한 누출/압박 지표.

### Phase 2 — B: 챕터 풀 플로우 골격
- 신규 `backend/tests/dev_b/test_baggage_chapter_flow.py`(결정적, 합성 understanding으로
  상태머신 라우팅 검증) + 신규 eval 시나리오
  `backend/tests/eval_harness/scenarios/baggage_brielle_full_flow.yaml`(NPC 대사 모순/일관성).
- 경로: 정상 통관 / 지속 불충분 실패 / critical / 욕설 4종. 각 전이가
  `scenario_nodes.json`의 `branch_candidates`와 일치하는지, 루프/조기종료 없는지 단언.

### Phase 3 — A: 노드 판정 일반화
- BAG_006 probe를 **노드 파라미터화**하여 7개 노드 공통 판정 probe로 일반화(불충분/충분/무효값
  답변 세트를 노드별 정의).
- 결정적 단위 테스트로 BAG_003 캐러셀 회귀(정황 확인 통과 / 모호 압박) 포함.

### Phase 4 — C, D: 자연스러움 + 엣지
- `baggage_brielle.yaml` 케이스를 노드별로 확충(현재 2 → 노드×주요분기). 되물음·확정사실
  재질문·모순 금지 어서션.
- 엣지 입력 세트를 A의 probe와 B의 플로우에 주입.

## 측정·게이트 정책

- **CI 게이트(결정적)**: 상태머신/라우팅(합성 understanding) + rule 모드 판정. 항상 통과 요구.
- **진단 하네스(비결정)**: LLM 모드 probe/flow는 로그·경향 관찰용. CI 게이트화하지 않음.
- 핵심 불변식: 고난이도 불충분 연속 → never success / 저난이도 generic → 과잉압박 없음 /
  충분답변 → 탈출 가능 / 미신고 고가품 → critical.

## 범위 / 주의

- 본 계획은 **테스트 전략·인프라** 수립. 판정 로직·프롬프트·노드 데이터의 추가 *수정*은
  테스트로 결함이 드러나면 별도 수정 계획으로 분리(과교정 회귀 방지).
- Phase 1(E)이 선행되지 않으면 이후 측정이 오염되므로 **E를 먼저** 끝낸다.
- 기존 BAG_006 자산(probe, test_customs_sustained_pressure)은 재사용·일반화하고 폐기하지 않음.

## 참고 파일
- 패턴 차용: [immigration_hale_full_flow.yaml](../../backend/tests/eval_harness/scenarios/immigration_hale_full_flow.yaml)
- 일반화 대상: [customs_pressure_probe.py](../../backend/tests/eval_harness/customs_pressure_probe.py),
  [test_customs_sustained_pressure.py](../../backend/tests/dev_b/test_customs_sustained_pressure.py)
- 노드 계약: [scenario_nodes.json](../../backend/app/data/scenario_nodes.json) (CH0_04)
- 상태머신: [scenario_state_machine.py](../../backend/app/services/service_b/scenario_state_machine.py)
