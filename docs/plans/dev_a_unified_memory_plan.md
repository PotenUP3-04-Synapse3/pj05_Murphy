# Developer A — 통합 작업계획서: NPC 메모리·꼬리물기·신규 슬롯·트집 게이팅

작성일: 2026-06-19
대상 실행 에이전트: **Gemini (Developer A 페르소나)**
이 계획서는 다음 세 개의 선행 계획서를 **하나로 통합**한 정본이다. 선행
계획서는 deprecation 대상이며 본 계획서가 모든 변경 사항을 포함한다.

- (대체) `docs/plans/dev_a_memory_followup_plan.md`
- (대체) `docs/plans/dev_a_imm_slots_v2_plan.md` (슬림판)
- (대체) `docs/plans/dev_a_npc_memory_langgraph_plan.md`

추가로 다음 Open 상태의 change request 두 건이 본 계획에 반영되어 있다.
- `[CR-B-CONV-A]` (2026-06-18, Open) — 트집 게이팅, 전 노드 히스토리 소비,
  대사 변주
- (참조만) `[CR-B-HISTORY-MEMORY]` (2026-06-19, Open) — C/Unreal 작업. A는
  arrival_form 컨텍스트가 들어올 자리만 비워두고 본 PR에서는 구현하지 않음.

---

## 0. 작업 가드레일 (필독)

### 0.1 수정 가능 파일 (Developer A 소유 한정)
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/agents/agent_a/npc_llm_client.py`
- `backend/app/agents/agent_a/schemas.py`
- `backend/app/services/service_a/*.py` (특히
  `dialogue_policy_service.py`, `developer_a_fallback_service.py`,
  `session_context_card_service.py`, `developer_a_input_service.py`,
  `npc_emotion_service.py`)
- 신규 파일: `backend/app/services/service_a/npc_short_term_memory_service.py`
- `backend/app/tools/tool_a/*.py`
- `backend/app/middleware/middleware_a/*.py`
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/prompts/npc_dialogue_prompt.short.md`
- `backend/app/prompts/npc_dialogue_few_shots.md`
- 본 계획서 (`docs/plans/dev_a_unified_memory_plan.md`)
- Developer A 테스트
  (`backend/tests/test_developer_a_npc_dialogue.py`,
   `backend/tests/test_developer_a_prompt_rendering.py`)
- `docs/handoff.md` (Developer A 섹션 append만)

### 0.2 절대 수정 금지 파일 (Developer B/C 소유)
- `backend/app/agents/agent_b/**`, `backend/app/services/service_b/**`
- `backend/app/agents/agent_c/**`, `backend/app/services/service_c/**`
- `backend/app/api/**`, `backend/app/main.py`, `backend/app/graphs/**`
- `backend/app/schemas/**`
- `backend/app/integrations/dev_a_npc_dialogue_client.py`,
  `backend/app/integrations/dev_b_level_hint_client.py`
- `backend/app/tools/tool_b/**`, `backend/app/tools/tool_c/**`
- `backend/app/middleware/middleware_c/**`
- `backend/app/data/scenario_nodes.json`, `scenario_nodes.yaml`
- `backend/app/kb/**`, `backend/runtime/openkb/**`
- `backend/app/prompts/english_level_hint_prompt.md`,
  `backend/app/prompts/understanding_prompt.md`
- 위 영역에 속하는 모든 테스트

위 영역 동작이 변경이 필요해지면 코드는 만지지 말고
`docs/contracts/change_requests.md`에 항목을 추가한 후 사용자에게 보고한다.

### 0.3 의존성 / 검증 규약
- `langchain==1.3.2`, `langgraph==1.2.2` 고정. 본 작업은 이미 사용 중인
  langgraph만 사용하며 신규 패키지 추가 금지.
- 테스트는 실제 OpenAI 키 / TTS / Unreal / 원격 OpenKB 없이 통과해야 한다.

### 0.4 핵심 원칙 — Fail-fast (코드 청결도 보호)

본 계획의 모든 작업은 **silently 폴백 동작을 만들지 않는다**. 의도와 다른
입력이 들어오면 그 자리에서 명시적 예외를 던져 호출자(C)가 보게 한다. "어떻게든
돌아가도록" 분기를 누적해 코드가 두꺼워지는 것을 막기 위해서다.

구체 규칙:
1. **thread_id 누락 금지.** `session_id`나 `npc_id`가 빈 값이면
   `build_thread_id`는 `ValueError("session_id and npc_id are required for memory isolation")`
   를 던진다. `"anon"`/`"unknown"` 폴백 키 만들지 않는다.
2. **알 수 없는 surface_goal 무시 금지.** `SURFACE_GOAL_FALLBACK_TEXTS` /
   `SURFACE_GOAL_QUESTIONS` 에 없는 키가 들어오면 `KeyError`로 즉시 실패.
3. **알 수 없는 슬롯 silently 무시 금지.** 세션 카드 빌드 시 모르는 슬롯이
   있으면 logger.warning 후 skip. 테스트는 strict=True 모드로 카드 빌드해
   `ValueError`로 잡는다.
4. **LangGraph import 실패 시 명시 오류.** import fallback이 모두 실패하면
   `RuntimeError("langgraph checkpointer unavailable; required for NPC memory")`
   로 그래프 컴파일 자체를 막는다. checkpointer 없는 모드로 우회 금지.
5. **상태 필수 키 누락 금지.** `node_persist_memory`가 `state["result"]`나
   `payload`에서 필수 필드(`npc_text`, `npc_id`)를 못 찾으면 `KeyError`.
   빈 문자열로 채우지 않는다.
6. **trippin suspicion 게이팅 위반 금지.** `dialogue_seed.suspicion_scope`가
   `none`/누락이면 SUSPICION MODE 블록이 프롬프트에 들어가지 않는다.
   템플릿 조건문으로 확실히 잘라낸다.

---

## 1. 통합 문제 정의

### 1.1 메모리 측면
- Agent A는 자체 메모리가 없고 C가 OpenKB에서 만들어 페이로드로 보내는
  `dialogue_seed.dialogue_history`를 받는다. 5턴 / 120자 preview / 모든 NPC
  공유 / 줄글 형태라 LLM이 의미적 사실을 추출하기 어렵다.
- 기내 승객과 입국심사관이 같은 메모리를 보는 비현실성. NPC 페르소나 일관성
  훼손.

### 1.2 꼬리물기 측면
- 후속 질문 의무가 `surface_goal` 있을 때만 발동. `next_question_style` 등
  정책값이 프롬프트에 노출되지 않음. 플레이어 발화 명사 후크 가이드 부재.

### 1.3 신규 슬롯/노드 측면
- B/C는 이미 9개 슬롯과 27개 노드를 추가 완료. A에는 매핑이 없어 신규
  surface_goal이 들어오면 fallback이 `default_text_fallback`("Okay. Please
  continue.")으로 silently 떨어진다. 이게 오류로 안 보여서 문제가 묻힌다.

### 1.4 트집(suspicion) 게이팅 측면 (CR-B-CONV-A)
- 현재 SUSPICION MODE는 `assigned_visit_location` 존재만 보고 활성화 → 방문
  목적 노드인데 호텔 이름이 박히는 등 노드 부적합 트집. 플레이어가 답하기 전
  선제 트집(블러팅) 발생. Rule 3의 verbatim 강제로 어색한 표현.

### 1.5 히스토리 소비 범위 측면 (CR-B-CONV-A)
- 현재 `discussed_topics`/`past_player_utterances`는 smalltalk_diagnostic
  전용. immigration/customs에서는 dialogue_history 활용이 약하다.

### 1.6 대사 변주 측면 (CR-B-CONV-A)
- stern/retry/clarify에서 동일 문장 반복. recommended_expression 패러프레이즈
  활용 미흡.

---

## 2. 통합 아키텍처

```
┌────────────────────────────────────────────────────────────┐
│ Developer C 페이로드 (turn.session.session_id, npc_id, ... )│
└────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────┐
│ Agent A: LangGraph (모듈 싱글톤 + InMemorySaver)     │
│                                                       │
│  thread_id = f"{session_id}:{npc_id}"                 │
│                                                       │
│  ┌──────────────────┐  ┌──────────────────┐          │
│  │ load_memory      │→ │ initialize_state │          │
│  └──────────────────┘  └──────────────────┘          │
│         (state 복원)        ▼                         │
│                       build_session_context_card     │
│                            ▼                         │
│                       generate_dialogue_llm          │
│                            ▼                         │
│                       (success/fallback)             │
│                            ▼                         │
│                       persist_memory  (turn push)    │
└──────────────────────────────────────────────────────┘

state (NPCDialogueState):
  payload, normalized, npc_profile, profile, emotion_state, policy,
  + turn_buffer[20]  ← player_text/npc_text 원문 + 메타
  + accumulated_slots: {slot: value}
  + forbidden_questions: list[str]
  + last_npc_intent: str
```

핵심:
- **메모리는 (session_id, npc_id)별로 격리.** 기내 승객 ↔ 입국심사관 분리.
- **메모리에는 원문 보존(N=20 슬라이딩).** LLM 프롬프트에는 카드 형태로 압축.
- **카드는 그래프 상태에서만 빌드.** C가 보내는 dialogue_history는 cold-start
  fallback에만 사용 (선택).
- **트집 게이팅은 `suspicion_scope`로만 결정.** location 노드는 location,
  declaration 노드는 declaration, 그 외는 트집 안 함.

---

## 3. 신규 슬롯·노드 사양 (B/C가 이미 적용)

| 노드(예) | 슬롯 | 추정 surface_goal |
| --- | --- | --- |
| IMM_002L | `long_stay_reason` | `ask_long_stay_reason` |
| IMM_004 | `hotel_reservation_status` | `ask_hotel_reservation_status` |
| IMM_004C | `hotel_choice_reason` | `ask_hotel_choice_reason` |
| IMM_005I | `itinerary_status` | `ask_itinerary_status` |
| IMM_007F | `first_visit_status` | `ask_first_visit_status` |
| IMM_008 | `occupation` | `ask_occupation` |
| IMM_010 | `cash_amount` | `ask_cash_amount` |
| IMM_010B | `payment_source` | `ask_payment_source` |
| IMM_011 | `denied_entry_status` | `ask_denied_entry_status` |

**§5의 surface_goal 키 동기화 단계를 작업 시작 직전에 1회 수행한다.**

---

## 4. 작업 항목

### M-1. NPC 단기 메모리 서비스 신설
**파일 (신규):** `backend/app/services/service_a/npc_short_term_memory_service.py`

- 그래프 상태 위에서 동작하는 순수 함수 묶음. checkpointer는 그래프가 보관.
- API:
  ```python
  def build_thread_id(session_id: str | None, npc_id: str | None) -> str
  def empty_memory_state() -> dict[str, Any]
  def append_turn(memory, *, node_id, surface_goal, branch_type,
                  player_text, npc_text, filled_slots, npc_emotion) -> dict
  def merge_slots(existing: dict, incoming: dict) -> dict
  def derive_forbidden_questions(slots: dict) -> list[str]
  def clear_memory_state() -> dict
  ```
- Fail-fast: `build_thread_id`는 빈 값에 `ValueError`. `turn_buffer`는 N=20
  슬라이딩(오래된 항목 드롭).

### M-2. 그래프 상태 스키마 확장
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

- `NPCDialogueState`에 다음 NotRequired 키 추가:
  ```python
  turn_buffer, accumulated_slots, forbidden_questions, last_npc_intent
  ```
- 기존 키는 모두 유지.

### M-3. 그래프 싱글톤 + InMemorySaver
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

- 모듈 상단 `_GRAPH_SINGLETON` 캐시. `_get_compiled_graph()`가 최초 호출 시
  `InMemorySaver`를 부착해 컴파일.
- import는 `from langgraph.checkpoint.memory import InMemorySaver`. 실패 시
  `from langgraph.checkpoint import MemorySaver`로 1회 fallback. 둘 다 실패
  하면 `RuntimeError`.
- 테스트용 `reset_graph_singleton_for_testing()` 함수 노출.

### M-4. invoke 진입점에 thread_id 적용
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

- `generate_npc_dialogue_from_level_design`에서
  - `session_id`를 페이로드(`session_id` 또는
    `turn.session.session_id`)에서 추출.
  - `npc_id`는 `_npc_id_from_payload`로 정규화.
  - 빈 값이면 `build_thread_id`가 `ValueError`를 던짐 → 그대로 전파.
  - `config={"configurable": {"thread_id": thread_id}}` 로 invoke.
- 초기 state에는 메모리 필드를 넣지 않는다 (LangGraph가 thread별 상태 복원).

### M-5. load / persist 노드 신설 + 그래프 재배선
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

- `node_load_memory(state)`: 누락 메모리 필드를 `empty_memory_state()`로 채움
  (체크포인터가 없거나 처음 호출).
- `node_persist_memory(state)`: 이번 턴 결과를 `append_turn` →
  `merge_slots` → `derive_forbidden_questions` 순으로 누적. `transition.status
  == complete_chapter`이면 push 후 `clear_memory_state()`로 그 NPC 메모리 정리.
- Edge:
  ```
  START → load_memory → initialize_state
    → (use_llm) generate_dialogue_llm → (error→apply_fallback→) persist_memory → END
    → (else)                                                    persist_memory → END
  ```
- `persist_memory`는 LLM 실패 시도 통과한다 (fallback 결과를 메모리에 push).

### M-6. 세션 컨텍스트 카드 신설 + 입력 소스 교체
**파일:** `backend/app/services/service_a/session_context_card_service.py`

- `build_session_context_card(normalized, npc_profile, payload, *, npc_memory=None, strict_unknown_slot=False)`:
  - `npc_memory`가 주어지면 그것을 우선 사용 (운영 경로).
  - 없으면 dialogue_history 기반 (cold-start fallback).
  - strict_unknown_slot=True일 때 모르는 슬롯은 `ValueError`.
- 카드 출력 키 (LLM 프롬프트 변수):
  - `confirmed_facts` (자연어 문장 리스트)
  - `open_hooks` (플레이어 마지막 발화의 영문 토큰, 최대 5개)
  - `last_npc_intent`
  - `recent_turns_compact` (최근 8턴 한 줄 포맷)
  - `topic_thread` (surface_goal 시간순 dedup)
  - `forbidden_repeat_questions`

### M-7. surface_goal · 슬롯 매핑 9개 확장 (이전 imm_slots_v2 핵심)
**파일:**
- `backend/app/services/service_a/dialogue_policy_service.py` →
  `SURFACE_GOAL_QUESTIONS` 9키 추가, `RETRY_PARAPHRASES` 9키 × 변주 3개
  이상 추가.
- `backend/app/services/service_a/developer_a_fallback_service.py` →
  `SURFACE_GOAL_FALLBACK_TEXTS` 9키 추가, `build_text_fallback` 분기
  우선순위 정리.
- `backend/app/services/service_a/session_context_card_service.py` →
  `SLOT_TO_PHRASE`, `SLOT_TO_FORBIDDEN_QUESTIONS` 9슬롯 추가.

`build_text_fallback` 분기 우선순위 (위에서부터 평가):
1. `transition_status == complete_chapter` 또는 `next_action == COMPLETE_CHAPTER`
2. `surface_goal in SURFACE_GOAL_FALLBACK_TEXTS`
3. `surface_goal == "explain_random_customs_item"` 특수
4. `purpose == "smalltalk_diagnostic"` (단, surface_goal이 위 매핑에 없을 때만)
5. assigned_visit_location / random_customs_item seeded
6. target_slot 기반
7. **silently default 금지**: `surface_goal`이 비어 있지 않은데도 매핑이
   없으면 `KeyError(f"unknown surface_goal: {surface_goal}")`.

신규 9개의 임시 라인은 §3 표 기반(§5 키 동기화 후 확정).

### M-8. 트집(suspicion) 게이팅 정리 (CR-B-CONV-A 1~3)
**파일:**
- `backend/app/prompts/npc_dialogue_prompt.md`,
  `backend/app/prompts/npc_dialogue_prompt.short.md`

- 기존 SUSPICION MODE 블록의 조건문을 `assigned_visit_location` 존재가 아니라
  **`suspicion_scope in ("location", "declaration")`** 으로 변경.
  `suspicion_scope == "none"` 또는 누락 시 블록이 통째로 비활성.
- "Answer-first" 규칙 강화: dialogue_history에서 해당 슬롯이 채워졌는지 확인 후
  그 후에만 트집. 선제 블러팅 금지를 명시적 1행으로 추가.
- Rule 3 verbatim 강제는 "맥락상 관련될 때 자연스럽게 지칭"으로 완화 (기존
  문장 일부 수정).

### M-9. 히스토리 전 노드 소비 (CR-B-CONV-A 4~5)
**파일:**
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/prompts/npc_dialogue_prompt.md`,
  `backend/app/prompts/npc_dialogue_prompt.short.md`

- `node_generate_dialogue_llm`에서 `discussed_topics`/`past_player_utterances`를
  smalltalk_diagnostic 분기 안에서만 채우던 코드를 모든 purpose에서 채우도록
  옮긴다. 단, 카드(M-6)가 이미 같은 정보를 더 풍부하게 제공하므로 LLM에는
  카드 변수만 노출하고 위 두 변수는 디버깅용 메타로만 유지하는 것을 권장.
- 프롬프트에 "이미 답변된 질문 반복 금지 + 직전 턴 반응 후 진행" 가이드를
  immigration/customs에서도 적용. 카드의 `confirmed_facts` /
  `forbidden_repeat_questions` 변수 사용을 명시.

### M-10. retry/clarify 변주 보강 (CR-B-CONV-A 6)
**파일:** `backend/app/services/service_a/dialogue_policy_service.py`

- `RETRY_PARAPHRASES`에 §M-7로 추가된 9개 키 외에, 기존 키
  (`ask_visit_purpose` 등)도 변주가 부족한 경우 한 줄씩 추가하여 모두 3개
  이상 유지.
- `get_retry_variation` 시그니처는 유지. 호출부(`node_initialize_state`)
  로직 변경 없음.
- 프롬프트의 retry/clarify 섹션에 "recommended_expression을 패러프레이즈
  힌트로 1회 제시 가능. verbatim 에코 금지" 가이드 추가.

### M-11. 프롬프트 SESSION MEMORY + 정책 노출
**파일:** `backend/app/prompts/npc_dialogue_prompt.md`,
`backend/app/prompts/npc_dialogue_prompt.short.md`

- 기존 `## DIALOGUE HISTORY` 블록을 `## SESSION MEMORY`로 교체. 헤더에 한 줄
  추가: "This is THIS NPC's private memory of this player. Do not reference
  events that did not happen between you and this player."
- 변수 바인딩: `confirmed_facts`, `open_hooks`, `forbidden_repeat_questions`,
  `last_npc_intent`, `recent_turns_compact`.
- 새 섹션 `### Dialogue Policy (from rule engine)` 추가:
  `policy_action`, `policy_next_question_style`,
  `policy_max_sentence_count` 변수 노출.
- short 프롬프트에도 동일 의미를 한 단락으로 압축.

### M-12. 후처리 가드 (꼬리물기 보장 + 재질문 차단)
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

`node_generate_dialogue_llm` 후처리에 두 가드 추가:
1. **`repeats_confirmed_fact`**: `npc_text`(소문자, 구두점 제거)가
   `forbidden_repeat_questions` 항목과 부분일치하면 fallback으로 전환.
2. **`weak_followup_no_hook`**: `branch_type in {"success", "neutral"}` 이고
   `open_hooks`가 비어 있지 않으며 `purpose != "smalltalk_diagnostic"`일 때,
   `npc_text`가 hook 토큰 하나도 포함하지 않고 문장이 1개 이하면 fallback.

이 가드들은 fail-fast가 아니라 LLM 출력의 자연어 품질 가드라 fallback 경로로
간다(설계 의도). fallback 합성에서는 §M-7의 `synthesize_fallback_next_question`
이 hook prefix를 붙여 안전한 라인을 생성.

### M-13. fallback 합성 hook prefix
**파일:** `backend/app/services/service_a/dialogue_policy_service.py`

- `synthesize_fallback_next_question(fallback_text, surface_goal, open_hooks=None)`:
  open_hooks가 있으면 `f"You mentioned {open_hooks[0]} — "` prefix 추가.
  hook이 ASCII 영문 단어일 때만 적용.
- 호출부(`node_initialize_state`)에서 `open_hooks` 전달.

### M-14. dialogue_history 의존성 축소
**파일:**
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/services/service_a/developer_a_input_service.py`

- `normalize_level_design_payload`의 dialogue_history 파싱은 유지 (cold-start
  보조).
- 운영 경로는 NPC 메모리 카드가 우선. dialogue_history는 메모리가 비어 있을
  때만 시드용으로 사용.
- smalltalk_diagnostic의 `OpenKBFinalResultRecordReader` 호출은
  `# TODO(dev-a): replace with internal NPC memory once verified` 주석만
  달고 본 PR에서 제거 안 함.

### M-15. few-shot 예시 보강
**파일:** `backend/app/prompts/npc_dialogue_few_shots.md`

- Example 4 (꼬리물기 hook): MGM Grand를 hook으로 잡는 immigration 후속.
- Example 5 (cross-turn callback): confirmed_facts에 직업 학생 → 다음 노드에서
  callback.
- Example 6 (forbidden repeat 회피): 이미 답한 슬롯 paraphrase.

모두 ASCII-only, JSON 스키마 준수. 압박 톤 예시는 본 계획서 범위 밖(§9).

### M-16. 테스트 / 문서
**파일:**
- `backend/tests/test_developer_a_npc_dialogue.py`
- `backend/tests/test_developer_a_prompt_rendering.py`
- `docs/handoff.md` (Developer A 섹션 append)

테스트 (최소 12종):
1. `build_thread_id` 빈 값에서 `ValueError`.
2. 같은 session, 다른 npc_id로 두 호출이 메모리 격리.
3. 같은 thread_id 5회 호출이 turn_buffer에 누적 (길이 5).
4. N=20 슬라이딩 (25회 호출 시 길이 20).
5. complete_chapter 후 같은 thread_id 호출 시 turn_buffer 비어 있음.
6. 신규 9 surface_goal 모두 `SURFACE_GOAL_QUESTIONS`에 존재.
7. 신규 9 surface_goal 모두 `RETRY_PARAPHRASES`에 3개 이상.
8. 신규 9 surface_goal 모두 `SURFACE_GOAL_FALLBACK_TEXTS`에 존재.
9. 알 수 없는 surface_goal → `build_text_fallback`이 `KeyError`.
10. `suspicion_scope == "none"` 일 때 프롬프트에 SUSPICION 블록 미포함.
11. `repeats_confirmed_fact` / `weak_followup_no_hook` 가드가 fallback 전환.
12. invoke 입출력 키 회귀 (speaker/npc_text/tts_text/tone/animation/...).

`docs/handoff.md` append 예시:
```
## Developer A 2026-06-19 — 통합 메모리/꼬리물기/슬롯/트집 게이팅
- LangGraph InMemorySaver로 (session_id, npc_id) 단위 NPC 단기 메모리.
- 세션 컨텍스트 카드 신설 (입력 소스: NPC 메모리, fallback: dialogue_history).
- 신규 9 슬롯/surface_goal 매핑. 알 수 없는 키는 KeyError로 즉시 실패.
- CR-B-CONV-A 반영: 트집 게이팅(suspicion_scope), 전 노드 히스토리, 변주 보강.
- 입출력 계약 변경 없음.
- 알려진 한계: in-process 휘발성. 압박 톤 연출은 별도 계획서로 분리.
- 검증: uv run pytest / ruff / mypy 통과.
```

---

## 5. surface_goal 키 동기화 단계 (작업 시작 직전 1회)

```
grep -oE '"surface_goal":\s*"[^"]+"' backend/app/data/scenario_nodes.json | sort -u
```

§3 표의 추정 키와 다르면 §M-7의 상수 키만 실제 값으로 치환한다. 라인 텍스트는
유지. 슬롯 이름이 다르면 §M-7의 `SLOT_TO_PHRASE`/`SLOT_TO_FORBIDDEN_QUESTIONS`
키도 동기화. `docs/handoff.md`에 "키 동기화: 추정 X → 실제 Y" 한 줄 기록.

---

## 6. 실행 순서 권장

1. §5 키 동기화 (5분)
2. M-1, M-2 (메모리 서비스 + 상태 스키마)
3. M-3, M-4 (싱글톤 + thread_id invoke)
4. M-5 (load/persist 노드 + 그래프 재배선)
5. M-6 (카드 입력 소스 교체)
6. M-7 (9개 매핑 확장 + fallback 분기 우선순위)
7. M-8 (suspicion 게이팅)
8. M-9 (전 노드 히스토리 소비)
9. M-10, M-11 (변주 + 프롬프트)
10. M-12, M-13 (후처리 가드 + fallback hook)
11. M-14 (dialogue_history 의존성 축소)
12. M-15 (few-shot)
13. M-16 (테스트/문서)

각 단계 후 `uv run pytest -k developer_a` 빠른 회귀, 마지막에 전체 스위트
+ `ruff` + `mypy`.

---

## 7. 검증 체크리스트

- [ ] §5 키 동기화 완료, `docs/handoff.md` 한 줄 기록.
- [ ] `uv sync` 성공.
- [ ] `from langgraph.checkpoint.memory import InMemorySaver` import 가능.
- [ ] `uv run pytest` 그린 (실제 API 키 없이).
- [ ] `uv run ruff check .` 그린.
- [ ] `uv run mypy .` 그린.
- [ ] `git diff --name-only`로 확인 시 변경 파일이 §0.1 화이트리스트 내부만.
- [ ] 알 수 없는 surface_goal에 fallback 호출 시 `KeyError` 발생 (silently 동작 금지).
- [ ] `build_thread_id`가 빈 값 입력에 `ValueError` (anon 폴백 없음).
- [ ] `suspicion_scope == "none"` 렌더에 SUSPICION 블록 미포함.
- [ ] 동일 session, 다른 npc_id → 메모리 격리.
- [ ] complete_chapter 후 메모리 정리.
- [ ] `dev_a_npc_dialogue_client.py`가 보는 입출력 키 구조 변화 없음.

---

## 8. 후속 (이번 범위 밖, change_requests.md에만 기록)

용어:
- **session_id**: 한 명의 플레이어가 게임을 시작해서 끝낼 때까지의 한 판을
  식별하는 ID. `turn.session.session_id`로 전달된다. Agent A는 이 값과
  `npc_id`를 묶어 메모리 thread_id를 만든다.

후속 항목:
- (요청 C) 페이로드에 `session_id`가 **항상** 포함되도록 계약 명시 요청.
  현재 optional이라 누락 시 본 계획서는 명시적 `ValueError`를 던지는 정책.
  C가 보장해 주면 클라이언트 측 오류 핸들링이 단순해진다.
- (요청 C) `dialogue_seed.dialogue_history` 의무 전송 폐지 검토. A가 자체
  메모리를 들고 가면 C가 이걸 만들 필요가 없다. 데이터 사이즈 절감.
- (참조 CR-B-HISTORY-MEMORY) Unreal이 입국신고서(arrival_form) 구조화 데이터를
  전송하고 C가 game_state로 유지/전달하기로 결정되면, A는 프롬프트에
  `arrival_form` 변수 노출 한 줄만 추가하면 된다. 본 PR에서는 변수 자리만
  비워둔다 (코드 변경 없음).

---

## 9. 본 계획서에서 분리된 작업

다음은 일관성과 PR 크기 관리를 위해 별도 PR로 분리한다. 사용자가 게임 연출
강화를 요청할 때 별도 계획서로 진행한다.

- **압박 톤 연출** (PRESSURE_SURFACE_GOALS 감정 분기, 프롬프트 PRESSURE
  블록, `add_officer_ack` 정책 가드, 압박형 few-shot 3개, `harris` 페르소나
  미세조정). 기능적 필수가 아니며 게임 연출용.
- **CR-A1~A4** (incivility/Bad Ending) — 별도 트랙으로 진행 중.

---

## 10. 선행 계획서와의 관계

본 통합 계획서는 다음 세 계획서를 **전부 대체**한다. 기존 파일은 유지하되
헤더에 "통합 계획서로 대체됨" 한 줄 추가 후 신규 작업은 본 계획서만 참조.

- `docs/plans/dev_a_memory_followup_plan.md`
- `docs/plans/dev_a_imm_slots_v2_plan.md`
- `docs/plans/dev_a_npc_memory_langgraph_plan.md`

본 PR 머지 후 다음 PR에서 위 세 파일을 한꺼번에 삭제한다.
