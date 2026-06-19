# retry 정책 완화 + A/B desync 대응 계획

## Context
입국심사 대화에서 정상 답변("maybe 13days")이 막히고 강제 2차 심사로 끝나는 사례가 보고됨.
로그 분석 결과 두 문제가 확인됨:

1. **retry 한도 정책이 과함** — `_clarify`(UNCLEAR)도 `retry_count`를 +1 하고
   (`scenario_state_machine.py:356`), `retry_count >= 3`이면 강제 `END_SECONDARY_INSPECTION`
   (`scenario_state_machine.py:67-68`). 즉 "불명확(UNCLEAR)"이 "명백한 오답(FAIL)"과
   동일하게 카운트되어, clarify 2회 + hint 1회 만에 게임이 강제 종료됨.
2. **A/B desync (치명적)** — 같은 턴에서 B는 `UNCLEAR→clarify`(체류기간 재질문)로
   판정했는데 A의 NPC 대사는 "Good. Next, tell me where you will stay."로 **다음 질문
   (숙소)으로 진행**. A의 LLM 생성 경로(`npc_dialogue_agent.node_generate_dialogue_llm`)에
   비-ADVANCE 분기에서 진행을 막는 가드가 없음. 플레이어가 NPC가 말한 질문(숙소)에
   답하면 B는 여전히 체류기간을 채점 → 반복 실패 → 강제 종료.

확정된 처리 방침(사용자):
- retry 정책: **UNCLEAR를 hard-fail 카운터에서 분리 + 한도 상향** (B 영역, 직접 구현).
- desync: **B 영역이 아니므로 change_request로 작성**(A 영역, 일부 C).
- false-UNCLEAR 트리거("maybe" 헤지로 UNCLEAR 처리)는 **이번 범위 제외**(별도 처리).

---

## Part A — retry 정책 완화 (B 영역, 직접 구현)

파일: `backend/app/services/service_b/scenario_state_machine.py`

1. **UNCLEAR 분리**: `_clarify`의 `retry_count_delta`를 `1 → 0`으로 변경(`:356`).
   - 불명확은 강제 탈락 카운터에 가산하지 않음. 무한 clarify 루프는 기존
     `patience <= 0` 안전망(clarify는 patience -5 유지)으로 자연 종료되므로 별도 cap 불필요.
   - 결과적으로 hard-fail 카운터(`retry_count`)는 `_retry`/`_hint`/`_critical_fail`
     (실제 오답·위험)만 누적.
2. **한도 상향**: 강제 탈락 임계를 상수화하고 `3 → 5`로 상향.
   - `:13` 부근에 `MAX_HARD_FAIL_RETRIES = 5` 상수 추가, `:68`의
     `payload.scenario_state.retry_count >= 3`을 상수 참조로 교체.
3. **부수 영향 점검 및 일관화**(코드 변경 아님, 검증 대상):
   - `_should_give_hint`(`:191` `retry_count >= 2`)와 `_critical_fail`의 bad_end 판정
     (`:398` `retry_count >= 2`)은 이제 clarify를 세지 않으므로 hint/bad_end 타이밍이
     약간 관대해짐 — 의도된 방향(완화)과 일치. 테스트로 확인만.
   - `decide()`의 retry≥2 분기 우선순위 로직(`:88-97`)도 동일 카운터 사용 — 영향 검증.

스키마 변경 없음(`ScenarioState.retry_count` 그대로 사용). C/Unreal 라운드트립 불변.

### 테스트
파일: `backend/tests/dev_b/test_developer_b_policy_engine.py`
- clarify(UNCLEAR)가 `retry_count_delta == 0`인지 단위 검증.
- clarify 3~4회 연속에도 강제 bad_end로 가지 않음(이전엔 3회에 종료) 회귀 테스트.
- 실제 FAIL/hint 누적이 5에 도달하면 `_force_bad_end`로 가는지 경계 테스트.
- patience<=0 안전망이 여전히 강제 종료시키는지 확인.

---

## Part B — A/B desync 대응 (change_request 작성, A 영역)

B 영역이 아니므로 코드 수정 대신 `docs/contracts/change_requests.md`에
**`[CR-B-AB-DESYNC]`** 신규 등록. 구성:

- **Affected Owner**: Developer A (일부 C).
- **Reason**: 위 desync 로그 + 메커니즘. B의 `branch.next_action`/`dialogue_seed.surface_goal`
  /`dialogue_directive.purpose`(`support_retry`/`warn_and_control_risk`)는 이미 A에 전달되나
  (`npc_dialogue_agent.py:255,389,396`), LLM 생성 경로에서 강제되지 않아 NPC가 다음
  질문으로 진행함. 근거 파일/라인 명시.
- **Proposed Contract Change (A)**:
  - `node_generate_dialogue_llm`에 **분기 준수(post-generation) 가드** 추가:
    `next_action != "ADVANCE"`(=purpose가 support_retry/warn)인 턴에서는 NPC가
    **현재 노드의 질문(surface_goal)을 재질문**해야 하며 다음 단계 질문을 도입하면 안 됨.
    위반 시 기존 결정형 재질문 경로(`get_retry_variation`(`:245-246`) 또는
    `synthesize_fallback_next_question`(`:262`))로 override.
  - 기존 smalltalk 전용 coherence guard(`:479-501`) 패턴을 입국심사(non-smalltalk)
    분기 준수에도 확장하는 형태 권장.
- **Compatibility Impact**: A 내부 후처리 가드라 additive, 계약 스키마 불변.
- **Deferred 메모**: 본 사례의 1차 트리거인 false-UNCLEAR("maybe 13days"를 불명확
  처리)는 이번 범위 제외임을 CR에 명시(추후 Understanding/`_is_unclear` 보정 별건).

> 주의: Part A(B)만으로는 조기 강제 종료는 완화되지만 desync 근본은 미해결.
> 완전 해소는 `[CR-B-AB-DESYNC]`(A) + 추후 false-UNCLEAR 보정까지 필요.

---

## 변경 파일 요약
- 구현(B): `backend/app/services/service_b/scenario_state_machine.py`,
  `backend/tests/dev_b/test_developer_b_policy_engine.py`
- 문서(CR): `docs/contracts/change_requests.md` (`[CR-B-AB-DESYNC]` 추가)

## 검증 방법
1. 단위/회귀: `cd backend && python -m pytest tests/dev_b/test_developer_b_policy_engine.py -q`
   (.venv: `C:\potenup3\pj05_Murphy\.venv\Scripts\python.exe -m pytest ...`).
2. 시나리오 재현 테스트: IMM_003_DURATION에서 clarify 3회 → 강제종료 안 됨,
   FAIL 5회 → 강제종료 확인.
3. 전체 회귀: `python -m pytest backend/tests/dev_b backend/tests/test_preprototype_flow.py -q`.
