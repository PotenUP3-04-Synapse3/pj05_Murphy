# Developer B 작업계획서 — 입국심사·세관 대화 자연스러움 복구

- 작성일: 2026-06-18
- 작성자: Developer B
- 대상 문제: alpha QA에서 입국심사(CH0_03)~세관(CH0_04) 대화가 무너진다.
  같은 질문 무한 반복, 플레이어가 말하지 않은 정보 호출("Downtown Luxury
  Hotel"), 답변과 무관한 노드로 채점되는 노드-질문 desync, 신고검사에서
  "clear answer"만 끝없이 요구하는 데드락.
- 방향(확정): **단기기억(히스토리)이 필요조건, 트집(suspicion) 게이팅이
  충분조건. 둘 다 필요하다.** 추가로 B 상태머신의 무한 clarify 루프 탈출과
  시나리오 노드 참조 무결성을 B가 닫는다.
- 소유 경계(1번 안 유지): **규칙·노드·상태머신은 B, 스키마·영속화·이해(C),
  대사·프롬프트(A).** 본 건도 B가 단독으로 닫을 항목과 A/C 변경요청을 분리한다.

> 직전 작업계획서(억까 장소·수화물 레벨별 배정, CR-B-EOKKKA)는 완료되어
> `docs/handoff.md`(2026-06-17)와 본 문서 §14.7 누적 포트폴리오에 기록되어 있다.
> 본 계획서는 그 위에서 발생한 **대화 품질 회귀**를 다룬다.

---

## 1. 진단 요약 (증상 → 근본원인 → 오너)

QA 대화 로그 1건(입국심사 전 구간 + 신고검사 데드락)을 코드까지 역추적한 결과,
증상은 서로 다른 3개 축의 결함이 겹친 것이다.

### 1.1 단기기억(히스토리) 미연결 — **오너: C(조립·영속화) + A(소비)**

- `npc_dialogue_agent.py:316-333`에서 `discussed_topics` / `past_player_utterances`는
  `purpose == "smalltalk_diagnostic"`일 때만 채워진다. 입국심사·세관 노드에서는
  항상 빈 리스트이고, A에 넘기는 `llm_payload`(`:342-383`) 어디에도 대화
  히스토리 필드가 없다. → NPC는 매 턴 stateless.
- 스키마에는 `PreviousNodeResult`(`game_turn.py:141`)와
  `GameState.completed_intents`가 이미 있으나, **player_text / npc_text / 채워진
  슬롯을 담지 않아** 대화 내용 기억으로는 못 쓴다.
- 증상: 호텔이라 답했는데 또 "Where will you stay?", 이미 답한 주제 재질문.

### 1.2 트집(SUSPICION MODE) 무차별 적용 — **오너: A(프롬프트) + B(노드 스코프 신호)**

- `prompts/npc_dialogue_prompt.md:80`의 `{% if assigned_visit_location or
  random_customs_item %}` 블록은 **할당만 되면 모든 입국심사 노드에서 True**다.
  Rule 3(`:103`)이 "visit_location string must appear **verbatim**"을 강제 →
  방문 목적 노드인데도 "Downtown Luxury Hotel"이 박힌다.
- 이 블록은 CR-B-EOKKKA의 Dev A 산출물(`handoff.md` 2026-06-17)로, 설계상
  verbatim 강제였다. **제거가 아니라 게이팅**이 답이다.
- 더 깊게: 진짜 "트집"("MGM Grand? 출장치곤 고급인데?")은 *플레이어가 말한
  목적*과 *할당된 장소*의 cross-turn 대조가 필요하다 → **히스토리 없이는
  트집이 불가능**하고 지금은 할당값을 블러팅만 한다. 그래서 §1.1이 §1.2의
  전제조건이다.

### 1.3 무한 clarify 루프 + 노드 참조 무결성 — **오너: B (단독)**

- `scenario_state_machine.py:67-78` `decide()` 순서: `_is_unclear` → clarify가
  `_should_give_hint`보다 **먼저** 평가된다. `needs_clarification=True`가 지속되면
  clarify로만 빠지고 hint 에스컬레이션(`retry_count>=2`, `:158`)은 **도달 불가
  데드코드**. retry_count는 매 턴 +1 되지만 아무도 그것으로 탈출시키지 않는다.
- 대화 루프에 **patience 바닥 탈출구가 없다.** patience는 최종 스코어보드
  (`final_result_score_policy.py:247`)에서만 평가된다. `_critical_fail`은 risk
  태그/수치로만 발동.
- clarify/retry 타겟 노드가 **정의되지 않았다.** `scenario_nodes.json`에 24개
  노드만 있는데 `allowed_next_nodes`/`branch_candidates`가 참조하는
  `IMM_EXTRA_005_CLARIFY_DECLARATION`, `IMM_006_RETRY_DECLARATION`,
  `END_SECONDARY_INSPECTION` 등 **35개+가 미정의**. REASK가 유령 노드를 가리켜
  결국 같은 노드에 머무르며 동일 대사를 반복한다.
- `IMM_006_DECLARATION_CHECK`의 정적 `npc_question`("small boat motor")과
  보트모터용 `allowed_slot_values`는 프로토타입 잔재. 실제 신고품은 런타임
  랜덤(`random_customs_item`, 김치 등)인데 슬롯 허용값/`hint_policy`가
  품목 무관이라 어떤 품목도 통과 불가.

### 1.4 노드-질문 desync — **오너: B(seed surface_goal) ↔ C(node_context 전달) 경계, 조사 필요**

- 로그상 여권 직후 officer가 "where are you staying?"(=IMM_004 질문)를 물었는데
  분기는 `IMM_001 → IMM_002_PURPOSE`. 즉 A가 만든 후속 질문이 B의 실제 다음
  노드 surface_goal과 한 칸 어긋난다.
- `surface_goal = node_context.npc_question_goal`
  (`english_level_hint_agent.py:708`). seed가 가리키는 노드와 다음 답변이
  채점되는 노드가 일치하는지 B/C 경계에서 검증해야 한다.

### 1.5 증상-원인 인과 체인

```
랜덤 김치 주입(품목 무관 슬롯, §1.3)
  → C 이해가 item_purpose 못 채움 → needs_clarification 고정
  → B: _is_unclear 항상 True → 항상 clarify(hint 도달 불가, §1.3)
  → clarify 타겟 유령 노드 → 같은 노드 그대로(§1.3)
  → patience 탈출구 없음(§1.3)
  → A: 히스토리 없음(§1.1) + 트집 verbatim 무차별(§1.2)
  = 없는 호텔 호출 + 동일 질문 무한 반복 + 갑작스런 김치
```

---

## 2. 핵심 설계 결정

1. **히스토리 먼저.** 단기기억이 없으면 트집 게이팅을 고쳐도 트집 로직이
   빈손이다. C가 직전 N턴(player_text/npc_text/채워진 슬롯)을 조립·영속화하고
   A가 모든 노드에서 소비한다. (§9 CR-B-CONV-C / §10 CR-B-CONV-A)
2. **트집은 제거가 아니라 게이팅.** 억까는 게임의 핵심 재미다. (a) 관련
   노드에서만 활성, (b) 플레이어가 답한 *후*에만 발동, (c) verbatim 하드룰
   완화. 활성 여부 신호는 **B가 노드 메타로 제공**, A가 소비.
3. **무한 루프는 B가 단독으로 닫는다.** clarify/retry/hint 에스컬레이션 순서
   교정 + patience/retry 상한 탈출 + 노드 참조 무결성(유령 노드 제거/정의).
4. **신고검사 노드는 품목-카테고리 구동으로 일반화.** 보트모터 잔재 제거,
   food/medicine 등 카테고리별 허용 용도·힌트 제공. (B 데이터 + C 이해 키워드)
5. **노드-질문 동기화는 조사 후 결정.** seed surface_goal과 채점 노드의
   off-by-one을 B/C 합동으로 재현·수정(§4 작업 6).

---

## 3. 범위

### 포함 (Dev B 소유, 단독 진행 가능)

- `service_b/scenario_state_machine.py` — `decide()` 분기 순서 교정, clarify/retry
  상한 후 hint→advance/bad_end 에스컬레이션, patience 바닥 탈출 가드.
- `backend/app/data/scenario_nodes.json` —
  - 참조-미정의 노드 해소(정의 또는 self-loop 설계로 유령 참조 제거).
  - `IMM_006_DECLARATION_CHECK` 보트모터 잔재 제거, 품목-카테고리 구동 허용값/
    `hint_policy`로 일반화.
  - `END_SECONDARY_INSPECTION` 등 종료/경고 노드 정의.
- B→A seed 경로(`tool_b` 정책 그래프): 트집 활성 스코프 신호
  (`suspicion_scope`: `location` / `declaration` / `none`)를 `dialogue_seed`에 emit.
- 노드-질문 desync 재현·근본원인 격리(§4 작업 6) 중 B 소유분(seed surface_goal).
- 테스트: `backend/tests/dev_b/test_scenario_state_machine_loop_exit.py`(신규),
  `test_scenario_nodes_referential_integrity.py`(신규),
  `test_developer_b_policy_engine.py`/`test_dev_b_bad_ending_branch.py` 회귀.

### 제외 (타 팀 → §9/§10 변경요청)

- **Dev C**: 히스토리 스키마 확장 + 턴 조립/영속화 + A 전달, 이해 에이전트
  `item_purpose` 키워드/주소 추출, 트집 스코프 신호의 dialogue_seed sync 타이밍.
- **Dev A**: SUSPICION MODE 게이팅(스코프 신호 소비 + 답변 후 발동 + verbatim
  완화), 히스토리 프롬프트 소비(전 노드), stern/retry 대사 변주·recast.
- **Unreal**: 입국신고서 UI, BAG reveal (기존 CR 유지).
- env, TTS/음성.

---

## 4. 작업 항목 (Dev B 소유)

### 작업 1 — 무한 clarify 루프 탈출 (최우선)

- `decide()`에서 동일 노드 누적 `retry_count`/patience를 먼저 검사해
  상한(예: clarify 2회) 초과 시 **clarify→hint, hint 후에도 미해결이면
  강제 ADVANCE 또는 bad_end**로 에스컬레이션. `_is_unclear`가 hint를 가리지
  않도록 순서/조건 교정.
- patience 바닥(`<=0`) 시 대화 루프 내에서 탈출 분기 추가(`_critical_fail`
  또는 전용 timeout 분기). 채점 권위는 그대로 유지.
- 회귀: 정상 clarify→해결 경로는 보존(트레이스의 IMM_002/IMM_004처럼 슬롯이
  채워지면 즉시 ADVANCE).

### 작업 2 — 시나리오 노드 참조 무결성

- 모든 `allowed_next_nodes`/`branch_candidates` 타겟이 `nodes`에 존재하는지
  검증하는 테스트 추가, 위반 35개+ 해소.
- 설계 선택: clarify/retry를 **현재 노드 self-loop**(REASK가 같은 노드에서
  다시 질문)로 단순화하거나, 필요한 EXTRA/RETRY 노드를 실제 정의. self-loop가
  데이터 단순성·유지보수에 유리하므로 1차 권장.
- `END_SECONDARY_INSPECTION`/종료·경고 노드 정의.

### 작업 3 — 신고검사 노드 일반화 (보트모터 잔재 제거)

- `IMM_006_DECLARATION_CHECK`의 정적 `npc_question`/보트모터 `allowed_slot_values`
  제거. 신고품은 `random_customs_item`이 단일 소스.
- 품목 카테고리별 허용 용도 도입(food→`personal_consumption`, medicine→
  `personal_health`, 등) + `hint_policy.keyword`에 카테고리별 표현 추가.
  (실제 키워드 매칭은 C 이해 에이전트와 합의 — §9)

### 작업 4 — 트집 스코프 신호 emit

- `tool_b` 정책 그래프에서 노드별 `suspicion_scope`(`location`/`declaration`/
  `none`)를 `dialogue_seed`에 실어 A가 관련 노드에서만 트집을 켜도록 한다.
  (A 소비는 §10)

### 작업 5 — 히스토리 입력 활용 (B 측)

- 히스토리가 생기면(§9) B의 `_is_unclear`/슬롯 판정이 직전 턴에서 이미
  채워진 슬롯(`completed_intents`/filled slots)을 재요구하지 않도록 보정.

### 작업 6 — 노드-질문 desync 조사·수정

- seed `surface_goal`이 "다음 답변이 채점될 노드"와 일치하는지 재현 테스트.
  off-by-one이면 B 측 seed 생성 시점 또는 C의 node_context 전달 시점을
  합동 격리(§9에 C 몫 분리).

---

## 5. 테스트 계획

신규 `backend/tests/dev_b/test_scenario_state_machine_loop_exit.py`:

- `test_clarify_escalates_to_hint_after_cap`: 동일 노드 clarify 2회 후 hint.
- `test_unresolvable_slot_force_advances_or_bad_ends`: 채울 수 없는 슬롯이
  무한 반복되지 않고 상한 내 종료 분기로 빠진다.
- `test_patience_floor_exits_dialogue_loop`: patience<=0이면 루프 탈출.
- `test_normal_clarify_then_resolve_still_advances`: 슬롯이 채워지면 즉시 ADVANCE
  (회귀, 정상 경로 보존).

신규 `backend/tests/dev_b/test_scenario_nodes_referential_integrity.py`:

- `test_all_branch_targets_are_defined`: 모든 분기/allowed-next 타겟이 노드로 존재.
- `test_declaration_node_has_no_prototype_residue`: IMM_006에 보트모터 잔재 없음.

회귀: `test_developer_b_policy_engine.py`, `test_dev_b_bad_ending_branch.py`,
`test_scenario_nodes_bad_ending.py`, `test_flight_smalltalk_diagnostic_policy.py`.

---

## 6. 검증 명령

```powershell
uv run pytest backend/tests/dev_b/test_scenario_state_machine_loop_exit.py
uv run pytest backend/tests/dev_b/test_scenario_nodes_referential_integrity.py
uv run pytest backend/tests/dev_b
uv run pytest
uv run ruff check .
uv run mypy .
```

---

## 7. 실행 순서 / 마일스톤

| 순서 | 작업 | 오너 | 차단 의존 |
|---|---|---|---|
| M1 | 무한 루프 탈출 + 노드 무결성(작업1·2) | **B** | 없음 (즉시 시작) |
| M2 | 신고검사 일반화(작업3) | **B** + C 키워드 | C 이해 키워드(§9) |
| M3 | 히스토리 스키마·조립·영속화 | **C** | 없음 |
| M4 | 히스토리 프롬프트 소비(전 노드) | **A** | M3 |
| M5 | 트집 게이팅(스코프 신호 emit/소비) | **B**(emit)+**A**(소비) | M3·M4 |
| M6 | 노드-질문 desync(작업6) | **B**+**C** | M1 |
| M7 | stern/retry 대사 변주·recast | **A** | M4 |

> M1은 의존 없이 B가 즉시 닫아 "무한 반복"이라는 가장 눈에 띄는 증상을 먼저
> 제거한다. M3(히스토리)는 M4·M5의 전제조건이므로 C가 병렬 착수한다.

---

## 8. 타 팀 의존 작업 (변경요청 요약)

상세 전문은 §9(Dev C), §10(Dev A), 핸드오프 초안은 §11에 둔다. §13 절차에 따라
`docs/contracts/change_requests.md`와 `docs/handoff.md`에 동기화한다.

- **Dev C**: 히스토리 스키마+조립+영속화+A전달, 이해 `item_purpose` 키워드/주소
  추출, 트집 스코프 신호 sync, desync 조사 C 몫.
- **Dev A**: SUSPICION MODE 게이팅, 히스토리 프롬프트 소비(전 노드), stern/retry
  변주·recast.

---

## 9. 변경요청 전문 — Dev C (CR-B-CONV-C)

> `docs/contracts/change_requests.md`에 추가할 전문.

```markdown
## Change Request - 2026-06-18 - [CR-B-CONV-C] 단기기억·이해·트집 스코프 (대화 복구)

Status: Open.

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
루프와 노드 무결성을 단독으로 닫지만, 위 3건은 C 경계다.

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
     존중해 location은 location 노드, item은 declaration 노드에서만 challenge_context를
     채우도록 게이팅.
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
```

---

## 10. 변경요청 전문 — Dev A (CR-B-CONV-A)

> `docs/contracts/change_requests.md`에 추가할 전문.

```markdown
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

트집 게이팅은 B의 `suspicion_scope` emit(§4 작업4)에 의존. 히스토리 소비는
C의 `dialogue_history`(CR-B-CONV-C)에 의존. 회귀 가드:
`test_developer_a_npc_dialogue.py`. 입국신고서 장소 동일 지칭은 location 노드
한정으로 유지.

### Temporary Workaround

없음. B의 상태머신 상한으로 무한 반복만 완화되며, 부자연스러운 verbatim 주입은
A 반영 전까지 잔존.
```

---

## 11. Handoff 초안 (M1 완료 시 `docs/handoff.md` 상단에 추가)

```markdown
## 2026-06-18 Developer B: 입국심사·세관 대화 무한 루프 탈출 + 노드 무결성

Developer B는 입국심사~세관 대화가 무너지는 QA 회귀를 진단하고, B 단독 소유분
(상태머신 무한 clarify 루프, 시나리오 노드 참조 무결성, 신고검사 노드 잔재)을
닫았다.

- 변경/산출물:
  - `scenario_state_machine.py` — clarify/retry 상한 후 hint→강제 ADVANCE/bad_end
    에스컬레이션, patience 바닥 탈출 가드.
  - `scenario_nodes.json` — 유령 참조 노드 35개+ 해소(self-loop 설계),
    IMM_006 보트모터 잔재 제거 및 품목-카테고리 구동 일반화,
    END_SECONDARY_INSPECTION 등 종료 노드 정의.
  - `tool_b` — 트집 스코프 신호 `suspicion_scope`를 dialogue_seed로 emit.
- 교차 의존: 단기기억·이해·트집 sync는 `[CR-B-CONV-C]`, 트집 게이팅·히스토리
  소비·대사 변주는 `[CR-B-CONV-A]`로 전달(`docs/contracts/change_requests.md`).
- 검증/후속: `uv run pytest backend/tests/dev_b` / `uv run pytest` /
  `ruff` / `mypy` 결과 첨부 예정. M2 이후는 C/A 반영 후 통합 회귀.
```

---

## 12. 포트폴리오 갱신 작업 (계획에 포함)

본 대화복구 작업이 마일스톤별로 완료되면 `docs/portfolio_dev_b.md`를 갱신한다.
포트폴리오는 **완료된 작업**을 기술하므로, M1 완료 시점에 1차 갱신한다.

추가할 항목(초안):

- **"Conversation Reliability — Infinite Clarify Loop Exit"**: `decide()`
  에스컬레이션 순서 교정과 patience/retry 상한 탈출로, 채울 수 없는 슬롯이
  무한 REASK로 빠지지 않게 한 결정론적 안전장치. (Reliability Design 절 보강)
- **"Scenario Node Referential Integrity"**: 분기 타겟 무결성 테스트와 유령
  노드 해소, 신고검사 노드의 프로토타입 잔재 제거·품목 카테고리 일반화.
  (Node Design / Testing 절 보강)
- **"Cross-owner conversation fixes"**: 단기기억(C)·트집 게이팅(A) 변경요청을
  진단부터 계약까지 주도한 협업 산출물. (Resume Bullets에 1줄 추가)

> 갱신 시 §14 누적 포트폴리오에 `14.8 대화 자연스러움 복구` 서브섹션도 추가하고
> 관련 커밋·테스트를 근거로 단다.

---

## 13. 산출물·문서 틀 (작업계획서가 교체되어도 유지)

> 이 절은 **이 계획서가 다른 건으로 교체되더라도 유지한다.** Dev B 작업이
> 타 오너(Dev A / Dev C / Unreal)에 의존하면 **handoff 와 change_request 문서를
> 반드시 남긴다.** 본 건의 실제 항목은 §9·§10·§11 에 작성되어 있다.

### 13.1 절차 (매 작업계획서 작성/교체 시)

1. §3 "제외(타 팀 소유)"와 §8 "타 팀 의존 작업"에 적힌 항목을 오너별
   change request 로 구체화한다(파일·함수 단위, 정확한 입출력/동작).
2. `docs/contracts/change_requests.md` **끝에** 아래 Change Request 틀로 추가한다.
3. `docs/handoff.md` **상단**(`# Handoff` 바로 아래)에 아래 Handoff 틀로 추가한다.
4. §8 에서 추가한 change request 의 제목/날짜를 역참조해 양방향으로 연결한다.
5. 타 팀 의존이 전혀 없으면 change request 는 생략하되, **handoff 는 항상 남긴다**
   (무엇을 왜 바꿨는지 + 검증 결과).

### 13.2 Change Request 틀

```markdown
## Change Request - YYYY-MM-DD - <짧은 제목>

Status: Open.

### Requested By

Developer B

### Affected Owner

Developer A and/or Developer C / Sean Han (필요 시 Unreal)

### Reason

왜 필요한가 — 증상 + 확정 방향 + "Dev B가 한 일 / 타 팀이 해야 할 일"의 경계.

### Proposed Contract Change

오너별로 머리표(`Dev A:`, `Dev C:`)를 달고, 정확한 입출력·동작 변경을
파일·함수 단위로 명시.

### Compatibility Impact

스키마/계약 파급, 회귀 가드(영향받지 않아야 할 씬·테스트).

### Temporary Workaround

타 팀 반영 전까지의 임시 동작.
```

### 13.3 Handoff 틀

```markdown
## YYYY-MM-DD Developer B <한 줄 제목>

Developer B는 <무엇을 / 왜> 했다.

- 변경/산출물: <작업계획서 교체, 신설 정책/메서드, 배선 지점 등>
- 교차 의존: Dev A/Dev C 변경 요청을
  `docs/contracts/change_requests.md`(<change request 제목>)로 전달.
- 검증/후속: <테스트·검증 명령 결과 또는 다음 단계>
```

---

## 14. Developer B 누적 작업 포트폴리오 (git 이력 기반)

> 작업계획서가 교체되어도 누적 기여 기록은 유지한다. 각 항목은 실제 커밋·모듈에
> 근거한다. (직전 계획서 §12에서 이어짐)

### 14.0 역할 한 줄 요약

Developer B는 **결정론적(rule-based) 정책 엔진**을 소유한다. 지저분한 여행 영어·
한국식 영어·짧은 비문 발화를 받아 **평가(verdict)·레벨/힌트·분기·상태 델타·
피드백·최종 점수**를 산출한다. NPC 대사(A)·오케스트레이션/검증(C)·TTS·Unreal
명령은 소유하지 않으며, 모든 출력은 C와의 JSON 계약(`dev_b_policy.v1`)을 엄격히 따른다.

### 14.1 정책 엔진 코어 — 상태 머신 & 난이도 컨트롤러

| 모듈 | 책임 |
|---|---|
| `service_b/scenario_state_machine.py` | 턴별 verdict(SUCCESS/PARTIAL/UNCLEAR/FAIL/CRITICAL_FAIL)와 분기(retry/clarify/hint/advance/bad_end) 결정 |
| `service_b/tier_difficulty_controller.py` | 6개 루브릭 영역(이해·유창·문법·어휘·명확·상호작용) × 0~2점 = **총점 0~12** → `travel_speaking_level_for_total()`로 TSL_1~4 판정, 티어 보정으로 NPC 말속도·질문 복잡도·힌트 빈도·압박 강도 산출 |
| `agent_b/policy_graph.py`, `tool_b/developer_b_policy_graph_tools.py` | LangGraph 기반 정책 파이프라인 배선 |

- 관련 커밋: `fb92130`(상태 머신 + 테스트 스위트, 06-16), `70b0f4a`(정책 엔진 통합, 06-16), `bed85e4`(진단 서비스·상태 머신·응답 오케스트레이션, 06-12).
- 회귀 가드: `test_developer_b_policy_engine.py`.

### 14.2 Chapter 0 시나리오 노드 설계 (`scenario_nodes.json`)

- 입국심사 라우트 `IMM_001_PASSPORT` ~ `IMM_007_FINAL_DECISION`: 각 노드에
  allowed-next-nodes와 retry/clarify/hint/warning/bad-end 분기 후보, `objective_kr`
  (한국어 UI 목표) 포함.
- 5턴 **기내 스몰토크 진단 라우트**, **수화물 분실 문제해결 라우트**
  (`BAG_001_*` ~ `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`), `ALPHA_999_FINAL_SCOREBOARD`
  최종 분기 노드.
- 관련 커밋: `9a9da1a`(입국심사 정책·노드 정의, 06-10), `e6b50b5`(한국어 objective, 06-04).

### 14.3 기내 스몰토크 진단 정책 (`flight_smalltalk_diagnostic_policy.py`)

- 게임 도입부 5턴 대화로 플레이어의 초기 TSL을 **숨은 진단**
  (`estimate_user_travel_speaking_level`)으로 추정. 슬롯 중립화로 진단 누설 방지.
- 관련 커밋: `08fa014`(기내 스몰토크 개선, 06-16), `fd10aeb`(진단·리포팅 계약, 06-11),
  `f1ca214`(smalltalk slot safety, 06-17).
- 회귀 가드: `test_flight_smalltalk_diagnostic_policy.py`.

### 14.4 레벨·힌트·피드백 생성 계층

| 모듈 | 책임 |
|---|---|
| `agent_b/english_level_hint_agent.py`, `agent_b/feedback_hint_llm_client.py` | 레벨별 힌트 산출. **결정론 정책이 verdict/분기/다음 노드/상태 델타의 단일 권위**, LLM은 한국어 힌트·피드백 문구·리포트 표현·Focus-on-Form 설명·루브릭 후보로만 제한(폴백 보장) |
| `service_b/feedback_hint_generator.py` | 인게임 힌트(keyword/sentence_pattern/situation/action) 생성 |
| `service_b/focus_on_form_report_policy.py` | Focus-on-Form 교정 타깃 산출 |
| `service_b/level_adaptation_controller.py` | 진행 중 레벨 적응 조정 |

- 관련 커밋: `df68ff3`(English level hint agent + 정책 그래프 인프라, 06-12),
  `a99b28d`(피드백 서비스·hint agent, 06-09).
- 회귀 가드: `test_focus_on_form_report_policy.py`.

### 14.5 최종 점수 & Bad Ending 정책

| 모듈 | 책임 |
|---|---|
| `service_b/final_result_score_policy.py` | Alpha 최종 스코어보드 점수·티어·강점/취약점 산출 및 검증 |
| `service_b/bad_ending_policy.py` | 인내심/의심 한계 초과 시 bad ending 분기 가드 |

- 관련 커밋: `174926d`(최종 점수 정책·검증, 06-05), `f1ca214`(bad ending guard, 06-17).
- 회귀 가드: `test_final_result_score_policy.py`, `test_dev_b_bad_ending_branch.py`,
  `test_scenario_nodes_bad_ending.py`.

### 14.6 학습 기록 영속화 & 실행 로깅

| 모듈 | 책임 |
|---|---|
| `service_b/openkb_feedback_writer.py` | B 소유 OpenKB `dev_b` 네임스페이스에 error capture·out-game 피드백 seed·Focus-on-Form 타깃·리포트 아이템·분기 결정·상태 델타를 **JSONL + 마크다운**으로 결정론 기록 |
| `service_b/developer_b_agent_run_logger.py` | Developer B 통합 AgentRun 실행 추적 로깅 |

- 관련 커밋: `eb51775`(OpenKB 통합·피드백 생성, 06-04), `2fbf91a`(AgentRun 로거, 06-04).
- 회귀 가드: `test_developer_b_agent_run_log.py`.

### 14.7 억까(트집) 장소·수화물 레벨별 배정 (CR-B-EOKKKA, 완료)

- 데이터 테이블 `data/challenge_tables.py`(장소 17·수화물 18종, 난이도 1~12),
  픽 서비스 `service_b/challenge_assignment_service.py`(`TSL_TO_DIFFICULTY_RANGE`,
  `pick_location`/`pick_customs_item`, 빈 풀 인접 폴백, `to_random_customs_item_context`).
- 밸런스 단일 소스를 B 순수함수로 소유, 실행·영속화는 C, NPC 트집 대사는 A.
- 관련 커밋: `0cc62aa`(코어 스키마 + 억까 픽 서비스, 06-17).
- 회귀 가드: `test_challenge_assignment.py`. 핸드오프: `docs/handoff.md`(2026-06-17).
- **후속 회귀**: 본 계획서(§1~§12)가 다루는 대화 품질 문제의 일부(트집 verbatim
  무차별)는 이 작업의 SUSPICION MODE 설계에서 파생됨 → CR-B-CONV-A로 게이팅 보완.

### 14.8 입국심사·세관 대화 자연스러움 복구 — 본 작업계획서(§1~§12)

- (진행 예정) 상태머신 무한 clarify 루프 탈출, 시나리오 노드 참조 무결성,
  신고검사 노드 일반화, 트집 스코프 신호 emit. 단기기억·트집 게이팅·대사 변주는
  CR-B-CONV-C / CR-B-CONV-A로 C/A에 전달.
- 회귀 가드(예정): `test_scenario_state_machine_loop_exit.py`,
  `test_scenario_nodes_referential_integrity.py`.

### 14.9 계약·문서 산출물

- `docs/contracts/developer_b_json_final_v1.md`, `developer_b_json_key_value_contract_v1.md`,
  `developer_b_report_and_dialogue_seed_contract.md`, `docs/dev_b_rubric.md`.
- 타 팀 의존은 `docs/contracts/change_requests.md`(`[CR-B-EOKKKA]`,
  `[CR-B-CONV-C]`, `[CR-B-CONV-A]`)와 `docs/handoff.md`로 양방향 연결(§13 절차).
- 관련 커밋: `4e6c640`(JSON Key-Value 계약 + 포트폴리오 문서, 06-04).
