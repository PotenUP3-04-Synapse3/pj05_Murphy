# 판정 권한 재배치 작업계획서 — enum 게이트 → LLM 수용 판정

> 작성일: 2026-06-19
> 작성자: wd14177 (level_agent)
> 소스: enum 게이트 전수 조사 + 실제 플레이 transcript(CH0_03) 진단
> 관련: `docs/workplan-dialogue-naturalness.md`(표면 패치 항목들은 본 계획서 아래로 재편), 메모리 `dialogue-awkwardness-diagnosis`
> 영향: `agent_c`(이해), `service_b`(상태기계), `schemas/game_turn.py`, `service_c`(오케스트레이션)

---

## 0. 배경 — 진짜 문제

LLM 모드(`MURPHY_UNDERSTANDING_MODE=llm`)를 켜도 **턴 수용 판정의 척추는 rule 기반 "슬롯 채움 + 허용 enum 멤버십"** 이다. LLM은 슬롯 추출기로 격하되고, 그 출력이 앞뒤 두 rule 게이트에 의해 필터/덮어쓰기 된다.

- "carpenter"가 막힌 건 LLM이 못 알아들어서가 아니라, `occupation` enum 7종에 carpenter가 없어서다(게이트 B1/C1). 메시지만 "not clear"로 표시될 뿐 실제는 "not in enum".
- 그래서 **허용 리스트 확장은 무한 두더지잡기**다. enum 게이트 자체가 문제이지 항목 수가 문제가 아니다.

**전수 조사 결론(§1):** enum 멤버십 게이트는 SUCCESS/UNCLEAR 수용 판정에만 쓰이고, **안전(risk_tags)·수치(duration/cash 파싱)·그래프(전이/재시도/patience)와 완전히 분리**되어 있다. 따라서 개방형 슬롯에서 게이트를 제거해도 안전·그래프는 무손상이다.

**설계 원칙:** "rule vs agent" 이분법이 아니라 **권한 분리**.
- LLM/agent = **의미 판단**("이 발화가 현재 질문의 의도를 충족하나?")
- rule/상태기계 = **불변식**(합법 전이, 재시도·patience 한도, risk escalation, 수치 임계, 챕터 완료)

---

## 1. enum 게이트 전수 조사 결과

### 1.1 게이트가 박힌 지점
| ID | 위치 | 동작 |
|---|---|---|
| C1 | `understanding_agent._is_supported_extracted_slot_value` (L1097) | `slot_value not in allowed_values` → 하드 reject |
| C2 | `understanding_agent._apply_generic_slot_evidence` (L726-817) | enum 통과 evidence만 승격, `intent_success`/`missing_slots` 재계산 |
| C3 | `understanding_agent._match_alpha_allowed_slot_value` + `ALPHA_SLOT_VALUE_KEYWORDS` (L503-) | literal 키워드 매칭(rule 폴백) |
| B1 | `scenario_state_machine._has_invalid_required_slot_value` (L202-243) | `value not in candidates` → True |
| B2 | `scenario_state_machine._is_success`(L245) / `_is_unclear`(L268) | B1 + `missing_slots` 의존 |

### 1.2 enum과 무관한(=유지해야 할) 결정 경로
- **위험**: `_is_critical_risk`(L291) — `risk_delta`/`risk_total`/`risk_tags`만 사용.
- **수치**: `_stay_duration_days`(L32) — `stay_duration`을 숫자로 파싱(≥14일 → IMM_003B).
- **그래프/한도**: `allowed_next_nodes`, `MAX_HARD_FAIL_RETRIES`, patience, 챕터완료 node 집합.

### 1.3 슬롯 25개 분류
- **🟢 개방형(게이트 제거 → LLM 수용 판정) — 23개**
  - 자유서술: occupation, stay_location, visit_purpose, long_stay_reason, hotel_choice_reason, customs_item_explanation, payment_source, missing_bag_statement
  - 이진/상태: first_visit_status, return_ticket_status, denied_entry_status, passport_submission_status, hotel_reservation_status, itinerary_status, claim_tag_status
  - 확인/인사: immigration_transition_acknowledgement, customs_clearance_acknowledgement, customs_hold_acknowledgement, customs_hold_redirect_acknowledgement, chapter_transition_acknowledgement, polite_response, carousel_search_confirmation
- **🔴 수치(rule 파서 유지) — 2개**: stay_duration, cash_amount
- **⚪ 시스템 산출(사용자 발화 아님) — 1개**: final_recommendation(점수 정책이 산출, 변경 없음)
- **🟠 위험 신호**: 전 슬롯 공통으로 risk_tags/risk_delta는 enum과 독립 — 변경 없음.

---

## 2. 목표 아키텍처

### 2.1 슬롯 정책 레지스트리 (단일 진실원)
슬롯별 처리 방식을 코드에 흩지 말고 한 곳에 선언한다(예: `service_b/slot_policy.py` 또는 노드 데이터 필드).
```python
SLOT_POLICY: dict[str, Literal["open", "numeric", "system"]] = {
    "occupation": "open", "stay_location": "open", "visit_purpose": "open",
    ...  # §1.3의 23개 = open
    "stay_duration": "numeric", "cash_amount": "numeric",
    "final_recommendation": "system",
}
```
- `allowed_slot_values`는 enum **게이트가 아니라**, open 슬롯에서는 **LLM 프롬프트 힌트 + 리포트 분류 라벨**로 강등.

### 2.2 C(이해) — LLM 수용 판정을 1급 신호로
- `UnderstandingOutput`에 LLM이 직접 내는 **`intent_satisfied: bool`(+ `judgment_reason: str`)** 를 정착시킨다(개념상 이미 `intent_success`가 있으나, 현재는 후처리로 enum 기반 재계산됨 → open 슬롯에서는 LLM 원판정을 보존).
- **open 슬롯**: C1(`_is_supported_extracted_slot_value`)·C2의 enum 하드 reject 미적용. `extracted_slots`에 원문값(예: "carpenter", "my brother's home at 725 5th Ave")을 보존하고, 가능하면 best-effort 카테고리 라벨을 부가하되 게이트로 쓰지 않는다.
- **numeric 슬롯**: 기존 파서/검증 유지(stay_duration, cash_amount).
- **risk_tags 분류**: 변경 없음(안전 신호).

### 2.3 B(상태기계) — 슬롯 정책에 따라 분기
- `_is_success`/`_is_unclear`/`_has_invalid_required_slot_value`를 `SLOT_POLICY`로 분기:
  - open 슬롯: enum 검사 제거. 성공 = `intent_satisfied`(LLM) AND not risk AND 그래프 합법. UNCLEAR = LLM `needs_clarification`/낮은 confidence/`answer_relevance`로 판단.
  - numeric 슬롯: 기존 파서 기반 검증 유지.
- risk/critical, patience/retry, GATED_ROUTES, 챕터완료 — **불변**.

### 2.4 A(대화) — 직교 결함 동반 처리
- 질문 의미 보존(yes/no↔wh 변형 금지) + 거절 시 긍정 리액션 금지 — 본 재구조와 별개 트랙이나 같은 transcript 결함이므로 P3에 포함.

---

## 3. 단계별 작업 (P0~P3)

### P0 — 슬롯 정책 레지스트리 + 스키마 (기반)
- `slot_policy.py` 신설(§2.1). `UnderstandingOutput`에 `intent_satisfied`/`judgment_reason` 필드 정착(또는 기존 필드 의미 고정).
- 테스트: 레지스트리 완전성(모든 required 슬롯이 정책을 가짐), 스키마 직렬화.

### P1 — C 이해: open 슬롯 enum 게이트 제거
- C1/C2를 `SLOT_POLICY`로 분기. open 슬롯은 LLM 판정·원문값 보존, numeric/risk는 그대로.
- 테스트: "carpenter"→occupation 수용, "my brother's home at 725 5th Ave"→stay_location 수용, "work here"→risk_tags 유지(여전히 위험), stay_duration 파싱 회귀.

### P2 — B 상태기계: 수용 판정 분기
- `_is_success`/`_is_unclear`/`_has_invalid_required_slot_value`를 정책 분기. risk/수치/그래프 게이트 불변 확인.
- 테스트: open 슬롯 SUCCESS가 enum 무관하게 결정, $10k/≥14일 수치 분기 회귀, illegal_work_intent → critical 유지, retry/patience 한도 유지.

### P3 — A 대화 결함(직교)
- 질문 의미 유형 보존 가드, REASK 시 긍정 리액션 금지.
- 테스트: IMM_008에서 yes/no 질문이 wh로 변형되지 않음, REASK 응답이 "Good"으로 시작하지 않음.

---

## 4. 현재 transcript 문제 → 해결 매핑
| 문제 | 원인(게이트) | 해결 단계 |
|---|---|---|
| carpenter "not clear" 거절 → 오escalation | B1/C1 enum | P1·P2 (occupation open) |
| brother's home + 주소가 거절, 부실한 답이 통과 | C1/C2 + 어휘 | P1 (stay_location open, 어휘 의존 제거) |
| first-visit 모순답("last year") 통과 | C 키워드 에코 매칭 | P1 (LLM 판정으로 모순 포착) |
| 질문 의미 깨짐(yes/no→wh) | A LLM 패러프레이즈 | P3 |
| "Good" 무차별 | A 톤 미바인딩 | P3 |

---

## 5. 리스크 & 가드
- **위험 게이트 약화 금지**: risk_tags/critical 경로는 절대 손대지 않는다(전수 조사상 enum과 분리됨을 근거로). P2 테스트에 illegal_work_intent/overstay 회귀 필수.
- **수치 신뢰성**: stay_duration/cash는 LLM에 넘기지 않고 파서 유지.
- **비결정성**: LLM 수용 판정은 흔들릴 수 있으므로 `confidence` 임계·`needs_clarification`을 UNCLEAR 경로로 활용(이미 B `_is_unclear`가 소비). 결정적 회귀 테스트는 mock LLM으로 고정.
- **그래프 무결성**: 다음 노드는 항상 `allowed_next_nodes` 내. B는 전이 합법성만 강제.
- **영역 경계(AGENTS.md)**: C 변경은 C, B 변경은 B, 스키마는 C 소유. 분리 PR.

## 6. 수용 기준
- carpenter·brother's home·기타 질문 부합 자유답이 통과(테스트 보장).
- 허용 리스트 확장 없이도 미등록 직업/장소 통과.
- risk/수치/그래프/챕터 분기 전부 회귀 그린.
- 표면 패치(어휘 확장) 항목 폐기, 본 구조로 대체.
