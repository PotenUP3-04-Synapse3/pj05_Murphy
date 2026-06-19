# CH0_03 입국심사 노드 일람표 (AI + Unreal 공유용)

> 대상: `scenario_id = ALPHA_AIRPORT_ARRIVAL` / `chapter_id = CH0_03_IMMIGRATION_CHECK`
> 기준: `backend/app/data/scenario_nodes.json` (2026-06-19 재구성 반영)
> 변경 요약: 신고물품/가방 검사(IMM_006·006B·Gold 전용)를 제거하고, 실무형 입국심사
> 질문 9종을 추가. 일부 질문은 **플레이어 tier**와 **답변 내용**에 따라 조건부 활성화.

## 1. 메인 플로우 노드 (canonical)

| # | 노드 ID | NPC 질문 (EN) | 목표 (KR) | 활성화 조건 | 성공 시 다음 | retry / clarify 변형 | 타입 |
|---|---------|---------------|-----------|-------------|--------------|----------------------|------|
| 1 | `IMM_001_PASSPORT` | Passport, please. | 여권 제출하기 | 항상 | `IMM_002_PURPOSE` | `IMM_001_RETRY_PASSPORT` / `IMM_EXTRA_001_CLARIFY_PASSPORT` | dialogue |
| 2 | `IMM_002_PURPOSE` | What is the purpose of your visit? | 방문 목적 말하기 | 항상 | `IMM_003_DURATION` | `IMM_002_RETRY_PURPOSE` / `IMM_EXTRA_001_CLARIFY_PURPOSE` | dialogue |
| 3 | `IMM_003_DURATION` | How long will you be staying? | 체류 기간 말하기 | 항상 | `IMM_004_STAY_LOCATION` | `IMM_003_RETRY_DURATION` / `IMM_EXTRA_002_CLARIFY_DURATION` | dialogue |
| 3b | `IMM_003B_LONG_STAY_REASON` | Why are you staying for so long? | 장기 체류 사유 설명하기 | **체류 14일 이상** | `IMM_004_STAY_LOCATION` | `..._RETRY_REASON` / `..._CLARIFY_REASON` | dialogue |
| 4 | `IMM_004_STAY_LOCATION` | Where are you staying? | 숙소 위치 말하기 | 항상 | `IMM_005_RETURN_TICKET` | `IMM_004_RETRY_LOCATION` / `IMM_EXTRA_003_CLARIFY_LOCATION` | dialogue |
| 4b | `IMM_004B_HOTEL_RESERVATION` | Can you show me your hotel reservation? | 호텔 예약 제시하기 | **Silver+** | `IMM_005_RETURN_TICKET` | `..._RETRY_RESERVATION` / `..._CLARIFY_RESERVATION` | dialogue |
| 4c | `IMM_004C_WHY_THIS_HOTEL` | Why did you choose this hotel? | 호텔 선택 사유 설명하기 | **Gold** | `IMM_005_RETURN_TICKET` | `..._RETRY_HOTEL` / `..._CLARIFY_HOTEL` | dialogue |
| 5 | `IMM_005_RETURN_TICKET` | Do you have a return ticket? | 귀국 항공권 여부 말하기 | 항상 | `IMM_008_FIRST_VISIT` | `IMM_005_RETRY_RETURN_TICKET` / `IMM_EXTRA_004_CLARIFY_RETURN_TICKET` | dialogue |
| 5b | `IMM_005B_TRAVEL_ITINERARY` | Can I see your travel itinerary? | 여행 일정표 제시하기 | **Silver+** | `IMM_008_FIRST_VISIT` | `..._RETRY_ITINERARY` / `..._CLARIFY_ITINERARY` | dialogue |
| 6 | `IMM_008_FIRST_VISIT` | Is this your first visit to the U.S.? | 미국 첫 방문 여부 답변하기 | 항상 | `IMM_009_OCCUPATION` | `..._RETRY_VISIT` / `..._CLARIFY_VISIT` | dialogue |
| 7 | `IMM_009_OCCUPATION` | What do you do for a living? | 직업 말하기 | 항상 | `IMM_007_FINAL_DECISION` | `..._RETRY_OCCUPATION` / `..._CLARIFY_OCCUPATION` | dialogue |
| 8 | `IMM_010_CASH` | How much cash are you carrying? | 소지 현금 액수 말하기 | **Silver+** | `IMM_010B_WHO_PAID` | `..._RETRY_CASH` / `..._CLARIFY_CASH` | dialogue |
| 8b | `IMM_010B_WHO_PAID` | Who paid for this trip? | 여행 경비 지불 주체 말하기 | 현금 체인(자동) | `IMM_011_DENIED_ENTRY` | `..._RETRY_PAID` / `..._CLARIFY_PAID` | dialogue |
| 9 | `IMM_011_DENIED_ENTRY` | Have you ever been denied entry to the U.S.? | 입국 거절 이력 답변하기 | 현금 체인(자동) | `IMM_007_FINAL_DECISION` | `..._RETRY_ENTRY` / `..._CLARIFY_ENTRY` | dialogue |
| 10 | `IMM_007_FINAL_DECISION` | All right, you're cleared to enter. Enjoy your stay. | 통과 후 수하물 찾는 곳으로 이동 | 항상 | `IMM_999_CLEARED` | `IMM_007_RETRY_FINAL_DECISION` / `IMM_EXTRA_007_CLARIFY_FINAL_DECISION` | dialogue |
| 11 | `IMM_999_CLEARED` | (Chapter complete) | 수하물 챕터로 전환 | 항상 | `BAG_001_REPORT_MISSING_AT_DESK` | — | transition |

- 모든 dialogue 노드의 **warning / bad_end** 분기는 공통으로 `END_SECONDARY_INSPECTION`(2차 심사실 회부 엔딩)으로 라우팅된다. 별도 IMM_BAD_END 노드는 만들지 않음.
- 욕설/폭언(verbal abuse)은 기존 `IMM_BAD_END_VERBAL_ABUSE` 엔딩으로 별도 처리(이번 변경과 무관, 유지).
- `IMM_999_CLEARED`는 transition 노드 → `CH0_04_BAGGAGE_CLAIM` 진입.

## 2. tier / 답변 기반 게이팅 규칙

조건부 노드는 백엔드 상태머신(`scenario_state_machine.py`)의 `GATED_ROUTES` 테이블이 결정한다.
규칙: 게이트 대상이 현재 노드의 `allowed_next_nodes`에 있고 조건이 참이면 그 노드로 우회,
아니면 기본 `success_next_node`로 진행.

| 게이트 노드 | 조건 |
|-------------|------|
| `IMM_003B_LONG_STAY_REASON` | `stay_duration ≥ 14일` (자연어/숫자 파서로 환산: "two weeks"=14, "5 days"=5) |
| `IMM_004B_HOTEL_RESERVATION` | tier ∈ {Silver, Gold} |
| `IMM_004C_WHY_THIS_HOTEL` | tier == Gold |
| `IMM_005B_TRAVEL_ITINERARY` | tier ∈ {Silver, Gold} |
| `IMM_010_CASH` | tier ∈ {Silver, Gold} → 이후 `IMM_010B_WHO_PAID` → `IMM_011_DENIED_ENTRY` 자동 체인 |

### tier별 실제 진행 경로

- **Bronze (초급)** — 게이트 전부 skip, 핵심 질문만:
  `001 → 002 → 003 → 004 → 005 → 008 → 009 → 007 → 999`
- **Silver (중급)** — 호텔 예약 + 여행 일정 + 현금/지불/입국거절 체인 추가:
  `… 004 → 004B → 005 → 005B → 008 → 009 → 010 → 010B → 011 → 007 …`
- **Gold (상급)** — Silver 경로 + 호텔 선택 사유(`004C`) 추가:
  `… 004 → 004B → 004C → 005 → 005B → … → 010 → 010B → 011 → 007 …`
- **공통(tier 무관)** — `stay_duration ≥ 14일`로 답하면 `003 → 003B → 004` 삽입.

## 3. Unreal 팀 연동 주의 (중요)

게이팅은 **백엔드가 주도**한다(tier·답변 내용은 백엔드만 안다). 검증기
(`validator.py`)는 백엔드가 고른 `next_node_id`가 `allowed_next_nodes`와
**Unreal이 보낸 `client_allowed_next_nodes`** 양쪽에 모두 포함될 것을 요구한다.

→ **Unreal은 각 노드에서 게이트 대상 노드를 `client_allowed_next_nodes`에 포함해 보내야 한다.**
누락 시 백엔드가 게이트 노드로 보내려 해도 검증 실패. 노드별 후보 목록은 위 표의
"성공 시 다음" + 게이트 대상(예: `IMM_004_STAY_LOCATION`이면 `IMM_004B_HOTEL_RESERVATION`도 후보)을 참고.

## 4. 진행 업무 요약 (Developer B, 2026-06-19)

- `scenario_nodes.json`: IMM_006·006B·Gold 노드 + 보조 9개 제거, 신규 질문 9종 +
  각 retry/clarify 풀세트(총 27노드) 추가, 분기 재배선(참조 무결성 0 dangling).
- `scenario_state_machine.py`: 기존 Gold 하드코딩 라우팅을 선언형 `GATED_ROUTES`로
  일반화, `_stay_duration_days` 체류기간 파서 추가.
- `english_level_hint_agent.py`: focus-target 맵 갱신, 삭제된 IMM_006 동적 치환 로직 정리.
- 문서/테스트: 계약 문서(developer_b_json_final_v1.md §13–15) 갱신, 게이팅·파서 테스트 추가.
- 검증: 전체 pytest PASS, ruff/mypy PASS.

## 5. A / C 후속 업무 (handoff)

### Developer C (필수) — change_request `[CR-B-IMM-SLOTS]` 참조
- `agent_c/understanding_agent.py`의 `ALPHA_SLOT_VALUE_KEYWORDS`에 신규 슬롯 9종
  키워드 등록: `long_stay_reason`, `hotel_reservation_status`, `hotel_choice_reason`,
  `itinerary_status`, `first_visit_status`, `occupation`, `cash_amount`,
  `payment_source`, `denied_entry_status`.
  - 미등록 시 **룰 모드(LLM fallback/오프라인)** 에서 슬롯 추출 실패 → 신규 노드가
    SUCCESS 불가, retry 루프. (LLM 모드는 정상 동작 예상)
- LLM 모드 프롬프트가 신규 intent/slot을 인식하는지 회귀 확인.

### Developer A (참고)
- 신규 9개 노드 + 보조 노드에 대한 NPC 대사 생성 검토(현재 `npc_question`/recommended
  표현은 B 시드값). 입국심사관 톤·트집(suspicion) 연출은 A 범위.
- `IMM_004C`(호텔 선택 사유), `IMM_010B`(지불 주체), `IMM_011`(입국 거절 이력) 등
  압박형 질문의 톤 가이드 확인.

### 공통
- Unreal: §3의 `client_allowed_next_nodes` 게이트 대상 포함 반영.
