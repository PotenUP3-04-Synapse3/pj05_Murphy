# 2인 멀티플레이 — 수정 작업계획서 (리뷰 지적 해결 + 재발 방지)

> 대상: 구현 담당 전원
> 상태: **수정 착수용**
> 최종 수정: 2026-06-24
> 선행: [multiplayer_2p_workplan.md](multiplayer_2p_workplan.md) 1차 구현 + 코드리뷰 지적

---

## 0. 작업 원칙 (반드시 준수)

### 0.1 개발자(Dev A/B/C) 구분 없이 구현한다
1차 구현과 동일. `agent_a/b/c`, `service_a/b/c`, `tool_a/b/c` 경계를 가로질러
**한 사람이 한 기능을 끝까지** 완결한다. "A 담당/B 담당" 분리·핸드오프 금지.
각 WP의 DoD에 **경계 통합 + 라운드트립 테스트 통과**를 포함한다.

### 0.2 (신규) 수직 슬라이스 = "레이어 가로지르기"가 아니라 "데이터를 종착지까지 따라가기"
1차 구현 실패의 핵심 교훈(§1). 슬라이스는 a/b/c를 한 번씩 만지는 것으로 끝이 아니다.
**새 필드/데이터는 입구에서 최종 소비처(저장소·응답)까지 전 구간을 따라가 검증**해야 완료다.

---

## 1. 근본 원인 분석 — "경계에서 안 풀리는 문제"는 왜 생겼나

### 1.1 무엇이 터졌나 (사실)
- 소비자(`/result`)는 저장 레코드에서 `room_id`·`speaker_player_id`를 읽도록 구현됨.
- 생산자(`openkb_feedback_writer._build_record`)는 **그 필드를 쓰지 않음**.
  점수 귀속도 `speaker_player_id`가 아니라 `session.player_id`로 됨.
- 그런데 **테스트는 초록**이었다. 채점 e2e가 이상적인 레코드를 **손으로 써넣어** 소비자만 검증했기 때문.

### 1.2 왜 생겼나 (구조적 원인 5가지)

| # | 원인 | 설명 |
|---|---|---|
| C1 | **저장 경계가 stringly-typed** | 레코드가 `dict[str,Any]` → JSONL. 소비자는 `r.get("room_id")`로 읽음. 생산자가 안 써도 `None`만 나올 뿐 **에러가 안 남**. HTTP 경계엔 Pydantic 계약이 있지만 **저장/로그 경계엔 계약이 없다.** |
| C2 | **테스트가 생산자를 우회** | 채점 테스트가 실제 `/respond`→writer 파이프라인 대신 **합성 레코드를 직접 작성**. 소비자가 "상상한 데이터"에 대해서만 통과. 생산자는 그 계약에 묶인 적이 없음. |
| C3 | **슬라이스가 종착지에 못 닿음** | `speaker_player_id`는 요청→DevBPolicyInput→DevADialogueInput "라이브 경로"엔 관통됐지만, **저장 경로(writer)는 다른 코드 경로**라 빠짐. 데이터를 끝까지 안 따라간 결과. |
| C4 | **DoD가 라운드트립에 정박 안 됨** | "발화자별 리포트가 다르다"는 합성 입력으로도 충족 가능 → **생산자 없이도 DoD 통과**. 인수 기준이 실제 write→read 왕복에 묶이지 않음. |
| C5 | **필드 '여정'을 강제하는 곳이 없음** | 새 식별자가 여러 스키마엔 추가됐지만 "이 필드는 요청부터 저장 레코드까지 전부 흘러야 한다"를 **검증·강제하는 단일 지점이 없음**. |

### 1.3 한 줄 진단
> **HTTP 경계엔 타입 계약·검증이 있는데, 저장/로그 경계엔 없다.**
> 그래서 생산자-소비자가 조용히 어긋나고, 테스트는 합성 데이터로 그 틈을 가렸다.

---

## 2. 재발 방지 메커니즘 (작업에 내장한다)

| 코드 | 메커니즘 | 무엇을 막나 |
|---|---|---|
| P1 | **저장 레코드를 타입 계약으로** — `PolicyTurnFeedbackRecord` Pydantic 스키마를 writer·reader가 **공유**. | C1: stringly-typed 드리프트. 소비자가 필드를 읽는데 생산자가 안 쓰면 **타입/검증에서 깨짐**. |
| P2 | **단일 레코드 팩토리** — 레코드 생성은 한 함수에서만. 테스트도 이 팩토리(또는 실제 writer)로 생성. | C2: 합성 레코드로 우회. |
| P3 | **라운드트립 테스트 규칙** — 저장-파생 출력을 검증하는 테스트는 **실제 `/respond` writer가 쓴 레코드**를 읽어야 함. 손으로 쓴 JSON 금지. | C2·C4. |
| P4 | **생산자-소비자 계약 테스트** — writer가 내보내는 키 집합 ⊇ reader가 읽는 키 집합을 **자동 검증**. | C1·C5. |
| P5 | **필드 여정 체크리스트**(§4) — 새 데이터 필드는 입구→…→저장→응답 전 구간 표로 추적, DoD에 포함. | C3·C5. |

---

## 3. 작업 패키지 (R0~R6) — 개발자 구분 없음

```
R0 (재발방지 기반) ──> R1 (정체성 일원화) ──> R2 (생산자 완결: HIGH) ──> R4 (라운드트립 테스트)
                  └──> R3 (스코프 헬퍼 단일화)
                                              R5 (정리)        R6 (회귀/통합)
```

### WP-R0 — 재발 방지 기반 먼저 깐다 (P1·P2·P4)
**목적**: 수정이 다시 어긋나지 않도록 계약·팩토리·계약테스트를 먼저 설치.

**건드리는 파일 (경계 가로지름)**
- `backend/app/schemas/game_turn.py` — `PolicyTurnFeedbackRecord` 스키마 신설(저장 레코드 타입 계약).
- `backend/app/services/service_b/openkb_feedback_writer.py` — `_build_record`를 **단일 팩토리**로 정리, 위 스키마로 검증 후 직렬화.
- `backend/app/services/service_b/final_result_score_policy.py` / `focus_on_form_report_policy.py` — reader가 같은 스키마로 역직렬화.
- `backend/tests/dev_b/test_record_contract.py` (신규) — **계약 테스트**(P4).

**DoD**
- [ ] writer 출력이 `PolicyTurnFeedbackRecord`로 검증됨.
- [ ] reader가 동일 스키마로 읽음.
- [ ] 계약 테스트: writer가 쓰는 키 ⊇ 모든 reader가 읽는 키 (누락 시 실패).

### WP-R1 — 정체성 일원화 (session_id vs room_id)
**목적**: 🟠 지적 해결. "어떤 키로 레코드를 묶는가"를 하나로 확정.

**결정(잠정 기본값, 회의 확정 시 교체)**: **레코드 파일 키 = `room_id`**(없으면 `session_id` 폴백).
레코드에 `room_id`·`player_id`·`speaker_player_id` 모두 포함. `/result`는 `room_id`로 집계.

**건드리는 파일**
- `openkb_feedback_writer.py` — 파일 경로·레코드 키를 room_id 기준으로.
- `final_result_score_policy.py`(reader) — room_id 기준 조회 추가.
- `backend/app/api/ai_respond.py` `/result` — room_id로 집계, `session_id`-as-room 가정 제거.

**DoD**
- [ ] 서로 다른 session_id를 가진 두 플레이어의 수화물 레코드가 **같은 room_id로 집계**됨(라운드트립 테스트).
- [ ] 1인(병렬) 경로는 기존대로 동작(회귀).

### WP-R2 — 생산자 완결: writer가 식별자 기록 + 발화자 귀속 🔴
**목적**: HIGH 지적 해결. `room_id`·`speaker_player_id`를 저장하고 **점수 귀속을 발화자 기준으로**.

**건드리는 파일 (요청→저장 라이브/저장 두 경로 모두)**
- `openkb_feedback_writer.py` `_build_record` — `room_id`, `speaker_player_id` 기록.
  점수/리포트 귀속 키 = `speaker_player_id`(없으면 `player_id` 폴백).
- `backend/app/tools/tool_c/developer_c_graph_tools.py` — 저장 시점까지 `speaker_player_id` 전달 확인.
- `backend/app/integrations/dev_b_level_hint_client.py` — 발화자 필터 기준을 `speaker_player_id`로.

**DoD (필드 여정 §4로 검증)**
- [ ] 실제 `/respond`(수화물, 도우미 발화 턴) 1회 → 저장 레코드에 `room_id`·`speaker_player_id`가 **실제로 들어있음**.
- [ ] 도우미가 답한 턴의 언어 점수가 **도우미** 리포트에 귀속(주인 아님).
- [ ] `has_room_id` 분기가 실데이터로 동작(합성 아님).

### WP-R3 — "공유 챕터" 판정 헬퍼 단일화
**목적**: 🟠 레이어 간 스코프 판정 불일치 해결.

**건드리는 파일**
- `backend/app/services/service_c/`(또는 schemas) — `is_shared_baggage(session) -> bool` 단일 헬퍼.
- `ai_respond.py`(락 판정)·`developer_c_graph_tools.py`(메모리 scope) — **둘 다 이 헬퍼만 사용**.

**DoD**
- [ ] BAG_ prefix가 아닌 수화물 노드에서도 락과 메모리 scope가 **일치**.
- [ ] 판정 로직이 코드 1곳에만 존재(중복 제거).

### WP-R4 — 채점 e2e를 실제 라운드트립으로 교체 (P3)
**목적**: C2·C4 차단. 합성 레코드 테스트 폐기.

**건드리는 파일**
- `backend/tests/dev_b/test_multiplayer_e2e.py` — 손으로 쓴 레코드 제거 →
  **실제 `/respond`로 두 발화자 턴을 발생시켜 레코드를 만들고**, `/result`로 분리 검증.

**DoD**
- [ ] 채점 분리 테스트가 **writer가 생산한 실레코드**만 읽음(합성 JSON 0건).
- [ ] 발화자별 점수 차이가 실파이프라인에서 재현됨.

### WP-R5 — 정리 (🟡 지적들)
- 락: `_ROOM_LOCKS` 정리 정책 + **멀티워커 한계 문서화**(in-process 락·NPC 메모리 싱글톤은 워커 간 공유 안 됨 → 단일 워커 전제 또는 외부 스토어).
- `final_result_score_policy._state_from_records` → **공개 메서드**(예: `result_for_player`)로 승격, private 침투 제거.
- `out_game_feedback_for_session`의 인라인 jsonl 파싱 → 기존 reader 재사용(DRY).
- `/result`의 죽은 폴백 `["player1","player2"]` 제거.

**DoD**: 위 4건 반영 + 회귀 그린.

### WP-R6 — 회귀/통합 재검증
- [ ] 기내(병렬)→입국(병렬)→수화물(공유) 2인 e2e 그린.
- [ ] 1인 시나리오 전부 회귀 그린.
- [ ] R0 계약 테스트·R4 라운드트립 테스트 CI 동시 그린.

---

## 4. 필드 여정 체크리스트 (재사용 도구 — P5)

새 데이터 필드를 추가/수정할 때 **모든 칸을 채워야 슬라이스 완료**.
(예시: `speaker_player_id`)

| 단계 | 위치 | 들어왔나? | 검증 테스트 |
|---|---|---|---|
| 1. 요청 입구 | `UnrealTurnRequest` / `GameState` | ✅ | schema |
| 2. 정책 입력 | `DevBPolicyInput` | ✅ | graph_tools |
| 3. 대사 입력 | `DevADialogueInput` | ✅ | dev_a client |
| 4. **저장 레코드** | `openkb_feedback_writer` | ❌→R2 | **라운드트립** |
| 5. reader 조회 | `final_result_score_policy` | ❌→R2 | 계약 테스트 |
| 6. 응답 출구 | `/result` | ⚠️ 부분 | e2e |

> 1차 구현은 1~3만 채우고 4~6을 빠뜨려 터졌다. **4(저장)가 종착지 직전 함정.**

---

## 5. 권장 순서
1. **R0**(재발방지 기반) → 이후 수정이 어긋나면 즉시 빨강.
2. R0 후 **R1·R3 병행** → **R2**(HIGH) → **R4**(라운드트립).
3. **R5 정리** → **R6 잠금**.

> 순서의 의도: 방지 장치(R0)를 먼저 깔아야, R2 HIGH 수정이 "또 합성 테스트로 통과"하는 일이 원천 차단된다.
