# Developer A 작업 요약 (main 미반영 / 2026-06-19)

작업자: BapSangE / kimyonghee
브랜치: `npc_dialogue_agent` (origin/main 대비 ahead 5 commits)
대상: Developer B / Developer C 전달용

---

## 1. 작업한 핵심 변경

| 영역 | 내용 | 영향 |
|---|---|---|
| **NPC 단기 메모리 도입** | LangGraph `InMemorySaver` checkpointer 위에 `(session_id, npc_id)` 단위 메모리 격리. `turn_buffer`/`accumulated_slots`/`forbidden_questions`/`last_npc_intent` 상태 보유. N=20 슬라이딩 윈도우. | NPC가 본인 대화만 기억하도록 분리. 챕터 종료 시 자동 정리. |
| **세션 컨텍스트 카드** | `session_context_card_service.py` 신설. dialogue_history(C 페이로드) 또는 자체 메모리에서 `confirmed_facts`/`open_hooks`/`forbidden_repeat_questions`/`last_npc_intent`/`recent_turns_compact` 카드 생성 후 프롬프트 변수로 노출. | LLM이 줄글 5턴이 아닌 구조화된 카드로 컨텍스트 인지. |
| **신규 9 슬롯/surface_goal 매핑** | `dialogue_policy_service.py`, `developer_a_fallback_service.py`, `session_context_card_service.py`에 IMM 신규 9 슬롯·surface_goal 추가. | B가 새로 추가한 27 노드의 fallback/retry 변주를 A가 정확히 처리. |
| **트집 게이팅 정리 (CR-B-CONV-A)** | SUSPICION MODE 활성 조건을 `assigned_visit_location` → `dialogue_seed.suspicion_scope`로 변경. 선제 블러팅 금지, Rule 3 verbatim 완화. | location 노드 / declaration 노드만 트집 발동. |
| **SPEAKER DISCIPLINE 강화** | 프롬프트에 "NPC가 자기 요청에 응답자 역할 하지 말 것" 명시. `speaker_role_confusion` 후처리 가드 신설. | 펜 부탁 화자 혼동 같은 사고 차단. |
| **fail-fast 원칙 도입** | `build_thread_id` 빈 값 → `ValueError`. 알 수 없는 `surface_goal` → `KeyError`. 알 수 없는 슬롯은 strict 모드에서 `ValueError`. silently 폴백 동작 금지. | 계약 위반이 즉시 노출되어 사후 봉합 방지. |
| **fallback 분기 우선순위 정리** | `build_text_fallback`을 7단계 분기로 재구성. `surface_goal` 매핑이 `smalltalk_diagnostic` generic 풀보다 먼저 잡히도록. | "펜 빌려달라"에 "I hear you. Let's move forward." 같은 사고 차단 시도. |
| **꼬리물기 강화 후처리 가드** | `repeats_confirmed_fact`(이미 답한 질문 차단), `weak_followup_no_hook`(open_hooks 없는 약한 후속 차단) 추가. fallback 합성 시 `"You mentioned X — "` hook prefix. | LLM 출력 품질의 자연어 가드. |
| **NPC 페르소나 7종 행동 방침 보강** | `npc_roster_service.py` 각 NPC의 `persona_instruction`에 Pending-request rule, Topic-discipline, Response length 추가. | LLM이 NPC 역할 일관성 유지. |
| **평가 하네스 구축** | `backend/tests/eval_harness/` 신설. 30개 골든 시나리오 + 결정형 scorer + LLM-judge 옵션 + reporter + pytest smoke (`test_eval_harness_smoke.py`). | 회귀 자동 감지 인프라. |

## 2. 변경된 파일 (소유권 준수: A 영역 + 공용 문서만)

**A 소유 코드:**
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/agents/agent_a/npc_implementation_plan.md`
- `backend/app/services/service_a/dialogue_policy_service.py`
- `backend/app/services/service_a/developer_a_fallback_service.py`
- `backend/app/services/service_a/session_context_card_service.py`
- `backend/app/services/service_a/npc_short_term_memory_service.py` (신규)
- `backend/app/services/service_a/npc_roster_service.py`
- `backend/app/services/service_a/voice_output_service.py`
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/prompts/npc_dialogue_prompt.short.md`
- `backend/app/prompts/npc_dialogue_few_shots.md`

**A 소유 테스트:**
- `backend/tests/test_developer_a_npc_dialogue.py`
- `backend/tests/test_developer_a_npc_roster.py`
- `backend/tests/test_developer_a_prompt_rendering.py`
- `backend/tests/test_developer_a_profanity_mirror.py`
- `backend/tests/eval_harness/**` (신규 디렉토리, 30개 시나리오 + runner + scorers + reporter + README)
- `backend/tests/test_eval_harness_smoke.py` (신규)

**공용 문서:**
- `docs/contracts/change_requests.md` (CR 3건 추가 — 아래 §4 참조)
- `docs/handoff.md` (Developer A 섹션 append)
- `docs/plans/dev_a_unified_memory_plan.md` (정본 통합 계획서, 신규)
- `docs/plans/dev_a_speaker_role_guard_plan.md` (신규)
- `docs/plans/dev_a_eval_persona_plan.md` (신규)
- `docs/plans/dev_a_memory_followup_plan.md` (deprecated 표기)
- `docs/plans/dev_a_imm_slots_v2_plan.md` (deprecated 표기)
- `docs/plans/dev_a_npc_memory_langgraph_plan.md` (deprecated 표기)
- `pyproject.toml`, `uv.lock` (pyyaml 추가)

## 3. 계약 변경 여부

**입력/출력 계약 변경 없음.** `dev_a_npc_dialogue_client.py`(C 소유)가 보는 키 구조는 동일합니다.

**의무화 신호:**
- A는 `payload.session_id`(또는 `payload.turn.session.session_id`)와 `npc_id`가 빈 값이면 `ValueError`로 즉시 실패합니다(fail-fast). 폴백 키 만들지 않습니다.

## 4. B/C에게 요청한 change request (Open 상태)

`docs/contracts/change_requests.md`에 등록되어 있고 A 작업의 결과로 발생한 것들입니다.

### [CR-A-SESSION-ID-REQUIRED] — **C 대상**
- `turn.session.session_id`를 required로 명시.
- `dev_a_npc_dialogue_client.py`에서 A 호출 직전 빈 값 검증 → 4xx로 사전 차단.
- C-side 회귀 테스트 1종 추가.
- **이유**: A의 NPC 메모리 격리가 `session_id`/`npc_id` 의무화에 의존. 누락 시 ValueError로 떨어지는데, C 어댑터에서 사전 차단되면 운영 디버깅이 단순해짐.

### [CR-A-HISTORY-DEPRECATION] — **C 대상**
- `_sync_dialogue_history_to_dialogue_seed` 점진 폐지 (3단계: 검증 → 옵션화 → 제거).
- `TurnHistoryEntry`/`DialogueSeed.dialogue_history` 필드 schema는 당분간 유지, deprecation 주석 추가.
- **이유**: A가 자체 NPC 메모리를 보유한 이후 `dialogue_history`는 cold-start fallback 외 사용되지 않음. 페이로드 사이즈 / OpenKB 읽기 비용 절감.

### [CR-A-E2E-TEST-SYNC] — **C 대상**
- `backend/tests/test_preprototype_flow.py` line 863 단언 한 줄 수정.
  ```diff
  - assert response.npc.text == "Okay. Please continue."
  + assert response.npc.text == "How long will you stay in the United States?"
  ```
- **이유**: A의 `ask_stay_duration` 폴백을 자연스러운 라인으로 개선한 결과, 옛 default 문자열을 단언하던 C 소유 테스트가 깨짐.

## 5. B/C에게 알리는 변경 (참고용)

- **SUSPICION MODE 게이팅이 `dialogue_seed.suspicion_scope`에만 의존**합니다. B가 `none`/`location`/`declaration`을 정확히 emit해야 트집이 발동합니다. (CR-B-CONV-A 1번 항목 반영)
- **신규 9 surface_goal/슬롯 매핑**은 A가 등록 완료. B/C가 추가/변경하는 신규 키도 동일 형태로 알려주시면 됩니다. **fail-fast 정책상 매핑 누락 시 `KeyError`로 즉시 실패**합니다 (silently 동작 안 함).
- **응답 텍스트가 평가 하네스로 회귀 검증**됩니다. B/C가 분기 정책이나 슬롯 추출을 바꾸면 `backend/tests/eval_harness/scenarios/` 의 시나리오 일부가 깨질 수 있습니다. 깨지면 시나리오 수정이 필요한지 알려주세요.

## 6. 검증

```powershell
uv sync
uv run pytest                       # 전체 그린
uv run pytest backend/tests/test_eval_harness_smoke.py  # 결정형 채점 pass_rate >= 0.8
uv run ruff check .
uv run mypy .
```

A 영역 가드레일(다른 개발자 파일 수정 금지) 준수 확인 완료.

---

## 7. main 머지 절차

작업자가 직접 진행합니다. 본 문서는 머지 전 B/C에게 사전 공유용입니다.

브랜치: `npc_dialogue_agent` → `main`
미반영 commit (origin/main 대비 ahead, merge 제외):
- `7269eb0` npc dialogue 프롬프트 고도화
- `346c4d2` 프롬프트 화자 강화_헷갈림 방지
- `adf7de7` 메모리 기능 추가
- `e50c839` retry정책완화pull작업
- `a81985f` npc 메모리 기능 추가
