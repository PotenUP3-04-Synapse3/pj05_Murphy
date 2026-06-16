# Developer B 작업계획서 — 기내 스몰토크를 채점형 분기에서 분리(대화형 모드)

- 작성일: 2026-06-16
- 작성자: Developer B
- 대상 개선: 기내(옆자리 승객) 스몰토크가 "취조처럼" 느껴지고, 엉뚱한 답에
  같은 질문만 반복하며, 꼬리를 무는 자연스러운 대화감이 없고, 선생님처럼
  "이렇게 말하면 돼"가 노출되며, 스몰토크인데 다음 질문 진행에만 집중하는 문제
- 방향(확정): **재미·라포 우선(절충)** — 표면 대화는 완전 자유, 영어 진단/채점은
  백그라운드에서 조용히 적립한 뒤 씬 종료 후 리포트로만 노출

## 1. 배경 및 문제 정의

기내 스몰토크 씬(`FLIGHT_A_001_SEATMATE_SMALLTALK`)이 **출입국 심사용으로
설계된 채점형 상태 머신을 그대로 재사용**하고 있다. 그 결과 매 턴이
"정답/오답 판정 → 슬롯 충족 검사 → 다음 노드 전진"으로 채점되며, 이것이
취조 느낌의 구조적 근원이다.

증상과 코드 원인의 매핑:

| 증상 | 코드 원인 |
|---|---|
| 취조하는 느낌 | `scenario_state_machine.py`의 `decide()`가 success/retry/clarify/hint/critical_fail 로만 분기. suspicion·patience·risk 로직을 스몰토크에도 적용 |
| 엉뚱한 말에 같은 질문 반복 | `_is_success` 실패 → `_retry()`/`_clarify()` → `REASK` → `retry_next_node`(주로 같은 노드). "플레이어가 새 화제를 꺼냄"을 수용하는 분기가 없음 |
| 꼬리 무는 대화 부재 | 다음 질문이 `dialogue_seed.surface_goal` + `SURFACE_GOAL_QUESTIONS`(service_a) 고정 큐로 미리 정해짐. 플레이어 발화에서 파생되지 않음 |
| 선생님처럼 교정 노출 | `in_game_feedback`/`recommended_expression`이 라이브 대사 흐름에 매 턴 노출 |
| 다음 질문 진행에만 집중 | Dev A 프롬프트가 surface_goal 존재 시 "(a) 인정 (b) 다음 질문"을 강제하고, 질문 누락 시 에러 처리 → NPC가 그냥 반응만 하는 턴이 금지됨 |

### 이 수정이 중요한 이유

`FlightSmallTalkDiagnosticPolicy`는 이미 존재하지만(`should_emit_out_game_feedback_seed=True`,
`should_show_out_game_feedback_now=False`로 "채점은 적립, 노출은 씬 종료 후"라는
의도까지 박혀 있음) **정책 그래프에 연결되어 있지 않아 사실상 고아 상태**다.
즉 설계 의도는 이미 있고, Dev B가 할 일은 기내 씬을 이 대화형 경로로
**실제 배선**하여 채점형 분기에서 떼어내는 것이다. 표면 대화를 자유롭게 만드는
가장 효과적인 단일 차단점이 Dev B 소유 영역(분기 결정)에 있다.

## 2. 범위

### 포함 (Dev B 소유)

- `backend/app/services/service_b/flight_smalltalk_diagnostic_policy.py`
  (대화형 분기 결정 로직 보강)
- `backend/app/services/service_b/scenario_state_machine.py`
  (기내 씬 가드 또는 위임 지점)
- `backend/app/tools/tool_b/developer_b_policy_graph_tools.py`
  (`decide_scenario_branch_tool` 분기 라우팅, `attach_report_and_dialogue_seeds_tool` 시드 조정)
- `backend/app/agents/agent_b/english_level_hint_agent.py` (보조: in-game feedback 억제)
- `backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py`,
  `backend/tests/dev_b/test_developer_b_policy_engine.py`

### 제외 (타 팀 → 변경 요청으로 전달)

- Dev A: NPC 대사 프롬프트의 스몰토크 페르소나 모드, 매 턴 질문 강제 해제
  (`missing_followup_question`), `SURFACE_GOAL_QUESTIONS` 고정 큐 비활성,
  `recommended_expression`의 라이브 대사 삽입 제거, 발화 기반 후속·대화 메모리
- Dev C: 스몰토크에서 슬롯 강제 추출/오인식 완화
- env 수정, TTS/음성 출력

## 3. 현재 코드 분석

- `developer_b_policy_graph_tools.py:102` `decide_scenario_branch_tool` 가
  씬 종류와 무관하게 `self.state_machine.decide(payload)` 를 호출한다.
  → **기내 씬 분기 라우팅이 들어갈 단일 지점.**
- `DevBPolicyInput` 에 `scene_id`, `current_node_id` 가 있으므로
  (`game_turn.py:262-263`) `scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK"`
  로 게이팅 가능하다. 추가 스키마 변경 불필요.
- `FlightSmallTalkDiagnosticPolicy` 는 `evaluate()` / `fallback_question()`
  만 갖고 있고 분기 결정(`ScenarioDecision` 산출)을 제공하지 않는다.
  → 대화형 결정 메서드를 추가해야 한다.
- **계약 제약:** `Branch.branch_type`(`game_turn.py:512`)에는 `neutral`이
  없다(`success/retry/clarify/hint/warning/bad_end/final`). 따라서 "채점 없이
  그냥 이어가기"를 표현하려면 (A) `branch_type="success"`+`ADVANCE`를 중립
  진행 의미로 재사용하거나 (B) enum을 확장해야 한다. 본 계획은 계약 파급을
  최소화하기 위해 **(A) 재사용**을 채택하고, 스몰토크임을 `branch_reason`과
  `dialogue_directive`로 신호한다(§6 참조).
- `attach_report_and_dialogue_seeds_tool` 가 `dialogue_seed.surface_goal` 을
  세팅한다 → 여기서 surface_goal 을 "강제 다음 질문"이 아닌 "느슨한 주제 힌트"로
  내보내고, `allowed_followup_intents` 를 넓혀 Dev A가 자유롭게 반응/자기 얘기/질문을
  고르게 한다.

## 4. 설계 방향 (절충)

1. 기내 씬에서는 **pass/fail 채점으로 분기하지 않는다.** 알아들을 수 있는
   발화는 모두 중립 진행(ADVANCE)으로 흘려보낸다.
2. **되묻기는 최소화.** `needs_repeat` 이거나 confidence 가 바닥(임계값 이하)일
   때만 가벼운 clarify. 엉뚱한 말은 재질문하지 않고 화제 이동을 허용한다.
3. **페널티 미적립.** patience/suspicion/retry/hint delta = 0. 슬롯 미충족이
   진행을 막지 않는다(스몰토크는 필수 슬롯 개념을 적용하지 않음).
4. **안전선만 유지.** critical risk(밀입국/취업 의도 등) 감지 시에는 기존
   `_critical_fail` 경로를 유지한다.
5. **채점은 백그라운드.** 영어 레벨/루브릭 점수·교정은 계속 산출하되
   `in_game_feedback.show=False`, `blocks_progression=False` 로 두고
   `out_game_feedback_seed` 로만 적립 → 씬 종료 후 리포트에서 노출.

## 5. 작업 항목 (Dev B 소유)

### 작업 1 — 기내 스몰토크 대화형 분기 결정 추가

`FlightSmallTalkDiagnosticPolicy` 에 `decide_conversational(payload)` 를 추가하여
`ScenarioDecision` 을 반환한다.

- critical risk → 기존 `ScenarioStateMachine._critical_fail` 로 위임(안전선).
- `needs_repeat` 또는 `confidence < CLARIFY_THRESHOLD`(예: 0.3) → 가벼운
  clarify(REASK, 단 patience delta 0, retry delta 0으로 페널티 없이).
- 그 외 전부 → ADVANCE. `branch_type="success"`, 모든 delta=0,
  `branch_reason="flight_smalltalk_continue"`.
- 다음 노드는 `node_context.success_next_node` 를 따르되,
  `allowed_next_nodes`/`client_allowed_next_nodes` 검증은 기존
  `_checked_next_node` 재사용.

### 작업 2 — 정책 그래프에 기내 씬 라우팅 배선

`decide_scenario_branch_tool` 에서 `scene_id` 가
`FLIGHT_A_001_SEATMATE_SMALLTALK` 이면 `decide_conversational` 로,
그 외에는 기존 `state_machine.decide` 로 분기한다. (또는 동등하게
`ScenarioStateMachine.decide` 진입부에 기내 씬 가드를 두어 위임.)
선택 기준: 로깅/도구 호출 추적을 유지하기 위해 tool 레이어 분기를 우선한다.

### 작업 3 — in-game 피드백 억제 / out-game 적립으로 일원화

기내 씬에서:

- `in_game_feedback.show=False`, `blocks_progression=False`,
  `feedback_strategy="none"`(또는 noop) 로 강제.
- `recommended_expression`/교정 텍스트는 `out_game_feedback_seed` 및
  `error_capture`(should_surface_in_game=False, should_surface_out_game=True)
  로만 적립.
- `report_seed_summary` 채점은 계속 산출(진단 유지).

구현 지점: `english_level_hint_agent.py` / `build_base_policy_output` 단계에서
기내 씬 플래그에 따라 in-game 노출 필드를 마스킹.

### 작업 4 — dialogue_seed surface_goal 을 느슨한 주제 힌트로

`attach_report_and_dialogue_seeds_tool` 에서 기내 씬일 때:

- `surface_goal` 을 단일 강제 질문이 아니라 주제 힌트로 표기(값 자체는 유지하되
  Dev A가 강제 질문으로 쓰지 않도록 §9 변경요청과 연동).
- `allowed_followup_intents` 를 넓혀 반응/자기개방/질문을 모두 허용.
- `dialogue_directive.purpose="smalltalk_rapport"`,
  `do_not_generate_npc_text=False` 로 설정하여 Dev A에 "자유 대화" 신호 전달.

### 작업 5 (보조) — 턴 게이팅 완화

`MINIMUM_PLAYER_TURNS` 기반 강제 진행을 "소프트 최소"로 유지하되, 고정
`FALLBACK_QUESTIONS` 큐는 LLM 실패 시 최후 폴백으로만 사용. 진행 종료는 착륙
안내 등 자연 종료 신호와 연동(다음 단계 과제).

## 6. 계약/주의

- `branch_type` enum 미확장: 중립 진행을 `success`+`ADVANCE` 로 재사용한다.
  스몰토크 의미는 `branch_reason="flight_smalltalk_continue"` 와
  `dialogue_directive` 로 구분한다. → Dev A가 이 신호를 보고 성공-축하형
  피드백 대신 중립 반응을 렌더링하도록 §9에 변경요청 포함.
- enum 확장(예: `smalltalk`/`continue`) 안은 `game_turn.py`, Agent A의
  `BranchType`, Dev C 어댑터까지 파급되므로 본 계획에서는 제외하고 후속
  과제로 분리.
- 가드레일 준수: 분기 제어는 규칙 기반을 유지하며 NPC 대사·다음 노드·verdict를
  LLM으로 생성하지 않는다.

## 7. 테스트 계획

`test_flight_smalltalk_diagnostic_policy.py` / `test_developer_b_policy_engine.py`:

- `test_flight_smalltalk_offtopic_does_not_reask`:
  기내 씬 + 질문과 무관한 발화(answer_relevance=off_topic) →
  `branch_type != "retry"`, `next_action == "ADVANCE"`(재질문 아님) 검증.
- `test_flight_smalltalk_missing_slot_still_advances`:
  `missing_slots` 가 있어도 ADVANCE 되는지(슬롯이 진행을 막지 않음) 검증.
- `test_flight_smalltalk_no_penalty_delta`:
  ADVANCE 시 patience/suspicion/retry/hint delta 가 모두 0 인지 검증.
- `test_flight_smalltalk_low_confidence_clarifies_softly`:
  `needs_repeat=True` 또는 confidence 바닥 → clarify 이되 페널티 0 인지 검증.
- `test_flight_smalltalk_critical_risk_still_guarded`:
  위험 태그 감지 시 critical_fail 안전선이 유지되는지 검증.
- `test_flight_smalltalk_feedback_is_out_game_only`:
  `in_game_feedback.show == False`, `blocks_progression == False`,
  교정이 `out_game_feedback_seed` 로만 적립되는지 검증.
- 회귀 가드: 입국심사(`IMM_*`)·수하물(`BAG_*`) 씬은 기존 채점 분기를 그대로
  통과해야 한다(`test_developer_b_policy_engine.py` 기존 케이스 유지).

## 8. 검증 명령

```powershell
uv run pytest backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py
uv run pytest
uv run ruff check .
uv run mypy .
```

## 9. 타 팀 의존 작업 (변경 요청)

본 수정은 Dev B 분기를 대화형으로 바꾸지만, "기계 느낌" 완전 제거에는 Dev A의
대사 생성 변경이 함께 필요하다.

- Dev A:
  - NPC 대사 프롬프트에 **스몰토크 페르소나 모드** 추가(자기 사연·목적을 지닌
    동승객; 매 턴 질문 강제 X; 반응/자기개방/질문 혼합; topic drift 허용;
    대화 중 영어 교정 금지).
  - 기내 씬에서 `missing_followup_question` 에러/매 턴 질문 강제 **해제**,
    반응-only 턴 허용.
  - `SURFACE_GOAL_QUESTIONS` 고정 큐 비활성화, 플레이어 발화·추출 토픽 기반
    맥락 후속 생성. 고정 질문은 LLM 실패 시 폴백으로만.
  - `recommended_expression`/교정 표현을 라이브 대사에 삽입하지 않음(피드백은
    out-game 리포트로).
  - `branch_reason="flight_smalltalk_continue"` 신호 시 성공-축하형이 아닌
    중립 반응 렌더링.
  - (질감) 대화 메모리: 다룬 화제·NPC가 밝힌 정보를 추적해 재질문 방지 및 콜백.
- Dev C:
  - 스몰토크에서 슬롯 강제 추출/오인식 완화(자유 발화를 임의 슬롯 값으로
    채우지 않음).

자세한 항목은 `docs/contracts/change_requests.md` 및 `docs/handoff.md`
(2026-06-16 기내 스몰토크 대화형 전환 항목)에 동기화한다.

## 10. 산출물·문서 틀 (작업계획서가 교체되어도 유지)

> 이 절은 **이 계획서가 다른 건으로 교체되더라도 유지한다.** Dev B 작업이
> 타 오너(Dev A / Dev C / Unreal)에 의존하면 **handoff 와 change_request 문서를
> 반드시 남긴다.** 본 건의 실제 항목은 §9 와 아래 2건(§9 참조)에 작성되어 있다.

### 10.1 절차 (매 작업계획서 작성/교체 시)

1. §2 "제외(타 팀 소유)"와 §9 "타 팀 의존 작업"에 적힌 항목을 오너별
   change request 로 구체화한다(파일·함수 단위, 정확한 입출력/동작).
2. `docs/contracts/change_requests.md` **끝에** 아래 Change Request 틀로 추가한다.
3. `docs/handoff.md` **상단**(`# Handoff` 바로 아래)에 아래 Handoff 틀로 추가한다.
4. §9 에서 추가한 change request 의 제목/날짜를 역참조해 양방향으로 연결한다.
5. 타 팀 의존이 전혀 없으면 change request 는 생략하되, **handoff 는 항상 남긴다**
   (무엇을 왜 바꿨는지 + 검증 결과).

### 10.2 Change Request 틀

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

### 10.3 Handoff 틀

```markdown
## YYYY-MM-DD Developer B <한 줄 제목>

Developer B는 <무엇을 / 왜> 했다.

- 변경/산출물: <작업계획서 교체, 신설 정책/메서드, 배선 지점 등>
- 교차 의존: Dev A/Dev C 변경 요청을
  `docs/contracts/change_requests.md`(<change request 제목>)로 전달.
- 검증/후속: <테스트·검증 명령 결과 또는 다음 단계>
```
