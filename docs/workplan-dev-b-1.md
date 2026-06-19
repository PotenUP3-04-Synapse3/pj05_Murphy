# 입국심사(CH0_03) 노드 재구성 계획

## Context
입국심사 챕터(`CH0_03_IMMIGRATION_CHECK`)를 핵심 질문 위주로 재편한다. 현재는 신고물품/가방 검사(IMM_006, IMM_006B, Gold 전용 IMM_ALPHA_GOLD_BAG_CONTENT_CHECK) 중심의 후반부가 있는데, 이를 제거하고 실제 미국 입국심사에서 자주 나오는 추가 질문(첫 방문/직업/현금/입국 거절 경험/장기체류 사유/호텔 예약·선택/여행 일정)을 넣는다. 일부 질문은 플레이어 **tier(Bronze/Silver/Gold)** 와 **답변 내용**에 따라 조건부로 활성화해 난이도를 적응시킨다.

확정된 설계 결정(사용자 답변):
- 레벨 기준 = `player_profile.tier`. **중간 이상 = Silver+Gold**, **상급 = Gold** (기존 Gold Bag route와 동일 메커니즘).
- 4개 신규 표준 질문 중 **첫 방문·직업은 항상**, **현금(→누가 비용 지불)·입국 거절 경험은 Silver+ 에서만** 활성화.
- 신규 노드도 기존과 동일하게 `_RETRY_`/`_CLARIFY_` 보조 노드 **풀세트** 생성.
- 부적절/위험 답변은 기존 `END_SECONDARY_INSPECTION` 으로 라우팅(별도 IMM_BAD_END 노드 생성 안 함).

## 핵심 아키텍처 (확인됨)
- 분기 데이터 소스: `backend/app/data/scenario_nodes.json` 의 각 노드 `branch_candidates` + `allowed_next_nodes`.
- 로더: `backend/app/services/service_c/openkb_service.py:26-66` `get_node_context()` 가 JSON → 평탄화된 `node_context`(`success_next_node` 등)로 변환.
- 분기 결정: `backend/app/services/service_b/scenario_state_machine.py` `decide()` → `_preferred_success_node()`. 조건부/레벨 라우팅은 **하드코딩**되어 있으며 현재 유일한 예시가 Gold route(`scenario_state_machine.py:13-14, 241-259`).
- 검증: `service_c/validator.py:42-46` 가 `next_node_id ∈ allowed_next_nodes ∩ client_allowed_next_nodes` 강제.

## 목표 흐름 (Bronze 기본 happy path)
`IMM_001_PASSPORT → IMM_002_PURPOSE → IMM_003_DURATION → IMM_004_STAY_LOCATION → IMM_005_RETURN_TICKET → IMM_008_FIRST_VISIT → IMM_009_OCCUPATION → IMM_007_FINAL_DECISION → IMM_999_CLEARED`

조건부 삽입(게이트 통과 시 끼어들고, 통과한 게이트 노드의 `success_next_node`가 본류로 복귀):
- `IMM_003_DURATION` —[체류 14일 이상]→ `IMM_003B_LONG_STAY_REASON` → `IMM_004_STAY_LOCATION`
- `IMM_004_STAY_LOCATION` —[Silver+]→ `IMM_004B_HOTEL_RESERVATION` —[Gold]→ `IMM_004C_WHY_THIS_HOTEL` → `IMM_005_RETURN_TICKET`
- `IMM_005_RETURN_TICKET` —[Silver+]→ `IMM_005B_TRAVEL_ITINERARY` → `IMM_008_FIRST_VISIT`
- `IMM_009_OCCUPATION` —[Silver+]→ `IMM_010_CASH` → `IMM_010B_WHO_PAID` → `IMM_011_DENIED_ENTRY` → `IMM_007_FINAL_DECISION`
  - (현금·누가지불·입국거절은 Silver+ 전용 체인. Bronze는 `IMM_009 → IMM_007` 로 직행)

## 작업 항목

### 1. `backend/app/data/scenario_nodes.json`
**삭제** (노드 + 모든 보조/clarify 변형):
- `IMM_ALPHA_GOLD_BAG_CONTENT_CHECK`, `IMM_ALPHA_GOLD_RETRY_BAG_CONTENT_CHECK`, `IMM_ALPHA_GOLD_CLARIFY_BAG_CONTENT_CHECK`
- `IMM_006_DECLARATION_CHECK`, `IMM_006_RETRY_DECLARATION`, `IMM_EXTRA_005_CLARIFY_DECLARATION`
- `IMM_006B_PACKED_BAG_CHECK`, `IMM_006B_RETRY_PACKED_BAG`, `IMM_EXTRA_006_CLARIFY_PACKED_BAG`

**재배선**: 기존 유지 노드의 `branch_candidates.success` / `allowed_next_nodes` 를 위 목표 흐름에 맞게 수정.
- `IMM_005_RETURN_TICKET` (및 retry/clarify): success 기본 `IMM_008_FIRST_VISIT`, allowed 에서 IMM_006/Gold 제거 후 `IMM_005B_TRAVEL_ITINERARY` 추가.
- `IMM_007_FINAL_DECISION` success는 그대로 `IMM_999_CLEARED`.

**신규 노드 추가** (각각 canonical + `_RETRY_` + `_CLARIFY_` 3종 세트, 기존 노드 스키마 형식 그대로: npc_question, npc_question_goal, objective_kr, required_intents/slots, critical_slots, allowed_slot_values, risk_keywords, recommended_expression, base_hint_kr, hint_policy, branch_candidates, allowed_next_nodes, node_type="dialogue"):
- `IMM_003B_LONG_STAY_REASON` — "Why are you staying for so long?" (장기 체류 사유) → success `IMM_004_STAY_LOCATION`
- `IMM_004B_HOTEL_RESERVATION` — "Can you show me your hotel reservation?" → success `IMM_005_RETURN_TICKET`, allowed 에 `IMM_004C_WHY_THIS_HOTEL` 포함
- `IMM_004C_WHY_THIS_HOTEL` — "Why did you choose this hotel?" → success `IMM_005_RETURN_TICKET`
- `IMM_005B_TRAVEL_ITINERARY` — "Can I see your travel itinerary?" → success `IMM_008_FIRST_VISIT`
- `IMM_008_FIRST_VISIT` — "Is this your first visit to the U.S.?" → success `IMM_009_OCCUPATION`
- `IMM_009_OCCUPATION` — "What do you do for a living?" → success `IMM_007_FINAL_DECISION`(기본), allowed 에 `IMM_010_CASH` 포함
- `IMM_010_CASH` — "How much cash are you carrying?" → success `IMM_010B_WHO_PAID`
- `IMM_010B_WHO_PAID` — "Who paid for this trip?" → success `IMM_011_DENIED_ENTRY`
- `IMM_011_DENIED_ENTRY` — "Have you ever been denied entry to the U.S.?" → success `IMM_007_FINAL_DECISION`

각 신규 노드의 `branch_candidates`: warning/bad_end = `END_SECONDARY_INSPECTION`(기존 패턴), retry/hint = 자기 RETRY 노드, clarify = 자기 CLARIFY 노드. 게이트 대상 노드(IMM_003B/004B/004C/005B/010)는 **소스 노드의 retry·clarify 변형의 allowed_next_nodes 에도 포함**시켜 재시도 성공 시에도 게이팅이 동작하도록 한다.
보조 노드 네이밍은 `<NODE>_RETRY_<X>` / `<NODE>_CLARIFY_<X>` 패턴 사용(기존 IMM_EXTRA_00N 혼란 회피).

### 2. `backend/app/services/service_b/scenario_state_machine.py`
- Gold 전용 상수/메서드 제거: `GOLD_CHALLENGE_SOURCE_NODE_ID`, `GOLD_BAG_CONTENT_CHALLENGE_NODE_ID`(13-14), `_should_route_gold_bag_content_challenge`(249-259).
- 일반화된 게이트 라우팅 도입. `_preferred_success_node`(241-247)를 다음으로 교체:
  ```python
  for route in GATED_ROUTES:
      if route.target in payload.node_context.allowed_next_nodes and route.condition(payload):
          return route.target
  return payload.node_context.success_next_node
  ```
- `GATED_ROUTES` 테이블(`@dataclass GatedRoute(target, condition)`), 평가 순서대로:
  1. `IMM_003B_LONG_STAY_REASON` — `_stay_duration_days(payload) >= 14`
  2. `IMM_004B_HOTEL_RESERVATION` — `tier in {"Silver","Gold"}`
  3. `IMM_004C_WHY_THIS_HOTEL` — `tier == "Gold"`
  4. `IMM_005B_TRAVEL_ITINERARY` — `tier in {"Silver","Gold"}`
  5. `IMM_010_CASH` — `tier in {"Silver","Gold"}`
  (입국거절·누가지불은 cash 체인에 연결되어 자동으로 Silver+ 전용이 되므로 별도 규칙 불필요.)
- `_stay_duration_days()` 헬퍼: `understanding.extracted_slots["stay_duration"]` 문자열에서 숫자(아라비아/영어 수사) + 단위(day/week/month) 파싱 → 일수 환산(weeks×7, months×30). 파싱 불가 시 0 반환(게이트 미발동). `_has_invalid_required_slot_value`(108-149)의 단위 매칭 로직과 일관되게 작성.

### 3. `backend/app/agents/agent_b/english_level_hint_agent.py`
- `_immigration_focus_target`(1417-1433): 삭제 노드(IMM_006/006B/GOLD) 항목 제거, 신규 노드 focus 타깃 추가(예: `IMM_003B_LONG_STAY_REASON: "long_stay_reason_statement"`, `IMM_010_CASH: "cash_amount_statement"` 등).
- `evaluate_turn` 내 IMM_006 동적 node_context 치환 블록(1117-1128)에서 **IMM_006 분기 제거**(BAG_006 분기는 유지). `{declared_item}` 의존 코드 정리.

### 4. 문서 `docs/contracts/developer_b_json_final_v1.md`
- 섹션 15 "Chapter 0 노드별 B 평가 기준 요약" 표에서 IMM_006/006B 행 제거, 신규 노드 행 추가, IMM_005 success-next 갱신.
- 섹션 13/14 예시의 IMM_006 node_results는 설명용이므로 신규 노드로 교체(선택적, 일관성 차원).

### 5. 테스트 갱신/추가
삭제 노드를 참조하는 기존 테스트 수정:
- `backend/tests/dev_b/test_developer_b_policy_engine.py`
- `backend/tests/dev_b/test_final_result_score_policy.py`
- `backend/tests/test_preprototype_flow.py`
- `backend/tests/test_understanding_agent.py`
- (필요 시) `backend/tests/test_developer_c_langgraph_orchestrator.py`, `test_unified_agent_run_log.py`, `dev_b/test_dev_b_bad_ending_branch.py`
신규 테스트: tier별 게이트 라우팅(Bronze 직행 / Silver itinerary·cash 체인 / Gold why-hotel) + 14일 이상 long-stay 라우팅 + `_stay_duration_days` 파싱 단위 테스트.

## 통합 주의 (Unreal 측)
게이트 라우팅은 백엔드 주도이므로, 검증 통과를 위해 **Unreal이 보내는 `client_allowed_next_nodes` 에 게이트 대상 노드가 포함**되어야 한다(validator.py:45-46). 본 작업은 JSON `allowed_next_nodes` 까지 처리하며, Unreal 클라이언트의 후보 목록 갱신은 별도 연동 필요(문서에 명시).

## 검증 방법
1. JSON 무결성: `python -c "import json; json.load(open('backend/app/data/scenario_nodes.json', encoding='utf-8'))"` + 모든 `branch_candidates`/`allowed_next_nodes` 참조 노드가 실재하는지 확인하는 임시 스크립트.
2. 단위/통합 테스트: `cd backend && python -m pytest tests/dev_b tests/test_preprototype_flow.py tests/test_understanding_agent.py -q`.
3. 라우팅 시나리오: Bronze→게이트 전부 skip, Silver→itinerary+cash 체인, Gold→why-hotel+cash 체인, 14일 답변→long-stay 가 의도대로 분기되는지 테스트로 확인.
