# Change Requests

Cross-owner change requests are listed below. Status lines describe the current
repository state as of the latest handoff entry.

## Change Request - 2026-06-19 - [CR-B-AB-DESYNC] 입국심사 비-ADVANCE 분기 준수 가드 (대화 일관성 확보)

Status: Resolved (Developer A 및 Developer C 구현 완료 - 2026-06-19).

### Requested By

Developer B

### Affected Owner

- **Developer A / kimyonghee — 구현 주체** (`npc_dialogue_agent.py` 가드 추가).
- Developer C / Sean Han — **신규 작업 없음**. 아래 §C 전달 경로(이미 충족) 확인 + 회귀 테스트만.

### Reason (재현 로그)

실제 플레이 로그에서 같은 턴에 A 대사와 B 분기가 어긋났다:

```
You: maybe 13days
Officer Hale: "Thirteen days. Good. Next, tell me where you will stay."  ← A: 숙소(다음 질문)로 진행
log:  IMM_003_DURATION -> IMM_EXTRA_002_CLARIFY_DURATION | REASK | UNCLEAR ← B: 체류기간 재질문(비-ADVANCE)
You: 133, kings street, manhatten...   ← 플레이어는 A가 말한 '숙소'에 답함
log:  IMM_003_DURATION -> ... | UNCLEAR ← B는 여전히 '체류기간'을 채점 → 계속 실패
... → 결국 END_SECONDARY_INSPECTION (강제 탈락)
```

B가 `next_action != "ADVANCE"`(재질문/힌트/경고)를 반환하면 플레이어는 **직전 질문**에 다시 답해야 한다. 그러나 A의 LLM 대사 생성기가 임의로 **다음 노드 질문**으로 진행하면, 플레이어 발화와 B가 채점하는 슬롯이 영구히 어긋나 무한 retry·조기 탈락이 발생한다. 이는 치명적 UX 결함이다.

### 정확한 코드 갭 (구현 위치 특정)

A가 받는 정규화 페이로드에는 가드에 필요한 신호가 **이미 모두 존재**한다
(`backend/app/services/service_a/developer_a_input_service.py`,
`normalize_level_design_payload`):

| 신호 | normalized 키 | 라인 | 값 예시 |
| --- | --- | --- | --- |
| 다음 행동 | `next_action` | :110 | `ADVANCE` / `REASK` / `GIVE_HINT` / `WARNING` / `FAIL_END` |
| 분기 타입 | `branch_type` | :82 | `success` / `retry` / `clarify` / `hint` / `warning` |
| 대사 목적 | `dialogue_purpose` | :84 | `continue_to_next_question` / `support_retry` / `warn_and_control_risk` |
| 질문 목표 | `dialogue_seed.surface_goal` | :88 | 비-ADVANCE 시 **현재 노드 질문의 goal**(예: `ask_stay_duration`) |

문제는 **A의 두 생성 경로 중 LLM 경로에만 가드가 없다**:

- **fallback(룰베이스) 경로** `node_generate_dialogue`(`npc_dialogue_agent.py:235-266`):
  retry/clarify일 때 `get_retry_variation(...)`(:240-250)와
  `synthesize_fallback_next_question(original, surface_goal)`(:260-266)로
  현재 질문을 재질문하도록 이미 처리됨. → 정상.
- **LLM 경로** `node_generate_dialogue_llm`(`npc_dialogue_agent.py:305-432`):
  생성된 `npc_text`(:436~)는 profanity/safe-english/recommended-echo/
  `missing_followup_question`(:470-477) 검사만 거친다. **질문이 "있는지"만 보고
  "올바른 질문인지"는 검사하지 않는다.** 그리고 coherence guard(:479-501)는
  `purpose == "smalltalk_diagnostic"` **전용**이라 입국심사/세관에는 적용되지 않는다.
  → 여기서 desync가 발생한다. **이 경로에 가드를 추가하는 것이 본 CR의 핵심.**

### Proposed Contract Change (Developer A)

**A1. 비-ADVANCE 분기 준수 가드 (`node_generate_dialogue_llm`, 핵심)**

생성된 `npc_text` 후처리 단계(:462~501 부근, smalltalk 가드와 동일 위치)에 다음을 추가:

```
is_non_advance = (next_action in {"REASK", "GIVE_HINT", "WARNING"})
                 # 또는 dialogue_purpose in {"support_retry", "warn_and_control_risk"}
if is_non_advance and purpose != "smalltalk_diagnostic":
    # 현재 노드 질문(surface_goal)을 재질문해야 하며 다음 질문/화제 전환 금지.
    # 위반 시 결정형 재질문으로 override (LLM 자유 텍스트 폐기):
    npc_text = synthesize_fallback_next_question(reaction_part, surface_goal)
    # 또는 직전 NPC 발화 변주가 필요하면 get_retry_variation(surface_goal, last_npc_text, npc_text)
```

- **권장: 결정형 override**(판정 단순·안전). 비-ADVANCE에서는 `surface_goal`이 곧
  현재 노드의 질문이므로, LLM의 질문 선택을 신뢰하지 말고 `surface_goal` 기반
  재질문으로 강제 교체한다. 반응(reaction) 문장은 유지하되 "다음 질문"은 금지.
- 대안(LLM self-tag): smalltalk coherence guard(:479-501)가 쓰는
  `llm_reason` 태그 방식을 확장해, 비-ADVANCE인데 다음 질문을 도입하면
  reject 후 fallback으로 조향.

**A2. coherence guard 일반화**

현재 `purpose == "smalltalk_diagnostic"`로 한정된 후처리 가드(:479-501)를
입국심사/세관(비-ADVANCE) 턴에도 적용되도록 일반화한다.

**재사용 가능한 기존 유틸 (신규 구현 불필요)**
- `synthesize_fallback_next_question(original_text, surface_goal)` — `npc_dialogue_agent.py`(:262에서 이미 사용).
- `get_retry_variation(surface_goal, last_npc_text, current_text)` — `backend/app/services/service_a/dialogue_policy_service.py`.
- smalltalk coherence guard 패턴 — `npc_dialogue_agent.py:479-501`.

### 수용 기준 (Acceptance Criteria)

1. `next_action != "ADVANCE"`인 모든 입국심사/세관 턴에서, 생성된 NPC 대사는
   **현재 노드의 질문(surface_goal)만** 재질문하고 **다음 노드 질문/화제 전환을
   포함하지 않는다.**
2. 위 재현 로그 입력(체류기간 노드에서 clarify 분기)에 대해, NPC가
   "tell me where you will stay"(숙소)로 진행하지 **않고** 체류기간 재질문을 한다.
3. `next_action == "ADVANCE"`(success/final) 턴의 기존 동작은 회귀 없이 유지.
4. smalltalk_diagnostic 경로의 기존 coherence/ topic_switch 동작은 변화 없음.

### §C — Developer C 확인 항목 (신규 작업 없음)

- A가 가드에 쓰는 `branch.next_action`, `dialogue_directive.purpose`,
  `dialogue_seed.surface_goal`은 C→A 어댑터(`dev_a_npc_dialogue_client.py`)와
  정규화기(`developer_a_input_service.py`)에서 **이미 전달됨**. 신규 필드/스키마 불필요.
- C는 위 3개 필드가 비-ADVANCE 분기에서 누락 없이 A에 도달하는지 회귀 테스트로
  보장만 하면 된다(예: `test_preprototype_flow.py`).

Developer C follow-up, 2026-06-19:
- Added a C-owned regression in `test_preprototype_flow.py` proving
  `branch.next_action`, `dialogue_directive.purpose`, and
  `dialogue_seed.surface_goal` reach the A-facing payload on a non-ADVANCE
  immigration branch.
- No new fields were added for this CR; Developer A still owns the dialogue
  behavior guard.

### 테스트 가이드 (Developer A)

- `backend/tests/test_developer_a_npc_dialogue.py`에 회귀 추가:
  입력 = `branch_type="clarify"`, `next_action="REASK"`,
  `dialogue_purpose="support_retry"`, `dialogue_seed.surface_goal="ask_stay_duration"`,
  `player_text`는 숙소/주소 발화. → 단언: 생성 NPC 대사가 숙소 질문(`where ... stay`)을
  포함하지 않고 체류기간 재질문 의도를 유지.

### Compatibility Impact

- A 내부 후처리 가드 + 기존 룰베이스 폴백 재사용. 공유 스키마
  (`DialogueDirective`, `DialogueSeed`) 변경 없음 → 하위 호환.
- 회귀 가드: `test_developer_a_npc_dialogue.py`, `test_preprototype_flow.py`.

### 범위 밖 (Deferred, 본 CR 제외)

- 1차 트리거인 **false-UNCLEAR**("maybe 13days"를 B/Understanding이 UNCLEAR로 오인)는
  본 CR 범위 밖이며 추후 Understanding/`_is_unclear` 보정 별건으로 처리한다.
- **주의**: A 가드만 적용하면 "엉뚱한 질문에 답하다 탈락"은 막지만, false-UNCLEAR가
  남아 있으면 NPC가 체류기간을 올바르게 재질문해도 B가 정답을 계속 UNCLEAR로 볼 수
  있다. 완전 해소는 A 가드 + Understanding 보정이 함께 필요.

### Temporary Workaround

Developer B는 UNCLEAR 시 hard-fail 카운터 증가를 배제하고 한도를 5로 상향
(`[CR retry 완화]`, 구현 완료)하여 조기 강제 종료 민감도만 완화함. desync로 인한
발화-슬롯 불일치 근본 문제는 A 가드 적용 전까지 잔존한다.

### Developer A & C Resolution - 2026-06-19

- **Developer A**: `npc_dialogue_agent.py` 내 `node_generate_dialogue_llm`에 `[5.3단계] 비-ADVANCE 분기 준수 가드`를 구현했습니다. `next_action`이 비-ADVANCE 분기(`REASK`, `GIVE_HINT`, `WARNING`)이거나 `dialogue_purpose`가 `support_retry`, `warn_and_control_risk`인 경우, 생성된 대사의 질문부를 원래 노드의 질문(`surface_goal`)으로 강제 재합성하고 `get_retry_variation`을 통해 직전 턴 NPC의 대사와 겹치지 않도록 변주 가드를 탑재하였습니다.
- **Developer C**: C측 어댑터 및 입력 정규화 단계에서 `next_action`, `dialogue_purpose`, `dialogue_seed.surface_goal`이 누락 없이 A-facing payload로 온전히 조립·전달됨을 검증 완료하고, `test_preprototype_flow.py` 및 신규 회귀 테스트 `test_desync_guard_overrides_llm_next_node_question`을 통해 비-ADVANCE 분기 시 강제 재질문 동작이 기대치대로 작동함을 단언했습니다.

## Change Request - 2026-06-19 - [CR-B-HISTORY-MEMORY] 대화 기억 및 입국신고서 컨텍스트

Status: Resolved for Developer C runtime wiring (2026-06-19). Unreal still needs to populate optional `GameState.arrival_form` from the UI when available.

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han (일부 Unreal 연동 필요)

### Reason

메인 시나리오(flight·immigration) 대화 기억이 "잘 동작하지 않는다"는 지적의 원인을
추적한 결과 3가지 구조 문제를 확인했다. (history 인프라는 계약상 C 영역이며,
`[CR-B-CONV-C]`와 동일 경계.)

1. **NPC 발화가 history에 누락됨 (주원인).**
   - history가 읽는 유일한 소스는 B가 쓰는
     `backend/runtime/openkb/dev_b/{session}.jsonl`이며, reader는
     `final_result_score_policy.py:59` `OpenKBFinalResultRecordReader.read_session_records`.
   - 그러나 B 레코드(`openkb_feedback_writer.py:105-135` `_build_record`)에는
     `node_id`/`player_text`/`understanding`만 있고 **npc 텍스트 필드가 없음**
     (파이프라인상 B는 A보다 먼저 실행되어 당 턴 NPC 대사를 모름).
   - history 빌더 `_history_npc_text`(`developer_c_graph_tools.py:904-919`)가
     `record["npc"][...]`/`record["npc_text"]`를 찾지만 부재 →
     **`npc_text_preview`가 항상 공백** → A가 받는 history는 플레이어 발화만 있고
     NPC가 직전에 뭘 물었는지가 비어, NPC가 자기 질문을 반복.

2. **단기기억 window(5턴)가 시나리오 길이에 비해 너무 작음.**
   - `_sync_dialogue_history_to_dialogue_seed`(`developer_c_graph_tools.py:846`,
     `max_entries=5`).
   - Alpha 1회는 flight ~5 + immigration 코어7(+게이트 최대~6) + baggage 7 ≈
     클린 진행만 ~24턴, retry 포함 30턴+. 5턴은 한 챕터도 못 덮어 초반 발화가 유실.

3. **입국신고서(arrival form) 사실 데이터 미전송.**
   - `GameState`(`game_turn.py:127-138`)는 `assigned_visit_location`(장소)만 운반하고,
     주석대로 입국신고서는 "Unreal UI가 표시할 장소 정보"에 한정됨.
   - 신고서에 작성되는 이름/주소/방문목적/체류기간/신고품 등 실제 작성 내용이
     백엔드 요청에 전혀 들어오지 않음 → NPC가 신고서 내용을 알 수 없고,
     말한 답변과 신고서 내용의 교차검증도 불가.

참고: 임의 사실마다 노드 슬롯을 만드는 방식은 확장 불가하므로 비채택.
"NPC가 안정적으로 알아야 할 사실"은 대화 히스토리가 아니라 입국신고서를 정식
출처로 삼는다(이름 망각 증상은 history 동작 확인용 프로브였을 뿐, nickname 의존
방식은 채택하지 않음).

### Proposed Contract Change

- **C1. NPC 발화 영속.** A가 생성한 최종 `npc.text`를 history가 읽는 세션 스토어에
  기록(턴 종료 시 C가 기록, 또는 history 엔트리 빌드 시 C-side 턴 로그의 npc text를
  조인)해 `_history_npc_text`가 실제 값을 읽도록 한다. `last_npc_message`로 대체 시
  한 턴 어긋남에 주의.
- **C2. window 상향.** `max_entries`를 한 챕터를 덮는 수준(권장 10~15턴)으로 상향한다.
  history는 대화 코히런스(반복 회피·직전 반응) 전용으로 두고, 사실 기억은 C3로 분리.
- **C3. 입국신고서 컨텍스트 전송 (핵심).** Unreal이 신고서 작성 내용을 구조화 객체로
  전송하고(예: `GameState.arrival_form { full_name, address, purpose, stay_length,
  declared_items, ... }`), C가 매 턴 game_state로 유지하며 A(및 필요시
  B/Understanding)에 전달한다. 이를 통해 슬롯·history window 의존 없이 NPC가 사실을
  항상 참조하고, 말한 답변과 신고서 내용을 대조할 수 있다.

### Compatibility Impact

- C1은 additive(추가 기록)로 기존 분기/검증에 영향 없음.
- C3는 신규 optional 필드(`GameState.arrival_form`)라 하위호환(Unreal 미전송 시
  `None`).
- C2의 window 상향은 A 프롬프트 토큰을 증가시키므로 비용/지연 검토 필요(긴 세션은
  요약형 영속 메모리가 더 유리하나, 본 CR은 우선 window 상향 + 신고서 전송으로 한정).
- 슬롯 스키마/노드 정의 변경 없음. 회귀 가드: `test_developer_a_npc_dialogue.py`,
  단기기억/이해 관련 테스트.

### Developer C Resolution - 2026-06-19

- Added C-owned `DialogueHistoryService` under
  `backend/runtime/openkb/dev_c/dialogue_history` so final Developer A
  `npc.text` is persisted after a turn and joined back into the next
  `dialogue_seed.dialogue_history` without mutating B-owned OpenKB records.
- Raised the short-term dialogue history window from 5 to 12 entries.
- Added optional `GameState.arrival_form` with `full_name`, `address`,
  `purpose`, `stay_duration`/`stay_length`, and `declared_items`; C preserves
  it in the Unreal response and forwards `game_state` to the A-facing payload.
- Added C-owned regression coverage for NPC text history, 12-entry history
  windows, arrival-form forwarding, and the `[CR-B-AB-DESYNC]` signal path.

## Change Request - 2026-06-19 - [CR-B-IMM-SLOTS] 입국심사 신규 노드 슬롯 이해 인식

Status: Resolved (Developer C implementation complete - 2026-06-19).

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B는 `docs/workplan-dev-b-1.md` 계획에 따라 입국심사 챕터
(`CH0_03_IMMIGRATION_CHECK`)를 핵심 질문 중심으로 재구성하면서 신규 노드 9종
(+ 각 retry/clarify, 총 27노드)과 tier/체류기간 기반 `GATED_ROUTES` 라우팅을
구현했다. 그러나 신규 노드들이 요구하는 `required_slots`가 Developer C 소유의
`agent_c/understanding_agent.py` 룰모드 추출 테이블(`ALPHA_SLOT_VALUE_KEYWORDS`,
50-134줄)에 등록돼 있지 않다.

영향:
- **LLM 모드**: node_context 기반으로 LLM이 슬롯을 추출하므로 정상 동작 예상.
- **룰 모드(LLM fallback·오프라인·일부 테스트 경로)**: 신규 슬롯이 미등록이라
  추출 실패 → `missing_slots` 고정 → 해당 노드가 영원히 SUCCESS에 도달하지 못하고
  retry/clarify 루프에 갇힌다. (B의 상태머신/노드 무결성은 이미 닫혀 있으나,
  슬롯 인식은 C 경계다. CR-B-CONV-C 항목 #4에서 `item_purpose`를 동일 테이블에
  추가했던 것과 같은 성격.)

참고: B의 신규 라우팅/파서 단위 테스트는 `extracted_slots`를 직접 주입해
상태머신을 검증하므로 이 갭을 잡지 못한다(설계상 이해 에이전트를 우회).

### Proposed Contract Change

`agent_c/understanding_agent.py`의 `ALPHA_SLOT_VALUE_KEYWORDS`에 아래 신규 슬롯의
키워드 패밀리를 추가(허용값은 `scenario_nodes.json`의 각 노드
`allowed_slot_values`와 정합해야 함). 예시 매핑(키워드는 C가 조정 가능):

- `long_stay_reason` — tourism/study/family_visit/remote_work/long_vacation
- `hotel_reservation_status` — has_reservation/has_digital_confirmation/has_address
- `hotel_choice_reason` — location/price/reviews/recommended/near_tourist_spots
- `itinerary_status` — has_itinerary/has_plans/has_list
- `first_visit_status` — yes_first_time/no_visited_before
- `occupation` — student/office_worker/engineer/designer/teacher/business_owner/unemployed
- `cash_amount` — under_10k/over_10k/zero/specific_amount
- `payment_source` — myself/parents/company/sponsor/family
- `denied_entry_status` — never_denied/has_denial_history

추가로 LLM 모드 프롬프트가 위 신규 `required_intents`
(`confirm_first_visit`, `state_occupation`, `state_cash_amount`,
`state_trip_payment_source`, `confirm_denied_entry_history`,
`explain_long_stay_reason`, `confirm_hotel_reservation`,
`explain_hotel_choice_reason`, `confirm_travel_itinerary`)와 슬롯을 정상 인식하는지
회귀 확인 권장.

### Developer C Resolution

- Added rule-mode keyword coverage for all 9 new immigration slots in
  `backend/app/agents/agent_c/understanding_agent.py`.
- Switched the strict Understanding LLM contract to slot-evidence-first. The
  LLM no longer returns `extracted_slots`; Developer C derives final slots from
  accepted `slot_evidence` and the current node metadata.
- Retained current-node filtering in `UnderstandingAgent`, so unrelated slot
  evidence still cannot leak into Developer B policy input.
- Added regression tests for rule-mode extraction, LLM evidence normalization,
  and ignoring direct LLM-provided `extracted_slots`.

### Compatibility Impact

키워드 테이블 추가는 additive이며 기존 통과 케이스에 영향이 없어야 한다(회귀
가드: `test_understanding_agent.py`). 미반영 시에도 LLM 모드 정상 동작은
유지되나, 룰 모드/오프라인 경로에서 신규 노드 진행이 막힌다.

## Change Request - 2026-06-18 - [CR-B-CONV-C] 단기기억·이해·트집 스코프 (대화 복구)

Status: Resolved (Developer C implementation complete - 2026-06-18).

Developer C follow-up:
- Added `TurnHistoryEntry` and `DialogueSeed.dialogue_history` as the C-owned short-term-memory payload for Developer A.
- Developer C now reads recent B OpenKB session records, excludes the current turn, compresses the previous turns to previews + filled slots, and forwards them to A on every node with a `dialogue_seed`.
- Understanding now recognizes `item_purpose` keyword families and free-form street-address answers as `stay_location=address`, including LLM-mode deterministic repair when the LLM leaves the required slot missing.
- `_sync_challenge_context_to_dialogue_seed` now respects `dialogue_seed.suspicion_scope`: `location` sends only location context, `declaration` sends only item/declaration context, and `none` clears challenge metadata before A sees it.

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

입국심사~세관 대화가 무너진다(같은 질문 무한 반복, 말하지 않은 정보 호출,
갑작스런 신고품). 근본원인 중 C 소유분은 (1) 메인 시나리오에 단기기억이
연결돼 있지 않음(`npc_dialogue_agent` 히스토리는 smalltalk 전용), (2) 이해
에이전트가 `item_purpose`/주소를 못 채워 needs_clarification가 고정됨,
(3) 트집 컨텍스트가 노드 무관하게 dialogue_seed로 sync됨. B는 상태머신 무한
루프와 노드 무결성을 단독으로 닫지만(`docs/workplan-dev-b.md` §4), 위 3건은
C 경계다.

### Proposed Contract Change

- **Dev C (스키마/조립/영속화):**
  1. `game_turn.py`에 대화 히스토리 표현 추가 — `PreviousNodeResult` 확장 또는
     신규 `TurnHistoryEntry { node_id, player_text_preview, npc_text_preview,
     filled_slots }`. (full raw text 대신 preview, 기존 로깅 정책 준수)
  2. 직전 N턴(권장 3~5)을 조립해 `dialogue_seed`(또는 game_state)에
     `dialogue_history`로 실어 A에 전달. 모든 노드에서.
  3. game_state 라운드트립/OpenKB 세션 레코드로 턴 간 영속화.
- **Dev C (이해 에이전트, agent_c/understanding_agent.py):**
  4. `ALPHA_SLOT_VALUE_KEYWORDS`에 `item_purpose` 추가(B가 정의할 카테고리별
     허용값과 정합). 예: food→("eat","eating","food","personal use"),
     medicine→("health","for my health"), 등.
  5. stay_location 주소 추출 — 자유형 주소 발화를 `address` 허용값으로 인식.
- **Dev C (트집 스코프 sync):**
  6. `_sync_challenge_context_to_dialogue_seed`가 B의 `suspicion_scope` 신호를
     존중해 location은 location 노드, item은 declaration 노드에서만
     challenge_context를 채우도록 게이팅.
- **Dev C (desync 조사):**
  7. seed `surface_goal`이 "다음 답변이 채점될 노드"와 일치하는지 B와 합동 재현.
     node_context 전달 시점이 원인이면 C 측 수정.

### Compatibility Impact

히스토리 필드는 additive optional. 이해 키워드 추가는 기존 통과 케이스에
영향 없어야 함(회귀 가드: `test_developer_a_npc_dialogue.py`, 이해 테스트).
트집 sync 게이팅은 CR-B-EOKKKA 동작을 "관련 노드에서만"으로 좁힐 뿐 verbatim
규칙 자체는 A 소유.

### Temporary Workaround

히스토리 도입 전까지 B는 상태머신 상한으로 무한 반복만 차단(부분 완화).

## Change Request - 2026-06-18 - [CR-B-CONV-A] 트집 게이팅·히스토리 소비·대사 변주

Status: Open.

### Requested By

Developer B

### Affected Owner

Developer A

### Reason

CR-B-EOKKKA로 도입된 SUSPICION MODE 블록
(`prompts/npc_dialogue_prompt.md:80`, Rule 3 verbatim 강제)이 **할당만 되면 모든
입국심사 노드에서 활성**된다. 그래서 방문 목적 노드인데 "Downtown Luxury Hotel"이
박히고, 플레이어가 답하기도 전에 트집한다. 또 메인 시나리오에 히스토리가
전달되지 않아 NPC가 이미 답한 질문을 반복하고, stern/retry 대사가 무변주로
동일 문장만 반복한다. 트집은 핵심 재미이므로 **제거가 아니라 게이팅**이 필요하다.

### Proposed Contract Change

- **Dev A (트집 게이팅):**
  1. SUSPICION MODE 활성 조건을 `assigned_visit_location` 존재가 아니라 B가
     보내는 `dialogue_seed.suspicion_scope`(`location`/`declaration`/`none`)로
     변경. location은 location 노드, item은 declaration 노드에서만 켠다.
  2. 플레이어가 해당 슬롯을 *답한 후*에만 트집(선제 블러팅 금지). 히스토리의
     플레이어 진술을 근거로 cross-turn 트집("출장이라며? 근데 고급 호텔?").
  3. Rule 3 verbatim 강제를 완화 — 장소/품목명을 맥락상 관련될 때만 자연스럽게
     지칭.
- **Dev A (히스토리 소비, 전 노드):**
  4. `llm_payload`에 C가 보내는 `dialogue_history`를 모든 purpose에서 주입.
     `discussed_topics`/`past_player_utterances` smalltalk 전용 제약 해제.
  5. 프롬프트에 "이미 답변된 질문 반복 금지 + 직전 턴 반응 후 진행" 가이드를
     입국심사/세관에도 적용.
- **Dev A (대사 변주):**
  6. stern/retry(clarify 반복)에서 동일 문장 반복 대신 표현 변주 +
     `recommended_expression`을 모범답안으로 1회 제시(verbatim 에코는 금지 규칙
     유지하되 패러프레이즈 힌트 허용). 필요 시 `dialogue_policy_service.py`
     (service_a) 보강.

### Compatibility Impact

트집 게이팅은 B의 `suspicion_scope` emit(`docs/workplan-dev-b.md` §4 작업4)에
의존. 히스토리 소비는 C의 `dialogue_history`(CR-B-CONV-C)에 의존. 회귀 가드:
`test_developer_a_npc_dialogue.py`. 입국신고서 장소 동일 지칭은 location 노드
한정으로 유지.

### Temporary Workaround

없음. B의 상태머신 상한으로 무한 반복만 완화되며, 부자연스러운 verbatim 주입은
A 반영 전까지 잔존.

## Change Request - 2026-06-17 - Deprecate and Remove do_not_generate_npc_text from Developer B Policy

Status: Resolved (Developer B implementation complete - 2026-06-19).

### Requested By

Developer C / Sean Han

### Affected Owner

Developer B

### Reason

The `do_not_generate_npc_text` field in `DialogueDirective` is not used by Developer C's orchestrator or Developer A's dialogue generation prompt (which is immediately filtered out at the adapter layer). Keeping it as a required field triggers unnecessary Pydantic validation errors and test fixture boilerplates.

### Proposed Contract Change

- Remove references to `do_not_generate_npc_text` from the system prompt guidelines in `backend/app/prompts/english_level_hint_prompt.md`.
- Remove the `do_not_generate_npc_text` keyword argument when instantiating `DialogueDirective` in `backend/app/agents/agent_b/english_level_hint_agent.py`.
- Developer C has made this field optional in the shared Pydantic schema to prevent immediate breaking changes, so Developer B can safely clean it up at any time.

### Developer B Resolution - 2026-06-19

- Removed the `do_not_generate_npc_text` keyword argument from all B-owned
  `DialogueDirective` instantiations: `english_level_hint_agent.py`
  (`_build_dialogue_directive`, 2 sites) and `bad_ending_policy.py`
  (`build_bad_ending_output`).
- Removed the `do_not_generate_npc_text` guideline from
  `backend/app/prompts/english_level_hint_prompt.md`.
- Updated B-owned assertion in `test_developer_b_policy_engine.py` (removed the
  `do_not_generate_npc_text is True` check). C-owned
  `test_preprototype_flow.py` already asserts the field is absent from the
  A-facing payload, which now holds.
- The shared schema field remains optional (`bool | None = None`, C-owned) and
  C's adapter sanitizer is untouched; B simply no longer emits it.
- Verification: `pytest` (dev_b + preprototype + dev_a) PASS, `ruff` PASS,
  `mypy` PASS on changed B files.

### Compatibility Impact

No breaking change is introduced on the runtime boundary, as the shared schema now treats this field as optional. B can safely deploy this cleanup without breaking C's validation.

### Temporary Workaround

Developer C has relaxed the shared schema constraint (`do_not_generate_npc_text: bool | None = None`) and continues to sanitize the field in the A-facing adapter.

## Change Request - 2026-06-16 - Clean Developer A Ruff Unused Imports

### Requested By

Developer C / Sean Han

### Affected Owner

Developer A

### Reason

After Developer C implemented the incivility signal sprint, full `uv run pytest`
and `uv run mypy .` pass. Full `uv run ruff check .` is blocked by unused imports
inside Developer A-owned implementation files:

- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/services/service_a/tts_text_polisher_service.py`

Developer C cleaned the unused imports in C-owned test files. The remaining
blocking files are Developer A-owned implementation files, so Developer C
should not silently edit them.

### Proposed Contract Change

Developer A should remove the unused imports reported by ruff, or confirm that
Developer C may apply a mechanical lint-only cleanup to these specific lines.

### Compatibility Impact

No runtime behavior change is expected. This is lint cleanup only.

### Temporary Workaround

Developer C verified the current C-owned sprint files with a focused ruff
command and documented that global ruff remains blocked by A-owned lint debt.

## Change Request - 2026-06-15 - Clarify Ownership for Developer C STT Smoke Scripts

### Requested By

Developer C / Sean Han

### Affected Owner

Shared repository guide / Developer C

### Reason

`AGENTS.md` explicitly lists Developer C ownership for STT pipeline,
orchestration, tests, contracts, handoff docs, and the A/B integration
adapters. It does not currently list `scripts/`, even though
`scripts/smoke_elevenlabs_realtime_stt_relay.py` is a Developer C realtime STT
smoke utility created for local validation of the C-owned WebSocket relay.

This can confuse future agents because the script is not Developer A or
Developer B implementation code, but it is also not explicitly listed in the
Developer C owned paths.

### Proposed Contract Change

Add a narrow Developer C ownership entry to `AGENTS.md` for:

- `scripts/smoke_elevenlabs_realtime_stt_relay.py`

The ownership should be limited to Developer C realtime STT smoke/testing
utilities and must not grant Developer C blanket ownership over all future
repository scripts.

### Compatibility Impact

No runtime behavior change. This only clarifies editing ownership for future
maintenance.

### Temporary Workaround

Treat `scripts/smoke_elevenlabs_realtime_stt_relay.py` as a C-owned realtime
STT smoke utility when the task is specifically about Developer C STT relay
testing. For unrelated scripts, keep the current unknown/shared-file caution.

## Change Request - 2026-06-03 - Developer A NPC Dialogue/TTS Implementation

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer C / Sean Han

### Reason

Developer A needs to implement NPC dialogue and TTS output while preserving Developer C ownership of orchestration, tests, dependency contracts, adapters, and runtime response assembly.

### Proposed Contract Change

1. Allow Developer A to add focused tests for Developer A owned services.
   - Proposed location: `backend/tests/developer_a/`
   - Reason: `backend/tests/` is currently Developer C owned, but Developer A needs isolated verification for dialogue/TTS services.

2. Approve Kokoro runtime dependencies after fake provider is verified.
   - Proposed dependencies: `kokoro`, `soundfile`, `torch`, and Windows espeak runtime helper packages if required.
   - Reason: real wav generation requires these dependencies, but dependency contract must be updated first.

3. Confirm Developer A output fields consumed by Developer C adapter.
   - Proposed fields: `speaker`, `npc_text`, `feedback_kr`, `tone`, `animation`, `tts`, `fallback`.

4. Confirm runtime audio serving policy.
   - Proposed local path: `backend/runtime/audio/kokoro/<cache_key>.wav`
   - Proposed URL field: `audio_url`, nullable until Developer C static serving is ready.

### Compatibility Impact

No existing Developer C mock should break if Developer C keeps using its current adapter behavior. Developer A will keep legacy `text` fields where useful and add `npc_text` for the new contract shape.

### Temporary Workaround

Developer A will implement a fake Kokoro provider that creates valid local wav files without adding external dependencies. Real Kokoro integration and Developer A test placement will wait for contract approval.

Use this format for future requests:

```markdown
## Change Request - YYYY-MM-DD - Short Title

### Requested By

Developer C / Sean Han

### Affected Owner

Developer A or Developer B

### Reason

Why this change is needed.

### Proposed Contract Change

Exact input/output or behavior change.

### Compatibility Impact

Does this break existing mocks or tests?

### Temporary Workaround

What Developer C will do until the change is accepted.
```

## Change Request - 2026-06-04 - Wire Developer B Policy Engine

Status: Resolved in the integrated pre-prototype. Keep this entry for contract
history.

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B exposes a real deterministic `dev_b_policy.v1` policy engine
under `backend/app/agents/agent_b/` and `backend/app/services/service_b/`.
At the time this request was filed, the runtime still called the C-owned mock
adapter at `backend/app/integrations/dev_b_level_hint_client.py`.

### Proposed Contract Change

Keep the existing `DevBPolicyInput` and `DevBPolicyOutput` schemas unchanged.
Update `DevBPolicyClient.evaluate_turn()` to delegate to
`backend.app.agents.agent_b.EnglishLevelHintAgent.evaluate_turn()` after
Developer C approves importing the B-owned package from the adapter.

Also sync or consume `backend/app/data/scenario_nodes.json` in the C-owned
OpenKB runtime so all Chapter 0 immigration nodes are available beyond
`IMM_002_PURPOSE`.

### Compatibility Impact

No schema-breaking change is requested. Existing mock tests may need expectation
updates if they depend on the previous simplified C mock behavior, especially
`dialogue_directive.do_not_generate_npc_text`, `error_capture`, and warning or
hint branch behavior.

### Temporary Workaround

Developer C can keep using the existing mock adapter until the adapter handoff is
accepted. Developer B tests call the B engine directly.

## Change Request - 2026-06-04 - Consume Developer B OpenKB Write References

Status: Partially resolved. Developer B writes local `dev_b` OpenKB records and
Developer C can read B session records for `final_result`, but C-owned
validation of successful `openkb_write.namespace` and path references is still
not implemented.

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B now owns feedback/error/focus-on-form runtime writes under the
OpenKB `dev_b` namespace. The B policy output includes an optional
`openkb_write` reference so C can validate and later retrieve the record without
creating duplicate log entries.

### Proposed Contract Change

Keep the existing `DevBPolicyOutput` fields and add the optional
`openkb_write` field:

- `attempted: bool`
- `succeeded: bool`
- `namespace: str`
- `record_id: str | None`
- `jsonl_path: str | None`
- `markdown_path: str | None`
- `error_message: str | None`

Developer C should update logging/validator/final-report code so that:

1. C does not create a duplicate runtime error record when
   `dev_b_policy.openkb_write.succeeded == true`.
2. C validator checks that successful B write references use namespace `dev_b`
   and point to expected local OpenKB runtime paths.
3. Final report retrieval can consume B-authored feedback/error records by
   `record_id`.

### Compatibility Impact

The field is additive and optional, so existing response assembly can continue
to work. Tests that compare the full `DevBPolicyOutput` dump may need to accept
the new optional `openkb_write` object.

### Temporary Workaround

Until C updates logging and final report retrieval, Developer B writes records
under `backend/runtime/openkb/dev_b/` and C can continue using existing response
payload fields. Any duplicate C-side markdown logging should be treated as a
known integration cleanup item.

## Change Request - 2026-06-04 - Consume Developer B LLM Feedback Metadata

Status: Partially resolved. Developer C accepts the additive B metadata and
validates final-result output, but C-owned validation of `feedback_generation`
and `difficulty_profile` metadata is still not implemented.

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B now exposes optional LLM-assisted learning feedback metadata while
keeping branch, verdict, next-node, and state-delta decisions rule-based. The
metadata helps C validator, final report, and future UI/debug views distinguish
rule, LLM, and fallback feedback.

### Proposed Contract Change

Keep all existing `DevBPolicyOutput` fields and add optional fields:

- `rubric_scores`
- `difficulty_profile`
- `feedback_generation`

Developer C should update validator/final-report consumers so that:

1. `feedback_generation.mode` is one of `rule`, `llm`, or `fallback`.
2. `feedback_generation.used_llm` is debug/trace metadata only and never branch
   authority.
3. `rubric_scores.total` stays in the 0-12 range.
4. `difficulty_profile.travel_speaking_level` is treated as learning
   difficulty metadata, not Unreal branch authority.
5. Any LLM-generated feedback must not override `branch`, `next_node_id`,
   `state_delta`, or `evaluation.verdict`.

### Compatibility Impact

The fields are optional and additive. Existing C response assembly can ignore
them until validator/final-report integration is ready.

### Temporary Workaround

Developer B stores these fields in the B-owned OpenKB `dev_b` runtime record.
C can continue consuming the existing `level_hint`, `evaluation`,
`report_item`, and `openkb_write` fields.

## Change Request - 2026-06-04 - Expose OpenKB objective_kr to Unreal UI

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B now defines `objective_kr` in Chapter 0 scenario node content so the
current node's Korean objective can be shown consistently in Unreal UI.

### Proposed Contract Change

`NodeContext.objective_kr` is an optional field populated from
`backend/app/data/scenario_nodes.json`. Developer C may expose it through the
final Unreal UI response when the response contract is ready for objective
display.

### Compatibility Impact

The field is optional and additive. Existing Understanding, Developer B policy,
Developer A dialogue, and response builder behavior can ignore it.

### Temporary Workaround

Until C adds a UI response field, `objective_kr` is available in the internal
node context only.

## Change Request - 2026-06-08 - Expose Developer B Focus-on-Form Report v1

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B now has a B-owned `FocusOnFormReportPolicy` that can build an
out-game Focus-on-Form report from B-owned OpenKB `dev_b` records and static
B-owned learning cards. Developer C owns final result endpoint shape and Unreal
response assembly, so Developer B cannot expose this report directly.

### Proposed Contract Change

Add an optional `out_game_feedback` object to the C-owned final result response
or a C-owned result detail endpoint. Treat it as learning feedback metadata
only. It must not affect branch, verdict, next node, state delta, or numeric
score authority.

### Compatibility Impact

Additive optional field only. Existing clients may ignore it.

### Temporary Workaround

Developer B keeps the report builder as a directly tested B-owned service.
Developer C can continue returning the existing final result payload until the
response surface is ready.

### Developer C Update - 2026-06-15

Implemented. `GET /api/game/ai/result/{session_id}` now returns additive
`out_game_feedback` learning metadata from B-owned
`FocusOnFormReportPolicy.build_session_report(session_id)` through the C-owned
`DevBPolicyClient` adapter. The field is optional response metadata and does
not affect branch, verdict, next node, state delta, or numeric score authority.

## Change Request - 2026-06-09 - Support Alpha Scene Flow Beyond Immigration

Status: Open.

Developer C Alpha 1 update, 2026-06-10: C added an additive
`dev_c_interaction_context.v1` request/response context for NPC-first vs
player-first and quest vs ambient turns, plus diagnostic response timing. This
does not yet implement the full Alpha scene flow, but it gives Unreal and A/B/C
logs a stable metadata surface for the next scenario-flow phase.

Developer C Alpha 3A update, 2026-06-12: C adopted the B-owned Alpha node
expansion at the runtime boundary for the base route. `IMM_007_FINAL_DECISION`
now remains a transition into `BAG_001_NOTICE_BAG_MISSING`, final-result
attachment is limited to `ALPHA_999_FINAL_SCOREBOARD`, C accepts
`scene_normalized_dimension_average` as a final score policy name, and rule-mode
Understanding can consume B-authored generic slot metadata for flight/BAG-style
nodes. Cutscene/skip orchestration, Unreal scene-state wiring, and final
`out_game_feedback` UI exposure remain open.

Developer C Alpha 3B update, 2026-06-12: C added additive
`dev_c_unreal_flow.v1` response metadata for the base Alpha presentation
transitions. Current flow ids are `flight_to_immigration_arrival` with
`CIN_FLIGHT_ARRIVAL_JFK` and skip eligibility, `immigration_to_baggage_claim`,
and `alpha_final_scoreboard`. Unreal still owns playing the actual cinematics,
moving scene state, and rendering scoreboard UI. Final `out_game_feedback` UI
exposure remains open.

Developer C Alpha 3C update, 2026-06-12: C added the provider-neutral
`dev_c_realtime_stt.v1` WebSocket contract at `/api/game/ai/stt/stream`.
The endpoint accepts `session_start`, `partial_transcript`, `final_transcript`,
and `cancel` events from Unreal or a safe STT bridge, returns subtitle-ready
events for Unreal, and marks final transcript events as committed candidates
for `POST /api/game/ai/respond`. Partial transcripts remain UI-only and do not
call Understanding, Developer B, Developer A, or TTS. Actual provider auth,
short-lived token issuance, and direct streaming-to-orchestrator commit remain
future integration work.

Developer C Alpha 3D update, 2026-06-12: C added the backend relay path for
ElevenLabs realtime STT. `session_start.provider = "elevenlabs_relay"` opens a
server-side WSS connection to ElevenLabs `/v1/speech-to-text/realtime` using
`ELEVENLABS_API_KEY` from the backend environment, `audio_chunk` events are
forwarded as ElevenLabs `input_audio_chunk` messages, and ElevenLabs
`partial_transcript` / `committed_transcript` messages are mapped back to
`dev_c_realtime_stt.v1` subtitle events. Unreal still must capture and send
base64 audio chunks, and direct final-transcript-to-orchestrator commit remains
future work.

### Requested By

Developer B

### Affected Owner

Developer A and Developer C / Sean Han

### Reason

Developer B now has Alpha scenario plan artifacts and B-owned baggage policy
nodes, but the integrated runtime still primarily behaves like an immigration
prototype. Alpha requires the scene order
`FLIGHT_A_001_SEATMATE_SMALLTALK -> IMMIGRATION_ALPHA -> BAGGAGE_MISSING`, silent
level carryover from flight small talk, no immediate out-game feedback after
small talk, cutscene/skip signals, non-immigration NPC roles, and a final
scenario-end result UI containing B-owned `evaluation` plus `out_game_feedback`.

### Proposed Contract Change

Developer C should add or approve request/response fields and orchestration for:

- Alpha scene transitions, including cutscene and skip eligibility.
- Silent carryover of the B-measured `tier`, `travel_speaking_level`,
  `rubric_scores`, and `difficulty_profile` from flight into immigration.
- Rule or LLM Understanding coverage for non-purpose slots such as
  `stay_duration`, `return_ticket_status`, baggage report details, baggage
  description, tag/flight info, delivery contact, and resolution acknowledgement.
- Final result or result-detail exposure of B-owned
  `FocusOnFormReportPolicy.build_report(...)` output as optional
  `out_game_feedback`.
- Final scenario-end `evaluation` payload from Developer B using
  `scene_normalized_dimension_average`:
  - convert each rubric dimension from 0..2 to 0..100,
  - average each dimension inside each scene first,
  - combine present Alpha scenes with default weights: flight 20%,
    immigration 50%, baggage 30%,
  - compute `overall` as the average of the weighted dimension scores,
  - keep optional events out of numeric scoring unless a later explicit weight
    is added.
- Update C-owned schema/validator acceptance for the new score policy name when
  C adopts the contract. Developer C now accepts both `simple_average` and
  `scene_normalized_dimension_average`.

Developer A should consume B difficulty metadata and scene/NPC role context for:

- Friendly seatmate small-talk dialogue.
- Tier-aware immigration officer response speed/strictness.
- Baggage service staff dialogue.

### Compatibility Impact

All fields should be additive until Alpha scene contracts are finalized. Existing
Chapter 0 immigration tests should continue to pass.

### Temporary Workaround

Developer B can keep authoring B-owned scenario nodes, hint policy, diagnostic
policy, and report seeds. Base C runtime routing and flow metadata now exist;
integrated Alpha behavior still depends on Unreal scene-state wiring and A-owned
dialogue support.

## Change Request - 2026-06-09 - Remove Developer B NPC Wording From A Adapter Payload

Status: Resolved for the current Developer C-to-A adapter payload.

Developer C boundary update, 2026-06-16:

- `dev_a_npc_dialogue_client.py` now removes B-authored live-dialogue fields
  from the A-facing level-design payload instead of passing them as `None`.
- Removed from A-facing payload: `node_context.npc_question`,
  `node_context.npc_question_goal`, `node_context.recommended_expression`,
  `in_game_feedback.npc_recast_line_candidate`,
  `in_game_feedback.recommended_expression`, `level_hint.recommended_expression`,
  `dialogue_directive.do_not_generate_npc_text`, A-facing `hint_frequency`, and
  A-facing `pressure_level`.
- `dialogue_seed.surface_goal`, `dialogue_seed.allowed_followup_intents`,
  `required_slots`, `target_slot`, branch metadata, and evaluation summary remain
  available so Developer A can generate NPC wording without receiving B's model
  answer or fixed node question.
- Unreal response UI still receives B's `recommended_expression` through
  Developer C response assembly where appropriate; this change only affects the
  internal B-to-A adapter boundary.

Developer A & C update, 2026-06-15:

- Developer A는 `candidate_text` (어댑터 단의 `npc_recast_line_candidate`가 변환된 값)가 A-side 에이전트(`npc_dialogue_agent.py`)에 유입되는 것을 차단하고, 유입될 경우 명시적으로 `ValueError` 예외를 발생시키도록 유효성 검증을 강화했습니다.
- Developer C는 `dev_a_npc_dialogue_client.py` 어댑터 단에서 B가 반환한 `npc_recast_line_candidate` 값을 A로 인가할 때 강제로 `None`으로 필터링 처리하여 유입을 차단했습니다.
- 이에 종속된 모든 관련 테스트(유닛 및 통합 테스트) 단언문들이 갱신 및 정상화되었습니다.

Developer C Alpha 3A update, 2026-06-12: C adopted the base runtime routing
portion of this request. `ALPHA_999_FINAL_SCOREBOARD` is now the only C adapter
trigger for attached `final_result`; `IMM_007_FINAL_DECISION` advances to
`BAG_001_NOTICE_BAG_MISSING`; the A adapter can seed next-node prompts for
non-`IMM_` nodes through OpenKB; and C rule Understanding has generic
B-metadata slot coverage for the new flight/BAG-style nodes. Unreal cutscene
state wiring and A-owned generated dialogue/TTS polish remain separate follow-up
work.

Developer C Alpha 3B update, 2026-06-12: C now emits `flow` metadata for
flight-to-immigration cutscene, immigration-to-baggage transition, and Alpha
scoreboard display. This gives Unreal a stable backend hint surface while
keeping actual scene/cinematic execution outside the backend.

Developer C Alpha 3C update, 2026-06-12: C now exposes
`/api/game/ai/stt/stream` for realtime STT subtitle events. This does not
change the A-facing dialogue payload yet; it only gives Unreal a stable C-owned
surface for partial and final transcript events while preserving the existing
`/respond` orchestration path.

Developer C Alpha 3D update, 2026-06-12: C now supports `elevenlabs_relay` as a
server-side realtime STT provider mode. This still does not alter the A-facing
dialogue payload; it only changes how subtitle transcripts can be produced
before the committed `/respond` turn.

### Requested By

Developer B

### Affected Owner

Developer A and Developer C / Sean Han

### Reason

Developer B should not author final NPC dialogue. The current integrated path
allows C to pass `node_context.npc_question` and generated next-question text to
Developer A as candidate dialogue, which makes B-owned scenario data behave like
NPC utterance text. This blocks tier-aware and emotionally dynamic NPC dialogue
because Developer A receives text to polish instead of metadata to generate
from.

### Proposed Contract Change

Developer C should update the internal C-to-A adapter payload only. Do not
change the external Unreal request/response contract for this migration.

Remove these fields from the A-facing payload:

- `node_context.npc_question`
- `in_game_feedback.npc_recast_line_candidate` when it contains next-question
  text derived from `npc_question`
- `dialogue_directive.do_not_generate_npc_text`
- A-facing `hint_frequency`
- A-facing `pressure_level`

Keep or pass these metadata fields instead:

| Key                   | Value                              | Meaning                                                                 |
| --------------------- | ---------------------------------- | ----------------------------------------------------------------------- |
| `npc_question_goal`   | string such as `ask_stay_duration` | Communicative goal for Developer A generation                           |
| `required_slots`      | list of strings                    | Information Developer A should prompt for                               |
| `target_slot`         | string or null                     | Primary slot for the current dialogue turn                              |
| `npc_speech_speed`    | integer `0-10`                     | `0` = very slow and learner-friendly, `10` = near-native fast           |
| `question_complexity` | integer `0-10`                     | `0` = very simple one-part question, `10` = complex multi-part question |
| `emotion_change`      | `positive`, `neutral`, `negative`  | NPC emotional/tone direction caused by the current turn                 |

`hint_frequency` remains Developer B feedback policy and should not be passed
as Developer A NPC-generation input.

`pressure_level` should be replaced by word-only `emotion_change` for
A/Unreal-facing tone and facial-expression direction. `emotion_change` is not a
numeric score and should not allow an LLM to manage score state.

Developer A owns final NPC utterance generation and TTS wording. Developer B
provides scenario goal, required intent/slot, difficulty policy, emotion-change
direction, hint policy, scoring policy, and report seeds only.

### Compatibility Impact

This is an internal adapter contract change. External Unreal payloads do not
need to change. Existing deterministic A/C tests that assert exact static
`npc_question` output will need to be updated to assert goal/slot metadata and
A-owned generated text behavior instead.

### Temporary Workaround

Until C updates the adapter and schema, Developer B may keep `npc_question` in
`scenario_nodes.json` as legacy node context required by current schemas, but it
must be treated as fallback/debug context rather than final NPC dialogue
authority.

## Change Request - 2026-06-11 - Adopt Alpha Scenario Node Expansion Across A/C/Unreal

Status: Open.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Reason

Developer B expanded the Alpha scenario node sequence to support five-turn
flight small-talk diagnostics, immigration-to-baggage transition, missing-bag
problem solving, and a dedicated Alpha final-scoreboard node. Dev B can author
and validate node policy, but integrated runtime behavior requires A/C/Unreal
ownership changes.

### Proposed Contract Change

Developer C should adopt the following runtime flow:

```text
FLIGHT_A_001_SEATMATE_SMALLTALK
-> FLIGHT_A_002_TRAVEL_PURPOSE
-> FLIGHT_A_003_STAY_PLAN
-> FLIGHT_A_004_CLARIFY_OR_ASK_BACK
-> FLIGHT_A_005_WRAP_UP
-> IMM_001_PASSPORT
-> existing IMM_* route
-> IMM_007_FINAL_DECISION
-> IMM_999_CLEARED
-> BAG_001_REPORT_MISSING_AT_DESK
-> BAG_002_PROVIDE_CLAIM_TAG
-> BAG_003_CONFIRM_SEARCHED_CAROUSEL
-> BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD
-> BAG_005_CUSTOMS_HOLD_EXPLANATION
-> Unreal unlock/open suitcase + random customs item reveal
-> BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM
-> BAG_007_CUSTOMS_CLEARANCE
-> BAG_999_COMPLETE
-> ALPHA_999_FINAL_SCOREBOARD
```

Developer C follow-up:

- Treat `ALPHA_999_FINAL_SCOREBOARD`, not `IMM_007_FINAL_DECISION`, as the
  Alpha scenario-end final-result trigger.
- Treat `IMM_007_FINAL_DECISION` as an immigration-clearance transition into
  baggage claim.
- Preserve silent flight-to-immigration carryover of B-measured `tier`,
  `travel_speaking_level`, `rubric_scores`, and `difficulty_profile`.
- Orchestrate flight exit, arrival/cutscene transition, baggage claim entry,
  and final scoreboard/result retrieval.
- Add Understanding coverage for the new flight and customs-hold baggage slots.

Developer A follow-up:

- Generate actual NPC dialogue/TTS for the five `FLIGHT_*` seatmate nodes from
  `dialogue_seed`, not from B-authored final lines.
- Generate baggage service and customs-officer dialogue for the new
  `BAG_001_REPORT_MISSING_AT_DESK` through `BAG_007_CUSTOMS_CLEARANCE` route
  from role/goal/slot metadata.
- Keep final NPC utterances, tone realization, voice, and animation A-owned.

Unreal follow-up:

- Connect the flight small-talk scene to the airport arrival/cutscene and then
  to immigration.
- Connect immigration clearance to baggage claim, then to the Alpha final
  scoreboard and ending cinematic.
- Do not show immediate out-game feedback after flight small talk; consume
  deferred feedback only at the Alpha scenario end.

### Compatibility Impact

The Dev B node expansion is additive for node data but changes semantic routing:
`IMM_007_FINAL_DECISION` is no longer the Alpha scenario-end terminal in B
policy. Existing C-owned final-result adapter behavior may keep treating
`IMM_007_FINAL_DECISION` as a legacy final trigger until C adopts this request.

### Temporary Workaround

Developer B keeps `IMM_007_FINAL_DECISION` in the node set and documents the
legacy C adapter mismatch. Integrated runtime can continue using the legacy
result endpoint while A/C/Unreal migrate to `ALPHA_999_FINAL_SCOREBOARD`.

## Change Request - 2026-06-12 - Adopt Alpha Chapter Boundary Transition Nodes

Status: Resolved (Developer A and B/C implementation complete - 2026-06-16).

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Reason

`chapter_id` previously acted like a whole-scenario namespace and did not tell
Unreal when a major NPC interaction was complete. Alpha needs explicit boundary
signals so Unreal can stop the current NPC dialogue and enter the airport
arrival tutorial, baggage claim, or result screen.

### Proposed Contract Change

Adopt `dev_b_scenario_nodes.v2`:

- `scenario_id = ALPHA_AIRPORT_ARRIVAL`.
- `chapter_id` is the ordered Alpha phase:
  `CH0_01_FLIGHT_SMALLTALK`, `CH0_02_ARRIVAL_TUTORIAL`,
  `CH0_03_IMMIGRATION_CHECK`, `CH0_04_BAGGAGE_CLAIM`, `CH0_05_RESULT`.
- Add transition nodes:
  `FLIGHT_999_COMPLETE`, `IMM_999_CLEARED`, and `BAG_999_COMPLETE`.
- Add `next_action = COMPLETE_CHAPTER`.
- Add optional Unreal response `transition` metadata containing
  `status`, `completed_chapter_id`, `next_chapter_id`, `entry_node_id`,
  `unreal_event`, and `requires_player_input=false`.
- Developer C passes additive `transition` metadata to the A-facing dialogue
  adapter payload on chapter-complete branches.

Developer A follow-up:

- Treat `COMPLETE_CHAPTER` as a closing-dialogue context.
- Do not generate the next chapter's opening question from transition metadata.
- Keep final NPC utterance, tone, TTS, and animation realization A-owned.

Unreal follow-up:

- Stop current NPC voice-turn capture when `next_action=COMPLETE_CHAPTER`.
- Use `transition.unreal_event` and `transition.next_chapter_id` to drive the
  next gameplay phase.
- Use `transition.entry_node_id` when the next phase starts with an AI dialogue
  node; allow `entry_node_id=null` for the airport-arrival tutorial phase.

### Compatibility Impact

This is a breaking semantic change for callers that still send
`CH0_IMMIGRATION`. Current immigration dialogue requests must send
`CH0_03_IMMIGRATION_CHECK`. The response `transition` field is additive and
nullable for normal dialogue responses.

### Temporary Workaround

Unreal can continue ordinary dialogue turns by using the node's new chapter id.
Until Unreal consumes the transition payload, chapter-complete responses can be
handled by checking `next_action == COMPLETE_CHAPTER` and reading
`transition.unreal_event`.

## Change Request - 2026-06-12 - Add Alpha Flight Smalltalk Route Variants

Status: Implemented in B-owned scenario node data; Developer A and Unreal should
consume the additive route metadata when they select or render the flight
small-talk opening.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Reason

The previous flight chapter was one fixed 5-turn stream. Alpha needs multiple
natural small-talk variants so the flight scene can feel less scripted while
still collecting a stable 5-turn level diagnostic sample.

### Proposed Contract Change

`CH0_01_FLIGHT_SMALLTALK` now has three route starts in chapter metadata:

- `FLIGHT_A_001_SEATMATE_SMALLTALK` for Friendly Seatmate.
- `FLIGHT_B_001_DESTINATION_CHAT` for Curious Seatmate.
- `FLIGHT_C_001_FORM_HELP_REQUEST` for Travel Form Help.

Each route has five dialogue nodes and then branches to the shared
`FLIGHT_999_COMPLETE` transition node. The default `entry_node_id` remains
`FLIGHT_A_001_SEATMATE_SMALLTALK`, and all flight dialogue route IDs now use
the same `FLIGHT_A_*`, `FLIGHT_B_*`, or `FLIGHT_C_*` naming pattern.

Developer A follow-up:

- Generate natural seatmate dialogue for the new `FLIGHT_B_*` and `FLIGHT_C_*`
  node metadata, and treat the former default route as `FLIGHT_A_*`.
- Keep each route as a 5-turn diagnostic conversation and close before
  `FLIGHT_999_COMPLETE`.

Unreal follow-up:

- Select one route start from `entry_node_ids` when beginning the flight
  chapter, or keep using `entry_node_id` to preserve the default route.
- Do not mix nodes across routes once a route is selected.

## Change Request - 2026-06-12 - Align Developer A/C NPC Routing for Alpha Non-Immigration Nodes

Status: Superseded for AI-only `/respond-dialog` testing on 2026-06-15.
Developer C now aligns the local test preset to Developer A's canonical roster
IDs instead of asking Developer A to support synthetic test IDs such as
`SEATMATE_A_01`. A future Unreal-facing ID mapping can be negotiated as a
separate contract if Unreal must keep synthetic NPC IDs. Developer B data is
ready, and no Developer B implementation change is required.

### Requested By

Developer B

### Affected Owner

Developer A and Developer C / Sean Han

### Reason

`/respond-dialog` now correctly starts `CH0_01_FLIGHT_SMALLTALK` at
`FLIGHT_A_001_SEATMATE_SMALLTALK`, but the first integrated test response still
returned:

- `Officer Miller`
- `Okay. Please continue.`

Runtime logs confirmed the scenario state was correct:

- request chapter: `CH0_01_FLIGHT_SMALLTALK`
- request node: `FLIGHT_A_001_SEATMATE_SMALLTALK`
- B branch: `SUCCESS -> FLIGHT_A_002_TRAVEL_PURPOSE`

The mismatch occurs after B:

- Developer C's A adapter only loads next-question seeds for `IMM_` nodes, so
  `FLIGHT_A_002_TRAVEL_PURPOSE` is not passed as an A candidate line.
- Developer A's NPC roster currently falls unknown NPC ids back to
  `officer_miller`, so `SEATMATE_A_01` resolves to `Officer Miller`.
- Developer A's text fallback is Officer Miller-specific:
  `Okay. Please continue.`

### Requested Contract / Runtime Change

Developer C follow-up:

- Update `backend/app/integrations/dev_a_npc_dialogue_client.py` so
  `_next_node_question()` can resolve supported Alpha dialogue nodes beyond
  `IMM_`, including `FLIGHT_` and `BAG_`.
- Preserve `payload.npc.npc_id`, `npc_role`, and `node_context.chapter_id` in
  the A-facing payload for all Alpha chapters.
- Add validation or diagnostic logging when the requested NPC id/role and
  Developer A response speaker/animation clearly mismatch.
- Add regression coverage for
  `FLIGHT_A_001_SEATMATE_SMALLTALK -> FLIGHT_A_002_TRAVEL_PURPOSE` verifying
  the A seed is the next seatmate line, not an Officer Miller fallback.

Developer A follow-up:

Superseded for the AI-only `/respond-dialog` preset. The local backend tester
should send Developer A roster IDs such as `arabella`, `novak`, `hale`,
`harris`, `dan`, and `brielle`.

- Add roster profiles for the Alpha non-immigration NPCs used by B scenario
  nodes:
  `SEATMATE_A_01`, `SEATMATE_B_01`, `SEATMATE_C_01`, and
  baggage service/customs officer roles.
- Make text fallback, default animation, display name, and voice profile derive
  from the resolved NPC profile instead of Officer Miller-only defaults.
- Generate seatmate-style dialogue/TTS for `FLIGHT_A_*`, `FLIGHT_B_*`, and
  `FLIGHT_C_*` nodes and baggage-service dialogue/TTS for `BAG_*` nodes.
- Treat `COMPLETE_CHAPTER` as a closing line context, not as a prompt to ask
  the next chapter's first question.

### Compatibility Impact

This change does not alter B scenario branching. It fixes A/C integration for
non-immigration chapters so existing `chapter_id`, `node_id`, `npc_id`, and
`next_node_id` values produce the correct speaker and dialogue style.

### Temporary Workaround

Until A/C complete this request, `/respond-dialog` can validate STT,
Understanding, B branching, transition behavior, and payload generation, but
NPC speaker/text quality for Flight and Baggage may still show Officer Miller
fallback output.

## Change Request - 2026-06-12 - Replace Baggage Missing-Bag Route with Customs Hold Required Flow

Status: Implemented in B-owned scenario node data; Developer A, Developer C,
and Unreal follow-up is required for natural integrated play.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Reason

The previous baggage route treated the missing suitcase as a service-desk report
and delivery-resolution flow. Alpha now requires a more natural airport flow:
the service desk confirms the bag is being held, the player returns to baggage
claim, a customs officer unlocks the suitcase, Unreal reveals a random item,
and the player explains that item before clearance.

### Proposed Contract Change

`CH0_04_BAGGAGE_CLAIM.entry_node_id` is now
`BAG_001_REPORT_MISSING_AT_DESK`, and the required baggage route is:

```text
BAG_001_REPORT_MISSING_AT_DESK
-> BAG_002_PROVIDE_CLAIM_TAG
-> BAG_003_CONFIRM_SEARCHED_CAROUSEL
-> BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD
-> BAG_005_CUSTOMS_HOLD_EXPLANATION
-> Unreal unlock/open suitcase + random customs item reveal
-> BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM
-> BAG_007_CUSTOMS_CLEARANCE
-> BAG_999_COMPLETE
-> ALPHA_999_FINAL_SCOREBOARD
```

New required slots:

- `missing_bag_statement`
- `claim_tag_status`
- `carousel_search_confirmation`
- `customs_hold_redirect_acknowledgement`
- `customs_hold_acknowledgement`
- `customs_item_explanation`
- `customs_clearance_acknowledgement`

Developer A follow-up:

- Generate service-desk dialogue for `BAG_001` through `BAG_004`.
- Generate customs-officer dialogue for `BAG_005` through `BAG_007`.
- Add or map roster/voice profiles for baggage service staff and customs
  officer roles so the route does not fall back to Officer Miller.
- Keep final NPC wording, tone, animation, and TTS A-owned.

Developer C follow-up:

- Add Understanding coverage for all new baggage intents and slots.
- Route the correct A-facing NPC role by BAG node phase: service staff for
  `BAG_001` through `BAG_004`, customs officer for `BAG_005` through
  `BAG_007`.
- Ensure `BAG_999_COMPLETE` still returns `next_action=COMPLETE_CHAPTER` with
  `transition.unreal_event = SHOW_ALPHA_SCOREBOARD`.
- Accept or pass through Unreal-provided random item context for
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` if available.

Unreal follow-up:

- After `BAG_005_CUSTOMS_HOLD_EXPLANATION`, stop dialogue capture and run the
  required interaction: show locked suitcase, unlock it, add suitcase to
  inventory, open suitcase UI, and reveal the random customs item.
- Start `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` only after the item is visible to
  the player.
- Use `BAG_999_COMPLETE.transition.unreal_event = SHOW_ALPHA_SCOREBOARD` for
  the final scoreboard transition.

### Compatibility Impact

This replaces the old `BAG_001_NOTICE_BAG_MISSING` through
`BAG_007_RESOLUTION` route. Any caller or test fixture still using the old BAG
IDs must migrate to the new route IDs above.

### Temporary Workaround

Until A/C/Unreal complete their follow-up, `/respond-dialog` can validate B
branching and response structure, but custom service-desk/customs NPC voice and
the suitcase unlock/random-item interaction remain integration work.

## Change Request - 2026-06-12 - Consolidated Alpha Follow-up for Developer A, Developer C, and Unreal

Status: Open. This consolidates the latest Alpha scenario-node changes after
chapter transitions, flight route variants, `/respond-dialog` chapter starts,
and the required baggage customs-hold route.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Current Implemented State

Developer B/C pre-prototype data now uses:

- `scenario_id = ALPHA_AIRPORT_ARRIVAL`.
- Ordered chapter IDs:
  `CH0_01_FLIGHT_SMALLTALK`,
  `CH0_02_ARRIVAL_TUTORIAL`,
  `CH0_03_IMMIGRATION_CHECK`,
  `CH0_04_BAGGAGE_CLAIM`,
  `CH0_05_RESULT`.
- Transition nodes:
  `FLIGHT_999_COMPLETE`,
  `IMM_999_CLEARED`,
  `BAG_999_COMPLETE`.
- `next_action = COMPLETE_CHAPTER` with optional `transition` metadata for
  Unreal state changes.
- Flight has three 5-turn route starts:
  `FLIGHT_A_001_SEATMATE_SMALLTALK`,
  `FLIGHT_B_001_DESTINATION_CHAT`,
  `FLIGHT_C_001_FORM_HELP_REQUEST`.
- Baggage claim now starts at `BAG_001_REPORT_MISSING_AT_DESK` and requires
  the customs-hold/random-item explanation route:
  `BAG_001_REPORT_MISSING_AT_DESK -> BAG_002_PROVIDE_CLAIM_TAG ->
BAG_003_CONFIRM_SEARCHED_CAROUSEL ->
BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD ->
BAG_005_CUSTOMS_HOLD_EXPLANATION ->
BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM -> BAG_007_CUSTOMS_CLEARANCE ->
BAG_999_COMPLETE`.
- `/respond-dialog` can start Flight, Immigration, Baggage, and Result from
  buttons without uploading a JSON turn file. The first turn can be submitted
  with WAV upload or browser recording.

### Developer A Required Follow-up

- Add or map NPC roster/voice profiles for:
  seatmate route A/B/C, baggage service staff, and customs officer.
- Stop falling unknown non-immigration NPCs back to Officer Miller.
- Generate natural seatmate dialogue/TTS for `FLIGHT_A_*`, `FLIGHT_B_*`, and
  `FLIGHT_C_*`.
- Generate service-desk dialogue/TTS for `BAG_001` through `BAG_004`.
- Generate customs-officer dialogue/TTS for `BAG_005` through `BAG_007`.
- Treat `next_action=COMPLETE_CHAPTER` as a closing-line context only; do not
  ask the next chapter's first question from transition metadata.

### Developer C Required Follow-up

- Extend the Developer A adapter so next-question seeds work for `FLIGHT_` and
  `BAG_` nodes, not only `IMM_` nodes.
- Preserve and validate A-facing `npc_id`, `npc_role`, `chapter_id`, and
  `node_id` for all Alpha chapters.
- Add diagnostics or validation when requested NPC role and A returned speaker
  clearly mismatch.
- Add Understanding coverage for new Flight route slots and the new baggage
  customs-hold slots, especially:
  `missing_bag_statement`,
  `claim_tag_status`,
  `carousel_search_confirmation`,
  `customs_hold_redirect_acknowledgement`,
  `customs_hold_acknowledgement`,
  `customs_item_explanation`,
  `customs_clearance_acknowledgement`.
- Route A-facing NPC context by BAG phase: service staff for `BAG_001` through
  `BAG_004`, customs officer for `BAG_005` through `BAG_007`.
- Keep `BAG_999_COMPLETE` returning `next_action=COMPLETE_CHAPTER` with
  `transition.unreal_event = SHOW_ALPHA_SCOREBOARD`.
- Pass through Unreal-provided random item context to
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` when available.

Developer C update, 2026-06-15:

- Implemented A-adapter `dialogue_seed` forwarding for non-immigration Alpha
  nodes.
- Implemented non-blocking `npc_speaker_mismatch` diagnostics.
- Added `game_state.random_customs_item` pass-through into Developer B input
  and Developer A payloads.
- Added BAG phase-based A-facing NPC context normalization:
  `BAG_001` through `BAG_004` route as baggage service staff, while `BAG_005`
  through `BAG_007` route as customs officer.
- Added deterministic Understanding fallback coverage for common Alpha
  Flight/Baggage slot values, including `customs_item_explanation`.
- Remaining C follow-up after this update: broader Alpha phrase coverage and
  any future Unreal-driven player-initiated/free-talk routing contract.

### Unreal Required Follow-up

- Start Alpha from chapter metadata:
  default Flight start is `FLIGHT_A_001_SEATMATE_SMALLTALK`; optional route
  starts are listed in `entry_node_ids`.
- Do not send player speech turns for `node_type=transition`.
- On `COMPLETE_CHAPTER`, stop current NPC voice capture and consume
  `transition.unreal_event`, `transition.next_chapter_id`, and
  `transition.entry_node_id`.
- Handle transition events:
  `START_AIRPORT_ARRIVAL_TUTORIAL`,
  `ENTER_BAGGAGE_CLAIM`,
  `SHOW_ALPHA_SCOREBOARD`.
- After `BAG_005_CUSTOMS_HOLD_EXPLANATION`, run the required non-dialogue
  interaction: show locked suitcase, unlock it, add suitcase to inventory, open
  suitcase UI, reveal random customs item, then start
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`.

### Compatibility Impact

Old callers using `CH0_IMMIGRATION`, `FLIGHT_001_*`, or the previous baggage
route `BAG_001_NOTICE_BAG_MISSING` through `BAG_007_RESOLUTION` must migrate
to the current chapter IDs and node IDs.

### Current Verification

- `uv sync` completed.
- `uv run pytest` passed with 201 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

## Change Request - 2026-06-12 - Propagate Developer B NPC Emotion Enum

Status: Implemented in B/C pre-prototype runtime; Developer A and Unreal should
consume the additive field when ready.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Proposed Contract Change

Developer B now returns `npc_emotion` on `DevBPolicyOutput`. Allowed values are:

```text
Nomal
Joy
Anger
Sadness
Panic
Suspicion
Disgust
Fear
Smirk
Surprise
Pain
Confusion
Boredom
```

Current rule mapping:

- Normal successful progress: `Nomal`.
- Clarify, retry, or hint branches: `Confusion`.
- Warning, bad-end, or critical-risk branches: `Suspicion`.

Developer C follow-up already implemented in the pre-prototype:

- Pass `DevBPolicyOutput.npc_emotion` to Developer A as A-facing
  `npc.emotion`.
- Return the same value in the Unreal response as `npc.emotion`.

Developer A follow-up:

- Use A-facing `npc.emotion` as the preferred emotion cue when selecting NPC
  facial expression, TTS style, animation tone, or fallback behavior.
- Keep dialogue text generation A-owned; B only supplies the enum cue.

Unreal follow-up:

- Treat response `npc.emotion` as the current NPC emotion state for the turn.
- Map the enum values above to available facial expression/animation states.

### Compatibility Impact

This is an additive field. Existing clients that ignore `npc_emotion` or
response `npc.emotion` can continue using `npc.tone` and `npc.animation`.

### Current Verification

- `uv sync` completed.
- `uv run pytest` passed with 201 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

## Change Request - 2026-06-12 - Expand NPC Dialogue Client Payload for Dynamic Emotion & Audio Parameters

Status: Resolved (Developer A implementation complete - 2026-06-16).

### Requested By

Developer A

### Affected Owner

Developer C / Sean Han, and Developer B

### Reason

Developer A is refactoring the NPC Dialogue generation flow to use a dynamic, unified single agent design. Under this design:

1. ElevenLabs TTS parameters (stability, style, speed, similarity_boost) will be dynamically calculated by the LLM based on emotion and context, rather than hardcoded in the service layer.
2. The Level Design Agent will provide one of 13 official emotion types (`joy`, `panic`, `sad`, `suspicion`, `disgust`, `fear`, `smirk`, `normal`, `anger`, `surprise`, `pain`, `confusion`, `boredom`) in its payload to Developer A.
3. Roster-defined personas (e.g. `persona_instruction`) will be resolved and injected dynamically into the system prompt.
   This requires Developer C adapters and schemas to support the expanded output fields.

### Proposed Contract Change

Developer C should update the `dev_a_npc_dialogue_client.py` adapter and the shared Pydantic response schemas to accept the following fields returned by the Developer A dialogue agent:

```json
{
  "speaker": "Arabella",
  "npc_text": "Hi there! Welcome to the flight.",
  "tts_text": "Hi there! ... Welcome to the flight.",
  "feedback_kr": "반갑습니다! 편안한 비행 되세요.",
  "tone": "formal_neutral",
  "animation": "move",
  "npc_emotion": "joy",
  "stability": 0.75,
  "style": 0.45,
  "speed": 1.0,
  "similarity_boost": 0.85
}
```

Developer C follow-up:

- Update the Pydantic validator schemas in `backend/app/schemas/` to allow these new fields (or relax strict schema validation temporarily).
- Forward these audio tuning parameters to the TTS service wrapper for ElevenLabs invocation.
- Integrate the LangChain-based NPC Dialogue Agent as a **single node/subgraph** inside the main orchestrator graph (`developer_c_graph.py`).

Developer B follow-up:

- Update payloads to ensure the `npc_emotion` field from the Level Design Agent contains one of the 13 supported emotion strings.
- Pass the correct `npc_id` and player `tier` inside the payload.

### Compatibility Impact

This change is additive for schema fields. The fallback and legacy adapters can safely default to standard parameters if the new fields are not populated.

## Change Request - 2026-06-13 - Update Developer C Tests to Support TTS Slimming Refactor

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer C / Sean Han

### Reason

Developer A is executing the cleanup and TTS slimming refactor plan (removing Chatterbox/Kokoro packages and unifying fallback to Edge TTS).
Since the default fallback provider changes from `kokoro` to `edge`, integrated test cases owned by Developer C that assert or mock the `kokoro` audio URL path will fail.
Specifically:

- `backend/tests/test_preprototype_flow.py` (L840) expects `/runtime/audio/kokoro/` URL prefix.
- `backend/tests/test_demo_ai_respond_page.py` (L404) uses `/runtime/audio/kokoro/demo.wav` as mock data.
- `backend/tests/test_final_result_payload.py` (L243) uses `/runtime/audio/kokoro/final.wav` as mock data.

### Proposed Contract Change

1. Update `backend/tests/test_preprototype_flow.py` to assert the `edge` audio URL path prefix instead of `kokoro` (e.g. `assert body["npc"]["audio_url"].startswith("/runtime/audio/edge/")`).
2. Update mock URL configurations in `backend/tests/test_demo_ai_respond_page.py` and `backend/tests/test_final_result_payload.py` to point to `/runtime/audio/edge/` paths.
3. This aligns with Developer A's refactored `voice_output_service.py` where the default fallback and served directory name is changed from `kokoro` to `edge`.

### Compatibility Impact

This change will resolve failing assertions in Developer C's integration tests after Developer A finishes removing the `kokoro` and `chatterbox` libraries. Until this change is made, `pytest` will fail during the integration validation phase.

### Temporary Workaround

Developer A can temporarily comment out or bypass these assertions during local development of Service A services, but the repository main branch tests will remain broken until Developer C applies these updates to the test assertions.

## Change Request - 2026-06-13 - Remove Deprecated Miller NPC and Update Default NPC to Hale

### Requested By

Developer C / Sean Han

### Affected Owner

Developer A / kimyonghee

### Reason

1. 기획 사양(스토리보드)에서 제외된 레거시 캐릭터인 `miller`를 완전히 삭제하여 기술적 부채를 청산합니다.
2. 실제 챕터 0의 메인 입국심사관 NPC인 `hale`을 기본(Default) NPC로 설정하여 기획 정합성을 높입니다.
3. 이에 따른 전체 소스코드와 유닛 테스트 코드의 종속성을 해소하여 일관된 에이전트 동작을 보장합니다.

### Proposed Contract Change

1. [npc_roster_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/npc_roster_service.py)에서 `miller` 객체를 삭제하고 `_DEFAULT_NPC_ID`를 `"hale"`로 수정합니다.
2. `_normalize_npc_id` 정규화 함수에 레거시 하위 호환 매핑 로직을 추가하여, 외부(Unreal) 또는 테스트에서 구 규격인 `"miller"`나 `"officer_miller"`를 참조해 통신을 시도해도 자동으로 `"hale"` 프로필로 변환 및 리턴하도록 조치합니다.
3. [voice_profile_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/voice_profile_service.py)에서 `miller` 음성 설정을 지웁니다.
4. 백엔드 및 전체 유닛 테스트 코드에서 `miller`를 기용한 Assertion 및 Mock 설정을 `hale`로 통일 및 갱신합니다.

### Compatibility Impact

레거시 `officer_miller` 혹은 `miller` 데이터가 전달되더라도 백엔드에서 자체적으로 `hale`로 안전하게 리다이렉트 처리(하위 호환)하기 때문에, 언리얼 엔진의 통신이나 외부 API 연동 흐름이 깨지지 않습니다.

### Temporary Workaround

해당 없음 (전면 리팩터링 적용 완료).

## Change Request - 2026-06-15 - Deprecate NPCDialogueAgentRunMiddleware and Transition to NPCDialogueAgentRunRecorder

Status: Resolved (Deprecated shim completely removed - 2026-06-16).

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer C / Sean Han

### Reason

LangChain 1.0+ 및 LCEL 체인 호출 구조 하에서 기존의 LangChain 0.x 방식 콜백/미들웨어 훅 작동 방식이 표준 규격에 어긋나 타입 경고 및 런타임 오류가 유발될 수 있습니다. 이를 해소하기 위해 상태 기계 및 서비스 내에서 명시적으로 동작하는 `NPCDialogueAgentRunRecorder`를 신설하고, 기존 미들웨어 클래스 `NPCDialogueAgentRunMiddleware`를 Deprecated 처리했습니다.

### Proposed Contract Change

1. Developer C는 향후 A/B/C 통합 레이어 및 오케스트레이터에서 `NPCDialogueAgentRunMiddleware`를 활용하여 callback 형태로 로깅 이벤트를 캡처하는 대신, `NPCDialogueAgentRunRecorder`를 직접 또는 오케스트레이터의 RunnableConfig/Callbacks 설정 내에서 호출하도록 교체할 것을 제안합니다.
2. 현재의 하위 호환성을 보장하기 위해 `NPCDialogueAgentRunMiddleware`는 Shim 형태로 남겨두어 `warnings.warn` 경고를 출력하며 내부적으로 `NPCDialogueAgentRunRecorder`로 작업을 위임하도록 처리했습니다. 향후 완전한 통합 정리를 위해 호출 부분의 마이그레이션이 필요합니다.

### Compatibility Impact

Shim 클래스가 존재하므로 당장의 통합 테스트 및 실행은 깨지지 않으나, 컴파일/정적 분석 경고(DeprecationWarning)가 콘솔에 찍히게 됩니다.

### Temporary Workaround

현재 구현된 Shim 미들웨어가 자동으로 새 기록기를 대리 호출하므로, 즉각적인 수정은 불필요하지만 중장기적으로 `NPCDialogueAgentRunRecorder` 직접 사용으로의 전환을 권장합니다.

### Current Verification

- `uv sync` 완료.
- `uv run pytest` 결과 231개 전체 테스트 성공 (Shim 미들웨어가 정상적으로 경고를 출력하며 이벤트를 위임하여 로깅되는 것 확인).
- `uv run ruff check .` 및 `uv run mypy .` 무오류 통과.

## Change Request - 2026-06-16 - Understanding Agent Slot Value Normalization and Hesitation Handling

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

플레이어가 단순 망설임("Um,")을 발화했을 때, Understanding Agent가
`intent_success=True`로 오인식하고 필수 슬롯 `polite_response`에
`"short acknowledgement / hesitant start"`라는 자유 텍스트 값을 채워
넣었습니다. 이 값은 노드의 `allowed_slot_values`(예: `offered_help`,
`declined_politely`, `short_acknowledgement`)에 실재하지 않는 후보입니다.

Developer B는 `ScenarioStateMachine`에 슬롯 값 유효성 검증을 추가하여 이
오판정을 2차 방어선에서 차단할 예정이나(`docs/workplan-dev-b.md`), 근본
원인은 Understanding Agent의 슬롯 채움 단계에 있습니다.

### Proposed Contract Change

1. Understanding Agent가 슬롯 값을 채울 때 해당 노드의 `allowed_slot_values`
   후보 중 하나로 정규화(canonicalize)하도록 제안합니다.
2. 발화를 허용 후보로 매핑할 수 없거나 단순 망설임/무의미 발화인 경우,
   임의 자유 텍스트를 채우지 말고 `intent_success=False` 또는
   `needs_clarification=True`(혹은 해당 슬롯을 `missing_slots`에 포함)로
   반환하도록 제안합니다.
3. 추가로, 통합 어댑터(`backend/app/integrations/dev_a_npc_dialogue_client.py`)의
   `npc_recast_line_candidate` 강제 None 필터링이 다음 질문 후보까지 함께
   제거하여 Dialogue Agent의 다음 질문 작문에 영향을 주는지 점검을
   요청합니다.

### Compatibility Impact

스키마 변경은 없습니다. 기존 필드(`intent_success`, `needs_clarification`,
`missing_slots`, `extracted_slots`)의 채움 정책만 강화됩니다. Developer B의
규칙 검증과 독립적으로 동작하며, 둘 다 적용 시 동일한 안전 동작으로
수렴합니다.

### Temporary Workaround

Developer B의 `ScenarioStateMachine` 슬롯 값 검증이 적용되면, 허용 후보에
없는 슬롯 값은 SUCCESS가 아니라 clarify(REASK)로 라우팅되어 잘못된 ADVANCE가
차단됩니다.

### Verified Runtime Reproduction (2026-06-16 업데이트 — Developer C 조치 필수)

Developer B의 슬롯 값 검증을 적용·검증(`uv run pytest` 94 passed)한 뒤
`/respond-dialog`로 재현 테스트한 결과, 이 변경 요청의 **우선순위가
긴급(critical)으로 상향**되었습니다. 이유는 다음과 같습니다.

`FLIGHT_A_001_SEATMATE_SMALLTALK` 노드("Could I borrow your pen ...")에서
플레이어가 off-topic 관용구 `"Okay, you're on."`(내기를 수락한다는 의미)을
발화했을 때, Understanding Agent가 반환한 실제 런타임 출력은 다음과 같습니다.

```text
player_text:         "Okay, you're on."
intent_success:      true
confidence:          0.98
answer_relevance:    "on_topic"
needs_clarification: false
extracted_slots:     {"polite_response": "short_acknowledgement"}   # 유효한 정규값
missing_slots:       []
```

즉, 최초 리포트의 자유 텍스트 쓰레기값(`"short acknowledgement /
hesitant start"`)과 달리, 지금은 **허용 후보군에 실재하는 정규값
`short_acknowledgement`** 가 confidence 0.98 / on_topic 으로 반환됩니다.

이로 인해 Developer B의 멤버십 기반 슬롯 값 검증은 이 케이스를 **원천적으로
잡을 수 없습니다**(값이 유효하므로 통과가 정상 동작). 상태 머신이 규칙
기반으로 사용할 수 있는 모든 신호(`intent_success`, `missing_slots`,
슬롯 값 유효성, `confidence`, `answer_relevance`, `needs_clarification`)가
SUCCESS를 가리키므로, 이 오판정은 **Understanding Agent(Developer C) 단계
에서만 차단 가능**합니다.

### Strengthened Request (정확도 차원 보강 요청)

기존 정규화 요청(위 1~2번)에 더해, off-topic / 관용구 / 무의미 발화를
질문의 의도와 무관함에도 정규 슬롯 값으로 confident 매핑하지 않도록
Understanding Agent의 **분류 정확도** 보강을 요청합니다. 구체적으로:

- 발화가 노드의 `required_intents` 의미에 실제로 부합하는지 먼저 판정하고,
  부합하지 않으면 `answer_relevance="off_topic"` 또는
  `intent_success=False`로 반환.
- 슬롯 값 매핑의 근거(`slot_evidence`)가 약하거나 추론에 가까우면
  높은 confidence(0.9+)를 부여하지 않도록 조정.

### Developer C Update - 2026-06-16

Implemented the first C-side guard for the verified root cause:

- `understanding_agent.py` now rejects known off-topic idioms for the current
  required slot before they can remain as successful extracted slots.
- The verified `"Okay, you're on."` case for
  `FLIGHT_A_001_SEATMATE_SMALLTALK` now returns `intent_success=false`,
  `answer_relevance="off_topic"`, `missing_slots=["polite_response"]`,
  `needs_clarification=true`, and confidence below `0.9`.
- If an LLM-filled required slot lacks strong accepted `slot_evidence`,
  Understanding now keeps the slot value but lowers confidence below `0.9`.
- `understanding_llm_client.py` developer instructions now explicitly require
  required-intent relevance judgment before slot filling and prohibit 0.9+
  confidence for weak, idiomatic, inferred, or loosely related slot evidence.
- Added `backend/app/prompts/understanding_prompt.md` as the C-owned prompt
  policy mirror referenced by `AGENTS.md`.
- Checked `dev_a_npc_dialogue_client.py`: forcing
  `npc_recast_line_candidate=None` does not remove `dialogue_seed` or
  `dialogue_directive` metadata used for next-prompt generation. C-owned tests
  now assert this behavior.

## Change Request - 2026-06-16 - Dialogue Agent Speaker Role Confusion and Missing Follow-up Question

Status: Resolved (Developer A update - 2026-06-16).

### Requested By

Developer B

### Affected Owner

Developer A / kimyonghee

### Reason

시나리오가 (오)판정으로 SUCCESS 처리된 뒤, Dialogue Agent에서 두 가지 품질
문제가 관찰되었습니다.

1. 화자 역할 혼동/환각: 플레이어가 해야 할 추천 표현("Sure, here you are.")에
   대고 NPC 본인이 고맙다고 덧붙이는 비자연적 대사("Sure, here you are.
   Thanks.")를 생성했습니다.
2. 다음 질문 작문 누락: `dialogue_seed`의 `surface_goal`(예:
   `ask_travel_purpose_smalltalk`)을 전달받았음에도, 첫 턴에서 리액션만 단답형
   으로 생성하고 다음 노드 질문("Are you visiting New York for a trip?")을
   이어 붙이지 못했습니다.

### Proposed Contract Change

1. Dialogue Agent 프롬프트에서 화자 역할(플레이어 발화 vs NPC 발화)을 명확히
   구분하여, 플레이어 추천 표현을 NPC 대사로 흡수하지 않도록 보강을
   제안합니다.
2. `dialogue_seed.surface_goal`을 활용해 직전 답변에 대한 리액션 이후 다음
   질문을 자체 작문하여 결합하도록 보강을 제안합니다.

참고: Developer B의 슬롯 값 검증 수정으로 "Um," 류 모호 발화가 더 이상
SUCCESS로 전달되지 않으므로, 본 현상의 발현 조건(시나리오가 성공으로 잘못
판정됨) 자체가 상당 부분 사라집니다. 다만 정상 SUCCESS 턴에서도 위 품질
문제가 재현될 수 있어 별도 보강을 요청합니다.

### Compatibility Impact

Developer A 소유 프롬프트/생성 로직 내부 개선이며, A/B/C 간 스키마·계약 변경은
없습니다.

### Temporary Workaround

`/respond-dialog` 테스트 시 "Sure, here is my pen."과 같이 의도에 부합하는
구체적 영어 답변을 입력하면 보다 자연스러운 NPC 전환 대사를 확인할 수
있습니다.

## Change Request - 2026-06-16 - 기내 스몰토크 대화형 전환 (Flight Smalltalk Conversational Mode)

Status: Resolved (Developer A update - 2026-06-17). Developer A 측 후속 작업
(스몰토크 페르소나 프롬프트, missing_followup_question 우회, SURFACE_GOAL_QUESTIONS
비활성화, recommended_expression 차단, 대화 메모리, generic 중립 폴백, Coherence Guard)
이 모두 구현 완료. 상세 내용은 handoff.md 2026-06-17 "Developer A 기내 스몰토크
적응형 진단(Adaptive Diagnostic) 연동 구현 완료" entry 참고. Developer C 측 후속
(off-topic 가드 씬 인지화, 슬лот 강제 추출 완화)은 별도로 처리됨.

Status: Open. Developer B 작업계획서(`docs/workplan-dev-b.md`) 기준. Dev B는
분기 결정·시드 측을 담당하며, 본 요청은 Dev A·Dev C 후속 작업을 정의한다.

### Requested By

Developer B

### Affected Owner

Developer A and Developer C / Sean Han

### Reason

기내(옆자리 승객) 스몰토크 씬 `FLIGHT_A_001_SEATMATE_SMALLTALK`(및
`FLIGHT_B_*`, `FLIGHT_C_*`)이 출입국 심사용 채점형 상태 머신
(`ScenarioStateMachine`)을 재사용해 다음 문제가 있다: (1) 취조처럼 느껴지고,
(2) 엉뚱한 답에 같은 질문을 반복하며, (3) 꼬리를 무는 자연 대화감이 없고,
(4) 매 턴 교정("이렇게 말하면 돼")이 노출되며, (5) 스몰토크인데 다음 질문
진행에만 집중한다.

확정 방향: **재미·라포 우선(절충)** — 표면 대화는 완전 자유, 영어 진단/채점은
백그라운드에서 조용히 적립한 뒤 씬 종료 후 리포트로만 노출. Dev B는 기내 씬을
채점형 분기에서 분리(대화형 결정 + 페널티 미적립 + in-game 교정 억제)하지만,
"기계 느낌" 완전 제거에는 Dev A 대사 생성과 Dev C 슬롯 정책 변경이 함께
필요하다.

### Proposed Contract Change

Dev A:

- NPC 대사 프롬프트(`backend/app/agents/agent_a/npc_llm_client.py`의
  `_developer_instructions`)에 **스몰토크 페르소나 모드**를 추가한다 —
  자기 사연·목적을 지닌 동승객; 매 턴 질문 강제 금지; 반응/자기개방/질문 혼합;
  topic drift 허용; 대화 중 영어 교정 금지.
- 기내 씬에서 `missing_followup_question` 검증/매 턴 질문 강제를 **해제**하고
  (`npc_dialogue_agent.py`), 반응-only 턴을 허용한다.
- `SURFACE_GOAL_QUESTIONS` 고정 질문 큐
  (`backend/app/services/service_a/dialogue_policy_service.py`)를 기내 씬에서
  **비활성화**하고, 플레이어 발화·추출 토픽 기반 맥락 후속을 생성한다. 고정
  질문은 LLM 실패 시 폴백으로만 사용.
- `recommended_expression`/교정 표현을 라이브 대사(`npc_text`/`tts_text`)에
  삽입하지 않는다(피드백은 out-game 리포트로).
- `branch_reason == "flight_smalltalk_continue"` 신호 시 성공-축하형이 아닌
  중립 반응을 렌더링한다.
- (질감, 후속) 대화 메모리: 다룬 화제·NPC가 밝힌 정보를 추적해 재질문 방지 및
  "아까 ~라 했죠" 콜백.

Dev C:

- 기내 스몰토크에서 슬롯 강제 추출을 완화한다 — 자유 발화를 임의 슬롯 값으로
  채우지 않는다.
- **off-topic 가드의 씬 인지화**: 2026-06-16 Understanding off-topic guard는
  입국심사(IMM\_\*)에서는 차단을 유지하되, 기내 스몰토크에서는 off-topic을
  패널티/재질문 유발로 쓰지 않는다(화제 이동 허용). Dev B 기내 분기는 채점
  신호를 무시하므로 재질문은 발생하지 않으나, understanding 출력이 리포트/적립을
  왜곡하지 않도록 조정 요청.
- 어댑터(`backend/app/integrations/dev_a_npc_dialogue_client.py`)가 기내 씬에서
  `dialogue_seed.surface_goal`/`allowed_followup_intents`를 강제 단일 질문이
  아니라 주제 힌트로 전달하는지 확인.

### Compatibility Impact

내부 어댑터/프롬프트/생성 정책 변경이며 외부 Unreal 계약은 불변. 입국심사

## Change Request - 2026-06-16 - Add `incivility_tier` to Understanding output + B branch policy

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer C / Sean Han, and Developer B

### Reason

플레이어가 욕설/모독/위협 발화 시 NPC도 동급의 거친 응답을 반환하는 'Profanity Mirror' 모드와 단호히 경고하는 'Firm' 모드를 지원하기 위해, 플레이어 발화의 무례함 정도를 감지하는 분류 신호(`incivility.tier`)가 필요합니다.
분류와 분기는 각각 Understanding Agent (Developer C) 및 Policy Engine (Developer B)에서 수행되어야 하며, Developer A는 이 신호를 수신해 적합한 발화 및 TTS 톤 조율만 수행합니다.

### Proposed Contract Change

1. **CR-1 (Affected: Developer C) - Understanding Agent `incivility` Signal**:
   Understanding Agent 출력에 `incivility` 객체를 추가합니다.

   ```json
   "incivility": {
     "tier": 0,           // 0=정상, 1=무례, 2=인격모독, 3=욕설/혐오/위협
     "detected_terms": ["stupid", "shut up"],
     "confidence": 0.87,
     "category": "rudeness|insult|profanity|slur|threat"
   }
   ```

   이 신호는 키워드 기반 혹은 LLM 분류 모드를 통해 산출됩니다.

2. **CR-2 (Affected: Developer B) - Bad Ending / Penalty Policy on `incivility.tier >= 2`**:
   B Policy는 `incivility.tier >= 2`일 때 분기 판정 및 bad ending 트리거 결정을 소유합니다.

3. **CR-3 (Affected: Developer C) - Forward `incivility` to A Payload**:
   Developer C 어댑터 `dev_a_npc_dialogue_client.py`는 `incivility` 객체를 A-facing payload 에 포함하여 전달합니다.

### Compatibility Impact

이 필드는 추가적인 속성이며, 신호가 누락되거나 기본값(0)인 경우 평상시의 정중한 응답으로 안전하게 수렴하므로 기존 호환성을 해치지 않습니다.
(IMM*\*)·수하물(BAG*\*) 채점 동작은 그대로 유지되어야 한다(회귀 가드).
`branch_type` enum은 확장하지 않으며, 중립 진행은 `success`+`ADVANCE` 재사용 +
`branch_reason="flight_smalltalk_continue"` 신호로 표현한다.

### Temporary Workaround

Dev B 기내 분기만 적용해도 기내 씬의 재질문·페널티는 사라진다. Dev A 프롬프트
변경 전까지는 NPC가 여전히 매 턴 질문형으로 응답할 수 있으나, 진행이 막히거나
취조형으로 채점되지는 않는다.

## Change Request - 2026-06-16 - [CR-A1] Add `incivility` Signal to Understanding Agent Output

Status update 2026-06-16: Implemented by Developer C. `UnderstandingOutput.incivility`
is now additive semantic evidence produced by the C-owned rule classifier after
both rule and LLM Understanding paths. CR-A2 and CR-A4 remain open for Developer
B before Bad Ending end-to-end can work.

Status: Open. 기존 2026-06-16 통합 CR(`Add incivility_tier to Understanding output + B branch policy`)을 owner 단위로 분해한 정식 요청입니다. CR-A1~A4 4건이 모두 머지되어야 Bad Ending end-to-end 가 동작합니다.

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer C / Sean Han

### Reason

A 측 Profanity Mirror/Firm 모드 구현은 완료되었으나, Understanding Agent가 `incivility` 신호를 산출하지 않아 `payload.get("incivility")` 가 항상 비어 있고 결과적으로 `incivility_tier = 0` 으로 평가됩니다. 욕설/모욕성 입력 분류는 Understanding 단계가 자연스럽고, 분류 신호는 A의 발화 표현(Profanity Mirror) 과 B의 Bad Ending 분기 양쪽에서 공유되어야 합니다.

### Proposed Contract Change

Understanding Agent 출력(`UnderstandingOutput` 또는 동등 스키마)에 다음 객체를 additive 로 추가합니다.

```json
"incivility": {
  "tier": 0,
  "detected_terms": ["fuck", "shut up"],
  "confidence": 0.92,
  "category": "rudeness | insult | profanity | slur | threat",
  "source": "rule | llm"
}
```

- `tier`: 0=정상, 1=무례, 2=인격모독, 3=욕설/혐오/위협
- 분류는 룰베이스(키워드 사전) 또는 LLM 모드에서 산출. 둘 다 가능하면 LLM 우선 + 룰 폴백.
- 한국어 욕설/우회 표기(`f*ck`, leetspeak) 도 가능한 범위에서 감지.
- 분류 자체는 신호이며 **분기 권한은 Developer B 가 유지** (가드레일).
- 신호가 없거나 누락된 경우 A 측은 `incivility_tier = 0` 으로 안전 동작.

### Compatibility Impact

Additive 필드. 기존 응답 형식 변경 없음. 기존 회귀 무영향.

### Temporary Workaround

A 측 `MURPHY_NPC_DEV_FORCE_INCIVILITY_TIER` dev override 또는 A 단독 룰베이스 분류기(`incivility_classifier.py`)를 신설하여 신호 누락 시 임시 폴백 (QA 한정).

## Change Request - 2026-06-16 - [CR-A2] Bad Ending Branch Policy for Severe Player Incivility

Status: Open. CR-A1 의 후속 분기 정책 정의.

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer B

### Reason

`incivility.tier == 3` (욕설·혐오·위협) 발화 시 NPC 만 거칠게 응답하고 게임은 정상 진행되는 반쪽 상태가 됩니다. Alpha 디자인 노트(`docs/handoff.md` "Developer C Alpha Plan Notice") 에 이미 명시된 "dangerous words can trigger an immediate bad ending" 정책의 정식 분기 구현이 필요합니다.

### Proposed Contract Change

1. `incivility.tier == 3` 발화가 들어오면 즉시 bad ending 분기로 라우팅:
   - `DevBPolicyOutput.branch.next_node_id = "<CHAPTER>_BAD_END_VERBAL_ABUSE"` (CR-A4 노드 사양 참고)
   - 기존 `branch_type` enum 확장이 부담스러우면 `branch_type = "fail"` 재사용 + `dialogue_directive.reason = "verbal_abuse"` 로 식별 가능.
   - `state_delta` 에 페널티 점수 (정책에 따라 -2 등).
   - `out_game_feedback.reason = "verbal_abuse"` 메타 첨부.
2. `incivility.tier == 2` 가 2턴 연속 반복되면 동일 분기 (정책 결정).
3. `final_result` 호출 시 bad ending 사유가 학습 리포트에 노출 (학습용 피드백).

### Compatibility Impact

CR-A4 의 시나리오 노드가 없으면 라우팅 실패. CR-A4 와 동시 머지 권장. `branch_type` enum 미확장 시 schema 변경 없음.

### Temporary Workaround

정책 머지 전까지 A 는 거친 응답만 하고 분기는 정상 노드로 진행. UX 상 "NPC 가 화는 내지만 게임은 계속 진행" 상태로 시연 가능.

## Change Request - 2026-06-16 - [CR-A3] Forward `incivility` from C Adapter to A-Facing Payload

Status update 2026-06-16: Implemented by Developer C. `DevANpcDialogueClient`
now forwards top-level `incivility` to the A-facing level-design payload and
uses a safe tier 0 default when older mock Understanding objects omit the field.

Status: Open. CR-A1 신호의 A 측 전달 경로 확보.

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer C / Sean Han

### Reason

CR-A1 에서 Understanding Agent 가 `incivility` 를 산출해도, C 어댑터가 A-facing payload 에 전달하지 않으면 A 측 Profanity Mirror 모드가 동작하지 않습니다. A 측 코드(`npc_dialogue_agent.py:218`)는 이미 `payload.get("incivility") or {}` 로 수신부가 준비되어 있습니다.

### Proposed Contract Change

`backend/app/integrations/dev_a_npc_dialogue_client.py` 의 `_build_level_design_payload` 가 Understanding 결과의 `incivility` 객체를 A-facing payload 최상위에 forward 합니다.

```python
return {
    ...,
    "incivility": (
        payload.understanding.incivility.model_dump()
        if payload.understanding.incivility is not None
        else {"tier": 0}
    ),
}
```

- 기본값 `{"tier": 0}` 으로 안전 폴백.
- A는 추가 변경 불필요.

### Compatibility Impact

Additive. A 측 `npc_dialogue_agent.py:218` 가 이미 `or {}` 로 안전 처리되어 기존 동작 무영향.

### Temporary Workaround

A 측 `incivility_classifier.py` 단독 분류 (payload 비어있을 때만) 또는 dev override 환경변수.

## Change Request - 2026-06-16 - [CR-A4] Add Bad Ending Scenario Nodes for Verbal Abuse

Status: Open. CR-A2 분기가 라우팅할 종착 노드 신설.

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer B

### Reason

CR-A2 의 bad ending 분기가 라우팅할 대상 노드(`*_BAD_END_VERBAL_ABUSE`)가 `scenario_nodes.json` 에 존재하지 않습니다. A 가 종결 대사를 일관되게 생성하려면 표준 메타(`npc_role`, `npc_question_goal`, `chapter_id`, `node_type`)가 필요합니다.

### Proposed Contract Change

`backend/app/data/scenario_nodes.json` 에 다음 노드를 추가합니다.

| 노드 ID                       | chapter_id                 | npc_role            | npc_question_goal  |
| ----------------------------- | -------------------------- | ------------------- | ------------------ |
| `FLIGHT_BAD_END_VERBAL_ABUSE` | `CH0_01_FLIGHT_SMALLTALK`  | seatmate            | `closing_eviction` |
| `IMM_BAD_END_VERBAL_ABUSE`    | `CH0_03_IMMIGRATION_CHECK` | immigration_officer | `closing_eviction` |
| `BAG_BAD_END_VERBAL_ABUSE`    | `CH0_04_BAGGAGE_CLAIM`     | customs_officer     | `closing_eviction` |

공통 사양:

- `node_type = "ending"`
- `next_action = "COMPLETE_CHAPTER"`
- `transition.unreal_event = "SHOW_BAD_END_SCOREBOARD"` (Unreal 측 컷씬/스코어보드 트리거)
- `transition.next_chapter_id = "CH0_05_RESULT"` (또는 동등)
- `objective_kr = "강제 종료 — 무례한 발언으로 인한 절차 중단"`
- `branch_candidates` 는 모두 `null` 또는 동일 ID (종착 노드)
- `required_slots = []`
- 각 NPC role 에 어울리는 짧은 `npc_question` 시드 (A는 이를 그대로 사용하지 않고 페르소나 기반 종결 대사 생성)

### Compatibility Impact

Additive node 추가. 기존 분기/노드 무영향. CR-A2 의 `branch.next_node_id` 와 1:1 매핑.

### Temporary Workaround

Bad ending 노드 미생성 시 A 는 기존 `COMPLETE_CHAPTER` 처리 로직으로 평이한 종결 대사 합성 (게임 종료 사유 미표시).

## Change Request - 2026-06-16 - [CR-B-SMALLTALK] 기내 스몰토크 적응형 진단 전환: Dev A 반응형 대사·coherence guard + Dev C 슬롯 완화

Status: Open (Dev B 구현 완료 / Dev C 슬롯 완화 및 OpenKB 세션 누적 회귀 테스트 반영 완료 / Dev A 반응형 대사 및 coherence guard 후속 필요). `docs/workplan-dev-b.md`(기내 스몰토크 적응형 진단 전환, C안)의 §4/§10 타 팀 의존 항목.
Status: Implemented (Developer A 및 Developer B 구현 완료 / Developer C 미반영). `docs/workplan-dev-b.md`(기내 스몰토크 적응형 진단 전환, C안)의 §4/§10 타 팀 의존 항목.

- Developer A 구현 완료 (2026-06-17) - 반응형 대사, coherence guard, missing_followup_question 해제, 중립 폴백 반응 완료.

### 구현 반영 (2026-06-17) — 계획 대비 변경점

- **폴백 대사 삭제(게임성 사유):** A가 정책이 넘긴 폴백 문장(`seed_text`)을 그대로 모방해
  **매 턴 같은 대사를 반복** → AI와 대화하는 느낌이 사라지는 문제가 관찰되어, Dev B는
  `FlightSmallTalkDiagnosticPolicy.fallback_question` 과 `FALLBACK_QUESTIONS` 를 **제거**했다.
  `seed_text` 는 probe 뱅크(`flight_smalltalk_probes.json`)에 남아 있으나 **A로 전달되지 않는다**
  (저자/디버그 참고용). → CR 본문의 "seed_text 폴백" 표현은 모두 무효이며, 아래 "폴백 대사 없음"
  규약으로 대체한다.
- **`surface_goal` 포맷 변경:** 진단 씬에서 `dialogue_seed.surface_goal` 은 노드 고정 질문이
  아니라 **의도 문자열 `{target_competency}_{topic_tag}`**(예: `travel_purpose_travel`)로 들어온다.
- **신규 계약 필드:** `DialogueDirective.topic_switch: bool|None`, `DialogueDirective.length_target: int|None`,
  `DialogueSeed.cumulative_confidence: float|None`, `LevelHint.cumulative_confidence: float|None`
  (`game_turn.py`). 모두 additive(Optional).
- **종료/턴 계수 의존성:** 컨트롤러는 OpenKB 세션 이력(`read_session_records(session_id)`)을 읽어
  `FLIGHT_` 레코드 수로 턴을 세고 신뢰도를 누적한다(§Dev C 통합 의존성 참조).

### Requested By

Developer B

### Affected Owner

Developer A / kimyonghee, Developer C / Sean Han

### Reason

기내 스몰토크 씬(`FLIGHT_A_001_SEATMATE_SMALLTALK`)을 15개 고정 노드(A/B/C × 5턴)에서
**단일 self-loop 진단 노드 + probe 뱅크 + 적응형 컨트롤러**로 전환한다(C안). Dev B는
분기/진행/probe 선택/종료를 결정적으로 소유하지만, 다음 두 가지가 남으면 "취조 느낌"과
역할 반전이 그대로 남는다.

- 증상 1: 플레이어가 펜을 빌려줬는데 NPC가 `"Sure, here you are."`(빌려주는 쪽 대사)로
  역할 반전 → 원인은 player 관점 `npc_question_goal`이 `surface_goal`로 흘러 NPC를
  응답자로 오인시킴. Dev B가 진단 노드에서 이 경로를 probe 의도로 대체하지만, Dev A가
  여전히 `surface_goal` 고정 질문만 읽으면 자연 대화가 안 된다.
- 증상 2: Dev A가 매 턴 질문을 강제(`missing_followup_question`)해 반응-only 턴이
  금지되고, 직전 발화를 무시한 맨 질문이 통과된다.

경계: **분기·진행·probe 선택·종료·verdict·다음 노드는 Dev B(규칙 기반).** Dev A는
선택된 probe 의도를 받아 **표면 대사 wording 과 출력 단계 coherence 검증**만 담당.
Dev C는 자유 발화를 임의 슬롯으로 채우지 않도록 추출을 완화.

### Proposed Contract Change

**Dev A:**

- 진단 씬(`dialogue_directive.purpose="smalltalk_diagnostic"`)에서:
  - **반응-먼저-탐색** 구조 강제: NPC 턴 = `[직전 발화 반응] + [연결] + [후속 의도]`.
    probe를 단독 질문으로 내보내지 않는다.
  - `missing_followup_question` 에러/매 턴 질문 강제 **해제** → 반응-only 턴 허용.
  - `SURFACE_GOAL_QUESTIONS` 고정 큐 **비활성** → `surface_goal` 은 이제 고정 질문이 아니라
    **의도 문자열 `{target_competency}_{topic_tag}`**(예: `travel_purpose_travel`,
    `future_plan_travel`)로 들어온다. A는 이를 **그대로 발화하지 말고** 직전 발화 반응 +
    해당 역량을 끌어내는 자연 후속으로 생성한다.
  - **폴백 대사 없음(중요):** Dev B가 반복 문제로 `fallback_question`/`FALLBACK_QUESTIONS` 를
    삭제했고 `seed_text` 는 A에 전달되지 않는다. 따라서 A는 **반드시 생성**하며, LLM 실패
    시에도 고정 질문 사다리로 회귀하지 말고 **매번 달라지는 generic 중립 응답**(예: 직전
    발화를 짧게 받아주는 한 문장)으로만 폴백한다.
  - `recommended_expression`/교정 표현을 **라이브 대사에 삽입 금지**(피드백은 out-game).
  - **coherence guard 신설**: `npc_dialogue_agent.py:308-322` 의 가드 패턴과 동일하게,
    플레이어 실질 발화에 대해 (a) 반응 없는 맨 질문, (b) 직전 발화와 비연결(non-sequitur)
    인 NPC 턴을 reject → 재생성 또는 generic 중립 폴백(반복 금지).
  - `dialogue_directive.length_target` 에 따른 **길이 미러링**(하한/상한 둔).
  - **대화 메모리**: 다룬 화제·NPC가 밝힌 정보를 추적해 재질문 방지 및 콜백.
  - `dialogue_directive.topic_switch=True` 신호 시 명시적 전환구("Anyway,", "By the way")
    를 붙여 화제 전환.
  - `branch_reason="flight_smalltalk_continue"` 신호 시 성공-축하형이 아닌 중립 반응 렌더.
- 제거되는 노드를 참조하는 테스트(`FLIGHT_A_005_WRAP_UP`, `FLIGHT_B_002_COMPANION_OR_VISIT`,
  `FLIGHT_C_004_HOTEL_HOSTEL` — `backend/tests/test_developer_a_npc_dialogue.py`) 를
  단일 진단 노드 기준으로 갱신.

**Dev C:**

- 스몰토크 씬에서 슬롯 강제 추출/오인식 완화 — 자유 발화를 임의 `required_slot` 값으로
  채우지 않는다. (진단 노드 `FLIGHT_A_001` 에 `required_slots:["polite_response"]`,
  `recommended_expression:"Sure, here you are."` 가 레거시로 남아 있으나 진단 분기는 슬롯
  충족을 진행 조건으로 쓰지 않는다 — C 어댑터가 이 잔여 슬롯을 강제 추출 대상으로 삼지 않도록.)
- **통합 의존성(중요):** 적응형 컨트롤러의 턴 계수·신뢰도 누적은 **OpenKB 세션 이력**에
  의존한다 — `OpenKBFinalResultRecordReader.read_session_records(session_id)` 로 읽은
  `FLIGHT_` 레코드 수가 곧 진행 턴이고, 각 레코드의 `understanding.confidence`,
  `evaluation.verdict`, `dialogue_seed.surface_goal` 로 신뢰도와 used-probe/현재 토픽을
  계산한다. 오케스트레이터가 **매 턴 이 레코드를 OpenKB에 적재**하지 않으면 턴이 1로 고정되어
  신뢰도가 누적되지 않고 `MAX_TURNS`(7) 종료도 트리거되지 않아 **종료 불가** 위험이 있다.
  C는 진단 씬에서 턴별 세션 레코드 적재를 보장해야 한다.
- 데모 `demo/respond-dialog/index.html` 는 진단 노드 ID(`FLIGHT_A_001_SEATMATE_SMALLTALK`)
  를 **유지**하므로 변경 불필요. (노드 ID가 바뀌는 경우에만 `firstNodeId` 갱신.)

### Compatibility Impact

- `branch_type` enum 미확장(중립 진행은 `success`+`ADVANCE` 재사용). Agent A `BranchType`,
  `game_turn.py`, Dev C 어댑터 파급 없음.
- 노드 제거는 기내 씬 한정 — `IMM_*`/`BAG_*` 채점 분기·테스트 회귀 없음.
- coherence guard 는 기존 가드와 동일한 에러-폴백 경로라 additive.
- Dev A 미반영 시: Dev B 컨트롤러는 동작하나 표면 대사가 여전히 고정 질문이라 자연스러움
  개선이 제한됨(아래 우회).

### Temporary Workaround

폴백 대사가 제거되었으므로 "고정 질문 노출" 우회는 더 이상 쓰지 않는다(반복 대사 문제의
원인이었음). Dev A 반영 전까지는 기존 LLM 생성 경로가 그대로 동작하되, surface_goal 의도
문자열을 A가 자연 후속으로 못 풀면 어색할 수 있다 — 이때도 **고정 질문 사다리로 회귀하지
않는다.** 진단 진행·종료(턴 상·하한, 신뢰도)는 OpenKB 세션 레코드만 적재되면 정상 동작한다.

## Change Request - 2026-06-17 - [CR-B-EOKKKA] 억까 장소·수화물 레벨별 배정

Status: Resolved (Developer C implementation complete - 2026-06-17).

Developer C follow-up:
- `DialogueSeed.challenge_context` is now the preferred A-facing Eokkka metadata field.
- Existing flat location/item metadata fields remain for backward compatibility while A migrates.
- C preserves an already assigned location/customs item and only picks a new value at the transition point when the `GameState` field is empty.

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han (스키마·배선·영속화), Developer A / kimyonghee (NPC 트집 대사),
Unreal (입국신고서 UI·BAG_006 reveal)

### Reason

입국심사 "억까 장소 리스트"와 세관 "억까 수화물 리스트"를 플레이어의 진단 레벨(TSL)에
맞춰 난이도 구간별로 랜덤 배정한다(잘할수록 어려운 억까로 난이도 유지). 난이도 1~12는
루브릭 total(0~12)과 동일 척도라 추가 변환 없이 직접 매핑된다.

배정은 두 책임으로 분리된다:

- **(가) 픽 규칙** — "TSL_3이면 난이도 7~9 풀에서 랜덤"이라는 밸런스 로직.
- **(나) 픽 실행 + 영속화** — 실제 선택·GameState 기록·턴 간 유지·Unreal 전달·NPC 대사.

확정 방향(1번 안): **(가)는 Dev B 소유**(밸런스 단일 소스, 유닛 테스트로 닫음),
**(나)는 Dev C/A/Unreal 소유**. 픽 규칙을 코드 밖(CSV/문서)으로 빼면 TSL 경계가 B·C
두 곳에 중복돼 "레벨 7인데 난이도 11" 같은 붕괴가 조용히 발생하므로, 픽 규칙은 B 코드에
둔다.

**Dev B가 한 일**(이 CR 발행 시점에는 작업계획 확정, 구현은 후속):

- `backend/app/services/service_b/tier_difficulty_controller.travel_speaking_level_for_total`
  의 TSL 경계(0-3/4-6/7-9/10+)를 그대로 재사용하는 난이도 구간 맵
  `TSL_TO_DIFFICULTY_RANGE` 정의.
- 신규 데이터 테이블 `backend/app/data/challenge_tables.py`(장소 17종·수화물 18종,
  난이도·en/ko·category·suspicion_reason 태깅) + 순수함수 픽 서비스
  `backend/app/services/service_b/challenge_assignment_service.py`
  (`pick_location(tsl, rng)`, `pick_customs_item(tsl, rng)`, 빈 풀 인접 구간 폴백,
  C 경계 변환 헬퍼 `to_random_customs_item_context`).
- B는 C 스키마 확장 전에도 **자체 dataclass로 테이블·픽을 완성·유닛 테스트**한다(디커플링).

### Proposed Contract Change

`Dev C:`

1. **스키마 확장**(`backend/app/schemas/game_turn.py`, 모두 additive·옵셔널):
   - `RandomCustomsItemContext` 에 `difficulty: int | None = None`,
     `suspicion_reason: str | None = None` 추가.
   - `GameState` 에 `assigned_visit_location: str | None`,
     `assigned_visit_location_ko: str | None`,
     `visit_location_difficulty: int | None`,
     `visit_location_suspicion_reason: str | None` 추가.
   - `DialogueSeed` 에 억까 사유 전달 필드 추가(또는 기존 필드 재활용 합의) —
     배정된 장소/품목의 `suspicion_reason`·식별자·difficulty 가 A로 흘러가게 한다.
2. **픽 실행**(전환 노드 처리):
   - `FLIGHT_999_COMPLETE`(CH0_01→CH0_02) 처리 시 `pick_location(<기내 진단 확정 TSL>)`
     호출 → `GameState.assigned_visit_location*` 기록. 입국심사(CH0_03) **전**에 확정돼야
     입국신고서에 노출된다.
   - `IMM_999_CLEARED`(CH0_03→CH0_04, `ENTER_BAGGAGE_CLAIM`) 처리 시
     `pick_customs_item(<입국심사로 조정된 TSL>)` 호출 →
     `GameState.random_customs_item` 기록. BAG_006 **전**에 확정돼야 reveal 가능.
3. **영속화**: 배정값을 다음 턴까지 유지하고, 입국신고서·`BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`
   로 Unreal 에 전달.

`Dev A:`

- 배정된 장소/품목의 `suspicion_reason` 의도대로 NPC 트집(억까) 대사를 LLM 생성한다.
  B 의 고정 질문/정답 예문은 `dev_a_npc_dialogue_client._A_BLOCKED_*` 로 차단되므로,
  억까 사유는 **`dialogue_seed` 메타로만** 받는다(고정 질문 모방 금지).
- 입국신고서에 표기된 장소와 NPC 대사가 **동일 장소를 지칭**하도록 유지.

`Unreal:`

- 입국신고서 UI 에 `visit_location`(en, 필요 시 ko) 표시.
- `BAG_006` 도달 시 배정된 수화물 시각 reveal.

### Compatibility Impact

- 스키마 변경은 전부 additive·옵셔널 → 구버전 요청은 필드 생략 그대로 유효, 기존
  `IMM_*`/`BAG_*` 채점 분기·테스트 회귀 없음.
- 픽 규칙은 기존 TSL 경계를 재사용하므로 난이도 정책 단일 소스 유지.
- **데이터 갭**: 억까 장소 리스트에 난이도 3 항목이 없음(수화물은 1~12 전 구간 분포).
  TSL_1 구간(1~3) 장소 풀은 난이도 1·2만으로 구성 → 픽 함수의 빈 풀 인접 구간 폴백으로
  흡수. 데이터 보강이 바람직하면 별도 데이터 과제로 분리.
- Dev C 스키마 미반영 시: B 픽 함수는 자체 dataclass 로 동작·테스트되나, GameState
  기록·Unreal 전달·A 대사 연동은 불가(아래 우회).

### Temporary Workaround

Dev C 스키마·배선 반영 전까지 B 픽 함수는 독립 유닛 테스트로만 검증한다. 런타임 배정·
영속화·대사 연동은 C 반영 후 활성화. 그 전에는 기존처럼 `RandomCustomsItemContext` 가
Unreal/외부에서 채워지면 그대로 사용(소유 모호 상태 유지).

## Change Request - 2026-06-17 - AgentRun Failure Logs Must Include Structured Error Details

### Owners

Developer A / kimyonghee, Developer B / policy owner, Developer C / Sean Han

### Problem

During realtime `/respond` testing, Developer A returned an NPC dialogue
fallback with `llm.reason="ValueError"`, but the AgentRun record did not include
the actual exception message. Developer C could prove that the fallback was
triggered inside Developer A's LLM dialogue path, but could not determine
whether the root cause was structured output validation, prompt rendering,
provider setup, or another A-owned validation step.

The same debugging gap can happen in any A/B/C agent if an AgentRun stores only
an exception type or a generic fallback reason.

Related contract note:

- `candidate_text` is no longer a live input that Developer A should consume.
  It is the old A-side normalized form of B's `npc_recast_line_candidate`.
- Developer B should not send `npc_recast_line_candidate` as NPC wording for
  Developer A to speak. B-owned recommended expressions remain learning/UI
  data, not live NPC dialogue.
- Developer C currently strips B-authored `npc_recast_line_candidate` before
  the A-facing payload. If `candidate_text` still reaches Developer A, that
  should be logged as a contract violation with structured `error_details`,
  not treated as normal dialogue input.

### Requested Contract

Each agent should write structured failure details whenever a tool, LLM call,
validator, fallback, or graph node fails.

Required fields:

- `error_type`: exception class name or stable failure code.
- `error_message`: sanitized human-readable message from the failing layer.
- `phase`: stable phase name, for example `npc_dialogue_llm`,
  `developer_b_feedback_llm`, `understanding_llm`, or `developer_c_langgraph`.
- `tool_name`: the tool or internal component that failed.
- `fallback_used`: whether the agent recovered through fallback.
- `fallback_reason`: stable fallback reason, if fallback was used.
- `input_summary`: safe, compact input summary that excludes API keys and raw
  long audio.

Recommended optional fields:

- `provider`: provider name such as `openai`, `elevenlabs`, `rule`, or
  `local_batch_fallback`.
- `model_name`: model attempted at the failed step.
- `retry_count`: retry attempt count if the client retried.
- `safe_context`: short context needed to reproduce the failure.

### Developer A Request

When `npc_dialogue_agent` falls back from the LLM path, please record the
underlying exception message in the Developer A AgentRun. The current output
shape:

```json
{ "llm": { "used": false, "fallback_used": true, "reason": "ValueError" } }
```

should be expanded with a structured detail block such as:

```json
{
  "llm": {
    "used": false,
    "fallback_used": true,
    "reason": "ValueError",
    "error_details": {
      "error_type": "ValueError",
      "error_message": "sanitized exact message",
      "phase": "npc_dialogue_llm",
      "tool_name": "agent_a.npc_dialogue_agent.generate_dialogue_llm"
    }
  }
}
```

Also, please keep treating `candidate_text` as deprecated input. If it appears,
record a structured failure/fallback detail that says the payload contained the
forbidden deprecated field, including the sanitized `error_message`.

### Developer B Request

Developer B already records several `fallback_reason` values for feedback LLM
fallback. Please keep that behavior and also include the same structured
`error_details` block for any failed policy graph tool, feedback/hint LLM call,
forbidden-key rejection, OpenKB write failure, or validation failure.

Also, please do not rely on `npc_recast_line_candidate` or `candidate_text` as
the path for live NPC dialogue. Use `dialogue_seed`, branch metadata, evaluation
summary, and learning feedback fields instead; C will continue stripping
B-authored dialogue candidates before calling A.

### Developer C Status

Developer C updated C-owned logging so failed C LangGraph runs and Understanding
LLM fallback traces include structured `error_details`. C did not modify A/B
implementation files.
