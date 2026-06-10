# 개발자 B 잔여 알파 작업 구현 계획 (Dev B Remaining Alpha Work Implementation Plan)

> **에이전트 작업 가이드:** 이 계획을 태스크별로 수행하기 위해 `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans` 역량을 필수로 사용해야 합니다. 각 단계의 진행 상황은 체크박스(`- [ ]`) 구문을 활용해 추적하세요.

---

## 개요 및 목표

**목표:** 2026-06-08 계획 구현 및 2026-06-09 코드 리뷰 결과를 반영하여, 개발자 B(Dev B) 소유의 잔여 알파(Alpha) 정책 및 보고서 관련 작업을 마무리합니다.

**아키텍처 역할 정의:**
*   **개발자 B (Dev B):** 결정론적(Deterministic) 레벨, 힌트, 시나리오 정책, 보고서 시드(seed) 데이터 및 Dev B 소유의 보고서 빌더(builder)를 책임집니다.
*   **개발자 A (Dev A):** NPC 대화 및 TTS를 담당합니다.
*   **개발자 C (Dev C):** 전체 오케스트레이션, 이해(Understanding) 모델, 응답 어셈블리, 엔드포인트 규격, 컷신/스킵 흐름 및 Dev B 이외 영역의 OpenKB 런타임 조율을 맡습니다.
*   *주의:* Dev A/C에 대한 런타임 요구사항은 `docs/contracts/change_requests.md`와 `docs/handoff.md`에 기록하여 협업합니다.

**기술 스택:** Python 3.12, uv, pytest, ruff, mypy, Pydantic 스키마, Dev B 소유의 시나리오 JSON, Dev B 소유의 OpenKB JSONL 레코드.

---

## 현재 상태 (2026-06-08 계획 기준)

### 완료된 항목 (Dev B 코드 내 구현 완료)
*   **IMMIGRATION_ALPHA:** 난이도(Tier) 정책 및 Gold 전용 `IMM_ALPHA_GOLD_BAG_CONTENT_CHECK` 챌린지를 포함한 프로토타입 확장.
*   **Chapter 0 테스트:** 플레이 가능한 입국 심사 노드, 골드 챌린지 노드, 수하물 노드에 대한 성공/재시도(success/retry) 테스트 구축.
*   **자가 검증(Self-checks):** OpenKB에 기록하기 전에 분기(branch), 힌트, 피드백, 에러 캡처, 최종 보고서 시드 및 루브릭(rubric) 불변 조건이 맞는지 Dev B 출력값 검증.
*   **FocusOnFormReportPolicy:** Dev B 소유의 보고서 빌더 클래스 구현 및 직접 테스트 완료.
*   **focus_on_form_cards.json:** 현재 Dev B의 Focus-on-Form 타겟 세트 추가 완료 (`backend/app/kb/dev_b/focus_on_form_cards.json`).
*   **OpenKB 런타임 호환성:** 기존 호환 키를 유지하면서 점진적인 `dev_b_openkb_record.v2` 메타데이터 지원.
*   **LLM 피드백 가드:** 허용되지 않은 권한(authority) 키를 차단하고, 공개용 `DevBPolicyOutput`에는 노출하지 않은 채 AgentRun 이벤트 요약에 LLM 사용 현황을 기록하도록 구현.
*   **수하물 미보유 (BAGGAGE_MISSING):** `BAG_002_FIND_STAFF`부터 `BAG_007_RESOLUTION`까지의 Dev B 소유 노드 정의 완료.
*   **문서 업데이트:** 현재 어댑터 및 알파 핸드오프 상태를 반영하여 관련 문서(`change_requests.md`, `portfolio_dev_b.md`, `handoff.md`) 최신화.

### 미구현 항목 (Dev B 소유 작업 중 미완료)
*   **FLIGHT_001_SEATMATE_SMALLTALK:** 시나리오 문서는 작성되었으나, Dev B 소유의 진단 정책(Diagnostic Policy) 및 노드 데이터가 정의되지 않음.
*   **기내 스몰토크 가드:** 비행기 안에서의 가벼운 대화(스몰토크) 단계에서 외부에 공개되는 게임 밖 피드백(out-game feedback)을 생성하지 않도록 강제하는 Dev B 소유의 안전 가드가 없음.
*   **세션 단위 Focus-on-Form 리포터:** Dev B 소유의 Focus-on-Form 보고서 작성이 개별 레코드 기록 방식으로만 되어 있어, Dev C가 `out_game_feedback`을 노출할 때 호출할 수 있는 세션 레벨의 리더/헬퍼 메서드가 없음.
*   **추가 선택적 이벤트 시드:** 세관 문제, 여권 분실, 도착 후 기내 승객과의 재회 등 수하물 단계 이후의 선택적 이벤트가 Dev B 시나리오 시드 문서에 부재함.

### 외부 블로커 (Dev B 외부 소유 영역)
*   **오케스트레이션 (Dev C):** `FLIGHT_001_SEATMATE_SMALLTALK -> IMMIGRATION_ALPHA -> BAGGAGE_MISSING`으로 이어지는 씬 흐름 연동 미구현.
*   **의도 이해 (Dev C):** 의도 파악(Understanding) 규칙 모드가 여전히 입국 목적 분류에 집중되어 있어, 비행/수하물 관련 슬롯 파싱을 지원하지 않음.
*   **대화 연동 (Dev A/C):** 현재 다음 노드 대화 탐색 기능이 `IMM_` 노드 ID에 대해서만 동작함.
*   **응답 데이터 규격 (Dev C):** 최종 응답/결과 데이터에 Dev B의 `FocusOnFormReportPolicy.build_report(...)` 결과물(`out_game_feedback`)을 노출하는 작업 미반영.
*   **오디오/대화 (Dev A):** Dev B의 난이도 메타데이터를 사용하여 난이도별 발화 속도, 엄격도, 씬 역할 조율을 연동하는 작업 미완료.

---

## 실행 순서 (Execution Order)

1.  **Dev B 소유의 기내 스몰토크 진단 정책 추가**
2.  **`FLIGHT_001_SEATMATE_SMALLTALK` 노드 데이터 정의 및 보고서 미노출 가드 구현**
3.  **Dev B 소유의 세션 레벨 Focus-on-Form 보고서 헬퍼 구현**
4.  **향후 시나리오 확장을 위한 알파 단계 선택적 이벤트 시드 문서 작성**
5.  **Dev A/C 잔여 협업 요청 사항을 핸드오프 문서에 반영**
6.  **Dev B 전용 테스트, 통합 테스트, 전체 테스트 실행 및 Ruff/Mypy 정적 분석 검증**

---

## 세부 태스크 계획

### 태스크 1: 기내 스몰토크 진단 정책 (Flight Small-Talk Diagnostic Policy)

*   **대상 파일:**
    *   [신규] `backend/app/services/service_b/flight_smalltalk_diagnostic_policy.py`
    *   [신규] `backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py`
    *   [수정] `backend/app/services/service_b/__init__.py`

*   [ ] **단계 1: 실패하는 진단 정책 테스트 작성**
    `backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py` 파일을 생성하고 실패 조건 테스트를 작성합니다. (스몰토크는 최소 3턴이 필요하며, 5턴 이상 시 스킵이 가능해지고, 게임 밖 피드백은 제공되지 않는 스펙을 검증합니다.)
*   [ ] **단계 2: 테스트 실행 및 실패(RED) 확인**
    아래 명령어를 통해 모듈을 찾을 수 없어 실패하는지 확인합니다:
    ```powershell
    uv run pytest backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py -q
    ```
*   [ ] **단계 3: 진단 정책 로직 구현**
    `backend/app/services/service_b/flight_smalltalk_diagnostic_policy.py` 파일을 생성하여 스몰토크 턴 수 평가 로직(`evaluate`) 및 폴백(fallback) 질문 조회 기능을 구현합니다.
*   [ ] **단계 4: 모듈 내보내기 설정**
    `backend/app/services/service_b/__init__.py`에서 새로운 `FlightSmallTalkDiagnosticPolicy` 클래스를 dynamic import할 수 있도록 `__all__`과 `__getattr__`을 업데이트합니다.
*   [ ] **단계 5: 테스트 재실행 및 성공(GREEN) 확인**
    다시 테스트를 실행하여 테스트가 모두 통과하는지 검증합니다:
    ```powershell
    uv run pytest backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py -q
    ```

---

### 태스크 2: 기내 노드 데이터 및 보고서 미노출 가드 (Flight Node Data & Feedback Guard)

*   **대상 파일:**
    *   [수정] [scenario_nodes.json](file:///C:/potenup3/pj05_Murphy/backend/app/data/scenario_nodes.json)
    *   [수정] [english_level_hint_agent.py](file:///C:/potenup3/pj05_Murphy/backend/app/agents/agent_b/english_level_hint_agent.py)
    *   [수정] [test_developer_b_policy_engine.py](file:///C:/potenup3/pj05_Murphy/backend/tests/dev_b/test_developer_b_policy_engine.py)

*   [ ] **단계 1: 스몰토크 노드 데이터 및 피드백 시드 정책 실패 테스트 작성**
    `backend/tests/dev_b/test_developer_b_policy_engine.py` 파일 끝에 비행 스몰토크 노드가 정상 정의되었는지, 그리고 해당 노드 평가 시 `out_game_feedback_seed`가 비활성화(`include_in_final_report = False`) 상태인지 검증하는 테스트를 추가합니다.
*   [ ] **단계 2: 테스트 실행 및 실패(RED) 확인**
    아직 노드가 데이터에 정의되지 않았으므로 실패하는지 확인합니다:
    ```powershell
    uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_node_exists_as_diagnostic_alpha_node backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_never_creates_visible_out_game_feedback_seed -q
    ```
*   [ ] **단계 3: 시나리오 데이터에 `FLIGHT_001_SEATMATE_SMALLTALK` 노드 정의 추가**
    `backend/app/data/scenario_nodes.json`에 비행기 옆자리 스몰토크 노드 상세 스펙(목표, 인텐트, 필수/선택적 슬롯, 힌트 등)을 추가합니다.
*   [ ] **단계 4: 피드백 시드 생성 시 비행기 노드 가드 처리 추가**
    `backend/app/agents/agent_b/english_level_hint_agent.py`의 `_build_out_game_feedback_seed(...)` 내부에 `FLIGHT_`로 시작하는 노드 ID의 경우, 최종 리포트에 포함하지 않고 피드백 타겟을 제거하는 예외 처리를 추가합니다.
*   [ ] **단계 5: 테스트 성공(GREEN) 확인**
    정상 작동하는지 다시 확인합니다:
    ```powershell
    uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_node_exists_as_diagnostic_alpha_node backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_smalltalk_never_creates_visible_out_game_feedback_seed -q
    ```

---

### 태스크 3: 세션 단위 Focus-on-Form 보고서 헬퍼 (Session-Level Focus-on-Form Helper)

*   **대상 파일:**
    *   [수정] [focus_on_form_report_policy.py](file:///C:/potenup3/pj05_Murphy/backend/app/services/service_b/focus_on_form_report_policy.py)
    *   [수정] [test_focus_on_form_report_policy.py](file:///C:/potenup3/pj05_Murphy/backend/tests/dev_b/test_focus_on_form_report_policy.py)

*   [ ] **단계 1: 세션 헬퍼 메서드 실패 테스트 작성**
    `backend/tests/dev_b/test_focus_on_form_report_policy.py`에 로컬 임시 디렉토리에 여러 JSONL 기록을 만들고, 세션 ID 기반으로 한 번에 병합하여 보고서를 추출해내는 헬퍼가 오동작하는지 실패 테스트를 작성합니다.
*   [ ] **단계 2: 테스트 실행 및 실패(RED) 확인**
    아직 인스턴스화 시 `runtime_root`를 받지 못해 실패하는지 검증합니다:
    ```powershell
    uv run pytest backend/tests/dev_b/test_focus_on_form_report_policy.py::test_focus_on_form_report_can_be_built_from_session_jsonl -q
    ```
*   [ ] **단계 3: `FocusOnFormReportPolicy` 기능 확장**
    생성자에서 `runtime_root`를 전달받을 수 있도록 설정하고, 특정 세션 ID를 받아 로컬 디렉토리에서 관련 JSONL 파일을 파싱하여 한꺼번에 보고서로 빌드해주는 `build_session_report(session_id)`를 구현합니다.
*   [ ] **단계 4: 전체 보고서 정책 테스트 성공(GREEN) 확인**
    구현 완료 후 모든 보고서 관련 테스트가 통과하는지 확인합니다:
    ```powershell
    uv run pytest backend/tests/dev_b/test_focus_on_form_report_policy.py -q
    ```

---

### 태스크 4: 알파 추가 선택적 이벤트 시드 문서 (Optional Alpha Event Seeds)

*   **대상 파일:**
    *   [신규] `docs/superpowers/plans/2026-06-09-alpha-optional-events-dev-b-seeds.md`

*   [ ] **단계 1: 선택적 이벤트 시드 문서 작성**
    수하물 회수 이후 단계에 들어갈 수 있는 후보 기획 문서(`CUSTOMS_DECLARATION_PROBLEM` 세관 신고 문제, `PASSPORT_STOLEN` 여권 도난, `SEATMATE_REUNION` 도착장 옆자리 승객 재회) 및 각 인텐트/슬롯 정보를 포함한 문서를 지정 경로에 생성합니다.
*   [ ] **단계 2: 임시 작성 마커(TBD, TODO 등) 점검**
    문서 내에 불완전하게 남겨진 기획이 없는지 `rg` 명령어로 검사합니다:
    ```powershell
    rg -n "TB[D]|TO[D]O|implement[ ]later|fill[ ]in" docs/superpowers/plans/2026-06-09-alpha-optional-events-dev-b-seeds.md
    ```

---

### 태스크 5: 핸드오프 문서 갱신 (Handoff Refresh)

*   **대상 파일:**
    *   [수정] [handoff.md](file:///C:/potenup3/pj05_Murphy/docs/handoff.md)
    *   [수정] [change_requests.md](file:///C:/potenup3/pj05_Murphy/docs/contracts/change_requests.md) (필요시 수정)

*   [ ] **단계 1: 개발자 B 잔여 작업 완료 항목 추가**
    `docs/handoff.md` 최신 Dev B 항목 뒤에 기내 스몰토크 진단 추가, 스몰토크 전용 노드 데이터 및 피드백 숨김 처리 가드 반영, 세션 보고서 헬퍼 제공, 추가 선택 이벤트 시드 완료 항목을 정성스럽게 기록합니다.
*   [ ] **단계 2: 문서 정합성 스캔**
    이전 빌드 기준의 잘못된 현재 상태 문구가 남아있는지 `rg` 명령어로 진단합니다:
    ```powershell
    rg -n "current runtime still calls|No cross-owner change requests|replace the current mock|full out-game practice-card generation from Focus-on-Form records is still not implemented" docs
    ```

---

### 태스크 6: 최종 검증 (Verification)

*   [ ] **단계 1: 개발자 B 집중 테스트 수행**
    ```powershell
    uv run pytest backend/tests/dev_b -q
    ```
*   [ ] **단계 2: 개발자 B 정책을 소비하는 통합 테스트 수행**
    ```powershell
    uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q
    ```
*   [ ] **단계 3: 전체 테스트 스위트 구동**
    ```powershell
    uv run pytest -q
    ```
*   [ ] **단계 4: 정적 검사 및 타입 힌팅 점검**
    ```powershell
    uv run ruff check .
    uv run mypy .
    ```

---

## 인수 조건 (Acceptance Criteria)

1.  `FLIGHT_001_SEATMATE_SMALLTALK` 노드가 진단 정책에 맞게 최소 턴(3회) 및 스킵 조건(5회) 판정을 정상 반환합니다.
2.  비행기 스몰토크 노드는 어떠한 경우에도 외부 노출용 피드백 시드(`out_game_feedback`)를 생성하지 않습니다.
3.  세션 ID만 전달하면 로컬 `dev_b` OpenKB 로그 데이터를 통합 조회하여 전체 세션 Focus-on-Form 리포트를 정상 추출할 수 있습니다.
4.  선택적 알파 이후 확장 이벤트 기획 시드 문서 작성을 완료합니다 (Dev C/A 런타임에 직접적 영향 없음).
5.  Dev A 및 Dev C를 향한 런타임 연동 요청 사항이 핸드오프 및 변경 요청 계약서에 명시됩니다.
6.  Ruff, Mypy를 포함한 전체 테스트 스위트가 온전히 통과됩니다.
