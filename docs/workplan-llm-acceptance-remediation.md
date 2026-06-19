# LLM 수용 판정 재구조 — 코드리뷰 보완 작업계획서

> 작성일: 2026-06-19
> 작성자: wd14177 (level_agent)
> 소스: `docs/workplan-llm-acceptance-restructure.md` 구현분에 대한 코드리뷰 findings
> 전제: **LLM 모드가 기본 모드**. rule-mode 폴백(원 리뷰 finding 3)은 고려하지 않음.
> 관련 메모리: `enum-gate-architecture`, `dialogue-awkwardness-diagnosis`
> 영향: `agent_c`(이해), `service_b`(상태기계), `schemas/slot_policy.py`, `integrations`(A 어댑터)

---

## 0. 요약

enum 게이트 → LLM 판정 재구조(restructure 계획서 P0~P2)는 구현·머지되어 전 테스트(368) 그린. 그러나 코드리뷰 결과 **재구조의 목표("LLM 판정을 신뢰")가 절반만 배선**된 것이 확인됨. 본 계획서는 그 보완을 4단계로 정리한다.

| Phase | finding | 핵심 | 성격 |
|---|---|---|---|
| 1 | 1+2 | open 슬롯 수용이 여전히 어휘 grounding/`intent_success`에 종속 → `intent_satisfied`를 진짜 1급 신호로 | 핵심(재구조 완성) |
| 2 | 5 | `cash_amount`가 "numeric"인데 numeric 파싱 부재 → `"closed"` 타입 신설, 재분류 | 잠복 갭 |
| 3 | 4 | 세관/장소 suspicion 차단이 `dialogue_seed` 경로 누락 → client에서 일원화 | 방어 일원화 |
| 4 | 6 | 함수 내부 import → top-level 정리 | 클린업 |

(원 리뷰 finding 3 = rule-mode 폴백 open 슬롯 enum 종속 → **본 계획서 범위 외**, LLM 기본 전제로 폐기.)

---

## 1. Phase 1 — `intent_satisfied`를 open 슬롯의 1급 신호로 (findings 1+2, 핵심)

### 1.1 문제
open 슬롯의 B 성공 조건이 `intent_satisfied AND intent_success AND not missing_slots`이고, `missing_slots`는 C의 evidence grounding(값/`evidence_text`가 player_text의 substring)에 의해 결정된다. 즉 **LLM의 holistic 판정이 슬롯 값의 어휘적 grounding에 종속**된다.

실패 시나리오: `"I build houses for a living"` → LLM `intent_satisfied=true`, `occupation="carpenter"`. 하지만 `"carpenter"`가 발화에 없고 `evidence_text` 약간 변형 시 grounding 실패 → evidence drop → `missing_slots=[occupation]` → REASK. **carpenter류 패러프레이즈가 다시 막힘** — 재구조가 없애려던 문제 클래스.

또한 후처리 override(understanding_agent L264)는 `intent_satisfied=False → intent_success=False` **단방향**뿐이라, True 판정이 룰이 깎은 슬롯을 되살리지 못함.

### 1.2 변경 — C ([understanding_agent.py](backend/app/agents/agent_c/understanding_agent.py))
- `_is_supported_slot_evidence` open 분기(L1078): confidence≥0.85/substring grounding 요구 제거. intent mismatch 가드(`_has_slot_intent_mismatch`)만 통과하면 LLM evidence를 그대로 수용(`return True`). → open 슬롯은 발화에 literal이 없어도 라벨로 보존되어 `missing_slots`에서 빠짐.
- 후처리 override(L264): open 슬롯에 한해 **양방향**으로 — `intent_success = intent_satisfied`. LLM이 맞다고 본 답을 룰이 깎지 못하게.
- evidence_text(원문 quote)는 계속 보존(리포트/환각 추적용, §5 참고).

### 1.3 변경 — B ([scenario_state_machine.py](backend/app/services/service_b/scenario_state_machine.py))
- `_is_success` open 분기(L257): 종속을 일으키는 `intent_success` 연언 제거. 다음으로 교체:
  ```
  intent_satisfied AND not missing_slots AND not _has_invalid_required_slot_value(payload) AND risk_delta <= 0
  ```
  - 혼합 노드(open+numeric)에서도 `missing_slots`/`_has_invalid`는 비-open 슬롯만 검사하므로 numeric 검증은 유지됨(`_has_invalid`는 이미 open bypass).

### 1.4 ⚠️ 결정 사항 — `risk_delta <= 0` 명시 유지
기존 `intent_success` 재계산에 `risk_delta<=0`이 포함되어, 비치명 저위험(risk_delta 1~19) open 답변이 REASK였다. `intent_success`를 떼면 이 가드가 사라지므로 open 분기에 `risk_delta <= 0`을 **명시 유지**해 저위험 답변이 조용히 ADVANCE되지 않게 한다. (치명 위험은 `decide()`의 `_is_critical_risk`가 success 이전에 처리 → 무손상.)

### 1.5 테스트
- 신규: mock LLM `intent_satisfied=true`, `occupation="carpenter"`, player_text=`"I build houses for a living"`(값이 발화에 없음) → 수정 후 SUCCESS.
- 회귀: `test_understanding_agent_rejects_open_slots_on_intent_mismatch`(intent_satisfied=false → fail) 그대로 통과.
- 회귀: 저위험(risk_delta=15) open 답변이 ADVANCE되지 않음(REASK 또는 suspicion 누적).

---

## 2. Phase 2 — slot_policy `"closed"` 타입 신설, `cash_amount` 재분류 (finding 5)

### 2.1 문제
`cash_amount`가 "numeric"으로 분류됐으나 실제 numeric 파싱은 `stay_duration`만 존재(`_has_invalid_required_slot_value`의 day/week/month 특수처리). cash는 사실상 enum 검증만 받음 → 라벨이 거짓이고, 잘못 제거 시 기본값 "open"으로 떨어져 금액 슬롯이 무검증될 위험.

### 2.2 변경
- [slot_policy.py](backend/app/schemas/slot_policy.py): `Literal`에 `"closed"` 추가. 레지스트리를
  `stay_duration → "numeric"`, `cash_amount → "closed"`, `final_recommendation → "system"`로. docstring에 "기본 open / closed=enum 게이트 / numeric=파서" 기준 명시.
- [scenario_state_machine.py](backend/app/services/service_b/scenario_state_machine.py) `_has_invalid_required_slot_value`: 정책 분기로 정리 — `open`→bypass(기존), `numeric`→일/주/월 파싱(기존 stay_duration 로직), `closed`→enum 멤버십(현재 default 동작), `system`→skip.

### 2.3 테스트
- `get_slot_policy("cash_amount")=="closed"`.
- cash enum 위반값 → invalid → REASK 유지.
- `test_stay_duration_strict_rule_validation`(numeric) 그대로 그린.

---

## 3. Phase 3 — suspicion 차단을 client에서 일원화 (finding 4)

### 3.1 문제
비-declaration 노드에서 `game_state`·top-level의 `random_customs_item`만 None 처리하고 `dialogue_seed.random_customs_item`은 안 비움([dev_a_npc_dialogue_client.py:134](backend/app/integrations/dev_a_npc_dialogue_client.py#L134)). `developer_a_input_service`는 `dialogue_seed` 경로도 fallback으로 읽으므로([:28](backend/app/services/service_a/developer_a_input_service.py#L28)) client 차단이 불완전. 현재는 프롬프트 jinja 게이트가 막아주나 이중 방어가 깨진 상태.

### 3.2 변경
[dev_a_npc_dialogue_client.py](backend/app/integrations/dev_a_npc_dialogue_client.py)에 헬퍼 하나로 모음 — 노드 `required_slots` 기준으로 A가 볼 suspicion 데이터를 결정하고 **세 경로(game_state / top-level / dialogue_seed)** 를 일관 정리:
- declaration scope인데 `customs_item_explanation`이 required가 아니면 → 세 경로의 `random_customs_item` 모두 제거.
- (대칭) location scope인데 `stay_location`/`visit_purpose`가 required가 아니면 → `assigned_visit_location` 등 정리(프롬프트 게이트와 이중 방어).

### 3.3 테스트
- 비-declaration 노드 + `dialogue_seed.random_customs_item` 세팅 → A-facing payload에 customs item 없음.
- declaration 노드에서는 정상적으로 전달됨(회귀).

---

## 4. Phase 4 — 함수 내부 import 정리 (finding 6, 클린업)

- [dev_a_npc_dialogue_client.py:116](backend/app/integrations/dev_a_npc_dialogue_client.py#L116): `public_node_context`를 top-level import로(같은 모듈에서 `OpenKBService`를 이미 top에서 import 중 → 동일 라인 확장).
- [developer_c_graph_tools.py:319](backend/app/tools/tool_c/developer_c_graph_tools.py#L319): top-level import로(순환참조 없음 확인 후).

---

## 5. 리스크 & 가드
- **환각 라벨**: Phase 1에서 open 슬롯의 ungrounded 값을 수용하면 LLM 환각 라벨이 extracted_slots에 남을 수 있다. 수용 판정엔 영향 없으나(intent mismatch·risk 가드 유지), 리포트/점수가 슬롯 값을 쓰면 `evidence_text`(원문 quote)를 함께 보존해 추적 가능하게 한다.
- **위험 게이트 불변**: `_is_critical_risk`/risk_tags 경로는 전 Phase에서 손대지 않는다. Phase 1 테스트에 risk 회귀 포함.
- **그래프 무결성**: 전이는 항상 `allowed_next_nodes` 내. B는 전이 합법성만 강제.
- **영역 경계(AGENTS.md)**: C 변경은 C, B 변경은 B, schema는 C 소유로 분리 PR.

## 6. 순서 & 수용 기준
- 순서: Phase 1 → 2 → 3 → 4. 각 Phase 후 `pytest backend/tests -q` 그린.
- 수용 기준:
  - `"I build houses for a living"` 류 패러프레이즈가 occupation으로 통과(Phase 1).
  - cash/duration 검증 회귀 그린, slot_policy 4종 타입 명시(Phase 2).
  - 비-declaration 노드에서 어느 경로로도 customs item이 A로 새지 않음(Phase 3).
  - 함수 내부 import 제거(Phase 4).
  - 전 스위트 그린 유지.
