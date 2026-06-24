# bad-end 결과조회 테스트 격리 작업 계획서

> 작성일: 2026-06-24
> 작성자: wd14177 (level_agent)
> 소스: 최종 결과 페이로드 잔여 작업 검증 중 발견된 테스트 위생 이슈
> 범위: `backend/tests/test_final_result_payload.py`의 신규 테스트 1건의 파일 I/O 격리. 프로덕션 코드 변경 없음.
> 영향: `backend/tests/test_final_result_payload.py` (테스트 전용)

---

## 0. 요약 & 문제

`test_result_endpoint_returns_bad_end_comic_fail_from_real_records`는 bad-end(욕설→Comic Fail→Iron) 경로가 `GET /result/{session_id}`에서 올바르게 집계되는지 검증한다. 검증 자체는 유효하나, **실 런타임 경로에 직접 파일을 쓰고 지우는** 방식이라 테스트 위생이 약하다.

**현재 동작:**
- `backend/runtime/openkb/dev_b/` 디렉터리를 `mkdir(parents=True, exist_ok=True)`로 생성.
- 고정 `session_id = "session_test_bad_end_comic_fail"`로 `.jsonl`을 직접 write.
- `finally`에서 해당 `.jsonl`만 `unlink`.

**문제점:**
1. **실 데이터 디렉터리 오염 위험:** 프로덕션/개발 런타임과 동일한 경로(`backend/runtime/openkb/dev_b/`)를 사용. 테스트가 실제 세션 로그와 같은 공간에 파일을 생성한다.
2. **불완전한 정리:** `.jsonl` 파일은 지우지만, 테스트가 새로 만든 디렉터리는 남는다. 또한 테스트가 중간에 죽으면(프로세스 강제 종료 등) 잔여 파일이 남을 수 있다.
3. **격리 부재:** `OpenKBFinalResultRecordReader` / `FocusOnFormReportPolicy`의 기본 `runtime_root`가 하드코딩 경로라, 병렬 실행이나 동일 id 충돌 시 비결정적일 수 있다.
4. **엔드포인트가 기본 reader를 사용:** `/result` 핸들러가 `DevBPolicyClient()`를 기본 생성하므로, 현재는 경로 주입 없이 실 경로에 의존한다.

> 참고: 같은 파일의 기존 테스트 `test_result_endpoint_returns_unreal_result_payload`는 `monkeypatch.setattr(ai_respond, "DevBPolicyClient", FakeDevBPolicyClient)`로 클라이언트를 통째로 교체해 파일 I/O를 회피한다 — 격리의 좋은 선례.

---

## 1. 목표

bad-end 집계 검증의 **의미(verbal_abuse → COMIC_FAIL → tier Iron)는 유지**하면서, 실 런타임 디렉터리에 의존하지 않도록 파일 I/O를 격리한다.

---

## 2. 작업 항목 (택1 — §3에서 결정)

### 옵션 A (권장) — `tmp_path` + reader runtime_root 주입
실제 JSONL을 통한 통합 검증 성격을 유지하되, 임시 디렉터리에 쓴다.
- pytest `tmp_path` 픽스처로 임시 openkb 루트 확보.
- `/result` 핸들러가 `DevBPolicyClient`를 기본 생성하므로, `monkeypatch`로 `tmp_path`를 `runtime_root`로 주입한 `DevBPolicyClient`(또는 그 내부 `OpenKBFinalResultRecordReader`/`FocusOnFormReportPolicy`)를 쓰도록 교체.
- 장점: 실 경로 오염 0, 자동 정리(tmp_path), bad-end 집계의 실제 산출 로직(`build_result`)은 그대로 통과.
- 작업: 테스트에서 `tmp_path` 기반 reader를 만들고 `ai_respond.DevBPolicyClient`를 주입 가능한 형태로 monkeypatch. (필요 시 `DevBPolicyClient.__init__`가 이미 받는 `final_record_reader` 인자를 활용.)

### 옵션 B — 정책 단위 테스트로 강등
엔드포인트 왕복 없이 `FinalResultScorePolicy().build_result(records)`에 verbal_abuse 레코드를 직접 넘겨 `COMIC_FAIL`/`Iron`을 단언.
- 장점: 파일 I/O 전무, 가장 빠르고 결정적.
- 단점: `/result` 엔드포인트 경유(라우팅·응답 envelope) 검증은 빠짐. 단, bad-end의 `rank`/`tier` 산출은 이미 `test_final_result_score_policy.py`가 정책 레벨에서 커버하므로 중복일 수 있음.
- 보완: 엔드포인트 검증이 필요하면 기존 `FakeDevBPolicyClient` 선례처럼 monkeypatch로 가짜 클라이언트가 bad-end FinalResult를 반환하게 하는 경량 테스트를 별도로 둔다.

---

## 3. 결정 필요 (Decisions)

- **D1 — 격리 방식:** 옵션 A(tmp_path 통합) vs 옵션 B(정책 단위 + 선택적 fake 엔드포인트). 
  - "실 JSONL→/result 왕복"의 통합 가치를 중시하면 A, 중복 최소화·속도 우선이면 B.
- **D2 — 공용 픽스처화:** 향후 유사 테스트를 위해 `tmp_path` 기반 openkb 루트 + `DevBPolicyClient` 주입을 conftest 픽스처로 추출할지.

---

## 4. 검증 계획

- 변경 후 `uv run pytest backend/tests/test_final_result_payload.py -q` 그린.
- 테스트 실행 전후로 `backend/runtime/openkb/dev_b/`에 **신규 파일이 생기지 않음**을 확인.
- bad-end 단언(`final_recommendation == "COMIC_FAIL"`, `rank == "Comic Fail"`, `tier == "Iron"`, `"verbal_abuse" in reason_tags`)은 그대로 유지.
- 전체 `uv run pytest` 회귀 그린 유지.

---

## 5. 비고

- 프로덕션 코드(`final_result_score_policy.py`, `dev_b_level_hint_client.py`, `ai_respond.py`) 변경은 불필요. 단, 옵션 A에서 reader 주입을 깔끔히 하려면 `DevBPolicyClient`가 이미 노출한 생성자 인자(`final_record_reader`, `focus_on_form_report_policy`)로 충분한지 확인 필요.
- 리스크: 낮음(테스트 전용). 기능/계약 영향 없음.
