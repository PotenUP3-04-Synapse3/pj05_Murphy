# 작업계획서 — respond-dialog 결과 보기 / Result 버튼 정리 (2026-06-24)

대상 페이지: `GET /respond-dialog` → [demo/respond-dialog/index.html](../demo/respond-dialog/index.html)
관련 백엔드(재사용, 변경 없음): [backend/app/api/ai_respond.py](../backend/app/api/ai_respond.py) `GET /api/game/ai/result/{session_id}`
연계 계획서: [docs/workplan-flight-smalltalk-redesign.md](workplan-flight-smalltalk-redesign.md)

---

## 0. 현재 상태 (중요)

- **결과 보기(A)는 지난 세션에서 이미 `index.html`에 코드가 선반영된 상태**다(검증 전). 본 계획서는 그 작업을 사후 문서화하고, 남은 항목(B 중복 버튼 제거)과 보류 항목(C flight, D test)을 정리한다.
- → **결정 필요:** 선반영된 결과 보기 코드를 **(a) 유지하고 검증으로 진행** / **(b) 되돌린 뒤 계획대로 재작업**. 기본 제안은 (a).

---

## 1. 배경 / 현황

- `respond-dialog`는 Unreal 없이 한 턴 흐름을 수동 검증하는 **내부 테스트용 페이지**.
- 점수·티어·Focus-on-Form(FonF) 피드백을 만드는 백엔드 엔드포인트 `GET /api/game/ai/result/{session_id}`는 **이미 존재**하나, 데모 페이지에서 **호출하지 않고** 있었다.
- 좌상단 챕터 그리드에 **"Result" 버튼(`CH0_05_RESULT`)** 이 있으나, 이는 실제 점수가 아니라 `ALPHA_999_FINAL_SCOREBOARD` **대화 노드**를 띄울 뿐이라 "결과 확인"과 혼동된다.

### result 엔드포인트 반환 형태 (재사용 대상)
- 단일: `UnrealResultResponse` = `final_result`(`FinalResult`) + `out_game_feedback`(dict|null).
- 멀티: `UnrealRoomResultResponse` = `room_id`, `team_outcome`, `players[]`(player_id + final_result + out_game_feedback).
- `FinalResult`: `final_score_100`(0~100), `tier`(Gold/Silver/Bronze/Iron), `rank`(6종), `final_recommendation`, `quantitative_scores`(overall + 6개 영역), `report_summary`(overall/best_node/weakest_node/main_improvement), `reason_tags`.
- `out_game_feedback`(FonF): `focus_on_form_items[]`(title_kr/rule_summary_kr/original_utterances/suggested_expressions/practice_prompt_kr/priority…), `personalized_next_step`, `overall_summary_kr`.
- **레코드 없는 세션**(턴 미진행)도 200 + UNRANKED/Iron/0점 + "FonF 기록 없음"으로 graceful 반환 → 빈 상태 안내만 필요.

---

## 2. 작업 항목

### A. 결과 보기 버튼 + 모달  ⏺ 선반영됨(검증 전)
**목표:** 좌상단에 "📊 결과 보기" 버튼을 두고, 현재 세션 ID로 `GET /result/{session_id}`를 호출해 점수/티어/FonF를 모달로 표시.

- 헤더 좌측(제목 옆)에 `#viewResultButton` 추가.
- 모달(`#resultOverlay`)에서 렌더:
  - 점수(`final_score_100`/100), 티어 칩(Gold/Silver/Bronze/Iron 색상), 랭크, 판정(`final_recommendation`).
  - 세부 점수 6종 막대그래프(`quantitative_scores`).
  - 총평(`report_summary`: overall / 개선 포인트 / best·weakest 노드).
  - FonF 카드(`focus_on_form_items`: 오답 ✗ / 교정문 ✓ / 연습 프롬프트 / priority) + 다음 연습 추천(`personalized_next_step`).
- 멀티(`players[]`) 응답 자동 감지 → 플레이어별 블록 + 팀 결과 표시.
- 닫기: 닫기 버튼 / 배경 클릭 / Esc.
- 세션 ID 출처: `parseTurn().session.session_id`(없으면 Session 카드 텍스트 폴백). 없으면 "No Session" 경고.

**변경 파일:** `demo/respond-dialog/index.html` (백엔드 변경 없음).

---

### B. 중복 "Result" 챕터 버튼 제거  ◻ 미적용
**목표:** A의 결과 보기가 실제 점수를 담당하므로, 혼동되는 `CH0_05_RESULT` 챕터 버튼을 제거.

- 제거: 챕터 그리드의 `<button data-chapter-id="CH0_05_RESULT">Result</button>`.
- 정리(잔존 코드):
  - `chapterStarts.CH0_05_RESULT` 항목 — 버튼이 사라지면 진입 경로가 없어지므로 함께 제거(방어적으로 남길지 결정).
  - `startChapter`의 `CH0_05_RESULT` 분기(억까 섹션 숨김 처리) 정리.
  - `_chapter_id_for_demo_node`의 `ALPHA_` → `CH0_05_RESULT` 매핑은 백엔드 노드 조회용이라 **유지**(영향 없음).
- 챕터 그리드는 2열 → Flight/Immigration/Baggage 3개로 축소(레이아웃 확인).

**변경 파일:** `demo/respond-dialog/index.html`.

---

### C. Flight 챕터 — 재설계 연계로 **보류**  ⏸
**상태:** flight 챕터는 별도 재설계 진행 중([workplan-flight-smalltalk-redesign.md](workplan-flight-smalltalk-redesign.md): 턴 30 상한, skip 종료, 숨은목표 토픽선정, 레벨추정 교체). 이는 **턴 요청 스키마 신규 필드(skip 신호) = Unreal 계약 변경**을 동반한다.

- 현재 페이지는 flight를 고정 노드 `FLIGHT_A_001_SEATMATE_SMALLTALK` + `FLIGHT_` prefix ADVANCE 로직으로 다룸 → 재설계 후 흐름과 어긋날 수 있음.
- **본 라운드에서는 flight 페이지 변경을 진행하지 않음.** 재설계가 계약(skip 필드 등)까지 확정되면, 그때 respond-dialog에 skip 버튼/신규 흐름을 반영하는 후속 작업으로 분리.

**변경 파일:** (이번 라운드 없음) — 추후 `demo/respond-dialog/index.html`.

---

### D. 테스트 — **이번 라운드 미구현**  ⏸
- A(결과 보기)·B(버튼 제거)에 대한 자동 테스트는 **이번에 작성하지 않음**(사용자 결정).
- 참고: 페이지 라우팅 테스트 [backend/tests/test_demo_ai_respond_page.py](../backend/tests/test_demo_ai_respond_page.py) 존재. 향후 결과 보기 e2e/렌더 검증이 필요하면 별도 항목으로 추가.

---

## 3. 결정 사항 / 확인 필요

1. **선반영 코드 처리(0절)**: 유지+검증(권장) vs 되돌리기 — 확정 필요.
2. **`chapterStarts.CH0_05_RESULT` 잔존 여부**: 버튼 제거 시 함께 제거(권장) vs 방어적 보존.
3. flight(C)·test(D)는 **보류**로 확정.

---

## 4. 작업 순서 / 규모

| 순서 | 항목 | 백엔드 | 프런트 | 상태 |
|---|---|---|---|---|
| 1 | A. 결과 보기 버튼/모달 | ✕ | ○ | 선반영(검증 전) |
| 2 | B. 중복 Result 버튼 제거 | ✕ | ○ | 미적용 |
| 3 | C. Flight 재설계 반영 | ○ | ○ | 보류(연계) |
| 4 | D. 테스트 | - | - | 보류 |

- 변경은 `demo/respond-dialog/index.html` 단일 파일에 집중. 백엔드/게임 본 계약(`/respond`) 영향 없음.

## 5. 검증 방법 (A·B 적용 후)
- 로컬 서버 기동 → `http://127.0.0.1:8000/respond-dialog`.
- 한 챕터에서 1턴 이상 진행 후 "📊 결과 보기" → 점수/티어/세부점수/총평/FonF 정상 표시 확인.
- 턴 미진행 세션에서 결과 보기 → UNRANKED/0점 + "기록 없음" 빈 상태 안내 확인.
- 챕터 그리드에 Result 버튼 미존재, Flight/Immigration/Baggage 정상 전환 확인.
