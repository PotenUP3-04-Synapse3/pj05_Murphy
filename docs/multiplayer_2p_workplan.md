# 2인 멀티플레이 확장 — 작업계획서

> 대상: 구현 담당 전원
> 상태: **구현 착수용**
> 최종 수정: 2026-06-24
> 설계 근거: [docs/multiplayer_2p_design.md](multiplayer_2p_design.md)

---

## 0. 작업 원칙 (가장 중요 — 반드시 준수)

### 0.1 개발자(Dev A/B/C) 구분 없이 구현한다
현재 코드는 `agent_a/b/c`, `service_a/b/c`, `tool_a/b/c`, `middleware_a/c` 로 개발자 단위 분할되어 있고,
**경계(boundary)에서 책임이 갈려 문제가 끝까지 해결되지 않는 일이 반복**되고 있다.

이 작업계획서는 그 분할을 따르지 않는다.

- **작업 단위 = 기능 수직 슬라이스(vertical slice)**. 개발자 소유 영역이 아니다.
- 하나의 작업 패키지(WP)는 `agent_a` · `service_b` · `tool_c` 등 **필요한 파일을 경계 넘어 전부 수정**한다.
- "이건 A 담당, 저건 B 담당" 식 분리·핸드오프 금지. **한 WP를 맡으면 a/b/c 경계의 접착(glue) 코드와 테스트까지 그 사람이 끝낸다.**
- WP의 완료 기준(DoD)에는 **경계 통합 + 회귀 테스트 통과**가 반드시 포함된다. 반쪽짜리(한 레이어만 고치고 다음 사람에게 넘김)는 완료 아님.

### 0.2 무상태(stateless-per-turn) 원칙 유지
백엔드는 턴 사이 상태를 저장하지 않는다(동시성 락 §WP6 제외). 상태는 Unreal이 보관·전달.

### 0.3 변경 최소화 / 기존 엔진 보존
`ScenarioStateMachine`, Developer B 정책 엔진, 난이도 로직(`pick_customs_item`)은 **로직 변경 없이** 재사용한다.
평가가 speaker-agnostic이므로 엔진은 손대지 않는다.

---

## 1. 작업 패키지 개요 & 의존 순서

```
WP1 (정체성 기반)  ──┬──> WP2 (병렬 챕터 멀티화)
                     ├──> WP3 (수화물 셋업/주인 선정) ──> WP4 (수화물 공유 런타임) ──> WP5 (채점 분리)
                     └──> WP6 (동시성 가드)
                                                                                     WP7 (통합/회귀) ← 전부
```

| WP | 제목 | 핵심 산출 | 선행 |
|---|---|---|---|
| WP1 | 정체성 기반 스키마·키 | room_id/player_id/speaker 전 구간 관통 | — |
| WP2 | 병렬 챕터 멀티화 | 기내·입국심사 2인 동시, 메모리 격리 | WP1 |
| WP3 | 수화물 셋업 & 주인 선정 | 신규 셋업 엔드포인트 | WP1 |
| WP4 | 수화물 공유 미션 런타임 | 공유 미터·기억, speaker-agnostic, NPC 주인 지목 | WP1, WP3 |
| WP5 | 채점 분리 | 팀 outcome + 발화자별 언어 리포트 | WP4 |
| WP6 | 동시성 가드 | room 단위 턴 직렬화 | WP1 |
| WP7 | 통합·회귀 테스트 | 2인 e2e 시나리오 | 전부 |

---

## WP1 — 정체성 기반 스키마·키 (Foundation)

**목적**: 모든 후속 작업이 딛고 설 식별자 체계를 한 번에 관통시킨다.

**건드리는 파일 (a/b/c 가로지름)**
- `backend/app/schemas/game_turn.py` — `SessionContext`에 `room_id` 추가, `player_id` 정식 사용.
  `UnrealTurnRequest`/`GameState`에 `speaker_player_id`·`bag_owner_player_id`·`addressed_player_id` 추가.
  `DevBPolicyInput`·`DevADialogueInput`에 동일 식별자 전파.
- `backend/app/services/service_a/npc_short_term_memory_service.py:17` — `build_thread_id(room_id, npc_id, *, player_id=None, scope="player")` 로 시그니처 확장 + 스코프 분기.
- `backend/app/agents/agent_a/npc_dialogue_agent.py:1240` — payload에서 `player_id`·`scope` 추출해 `build_thread_id`·config로 전달.
- `backend/app/tools/tool_c/developer_c_graph_tools.py` — `build_dev_b_policy_input` 등에서 신규 식별자 전달.
- `backend/app/integrations/dev_a_npc_dialogue_client.py:96` — `user_id=session_id` 하드코딩 → `player_id` 로 교체.

**구현 내용**
1. 신규 식별자 필드 추가 (전부 Optional + 하위호환 기본값 → 기존 1인 요청 깨지지 않게).
2. `build_thread_id` 스코프 분기: `scope="room"` → `f"{room_id}:shared:{npc_id}"`, 그 외 → `f"{room_id}:{player_id}:{npc_id}"`.
3. `room_id` 미지정 시 `session_id`로 폴백(하위호환).

**완료 기준 (DoD)**
- [ ] 기존 1인 요청/테스트 전부 그대로 통과 (회귀 0).
- [ ] 같은 room_id·다른 player_id 두 요청이 **서로 다른 thread_id**를 만든다(단위 테스트).
- [ ] scope="room" 두 요청이 **같은 thread_id**를 공유한다(단위 테스트).
- [ ] mypy/ruff 통과.

---

## WP2 — 병렬 챕터 멀티화 (기내·입국심사)

**목적**: 두 플레이어가 기내/입국심사를 **동시에 독립**으로 진행. 메모리·상태 완전 격리.

**건드리는 파일**
- (대부분 WP1으로 충족) 검증 위주. 필요 시 `developer_c_graph_tools.py`, `orchestrator.py` 식별자 전달 점검.

**구현 내용**
1. 두 플레이어가 같은 NPC(예: 입국심사관 hale)와 같은 room에서 대화해도 thread_id 충돌 없음을 보장.
2. 각 플레이어 scenario_state·game_state는 각자 1벌 (Unreal이 분리 관리, 백엔드는 그대로 처리).

**완료 기준 (DoD)**
- [ ] 2인 병렬 e2e: P1·P2가 같은 챕터를 동시에 진행해도 NPC 기억/슬롯이 섞이지 않음.
- [ ] `/result` 가 player_id별로 분리 조회됨(WP5 선반영 또는 최소 키 분리).

---

## WP3 — 수화물 셋업 & 주인 선정

**목적**: 수화물 챕터 진입 시 **백엔드가** 분실 가방 주인과 가방을 결정한다.

**건드리는 파일**
- `backend/app/api/ai_respond.py` — 신규 라우트 `POST /api/game/ai/room/baggage/setup`.
- `backend/app/services/service_b/challenge_assignment_service.py` — `pick_customs_item`/`pick_location` 재사용.
- `backend/app/services/service_b/tier_difficulty_controller.py:163` — `travel_speaking_level_for_total` 비교에 활용.
- 신규 서비스 1개: `service_b/baggage_room_setup_service.py` (주인 선정 규칙 캡슐화).

**구현 내용 (무상태 순수 결정)**
```
POST /api/game/ai/room/baggage/setup
  입력:  room_id, player1_profile(TSL/tier/총점), player2_profile
  처리:  낮은 TSL = 주인. 동점 → 루브릭 총점 낮은 쪽 → 그래도 동점 → 결정적 랜덤(room_id seed).
         주인 TSL로 pick_customs_item / 분실 가방 정보 배정.
  출력:  bag_owner_player_id, 배정 가방(item/난이도/사유)
  Unreal: 응답 저장 → 이후 매 턴 game_state.bag_owner_player_id 로 전송
```

**완료 기준 (DoD)**
- [ ] 낮은 TSL이 주인으로 선정됨(단위 테스트, 동점 케이스 포함).
- [ ] 같은 입력 → 같은 출력(결정적, room_id seed).
- [ ] **fallback TSL** 처리: 한쪽 추정 증거 부족/기내 스킵 시 기본값 적용 (기본 정책 §8-A).

---

## WP4 — 수화물 공유 미션 런타임

**목적**: 두 플레이어가 한 NPC와 **공유 미터/공유 기억**으로 분실 가방을 함께 해결. 자유 참여, NPC는 주인 지목.

**건드리는 파일 (가장 넓게 가로지름)**
- `backend/app/services/service_a/npc_short_term_memory_service.py` — `append_turn`에 `speaker_player_id` 태깅. `accumulated_slots/completed_intents/forbidden_questions`는 **미션 단위 공유**(발화자 분리 X).
- `backend/app/agents/agent_a/npc_dialogue_agent.py` — `node_persist_memory`/`node_load_memory`에 발화자 기록, scope="room" 경로.
- `backend/app/integrations/dev_a_npc_dialogue_client.py` — A-facing payload에 `addressed_player_id`(=주인) 전달 → NPC가 주인을 향해 말하도록 연출.
- `backend/app/agents/agent_c/understanding_agent.py` & `service_b` 정책 경로 — **평가 speaker-agnostic 확인**(발화자가 도우미여도 슬롯 충족/진행 동일). 로직 변경이 아니라 "발화자 의존성이 없는지" 점검·보장.
- `backend/app/tools/tool_c/developer_c_graph_tools.py` — 수화물 챕터에서 scope="room" + speaker 전달.

**구현 내용**
1. 매 턴 `speaker_player_id`로 누가 말했는지 기록(turn_buffer).
2. 슬롯/인텐트/금지질문은 공유 → P1이 claim tag 답하면 P2에게 다시 안 물음.
3. scenario_state(patience/suspicion 등)는 팀 1벌 공유 — `state_delta`는 그대로 공유 미터에 적용(Unreal).
4. NPC 대사는 주인을 지목하되, **도우미가 답해도 진행 통과**.

**완료 기준 (DoD)**
- [ ] 도우미(주인 아님)가 답해도 슬롯 충족·진행됨(테스트).
- [ ] 한 명이 답한 슬롯을 NPC가 재질문하지 않음(forbidden_questions 공유, 테스트).
- [ ] turn_buffer에 발화자가 남고, 같은 room의 두 발화가 같은 공유 기억에 누적됨.
- [ ] 한 명의 위험 발화가 팀 suspicion을 올림(공유 미터, 테스트).

---

## WP5 — 채점 분리 (팀 outcome + 발화자별 언어 리포트)

**목적**: 결과(통과/2차심사)는 팀 공동, 언어 학습 점수는 말한 사람 개인.

**건드리는 파일**
- `backend/app/api/ai_respond.py:397` — `/result` 를 팀 outcome + player별 리포트로 분리.
- `backend/app/integrations/dev_b_level_hint_client.py` — `final_result_for_session` / `out_game_feedback_for_session` 를 (room, player) 키로 확장.
- `backend/app/services/service_b/openkb_feedback_writer.py` — 발화자별 누적 키.

**구현 내용**
- 언어 루브릭(문법/명료성 등)은 매 발화의 `speaker_player_id`에 귀속.
- 팀 outcome(통과/2차심사)은 공유 미터 결과에서 1개 산출, 두 플레이어 리포트에 공통 표기.

**완료 기준 (DoD)**
- [ ] 도우미만 살짝 말한 경우, 도우미 리포트는 얇고 주인 리포트는 두껍게 나옴(테스트).
- [ ] 팀 outcome은 두 플레이어 결과에서 동일.
- [ ] `/result` 응답 스키마 확정(§8-C).

---

## WP6 — 동시성 가드

**목적**: 자유 참여 + 공유 미터에서 동시 `/respond`로 인한 lost-update 방지.

**건드리는 파일**
- `backend/app/api/ai_respond.py` 또는 `service_c` — room 단위 턴 직렬화.

**구현 내용 (기본 정책 §8-B: 백엔드 room 락)**
- 수화물 공유 챕터 한정, room_id 단위 비동기 락으로 동일 room 턴을 직렬 처리.
- 병렬 챕터(thread_id 분리)는 락 불필요.

**완료 기준 (DoD)**
- [ ] 동일 room 동시 2요청 → 공유 미터가 두 델타를 모두 반영(lost-update 없음, 테스트).
- [ ] 다른 room 요청은 병렬 처리(블로킹 없음).

---

## WP7 — 통합·회귀 테스트

**목적**: 개발자 경계가 아니라 **플레이어 시나리오 전체**가 동작함을 보장.

**건드리는 파일**
- `backend/tests/` — 신규 2인 e2e 시나리오, `eval_harness` 확장.

**완료 기준 (DoD)**
- [ ] 기내(병렬) → 입국심사(병렬) → 수화물(공유) 전 구간 2인 시나리오 통과.
- [ ] 기존 1인 시나리오 전부 회귀 통과.
- [ ] 위 모든 WP의 DoD 테스트가 CI에서 함께 green.

---

## 2. 공통 규칙

- **스키마 단일 출처**: 식별자 필드는 `game_turn.py`에서만 정의, 중복 정의 금지.
- **하위호환**: 신규 필드 Optional + 폴백(`room_id`←`session_id`). 기존 1인 클라이언트 무중단.
- **회귀 우선**: 각 WP는 자기 테스트 + 기존 테스트 동시 green이어야 머지.
- **경계 접착 포함**: 각 WP는 a↔b↔c 사이 데이터 전달까지 완결 (반쪽 머지 금지).

---

## 3. 미해결 결정 — 기본값 선반영 (작업 비차단)

블로킹 방지를 위해 **기본값을 정해 진행하고, 회의에서 확정 시 교체**한다.

| # | 항목 | 기본 정책(잠정) | WP |
|---|---|---|---|
| 8-A | fallback TSL (기내 스킵/증거 부족) | `tier` 기반 기본값, 없으면 `TSL_2_FUNCTIONAL` | WP3 |
| 8-B | 동시성 책임 계층 | **백엔드 room 락** (Unreal 의존 X) | WP6 |
| 8-C | `/result` 응답 스키마 | `{ team_outcome, players: [{player_id, rubric_report}] }` | WP5 |
| 8-D | 셋업 엔드포인트 계약 상세 | §WP3 입출력안 그대로 | WP3 |

---

## 4. 리스크 & 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| 발화자 의존성이 평가 코드에 숨어 있음 | 도우미 답이 통과 안 됨 | WP4에서 understanding/policy 경로 speaker 의존성 전수 점검 |
| 공유 기억 동시 쓰기 레이스 | 슬롯 유실 | WP6 락 + WP4 테스트로 동시성 검증 |
| 하위호환 깨짐 | 기존 1인 깨짐 | 신규 필드 Optional + 폴백, 회귀 테스트 게이트 |
| TSL 추정 미완 상태로 수화물 진입 | 주인 선정 불가 | WP3 fallback TSL(8-A) |

---

## 5. 권장 진행 순서

1. **WP1** 먼저 완결(기반). 이게 안 되면 나머지 전부 막힘.
2. WP1 후 **WP2 / WP3 / WP6 병행 가능**.
3. WP3 완료 후 **WP4 → WP5**.
4. 마지막 **WP7**로 전체 시나리오 잠금.
