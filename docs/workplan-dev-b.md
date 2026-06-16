# Developer B 작업계획서 — 기내 스몰토크를 적응형 진단(Adaptive Diagnostic)으로 전환

- 작성일: 2026-06-16
- 작성자: Developer B
- 대상 개선: 기내(옆자리 승객) 스몰토크가 "취조처럼" 느껴지고, 플레이어의
  답을 무시한 채 다음 질문만 이어가며, 꼬리를 무는 자연스러운 대화감이 없고,
  씬을 15개 고정 노드(A/B/C × 5턴)로 스크립트해 둔 탓에 화제 점프·역할 반전이
  발생하는 문제.
- 방향(확정): **C안 — 적응형 진단(Adaptive Diagnostic)**
  - 표면 대화는 생성형(LLM)으로 자연스럽게, **다음에 무엇을 떠볼지(probe 의도)**
    는 결정적 컨트롤러가 결정.
  - 진단은 "free-form에서 레벨을 느낌으로 추정"이 아니라 **설계된 역량 probe로
    커버리지를 통제**해 타당성을 확보.
  - 자연스러움은 LLM 선의가 아니라 **구조 제약 + coherence guard + eval 측정**
    3중으로 보증.
  - 종료는 **신뢰도(표준오차) + 턴 상·하한**으로 bounded → `FLIGHT_999_COMPLETE`.

## 0. 이전 계획 대비 변경점 (B-ish 절충 → C 적응형)

직전 계획서는 "재미·라포 우선(절충)" — 표면 대화 완전 자유 + 백그라운드 채점
(사실상 B안, steering 없음) 이었다. 본 계획은 그 토대(중립 진행 ADVANCE,
페널티 미적립, 안전선 유지, out-game 적립)를 **그대로 유지하면서** 다음을
추가하여 C안으로 격상한다.

| 추가 요소 | 목적 |
|---|---|
| probe 뱅크(역량·난이도·토픽 태깅) | 진단 커버리지 통제(타당성) |
| 적응형 probe 선택 + steering 노브 | 능력 추정에 따라 다음 의도 결정. steering=0이면 B 행동과 동치 |
| bounded 종료(최소·최대 턴 + 신뢰도) | 무한/지루/비용 방지, 설명 가능한 종료 |
| coherence guard(Dev A) | 반응 없는 맨 질문·비연결 턴을 출력 단계에서 차단 |
| 자연스러움 eval 루브릭 | "느낌"이 아니라 측정값으로 품질 관리·자동 후퇴 |

> **B는 별개 대안이 아니라 C의 극단값이다.** steering=0이면 컨트롤러가 절대
> 화제를 끌어오지 않고 학습자를 따라가므로 B 행동이 된다. 자연스러움이
> 부족하면 구조를 버리는 대신 **steering 노브를 follow 쪽으로 내려** 대응한다
> (§3.4).

## 1. 배경 및 문제 정의

기내 스몰토크 씬은 출입국 심사용 채점형 상태 머신을 재사용하면서, 동시에
`FLIGHT_A_*/B_*/C_*` **15개 고정 노드의 일렬 스크립트**로 짜여 있다. 그 결과:

| 증상 | 코드 원인 |
|---|---|
| 답을 무시하고 다음 질문만 | `decide_conversational`이 내용과 무관하게 항상 `success`+`ADVANCE`, 각 노드 `npc_question` 고정, Dev A가 `surface_goal`(=노드 고정 질문)만 읽음 |
| 화제 점프·취조감 | 다음 질문이 노드 그래프로 미리 정해짐 — 플레이어 발화에서 파생되지 않음 |
| 역할 반전(예: 펜을 빌려줬는데 NPC가 "here you are") | `FLIGHT_A_001`의 `npc_question_goal="respond_to_polite_request"`(=플레이어 관점)가 그대로 `dialogue_seed.surface_goal`로 복사되어(`english_level_hint_agent.py:708`) NPC를 응답자로 오인시킴 |
| 진단 커버리지 불투명 | 어떤 영어 역량을 실제로 검증했는지 보장 없음 — 5턴을 채워도 시제/의문문 형성 등이 한 번도 안 나올 수 있음 |

### 이 수정이 중요한 이유

`FlightSmallTalkDiagnosticPolicy`는 이미 `diagnostic_only=True`,
`decide_conversational`, `FLIGHT_999_COMPLETE` 참조까지 갖춘 **토대가 반쯤
완성**된 상태다. 부족한 것은 (1) "무엇을 떠볼지"를 능력 추정에 따라 고르는
적응형 선택, (2) bounded 종료, (3) 노드 그래프를 probe 뱅크로 대체하는 것이다.
표면 대화를 자연스럽게 만드는 가장 효과적인 단일 차단점(분기·진행 결정)이
Dev B 소유 영역에 있다.

## 2. 핵심 설계 (C안)

### 2.1 단일 self-loop 진단 노드

A/B/C 15개 노드의 **그래프 분기는 제거**한다. 단, 엔진/계약/데모 파급을
최소화하기 위해 **노드 추상화는 1개 유지** — `FLIGHT_A_001_SEATMATE_SMALLTALK`
을 챕터의 유일한 진단 노드로 남기고 **자기 자신으로 루프**시킨다(종료 전까지
`success_next_node = self`). 제거되는 A_002~005 / B_* / C_* 의 질문 텍스트는
버리지 않고 **probe 뱅크 항목으로 강등**해 다양성 재료로 재활용한다.

- `entry_node_ids` 는 단일 진단 노드로 정리.
- `FLIGHT_A_001` 의 잘못된 `npc_question_goal`(역할 반전 원인)은 NPC 관점으로
  교정하거나, 진단 노드에서는 `surface_goal`을 probe가 대체하므로 제거.

### 2.2 probe 뱅크 (Dev B 데이터)

신규 데이터 파일 `backend/app/data/flight_smalltalk_probes.json` 를 도입한다.
각 probe 항목 스키마(안):

```jsonc
{
  "probe_id": "PAST_NARRATIVE_TRIP",
  "target_competency": "past_tense_narrative", // 평가 대상 언어 역량
  "difficulty": 3,                              // 1~5 (CEFR 근사)
  "topic_tag": "travel",                        // 화제 연속성 판단용
  "coherent_topics": ["travel", "vacation"],    // 자연 연결 가능 화제
  "seed_text": "What did you do on your last trip?" // LLM 실패 시 폴백 문구
}
```

- `target_competency` 예: `question_formation`, `past_tense_narrative`,
  `future_plan`, `opinion_giving`, `vocab_range`, `clarification_handling`.
- seed_text 는 **폴백 전용** — 정상 경로의 실제 문장은 Dev A가 생성.

### 2.3 진단 컨트롤러 (결정적)

`FlightSmallTalkDiagnosticPolicy` 에 적응형 선택·종료 로직을 추가한다.

- **능력 추정 소비**: `english_level_hint_agent` 가 산출하는 레벨 추정치와
  **신뢰도(또는 표준오차)** 를 매 턴 누적(§6 작업 3). 컨트롤러는 이 추정값만
  소비하고 LLM을 호출하지 않는다.
- **probe 선택(기회주의적 + 화제 연속)**:
  1. 플레이어가 새 화제를 꺼냈고 신호가 충분하면 → **그 화제를 받아준다**
     (probe 강제 안 함). 평가는 관찰된 feature로 점수화.
  2. 신호가 얇은 역량이 있으면 → 현재 화제(`topic_tag`/`coherent_topics`)에서
     **도달 가능한 probe 우선 선택**. 부득이 화제 전환 시 dialogue_seed에
     명시적 전환 신호를 실어 Dev A가 전환구를 붙이게 한다.
  3. 능동 개입 강도는 **`steering` 파라미터(0.0~1.0)** 로 조절(§3.4).
- **bounded 종료**: `MIN_TURNS ≤ turns` 이고 `confidence ≥ THRESHOLD`(또는
  표준오차 < ε) 이면 종료. `turns ≥ MAX_TURNS` 면 무조건 종료. 종료 시
  `next_action="COMPLETE_CHAPTER"`, `next_node_id="FLIGHT_999_COMPLETE"`.
- **안전선 유지**: critical risk 감지 시 기존 `_critical_fail` 위임.

기본 파라미터(안): `MIN_TURNS=3`, `MAX_TURNS=7`, `CONFIDENCE_THRESHOLD=0.7`,
`steering=0.4`. 모두 단일 상수/설정으로 노출해 튜닝을 코드 수정 없이 가능하게.

### 2.4 dialogue_seed = "느슨한 의도", 강제 질문 아님

`attach_report_and_dialogue_seeds_tool` 에서 진단 노드일 때:

- `surface_goal` 을 노드 고정 질문이 아니라 **선택된 probe 의도**
  (`target_competency` + `topic_tag`)로 표기.
- `dialogue_directive.purpose="smalltalk_diagnostic"`,
  `topic_switch`(true/false), `length_target`(플레이어 발화 길이 기반 권고),
  `do_not_generate_npc_text=False`.
- `allowed_followup_intents` 를 넓혀 반응/자기개방/질문을 모두 허용.

## 3. 자연스러움 3중 보증

LLM 출력의 자연스러움은 증명할 수 없다. 따라서 **구조로 부자연을 어렵게 만들고,
가드로 미달 출력을 막고, 측정으로 품질을 관리**한다.

### 3.1 구조 제약 (Dev B 결정 + Dev A 렌더)

- **반응-먼저-탐색**: NPC 턴 = `[직전 발화 반응] + [연결] + [후속 의도]`.
  probe를 단독 질문으로 내보내지 않는다(Dev A 강제, §10 CR).
- **화제 연속성**: probe 선택을 `topic_tag`/`coherent_topics`로 제약(§2.3).
- **기회주의적 추종**: 학습자가 꺼낸 화제를 받아주고, 신호 부족 시에만 steer.
- **중복 방지/콜백**: 다룬 화제·NPC가 밝힌 정보를 추적(Dev A 대화 메모리).

### 3.2 coherence guard (Dev A, 출력 차단)

`npc_dialogue_agent.py:308-322` 의 기존 가드 패턴
(`recommended_expression_echo` / `missing_followup_question` /
`invalid_llm_dialogue_language`)과 동일 방식으로 추가:

- 플레이어가 실질 발화를 했는데 NPC 턴이 **반응 없는 맨 질문**이면 reject.
- 직전 발화와 **의미적 연결이 없으면(non-sequitur)** reject.
- reject 시 재생성 또는 폴백(seed_text).
- 단, 진단 노드에서는 `missing_followup_question`(매 턴 질문 강제)을 **해제**해
  반응-only 턴을 허용(§10 CR).

### 3.3 eval 측정 (검증 산출물)

자연스러움 루브릭(반응 존재 / 화제 연속 / 콜백 / 점프 없음)으로 트랜스크립트를
LLM-judge 또는 사람 스팟체크. 컨트롤러의 probe 선택·종료는 결정적이라 유닛
테스트로, 자연스러움은 eval로 분리 측정한다(§8).

### 3.4 steering 연속선 (B는 극단값)

`steering` 한 파라미터로 C↔B를 잇는다.

```
steering = 1.0  → 매 턴 능동 probe 강제  (가장 진단적, 부자연 위험↑)
steering = 0.0  → 절대 steer 안 함        (= B안 행동: 순수 추종)
```

자연스러움 eval 점수가 기준 미달이면 **steering을 내려** 대응(데이터 기반 후퇴).
구조(probe 뱅크·컨트롤러·가드·테스트)는 그대로 유지된다. 진단 자체가 불필요하다는
**제품 결정**이 날 때만 구조를 폐기한다.

## 4. 범위

### 포함 (Dev B 소유)

- `backend/app/data/scenario_nodes.json` (A/B/C 분기 노드 제거, 단일 진단 노드,
  `FLIGHT_A_001` 역할 반전 교정, `entry_node_ids` 정리, `FLIGHT_999_COMPLETE` 확인)
- `backend/app/data/flight_smalltalk_probes.json` (신규 probe 뱅크)
- `backend/app/services/service_b/flight_smalltalk_diagnostic_policy.py`
  (적응형 probe 선택 + bounded 종료 + steering)
- `backend/app/services/service_b/scenario_state_machine.py` (진단 씬 위임 지점)
- `backend/app/tools/tool_b/developer_b_policy_graph_tools.py`
  (분기 라우팅, dialogue_seed probe/의도 emit)
- `backend/app/agents/agent_b/english_level_hint_agent.py`
  (능력 추정치+신뢰도 노출, in-game feedback 억제·out-game 적립)
- `backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py`,
  `backend/tests/dev_b/test_developer_b_policy_engine.py`

### 제외 (타 팀 → 변경 요청으로 전달, §10)

- **Dev A**: 반응-먼저 스몰토크 페르소나, `missing_followup_question` 해제,
  `SURFACE_GOAL_QUESTIONS` 고정 큐 비활성, `recommended_expression` 라이브
  삽입 제거, 발화 기반 후속·대화 메모리/콜백, **coherence guard 신설**,
  길이 미러링, `branch_reason="flight_smalltalk_continue"` 중립 렌더,
  제거된 노드(`FLIGHT_A_005_WRAP_UP`, `FLIGHT_B_002`, `FLIGHT_C_004`)를
  참조하는 테스트 갱신.
- **Dev C**: 스몰토크에서 슬롯 강제 추출/오인식 완화. 데모
  `demo/respond-dialog/index.html`(`FLIGHT_A_001` 하드코딩)은 진단 노드 ID를
  유지하므로 무영향(노드 ID 변경 시에만 갱신).
- env 수정, TTS/음성 출력.

## 5. 현재 코드 분석

- `developer_b_policy_graph_tools.py:102` `decide_scenario_branch_tool` 가
  씬과 무관하게 `state_machine.decide(payload)` 호출 → **진단 씬 라우팅 단일 지점.**
- `DevBPolicyInput` 에 `scene_id`/`current_node_id` 존재(`game_turn.py:262-263`)
  → 추가 스키마 변경 없이 게이팅 가능.
- `FlightSmallTalkDiagnosticPolicy.decide_conversational` 가 이미 중립 진행·
  페널티 0·안전선을 구현 → 여기에 **probe 선택 + 종료 판정**을 더한다.
- **계약 제약:** `Branch.branch_type`(`game_turn.py:512`)에 `neutral` 없음
  (`success/retry/clarify/hint/warning/bad_end/final`). 중립 진행은
  **`success`+`ADVANCE` 재사용**, 스몰토크 의미는 `branch_reason` +
  `dialogue_directive` 로 신호(enum 미확장).
- `english_level_hint_agent.py:708` 가 `surface_goal=npc_question_goal` 로
  복사 → 진단 노드에서는 **이 경로를 probe 의도로 대체**(역할 반전 근본 차단).

## 6. 작업 항목 (Dev B 소유)

### 작업 1 — 시나리오 노드 정리 (단일 진단 노드)

- `scenario_nodes.json` 에서 `FLIGHT_A_002~005`, `FLIGHT_B_001~005`,
  `FLIGHT_C_001~005` 의 그래프 분기를 제거.
- `FLIGHT_A_001_SEATMATE_SMALLTALK` 를 유일 진단 노드로 남기고 자기 루프
  (`success_next_node = self`, 종료 시에만 `FLIGHT_999_COMPLETE`).
- `npc_question_goal` 의 플레이어 관점 라벨(`respond_to_polite_request`) 교정/제거.
- `entry_node_ids` 를 단일 진단 노드로 정리. `FLIGHT_999_COMPLETE` 전이 확인.

### 작업 2 — probe 뱅크 신설

- `flight_smalltalk_probes.json` 작성(§2.2 스키마). 제거된 노드 질문을 역량·
  난이도·토픽 태깅해 이관. 로더 헬퍼를 정책에서 사용.

### 작업 3 — 능력 추정치 + 신뢰도 노출

- `english_level_hint_agent` 가 레벨 추정과 함께 **누적 신뢰도(또는 표준오차)** 를
  policy output/seed 로 노출 → 컨트롤러가 종료 판정에 사용.
- 진단 씬에서 `in_game_feedback.show=False`, `blocks_progression=False`,
  교정은 `out_game_feedback_seed`/`error_capture(should_surface_out_game=True)`
  로만 적립. `report_seed_summary` 채점은 유지.

### 작업 4 — 적응형 컨트롤러

- `decide_conversational` 확장: probe 선택(기회주의 + 화제 연속 + steering),
  bounded 종료(MIN/MAX/THRESHOLD), 안전선 위임. 모든 delta=0.
- 파라미터를 모듈 상수/설정으로 노출.

### 작업 5 — 그래프 배선 + dialogue_seed emit

- `decide_scenario_branch_tool` 에서 진단 씬이면 `decide_conversational` 로 분기.
- `attach_report_and_dialogue_seeds_tool` 에서 선택 probe를 `surface_goal`(의도) +
  `dialogue_directive`(`purpose`, `topic_switch`, `length_target`) 로 emit(§2.4).

## 7. 계약/주의

- `branch_type` enum 미확장: 중립 진행은 `success`+`ADVANCE` 재사용,
  스몰토크 의미는 `branch_reason="flight_smalltalk_continue"` +
  `dialogue_directive` 로 구분. enum 확장은 `game_turn.py`/Agent A `BranchType`/
  Dev C 어댑터 파급이라 후속 과제로 분리.
- 가드레일: probe 선택·종료·verdict·다음 노드는 **규칙 기반** 유지. LLM은 표면
  대사 wording 만 담당.
- 노드 제거는 데모/테스트/openkb 참조에 파급되므로 §10 CR로 타 팀과 동기화.

## 8. 테스트 계획

`test_flight_smalltalk_diagnostic_policy.py` / `test_developer_b_policy_engine.py`:

- `test_diagnostic_advances_without_pass_fail`: 알아들을 수 있는 발화는 retry가
  아니라 ADVANCE(자기 루프), 모든 delta=0.
- `test_diagnostic_offtopic_is_followed_not_reasked`: 새 화제 발화 →
  재질문하지 않고 진행(기회주의 추종).
- `test_probe_selection_prefers_coherent_topic`: 현재 토픽에서 도달 가능한
  probe를 우선 선택, 강제 전환 시 `topic_switch=True` 신호.
- `test_steering_zero_never_forces_probe`: steering=0이면 probe 강제가 없어
  (B 행동) 학습자 화제만 따라가는지.
- `test_termination_bounded_by_turns_and_confidence`: `MIN_TURNS` 미만이면
  미종료, 신뢰도 충족 시 `COMPLETE_CHAPTER`+`FLIGHT_999_COMPLETE`,
  `MAX_TURNS` 도달 시 무조건 종료.
- `test_diagnostic_critical_risk_still_guarded`: 위험 감지 시 critical_fail 유지.
- `test_diagnostic_feedback_is_out_game_only`: `in_game_feedback.show=False`,
  `blocks_progression=False`, 교정이 out-game 으로만 적립.
- 회귀 가드: `IMM_*`/`BAG_*` 씬은 기존 채점 분기 그대로 통과.
- 자연스러움 eval(별도): 루브릭 기반 트랜스크립트 채점(유닛 아님, §3.3).

## 9. 검증 명령

```powershell
uv run pytest backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py
uv run pytest
uv run ruff check .
uv run mypy .
```

## 10. 타 팀 의존 작업 (변경 요청)

C안의 "기계 느낌" 완전 제거와 coherence 보증에는 Dev A의 대사 생성 변경이,
슬롯 오인식 완화에는 Dev C 변경이 함께 필요하다. 상세 항목은
`docs/contracts/change_requests.md`
(**Change Request - 2026-06-16 - [CR-B-SMALLTALK] 기내 스몰토크 적응형 진단 전환**)
및 `docs/handoff.md`(2026-06-16 Developer B 기내 스몰토크 적응형 진단 전환 항목)에
동기화한다.

- **Dev A**: 반응-먼저 스몰토크 페르소나, `missing_followup_question` 해제(반응-only
  허용), `SURFACE_GOAL_QUESTIONS` 고정 큐 비활성·발화 기반 후속, **coherence guard
  신설**, `recommended_expression` 라이브 삽입 제거, 길이 미러링, 대화 메모리/콜백,
  `flight_smalltalk_continue` 중립 렌더, 제거 노드 참조 테스트 갱신.
- **Dev C**: 스몰토크 슬롯 강제 추출/오인식 완화. (노드 ID 유지 시 데모 무영향.)

## 11. 산출물·문서 틀 (작업계획서가 교체되어도 유지)

> 이 절은 **이 계획서가 다른 건으로 교체되더라도 유지한다.** Dev B 작업이
> 타 오너(Dev A / Dev C / Unreal)에 의존하면 **handoff 와 change_request 문서를
> 반드시 남긴다.** 본 건의 실제 항목은 §10 과 아래 2건(§10 참조)에 작성되어 있다.

### 11.1 절차 (매 작업계획서 작성/교체 시)

1. §4 "제외(타 팀 소유)"와 §10 "타 팀 의존 작업"에 적힌 항목을 오너별
   change request 로 구체화한다(파일·함수 단위, 정확한 입출력/동작).
2. `docs/contracts/change_requests.md` **끝에** 아래 Change Request 틀로 추가한다.
3. `docs/handoff.md` **상단**(`# Handoff` 바로 아래)에 아래 Handoff 틀로 추가한다.
4. §10 에서 추가한 change request 의 제목/날짜를 역참조해 양방향으로 연결한다.
5. 타 팀 의존이 전혀 없으면 change request 는 생략하되, **handoff 는 항상 남긴다**
   (무엇을 왜 바꿨는지 + 검증 결과).

### 11.2 Change Request 틀

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

### 11.3 Handoff 틀

```markdown
## YYYY-MM-DD Developer B <한 줄 제목>

Developer B는 <무엇을 / 왜> 했다.

- 변경/산출물: <작업계획서 교체, 신설 정책/메서드, 배선 지점 등>
- 교차 의존: Dev A/Dev C 변경 요청을
  `docs/contracts/change_requests.md`(<change request 제목>)로 전달.
- 검증/후속: <테스트·검증 명령 결과 또는 다음 단계>
```
