# 2인 멀티플레이 확장 설계 (합의 공유본)

> 대상: AI 팀 · Unreal 팀
> 상태: **방향 합의 완료 / 구현 전**
> 최종 수정: 2026-06-24

---

## 0. 한 줄 요약

기존 **1인 싱글플레이** 시스템을 **2인 멀티플레이**로 확장한다.
백엔드가 **턴 단위 무상태(stateless-per-turn)** 라서, 확장의 본질은 *엔진 재작성*이 아니라
**"정체성 키(identity) + 발화자 태깅 + 챕터별 메모리 스코프"** 다.

---

## 1. 현재 아키텍처 전제 (왜 확장이 가벼운가)

- 백엔드는 매 턴 `POST /respond` 로 한 턴을 처리하고 **델타만 반환**한다.
- **상태의 주인은 Unreal**. 매 턴 `session / player_profile / scenario_state / game_state` 를
  통째로 실어 보내고, 백엔드는 다음 상태 변화량(`state_delta`)을 돌려준다.
- 따라서 서버에 "이 게임은 1명짜리"라고 박힌 전역 상태는 거의 없다.
- **Unreal = thin client**: STT 전송, `/respond` 호출, NPC 대사·오디오 렌더링, 상태 보관.
  게임 규칙/평가/난이도 판정은 모두 백엔드(service_a/b/c)에 있다.

---

## 2. 게임 형태 (챕터별)

| 챕터 | 모드 | 설명 |
|---|---|---|
| CH0_01 기내 스몰토크 | **병렬 독립** | 둘이 따로 앉음. 각자 동시 진행. 서로 영향 없음. |
| CH0_03 입국심사 | **병렬 독립** | 각자 따로 심사. 동시 진행. |
| CH0_04 수화물 | **공유 협동** | 둘 중 한 명의 위탁수화물 분실 → **함께 해결**. |

### 현실 시나리오 (CH0_04 기준)
두 사람이 함께 미국 여행. 기내는 따로 앉았고 입국심사도 따로 받지만,
같이 왔기에 **둘 중 한 명의 위탁수화물이 도착하지 않은** 상황을 함께 해결한다.
보통 한 명이 주로 의사소통하고, 잘 안 되면 다른 한 명이 돕는 구조.

---

## 3. 확정된 기획 결정

1. **분실 가방 주인 = 둘 중 낮은 TSL**
   영어를 잘하는 사람 가방이 없어지면 못하는 사람이 할 일이 없어진다.
   그래서 **두 플레이어의 TSL을 비교해 낮은 쪽을 주인**으로 한다(학습 압박 유지).
   동점 시 tie-break: 루브릭 총점(0–12) 더 낮은 쪽 → 그래도 같으면 랜덤.

2. **도움(helper)은 아무때나 자유롭게**
   옆 사람이 언제든 끼어들어 대신 답할 수 있다. 턴 게이팅 없음.

3. **NPC는 주인에게 말 걸되, 옆 사람 답도 인정**
   NPC는 주인을 향해 질문(연출)하지만, **평가·슬롯 충족은 발화자 무관**(speaker-agnostic).
   누가 답했든 정보가 채워지면 진행한다.

4. **수화물 챕터 범위 = 분실 가방 해결만 (공유)**
   세관검사(신고품) 서브단계는 이 2인 챕터에서 다루지 않는다. 단일 공유 미션.

5. **scenario_state = 팀 1개 공유 (공동 인내심/의심)**
   분실 가방은 하나의 공유 문제이므로 patience/suspicion을 팀이 공유한다.
   한 명의 위험 발화가 팀 의심도를 올려 둘 다 2차 심사로 갈 수 있다(의도된 협동 긴장).

6. **언어 학습 점수 = 발화자별 귀속**
   결과(통과/2차심사) = **팀 공동**. 문법/명료성 등 **언어 루브릭 = 말한 사람 개인 리포트**.
   주인이 많이 말하면 주인 리포트가 두껍고, 도운 사람은 도운 만큼만.

---

## 4. 챕터별 상태/메모리 스코프 (구현 기준표)

| 챕터 | NPC 단기기억 | scenario_state | 슬롯/인텐트 | 채점 |
|---|---|---|---|---|
| CH0_01 기내 | 플레이어별 격리 | 각자 1개 | 각자 | 개인 |
| CH0_03 입국심사 | 플레이어별 격리 | 각자 1개 | 각자 | 개인 |
| CH0_04 수화물 | **방 공유 1개** | **팀 1개 전부 공유** | **미션 단위 공유** | outcome=팀 / 언어=발화자별 |

> ⚠️ **중요 정정**: "공유 챕터에서도 슬롯을 발화자별로 분리"는 **틀린 설계**다.
> 수화물 분실 가방은 **단일 미션**이므로 `accumulated_slots / completed_intents /
> forbidden_questions` 는 **미션 단위로 공유**한다(누가 답하든 채워지면 끝, NPC는 다시 안 물음).
> 발화자 태깅은 오직 `turn_buffer` 기록 + 언어 점수 귀속에만 쓴다.
> (단, 병렬 입국심사에서는 각자 항목이 다르므로 `completed_intents`는 플레이어별로 유지)

---

## 5. 싱글플레이 가정이 박혀 있는 위치 (백엔드)

1. `backend/app/schemas/game_turn.py` — `SessionContext`: `session_id` 1개, `player_id` Optional·미사용
2. `backend/app/services/service_a/npc_short_term_memory_service.py:17` —
   `build_thread_id = f"{session_id}:{npc_id}"` (player_id 없음 → 병렬 챕터 충돌)
3. `backend/app/api/ai_respond.py:397` — `/result/{session_id}` 세션 단위 채점
4. 로그·OpenKB가 세션 키 기준 누적

---

## 6. 정체성 모델

`session_id` 하나에 다 묶지 말고 두 축으로 분리한다.

- **`room_id`** — 두 플레이어가 함께 있는 매치(현재 `session_id`가 사실상 이 역할)
- **`player_id`** — 개인 (스키마에 Optional로 존재, 현재 라우팅 미사용)

NPC 기억 키를 **챕터 스코프로 분기**:

```python
def build_thread_id(room_id, npc_id, *, player_id=None, scope="player"):
    if scope == "room":        # 수화물: 두 사람 누적 공유
        return f"{room_id}:shared:{npc_id}"
    return f"{room_id}:{player_id}:{npc_id}"   # 기내/입국: 플레이어 격리
```

---

## 7. 주인 선정은 백엔드가 한다 (TSL 출처가 백엔드이므로)

**TSL은 백엔드가 추정한다.** Unreal은 그 값을 메아리로 들고 있을 뿐이다.

- `travel_speaking_level_for_total(rubric_total)` (tier_difficulty_controller.py:163) 로
  백엔드가 발화를 채점해 TSL 도출.
- **기내 챕터의 존재 이유 자체가 레벨 추정**:
  `hidden_assessment_goal="estimate_user_travel_speaking_level"`,
  종료 조건 `"enough_evidence_for_level_estimation"` (english_level_hint_agent.py:785).
- `PlayerProfile.travel_speaking_level` 은 백엔드가 응답으로 돌려준 값을 Unreal이 되돌려주는 것.

→ 판정 기준(TSL)도, 분실 품목 배정(`pick_customs_item`)도 백엔드에 있으므로
**주인 선정도 백엔드 책임**. Unreal에 두면 판정 로직이 클라이언트로 새어나간다.

### 신규: 방 셋업 엔드포인트 (무상태 · 순수 결정)

```
POST /api/game/ai/room/baggage/setup
  입력:  player1_profile, player2_profile   (Unreal이 들고 있는 TSL/tier 값 전달)
  처리:  백엔드가 낮은 TSL 비교 → 주인 선정
         + challenge_assignment_service 로 분실 가방 난이도/품목 배정
  출력:  bag_owner_player_id, 배정된 가방 정보
  Unreal: 응답 저장 → 이후 매 턴 game_state 에 실어 보냄 (여전히 무상태)
```

> 전제: 수화물 시작 시점에 두 플레이어의 TSL 추정이 끝나 있어야 한다.
> 기내→입국심사를 거치면 보통 충족. **기내 스킵/증거 부족 시 fallback TSL 정책 필요**
> (예: 초기 placement 값 또는 tier 기반 기본값) — **미정, 합의 필요**.

---

## 8. 수화물 한 턴의 데이터 계약 (초안)

```
요청 (UnrealTurnRequest, CH0_04):
  session.room_id                   # 매치 식별
  speaker_player_id                 # 이번에 말한 사람 (주인이든 도우미든)
  game_state.bag_owner_player_id    # 셋업에서 받은 주인
  scenario_state                    # 팀 공유 1개 (방이 보유한 그대로)
  game_state (공유), npc (공유: BAGGAGE_STAFF)

응답 (UnrealResponse):
  state_delta                       # 팀 공유 미터에 그대로 적용
  npc (addressed = 주인)             # NPC는 주인을 향해 말하도록 연출
  언어 rubric 점수 → speaker_player_id 개인 리포트에 귀속
```

신규 필드: `room_id`, `speaker_player_id`, `bag_owner_player_id`, `addressed_player_id`

---

## 9. 변경 체크리스트

### 백엔드 — 변경 없음 (무상태 설계의 이득)
- `ScenarioStateMachine`, Developer B 정책 엔진 — **무변경** (평가가 speaker-agnostic이라 오히려 단순)
- `pick_customs_item` 등 난이도 로직 — 그대로

### 백엔드 — 손볼 것
1. `game_turn.py` — `room_id / speaker_player_id / bag_owner_player_id / addressed_player_id` 필드 추가
2. `npc_short_term_memory_service.py` — `build_thread_id` 스코프 분기, `append_turn` 에 발화자 태깅
3. `dev_a_npc_dialogue_client.py:96` — `user_id=session_id` 하드코딩 → `player_id`, A-facing에 `addressed_player_id` 전달
4. `ai_respond.py` `/result` — 팀 outcome + 발화자별 언어 리포트 분리
5. 신규 `POST /room/baggage/setup` — 주인 선정 + 가방 배정 (무상태)
6. **동시성 가드** — 공유 미터 race 방지 (아래 §10)

### Unreal — 손볼 것
- 상태 블롭 2벌 관리 (병렬 챕터), 수화물은 공유 상태 1벌
- 매 턴 `speaker_player_id` stamp
- 셋업 응답 보관 → 매 턴 `bag_owner_player_id` 전송
- `state_delta` 를 팀 공유 미터에 적용
- (병렬 챕터) 각 플레이어 독립 세션/턴 스트림

---

## 10. 동시성 (반드시 합의 필요)

수화물은 **자유 참여 + 팀 공유 미터**라, 두 플레이어가 동시에 `/respond` 를 쏘면
공유 patience/suspicion 에 **lost update(레이스)** 가 날 수 있다.
(병렬 챕터는 thread_id가 달라 안전)

**해결안 후보 (택1, 합의 필요):**
- (A) Unreal이 room 단위로 턴 직렬화 보장 (한 번에 한 명만 `/respond`)
- (B) 백엔드가 room 단위 턴 락

---

## 11. 미해결 / 합의 대기 항목

- [ ] 기내 스킵·레벨 추정 증거 부족 시 **fallback TSL 정책** (§7)
- [ ] 동시성 책임 계층: Unreal 직렬화 vs 백엔드 락 (§10)
- [ ] `/result` 의 팀 outcome + 개인 리포트 **응답 스키마 형태** 확정
- [ ] 셋업 엔드포인트 입출력 **계약 필드 상세** 확정

---

## 부록: 용어

- **TSL (Travel Speaking Level)**: `TSL_1_SURVIVAL` ~ `TSL_4_STRATEGIC`. 백엔드가 발화 채점으로 추정.
- **주인(owner)**: 분실 가방의 소유자 = 낮은 TSL 플레이어.
- **도우미(helper)**: 주인을 돕는 다른 플레이어.
- **speaker-agnostic**: 누가 말했든 슬롯/평가는 동일하게 처리(진행 판정엔 발화자 무관).
- **stateless-per-turn**: 백엔드가 턴 사이 상태를 저장하지 않고, Unreal이 매 턴 전체 상태를 전달.
