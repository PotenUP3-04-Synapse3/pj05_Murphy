# 작업계획서 — respond-dialog 테스트 페이지 개선 (2026-06-17)

대상 페이지: `GET /respond-dialog` → [demo/respond-dialog/index.html](../demo/respond-dialog/index.html)
관련 백엔드: [backend/app/api/ai_respond.py](../backend/app/api/ai_respond.py), [backend/app/services/service_c/agent_run_summary_service.py](../backend/app/services/service_c/agent_run_summary_service.py)

---

## 1. 배경 / 현황

- `respond-dialog`는 Unreal 없이 한 턴(turn) 흐름을 수동으로 검증하는 **내부 테스트용 페이지**다.
- 현재 챕터 버튼(Flight / Immigration / Baggage / Result)만 있고, 각 챕터의 NPC는 `chapterStarts` 객체에 **하드코딩**되어 있어 변경 불가.
- 입력은 (1) WAV 업로드, (2) 브라우저 녹음 + 실시간 STT 두 경로뿐 → **STT API 비용이 항상 발생**.
- "Session Usage" 카드의 토큰/비용이 `0` / `$0.000000`으로만 표시되는 문제 존재.
- 억까(Eokkka, 부당 의심) 상황의 방문지/수화물은 `game_state.assigned_visit_location*` / `game_state.random_customs_item`으로 턴에 실려야 하나, 테스트 페이지에서는 **전혀 주입하지 못함**.

### 관련 데이터/서비스 (재사용 대상)
- 억까 테이블: [backend/app/data/challenge_tables.py](../backend/app/data/challenge_tables.py) — `LOCATIONS`(17개), `CUSTOMS_ITEMS`(난이도 1~12).
- 억까 부여 로직: [backend/app/services/service_b/challenge_assignment_service.py](../backend/app/services/service_b/challenge_assignment_service.py) — `pick_location`, `pick_customs_item`, `TSL_TO_DIFFICULTY_RANGE`.
- NPC 로스터: [backend/app/services/service_a/npc_roster_service.py](../backend/app/services/service_a/npc_roster_service.py) — role별 NPC 목록.
- 턴 스키마: [backend/app/schemas/game_turn.py](../backend/app/schemas/game_turn.py) — `GameState`, `RandomCustomsItemContext`, `PlayerProfile`.
- 비용 추정: [backend/app/agents/agent_c/llm_cost_estimator.py](../backend/app/agents/agent_c/llm_cost_estimator.py).

---

## 2. 작업 항목

### A. 페이지 최신화
**목표:** 현재 백엔드 계약(`dev_c_unreal_turn.v1`)·노드·NPC 데이터와 어긋난 부분 정리.
- `chapterStarts`의 NPC id/role/speaker를 로스터(`npc_roster_service`) canonical 값과 일치시킨다.
  - 예: Immigration `OFFICER_HALE` → `hale` / "Officer Hale", Baggage `BAGGAGE_STAFF_01` → `brielle`.
- 챕터별 시작 inventory/flags가 실제 노드 컨텍스트와 맞는지 점검(특히 Baggage `baggage_claim_tag`).
- 아래 B~F 작업으로 추가되는 UI 영역과 충돌하지 않게 좌측 레일(left-rail) 레이아웃 재정리.

**변경 파일:** `demo/respond-dialog/index.html` (필요 시 `_chapter_id_for_demo_node` 보강).

---

### B. 챕터별 NPC 선택 UI
**목표:** 챕터 선택 버튼 **아래**에 해당 챕터에 할당 가능한 NPC를 고르는 드롭다운 추가.

- 챕터→선택 가능 NPC 후보(로스터 role 기준):
  | 챕터 | 후보 NPC |
  |---|---|
  | Flight (seatmate) | arabella, novak, emily |
  | Immigration (immigration_officer) | hale, harris |
  | Baggage (baggage_agent / security_officer) | brielle, dan |
  | Result | 선택 불필요(비활성) |
- 동작:
  - 챕터 전환 시 드롭다운 옵션을 해당 챕터 후보로 갱신, 기본값은 챕터 디폴트 NPC.
  - NPC 변경 시 `turn.npc.npc_id` / `npc_role` / 표시용 speaker를 갱신하고, `resetTranscript`의 화자명도 반영.
- 데이터 공급 — **확정: demo 엔드포인트 신설**:
  - `GET /api/game/ai/demo/npc-roster` → role/챕터별 NPC 후보 목록(id, display_name, role) 반환. `npc_roster_service`에 목록 반환 헬퍼 추가.

**변경 파일:** `demo/respond-dialog/index.html`, `backend/app/api/ai_respond.py`(roster 엔드포인트), `npc_roster_service.py`(목록 반환 헬퍼).

---

### C. 토큰 예상비용 미표시 버그 수정
**현상:** "Session Usage"의 Cost USD가 항상 `$0.000000`.

**원인 후보 (조사 → 수정):**
1. **가격표 누락(가장 유력):** [llm_cost_estimator.py](../backend/app/agents/agent_c/llm_cost_estimator.py)의 `OPENAI_TEXT_MODEL_PRICES_USD_PER_1M`에 `gpt-4o-mini` **단 1종**만 등록. 실제 호출 모델명이 다르면 `estimate_openai_llm_cost_usd`가 `0.0` 반환.
2. **로그에 model_usage 미기록:** AgentRun 로그(`unified_agent_runs.jsonl`)의 `model` 필드에 `model_name` 또는 `input/output_tokens`가 비면 `_model_usage`가 0 처리.
3. **request_id 매칭 누락:** 프런트의 `submittedRequestIds`와 로그 `request_id` 불일치 시 세션 합산에서 제외.

**수정 방향:**
- 실제 사용 모델명을 로그에서 확인 → 가격표에 해당 모델 단가 추가(필요 시 provider별 표로 확장, OpenAI 전용 가정 제거).
- 토큰은 나오는데 비용만 0이면 (1)번, 토큰도 0이면 (2)·(3)번을 우선 점검.
- 프런트는 이미 `estimated_cost_usd`를 읽으므로 정상화 후 표시 확인. 진단을 돕도록 토큰/비용 카드에 "모델명" 또는 "no price for &lt;model&gt;" 보조 표기 추가 검토.

**검증:** 실제 1턴 실행 후 `GET /agent-runs/session-usage?session_id=...&request_ids=...` 응답에 `total_tokens>0`, `estimated_cost_usd>0` 확인.

**변경 파일:** `llm_cost_estimator.py`(가격표), 필요 시 로그 기록 경로 / `agent_run_summary_service.py`, `demo/respond-dialog/index.html`(보조 표기).

---

### D. 텍스트 직접 입력 → 전송 (STT 생략, 비용 절감)
**목표:** record 영역 **아래**에 텍스트 입력란 + 전송 버튼을 두어, 녹음/STT 없이 입력 텍스트를 바로 `/respond`로 전송.

- 백엔드는 이미 텍스트 직행 경로를 지원: `/respond`가 JSON 본문 `{ turn, audio: { transcript, transcript_provider } }`를 받음(현재 실시간 STT 최종본 제출이 이 경로 사용 — `submitFinalRealtimeTranscript` 참고).
- 추가 UI:
  - `<textarea id="manualText">` + `<button id="sendTextButton">전송</button>` (record-panel 하단).
  - 핸들러: 입력 텍스트로 `turn.audio.transcript` 설정, `transcript_provider`는 `"mock"`(또는 `manual_text`) 사용 → 기존 `submitFinalRealtimeTranscript`를 일반화한 `submitManualText()` 신설.
  - 빈 문자열/터미널 상태 가드, 전송 중 컨트롤 비활성화는 기존 `setSubmitting` 재사용.
- `transcript_provider`로 허용되는 값 확인 필요(스키마 `SttRuntimeUsed`에 `mock` 포함됨 → 사용 가능).

**변경 파일:** `demo/respond-dialog/index.html`. (백엔드 변경 불필요 예상; provider 값 검증만 확인.)

---

### E. 억까 방문지/수화물 부여 + 드롭다운 선택 + 확인 적용
**목표:** 좌측 하단에 플레이어에게 부여된 **방문 위치 / 수화물**을 표시하고, 드롭다운으로 직접 선택·`확인` 적용.

- UI(좌측 하단 신규 섹션, Flight 외 챕터에서만 노출):
  - "방문 위치" 드롭다운(`LOCATIONS` 목록), "수화물" 드롭다운(`CUSTOMS_ITEMS` 목록), `확인` 버튼.
  - `확인` 클릭 시 선택값을 `turn.game_state`에 반영:
    - `assigned_visit_location`, `assigned_visit_location_ko`, `visit_location_difficulty`, `visit_location_suspicion_reason`
    - `random_customs_item`(= `RandomCustomsItemContext`: item_id/name/category/description/difficulty/suspicion_reason)
- 부여 규칙(영어 레벨 기반) — **기존 12점 루브릭 체인 재사용**:
  - 페이지에 **English Level 입력(루브릭 총점 0~12, 기본값 0)** 추가. 게임 시작 기본값은 `TSL_1_SURVIVAL`(= 총점 0~3)과 일치.
  - **레벨이 구체 값(0~12)** → `tier_difficulty_controller.travel_speaking_level_for_total(level)`로 TSL 도출 후 해당 난이도 풀에서 **결정적**으로 부여(seed 고정 rng 사용, 드롭다운 기본 선택값으로 채움).
    | 총점 | TSL | 난이도 풀 |
    |---|---|---|
    | 0–3 | TSL_1_SURVIVAL | 1–3 (장소는 1–2로 fallback) |
    | 4–6 | TSL_2_FUNCTIONAL | 4–6 |
    | 7–9 | TSL_3_INDEPENDENT | 7–9 |
    | 10–12 | TSL_4_STRATEGIC | 10–12 |
  - **레벨이 null/none** → 억까 리스트 전체에서 **랜덤** 부여.
  - 부여 로직은 `challenge_assignment_service`(`pick_location`/`pick_customs_item`, `TSL_TO_DIFFICULTY_RANGE`)와 `tier_difficulty_controller.travel_speaking_level_for_total` 재사용. **새 매핑표 신설 없음.**
- 데이터 공급 — **확정: demo 엔드포인트 신설**(테이블 프런트 복제 안 함):
  - `GET /api/game/ai/demo/eokkka/options` → `LOCATIONS`/`CUSTOMS_ITEMS` 두 테이블 전체(드롭다운 채우기).
  - `GET /api/game/ai/demo/eokkka/assign?level=<int|null>` → 레벨 기반 부여 1건. `level`이 정수면 결정적, 비우면 랜덤. 응답에 `game_state`에 넣을 4개 location 필드 + `random_customs_item` 객체를 그대로 반환.

**변경 파일:** `demo/respond-dialog/index.html`, `backend/app/api/ai_respond.py`(신규 demo 엔드포인트 2종), 필요 시 `challenge_assignment_service.py`(레벨→결정적 선택 헬퍼 추가).

---

### F. Flight 챕터에서 억까 비활성화
**목표:** 억까는 입국심사/수화물 맥락 전용이므로 **Flight 챕터에서 E 섹션 전체 비활성/숨김**.

- 챕터 선택이 `CH0_01_FLIGHT_SMALLTALK`이면 억까 섹션(방문지/수화물 드롭다운 + 확인 + English Level) 숨김 또는 disabled.
- 챕터 전환 시 `turn.game_state`의 `assigned_visit_location*` / `random_customs_item`을 **초기화(null)** 하여 잔존 값 유입 방지.
- Result 챕터는 별도 정책 확인(부여 불필요 예상 → 함께 비활성).

**변경 파일:** `demo/respond-dialog/index.html`.

---

## 3. 확정된 결정 사항

1. **데이터 공급 방식 (NPC / 억까)**: **demo 엔드포인트 신설**로 확정. 테이블 프런트 복제 안 함.
   - `GET /api/game/ai/demo/npc-roster`, `GET /api/game/ai/demo/eokkka/options`, `GET /api/game/ai/demo/eokkka/assign?level=`
2. **영어 레벨 정의 / 매핑**: 신규 매핑표 없이 **기존 12점 루브릭 체인 재사용**으로 확정.
   - `travel_speaking_level` 게임 시작 기본값 = `TSL_1_SURVIVAL`(de-facto). 테스트 페이지 입력은 **루브릭 총점 0~12 정수**.
   - level(0~12) → `tier_difficulty_controller.travel_speaking_level_for_total()` → TSL → `challenge_assignment_service` 난이도 풀 → 결정적 부여. null/none → 랜덤.

### 남은 사소한 확인 (구현 중 결정 가능)
- **텍스트 전송 시 `transcript_provider` 표기값**: `"mock"` 사용 가능. 분석 로그 구분이 필요하면 신규 값 추가 여부만 결정.
- **Result 챕터 억까 처리**: Flight와 함께 비활성 처리 예정(부여 불필요 가정).

---

## 4. 작업 순서 / 예상 규모

| 순서 | 항목 | 백엔드 | 프런트 | 비고 |
|---|---|---|---|---|
| 1 | C. 비용 버그 수정 | ○ | △ | 독립적, 먼저 처리 가능 |
| 2 | A. 페이지 최신화 | △ | ○ | 이후 작업 토대 |
| 3 | D. 텍스트 직접 전송 | ✕ | ○ | 백엔드 변경 거의 없음 |
| 4 | B. 챕터별 NPC 선택 | △/○ | ○ | 엔드포인트 결정에 따라 |
| 5 | E. 억까 부여/드롭다운 | ○ | ○ | 확인 사항 2 합의 후 |
| 6 | F. Flight 억까 비활성 | ✕ | ○ | E에 의존 |

- 대부분 변경은 `demo/respond-dialog/index.html`(단일 파일)에 집중.
- 신규 백엔드는 demo 전용 읽기 엔드포인트(roster/eokkka) 2~3개로 한정 → 게임 본 계약(`/respond`)에는 영향 없음.

## 5. 검증 방법
- 로컬 서버 기동 후 `http://127.0.0.1:8000/respond-dialog`에서 각 챕터·NPC·텍스트 전송·억까 부여 수동 확인.
- 1턴 실행 후 Session Usage 토큰/비용 > 0 확인.
- Flight 챕터에서 억까 섹션 미노출 확인.
- 기존 테스트 [backend/tests/test_demo_ai_respond_page.py](../backend/tests/test_demo_ai_respond_page.py) 및 신규 엔드포인트용 테스트 추가.
