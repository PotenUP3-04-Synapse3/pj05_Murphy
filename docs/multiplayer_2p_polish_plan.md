# 2인 멀티플레이 — Polish 계획 (잔여 LOW 5건)

> 대상: 구현 담당 전원
> 상태: **선택적 보강 (머지 차단 아님)**
> 최종 수정: 2026-06-24
> 선행: [multiplayer_2p_remediation_workplan.md](multiplayer_2p_remediation_workplan.md) 수정 + 리뷰

---

## 0. 원칙
- **개발자(Dev A/B/C) 구분 없이** 한 사람이 항목을 종착지까지 완결. 경계 접착·테스트 포함.
- 전부 LOW. 기능·안전성엔 문제없음. **품질/운영 견고성 보강**이 목적.

---

## 1. 먼저 정할 결정 (P-1·P-5를 한 번에 가름)

**질문: 공유 수화물 챕터에서 두 플레이어의 `session_id`는 같은가, 다른가?**

- **(권장) 같다 = `session_id == room_id`** (Unreal이 방을 세션으로 사용)
  → 디렉터리 스캔 폴백(현재 reader)을 **삭제**. P-1 테스트는 same-room 집계만,
  P-5 성능 문제도 **자동 소멸**(전수 스캔 제거).
- (대안) 다르다 = 플레이어별 session_id, 공유 room_id
  → 폴백 **유지**하고 P-1에 *다른 session_id* 라운드트립 테스트 추가, P-5 인덱싱 고려.

> 기본값: **같다(session_id==room_id)** 로 진행. 회의에서 "다르다"로 확정되면 대안 경로로 전환.
> 이 결정 하나로 아래 P-1·P-5 작업 내용이 갈린다.

---

## 2. 항목별 작업

### P-1 — 정체성 집계 일관성 마감
**목적**: R1 DoD("다른 session_id, 같은 room_id 집계")가 코드엔 있으나 테스트 미검증인 갭 정리.

**기본값(같다) 경로**
- `final_result_score_policy.py` `OpenKBFinalResultRecordReader.read_session_records` — **디렉터리 스캔 폴백 제거**, `{room_id}.jsonl` 직접 조회로 단순화.
- `backend/tests/dev_b/test_multiplayer_e2e.py` — same-room 집계가 동작함을 명시 단언(현 e2e에 1줄 추가).

**대안(다르다) 경로**
- 폴백 유지 + `test_multiplayer_e2e.py`에 **player1·player2가 서로 다른 session_id, 같은 room_id**로 `/respond` → `/result` 집계되는 라운드트립 테스트 신규.

**DoD**
- [ ] 선택한 정체성 규약이 reader·writer·`/result`에서 일치.
- [ ] 그 규약을 검증하는 라운드트립 테스트 1개 그린.

---

### P-2 — `/result` room_id 라벨 정확화
**목적**: 응답의 `room_id`가 경로 파라미터(`session_id`)가 아니라 **실제 room_id**를 반영하도록.

**파일**: `backend/app/api/ai_respond.py` `result()`

**작업**
- 멀티 분기에서 `room_id`를 레코드의 `room_id`(없으면 path 값)에서 도출해 `UnrealRoomResultResponse.room_id`에 사용.

**DoD**
- [ ] 플레이어 session_id로 조회해도 응답 `room_id`가 실제 방 ID와 일치(테스트).
- [ ] same-room(==) 케이스 회귀 그린.

---

### P-3 — reader 무음 드롭 로깅
**목적**: 검증 실패 레코드를 조용히 버려 런타임 드리프트가 숨는 위험 제거.

**파일**: `backend/app/services/service_b/final_result_score_policy.py` `_parse_file`

**작업**
- `except Exception: continue` → 동일하게 skip하되 **`logger.warning`으로 record_id/사유 남김**.
- 모듈 로거 추가(없으면).

**DoD**
- [ ] 깨진 레코드 1줄 포함 파일 파싱 시, 정상 레코드는 살고 **경고 로그가 1건** 남음(테스트).

---

### P-4 — 계약 테스트 자동 키-셋 비교 추가
**목적**: P4를 "필드별 명시 단언"에서 **"writer 출력 키 ⊇ reader 소비 키"의 자동 검증**으로 보강.

**파일**: `backend/tests/dev_b/test_record_contract.py`

**작업**
- writer `_build_record` 출력 키 집합 ⊇ `PolicyTurnFeedbackRecord.model_fields` 키 집합 자동 단언.
- (선택) reader가 실제 참조하는 키 목록과 스키마 필드 일치 점검.

**DoD**
- [ ] 스키마에 새 필드를 넣고 writer를 안 고치면 **테스트가 자동 실패**(역방향도 1케이스로 확인).

---

### P-5 — `/result` 디렉터리 스캔 성능
**목적**: 세션 누적 시 `*.jsonl` 전수 스캔(O(파일수)) 제거/완화.

- **기본값(같다)**: P-1에서 폴백 삭제 → **본 항목 자동 해소**. 별도 작업 없음.
- **대안(다르다)**: room_id→파일 인덱스(경량 매핑) 도입 또는 파일명 규약으로 직접 조회.

**DoD (대안 선택 시)**
- [ ] `/result` 조회가 전수 스캔 없이 상수/로그 시간에 파일 해결.

---

## 3. 순서
1. **§1 결정** 먼저(같다/다르다) → P-1·P-5 경로 확정.
2. P-1 → P-2 → P-3 → P-4 순(서로 독립이라 병행 가능).
3. 마지막 회귀: dev_b 전체 + 멀티 e2e 그린 확인.

> 기본값(같다)로 가면 실작업은 **P-1(단순화+테스트)·P-2·P-3·P-4** 넷이고 P-5는 자동 해소.
