# Developer A NPC 메모리 / 꼬리물기 강화 작업계획서

작성일: 2026-06-19
대상 실행 에이전트: **Gemini (Developer A 페르소나)**
선행 문서: `AGENTS.md`, `backend/app/agents/agent_a/npc_implementation_plan.md`

---

## 0. 작업 가드레일 (필독)

Gemini는 본 작업계획서를 실행할 때 반드시 다음 규칙을 지킨다. 위반 시 즉시 중단하고
`docs/contracts/change_requests.md`에 요청을 추가한다.

### 0.1 수정 가능 파일 (Developer A 전용)
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/agents/agent_a/npc_llm_client.py`
- `backend/app/agents/agent_a/schemas.py`
- `backend/app/services/service_a/*` (전체)
- `backend/app/tools/tool_a/*` (전체)
- `backend/app/middleware/middleware_a/*` (전체)
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/prompts/npc_dialogue_prompt.short.md`
- `backend/app/prompts/npc_dialogue_few_shots.md`
- 본 계획서 (`docs/plans/dev_a_memory_followup_plan.md`)
- Developer A 자신의 테스트: `backend/tests/test_developer_a_npc_dialogue.py`,
  `backend/tests/test_developer_a_prompt_rendering.py`

### 0.2 절대 수정 금지 파일 (Developer A 소유가 아님)
다음 파일들은 Developer B 또는 Developer C 소유이므로 **읽기 전용**으로만 다룬다.
- `backend/app/agents/agent_b/**`, `backend/app/services/service_b/**`
- `backend/app/agents/agent_c/**`, `backend/app/services/service_c/**`
- `backend/app/api/**`, `backend/app/main.py`, `backend/app/graphs/**`
- `backend/app/schemas/**` (계약 스키마는 C 소유)
- `backend/app/integrations/dev_a_npc_dialogue_client.py`,
  `backend/app/integrations/dev_b_level_hint_client.py`
- `backend/app/tools/tool_b/**`, `backend/app/tools/tool_c/**`
- `backend/app/middleware/middleware_c/**`
- `backend/app/data/scenario_nodes.json`, `scenario_nodes.yaml`
- `backend/app/kb/**` (단, `backend/app/kb/dev_b/`는 B 소유)
- `backend/runtime/openkb/**`
- `backend/app/prompts/english_level_hint_prompt.md`,
  `backend/app/prompts/understanding_prompt.md`
- 위 영역에 속하는 모든 테스트 (예: `backend/tests/dev_b/**`,
  `backend/tests/test_preprototype_flow.py`)

다른 개발자 영역의 동작 변경이 꼭 필요하다면, **코드는 건드리지 말고**
`docs/contracts/change_requests.md`에 항목을 추가하고 `docs/handoff.md`에 요약만 적는다.

### 0.3 의존성 규약
- `langchain==1.3.2`, `langgraph==1.2.2` 고정. 신규 라이브러리를 추가할 필요가
  생기면 `uv add`만 사용하고, 이유를 `docs/handoff.md`에 기록한다. (가능하면
  추가 없이 처리한다.)
- 테스트는 실제 OpenAI 키 / TTS / Unreal / 원격 OpenKB 없이도 통과해야 한다.

---

## 1. 문제 정의 및 원인 분석

### 1.1 증상
1. NPC가 이전 턴 발화를 기억하지 못해, 같은 질문을 반복하거나 이미 답한 슬롯을
   다시 묻는 경우가 발생한다.
2. 꼬리물기 질문이 약하다. NPC가 플레이어 발화 내용을 받아 자연스럽게 후속 질문을
   확장하지 못하고, 단답형 다음 질문이나 일반론으로 빠진다.

### 1.2 원인 분석 (코드 베이스 진단)

#### 1.2.1 메모리 측면
- Developer A는 자체 메모리를 갖지 않는다. 메모리는 Developer C가 OpenKB 세션
  레코드를 읽어 만든 `dialogue_seed.dialogue_history`를 통해 들어온다.
  (`backend/app/tools/tool_c/developer_c_graph_tools.py` 의
  `_sync_dialogue_history_to_dialogue_seed`)
- 외부에서 주입되는 히스토리는 다음 제약을 갖는다.
  - 최근 5턴만 유지 (`max_entries=5`).
  - `player_text_preview`, `npc_text_preview` 모두 `_preview(..., limit=120)`
    로 잘린 미리보기.
  - 엔트리에 담기는 의미 단위는 `node_id`, `player_text_preview`,
    `npc_text_preview`, `filled_slots` 뿐. **surface_goal 흐름, NPC가 직전에 어떤
    의도/감정으로 말했는지, 누적된 토픽/슬롯 충족 요약 같은 의미적 상태가 결여**
    되어 있다.
- Developer A 내부에서도 이 히스토리를 단순 리스트로 프롬프트에 풀어쓴다
  (`prompts/npc_dialogue_prompt.md` 의 `## DIALOGUE HISTORY` 블록). LLM이 봤을 때
  "어떤 사실이 이미 확정됐고, 어떤 토픽이 열려 있는가"가 한눈에 보이지 않는다.
- smalltalk_diagnostic 모드에서만 `OpenKBFinalResultRecordReader`로 더 긴 누적
  데이터를 가져오지만, 일반 모드(immigration 등)에서는 이 보강이 없다.
- Agent A는 동일 세션 안의 누적 컨텍스트 캐시(예: 확정 슬롯 요약, 직전 NPC 발화
  의도 태그, 본인이 던졌던 후속 훅)를 별도로 보관하지 않는다.

#### 1.2.2 꼬리물기 약화 측면
- 일반(비 smalltalk_diagnostic) 프롬프트의 후속 질문 의무는 `surface_goal`이
  존재할 때만 발동한다. `surface_goal`이 비어 있는 자연 대화 턴에는 후속 질문
  강제 규칙이 없다.
- `node_generate_dialogue_llm` 의 가드
  (`missing_followup_question`)도 `surface_goal`이 있을 때만 검사한다.
  surface_goal이 비면 응답이 단문/평문이어도 통과한다.
- `dialogue_policy_service.py`에서 산출된 `next_question_style`, `action` 등
  정책 값이 LLM 프롬프트 변수로 노출되지 않는다. 즉 정책이 결정한 "어떤 톤·어떤
  깊이의 후속 질문을 던질지"가 LLM에 전달되지 않는다.
- 프롬프트가 "acknowledge before progressing" 정도만 시키고, **플레이어의 직전
  발화에서 어떤 토큰/사실을 후속 질문의 hook으로 삼아야 하는지** 명시하지 않는다.
  결과적으로 LLM이 일반화된 두 번째 질문(예: "How long will you stay?")만 반복
  하기 쉽다.
- few-shot 예시(`npc_dialogue_few_shots.md`)에 "이전 턴 내용을 인용해 꼬리무는
  성공 사례"가 없다. 모델이 본받을 패턴이 부족하다.
- smalltalk_diagnostic의 `discussed_topics`는 dedup 리스트일 뿐, 토픽별로 어떤
  훅이 열려 있고 어디까지 깊이 들어갔는지 추적하지 않는다.

---

## 2. 목표 (Definition of Done)

1. **세션 메모리 강화**: Developer A 내부에 "세션 컨텍스트 카드(Session Context
   Card)" 개념을 도입해 LLM 프롬프트에 명시적인 누적 사실/열린 훅/직전 NPC 의도
   요약을 전달한다. 기존 외부 입력(dialogue_history)은 그대로 활용하되, A 내부에서
   풍부하게 재구성한다.
2. **꼬리물기 강화**: 프롬프트와 정책 노출, few-shot, 후처리 가드를 다층적으로
   보강하여 LLM이 플레이어 직전 발화의 구체 명사/사실에서 후속 질문을 만들도록
   강제한다.
3. **테스트 통과**: `uv run pytest`, `uv run ruff check .`, `uv run mypy .` 모두 통과.
4. **계약 변경 없음**: `dev_a_npc_dialogue_client.py`가 보는 입력/출력 키 구조는
   현재와 동일해야 한다 (값의 풍부함만 향상).

---

## 3. 작업 항목

각 작업은 독립적으로 PR/커밋 단위가 될 수 있도록 구성한다. 항목 순서대로 진행 권장.

### 작업 A-1. 세션 컨텍스트 카드 빌더 신설
**대상 파일 (신규):** `backend/app/services/service_a/session_context_card_service.py`

목적: dialogue_history와 정규화된 페이로드를 입력받아, LLM이 즉시 활용 가능한
구조화된 "세션 컨텍스트 카드" 사전을 만든다.

구현 명세:
- 함수 시그니처: `def build_session_context_card(normalized: dict, npc_profile, payload: dict) -> dict`
- 반환 사전 키:
  - `confirmed_facts`: `list[str]` — 지금까지 플레이어가 답한 슬롯(예:
    `"purpose=business"`, `"duration=10 days"`)을 자연어 문장으로 변환.
    `dialogue_history[*].filled_slots`를 누적 dedup해서 만든다.
  - `open_hooks`: `list[str]` — 플레이어 마지막 발화에서 추출된 명사/사실 후보.
    구현은 간단히, 마지막 `player_text_preview`를 토큰화 후 alphabetic 토큰
    중 길이 3+인 토큰을 상위 5개 추출 (의미 분류는 LLM에 위임).
  - `last_npc_intent`: `str` — 직전 NPC 발화의 surface_goal 또는, 없으면
    `npc_text_preview`의 첫 문장.
  - `recent_turns_compact`: `list[str]` — 5턴을 사람이 읽기 쉬운 한 줄 포맷
    (`"T-3 player='...' npc='...' filled={...}"`)으로 정리.
  - `topic_thread`: `list[str]` — smalltalk_diagnostic이 아니어도, 누적 NPC
    `surface_goal`(있다면) 또는 npc_text_preview의 핵심 명사를 시간 순으로
    나열. dedup.
  - `forbidden_repeat_questions`: `list[str]` — 이미 답이 채워진 슬롯에 해당하는
    질문 패턴. 예: `filled_slots`에 `purpose`가 있으면
    `"What is the purpose of your visit?"`, `"What brings you here?"` 등을
    하드코딩 맵에서 가져온다. 맵은 같은 파일 모듈 상수로 둔다.
- 헬퍼 모듈 상수 `SLOT_TO_PHRASE`, `SLOT_TO_FORBIDDEN_QUESTIONS`를 추가한다.
- 모든 함수에 한국어 docstring을 단다 (Developer A 컨벤션).

검증: `backend/tests/test_developer_a_npc_dialogue.py`에 케이스 추가.
- `filled_slots`가 누적될 때 `confirmed_facts`/`forbidden_repeat_questions`가
  올바르게 합쳐지는지.
- 빈 history도 안전하게 처리되는지.

### 작업 A-2. 에이전트 초기화 노드에서 카드 주입
**대상 파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

구현 명세:
- `node_initialize_state`에서 `session_context_card`를 빌드하고
  `state["session_context_card"]`에 저장한다.
- `NPCDialogueState`에 `session_context_card: NotRequired[dict[str, Any]]`
  키를 추가한다.
- `node_generate_dialogue_llm`에서 `llm_payload`에 다음 키를 추가:
  - `confirmed_facts`
  - `open_hooks`
  - `last_npc_intent`
  - `recent_turns_compact`
  - `topic_thread`
  - `forbidden_repeat_questions`
- 기존 `dialogue_history` 변수도 유지 (하위 호환).

### 작업 A-3. 프롬프트 메모리 섹션 신설
**대상 파일:** `backend/app/prompts/npc_dialogue_prompt.md`, `npc_dialogue_prompt.short.md`

구현 명세 (긴 프롬프트):
- 기존 `## DIALOGUE HISTORY (전 노드 적용)` 블록을 **`## SESSION MEMORY`** 로
  교체/확장. 다음 하위 섹션을 포함:
  - `### Confirmed Facts (already answered, NEVER re-ask)`
    - `{{ confirmed_facts }}`를 bullet으로 출력. 비어 있으면 "(none)".
  - `### Forbidden Repeats (do not phrase these questions again)`
    - `{{ forbidden_repeat_questions }}`.
  - `### Open Hooks (use one as the follow-up anchor)`
    - `{{ open_hooks }}`. 규칙: "Your follow-up MUST reference at least one
      of these tokens when natural."
  - `### Last NPC Intent`
    - `{{ last_npc_intent }}`.
  - `### Recent Turns (compact)`
    - `{{ recent_turns_compact }}` 그대로.
- 새 규칙 추가:
  - "If the player's last turn provides a concrete noun/fact, the NPC's follow-up
    question MUST hook onto that noun/fact (e.g., player said 'red ginseng' →
    NPC asks about quantity/recipient/customs)."
  - "If `confirmed_facts` already contains a fact, DO NOT ask for it again."

구현 명세 (short 프롬프트):
- 동일 의미를 압축해서 한 단락으로 추가:
  ```
  SESSION MEMORY:
  Confirmed: {{ confirmed_facts }}.
  Forbidden repeats: {{ forbidden_repeat_questions }}.
  Hooks (anchor follow-up here): {{ open_hooks }}.
  Last NPC intent: {{ last_npc_intent }}.
  Rule: never re-ask a confirmed fact; hook follow-up onto the player's concrete noun/fact.
  ```

### 작업 A-4. 정책값을 프롬프트에 노출
**대상 파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`,
`backend/app/prompts/npc_dialogue_prompt.md`(+`.short.md`)

구현 명세:
- `llm_payload`에 다음 키 추가:
  - `policy_action`: `policy.action`
  - `policy_next_question_style`: `policy.next_question_style`
  - `policy_max_sentence_count`: `policy.max_sentence_count`
- 프롬프트 `# DIALOGUE STRUCTURE` 하단에 `### Dialogue Policy (from rule engine)`
  섹션 추가:
  ```
  - Action: {{ policy_action }}
  - Next-question style: {{ policy_next_question_style }}
    (short: terse direct probe; natural: warm conversational hook; direct_repeat: firm re-ask; direct_warning: stern stop.)
  - Max sentences: {{ policy_max_sentence_count }}
  ```
- short 프롬프트에도 한 줄로 같이 추가.

### 작업 A-5. 후처리 가드 강화 (꼬리물기 보장)
**대상 파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

구현 명세:
- `node_generate_dialogue_llm` 후처리에서 새 가드 추가:
  1. **재질문 차단:** `npc_text`(lowercase, 구두점 제거)가
     `forbidden_repeat_questions`의 임의 항목과 부분일치하면
     `return {"error": "repeats_confirmed_fact"}`.
  2. **꼬리물기 hook 가드:** `branch_type in {"success", "neutral"}`이고
     `open_hooks`가 비어 있지 않으며 `purpose != "smalltalk_diagnostic"` 일 때,
     `npc_text`가 `open_hooks` 중 어떤 토큰도 포함하지 않고 문장이 1개 이하면
     `return {"error": "weak_followup_no_hook"}`.
  3. 위 모든 에러는 기존 `route_after_llm` 흐름을 통해 `apply_fallback`로 빠지며,
     fallback 라인은 `dialogue_policy_service.synthesize_fallback_next_question`이
     이미 surface_goal 기반으로 합성하므로 안전한 fallback이 보장된다.
- `purpose == "smalltalk_diagnostic"`에서는 hook 가드를 끄고, 기존
  coherence 가드만 유지한다. (자유 토픽 전환을 막지 않기 위함)

검증 케이스 추가:
- LLM이 `forbidden_repeat_questions`에 있는 질문을 그대로 돌려줄 때 fallback이
  적용되는지.
- open_hooks가 있는 상태에서 hook 없는 짧은 답변을 줄 때 fallback이 적용되는지.

### 작업 A-6. fallback 합성 강화
**대상 파일:** `backend/app/services/service_a/dialogue_policy_service.py`

구현 명세:
- `synthesize_fallback_next_question(fallback_text, surface_goal, open_hooks=None)`
  으로 시그니처 확장 (기본값 `None`이라 호출부 하위 호환 유지).
- `open_hooks`가 주어지고 비어 있지 않으면, surface_goal 기반 질문 앞에
  `f"You mentioned {open_hooks[0]} — "` 같은 형식의 자연스러운 hook prefix를
  추가한다 (단, hook이 ASCII 영문이고 1단어 이상일 때만).
- 호출부(`npc_dialogue_agent.py`)에서 `open_hooks` 인자 전달.

검증: 단위 테스트에 prefix 추가 케이스 / hook 없을 때 기존 동작 유지 케이스.

### 작업 A-7. few-shot 예시 보강
**대상 파일:** `backend/app/prompts/npc_dialogue_few_shots.md`

구현 명세 (예시 4~6 추가):
- **Example 4: Follow-up that hooks onto a concrete noun** —
  플레이어가 "I'm going to MGM Grand for a meeting."이라 답했을 때 NPC가
  `open_hooks: ["MGM", "Grand", "meeting"]` 중 하나를 잡아
  `"MGM Grand for a meeting? Who's the meeting with?"` 같은 꼬리물기 응답.
- **Example 5: Cross-turn callback** —
  세션 메모리에 `confirmed_facts: ["purpose=business trip"]`이 있을 때
  NPC가 다음 노드에서 `"You mentioned business earlier — who arranged the
  trip?"` 식으로 꼬리물기.
- **Example 6: Forbidden repeat avoided** —
  `forbidden_repeat_questions: ["What is the purpose of your visit?"]` 가
  주어지고 노드가 같은 슬롯을 묻도록 요구할 때, NPC가 같은 질문 대신
  `"So this trip — strictly business, or some leisure too?"`로 paraphrase.

각 예시는 기존 Example 1~3과 동일한 입력 payload + expected output JSON 형식
(`speaker`, `npc_text`, `tts_text`, …, `llm_reason`)을 따른다.

### 작업 A-8. retry 변주 풀 확장
**대상 파일:** `backend/app/services/service_a/dialogue_policy_service.py`

구현 명세:
- `RETRY_PARAPHRASES` 맵에 다음 surface_goal 키 보강:
  - `ask_travel_purpose_smalltalk`
  - `ask_stay_plan_smalltalk`
  - `respond_to_polite_request`
- 각 키마다 자연스러운 변주 3개 이상.
- `get_retry_variation`은 기존 시그니처/동작 유지 (테이블만 확장).

### 작업 A-9. 테스트 정리 및 문서 갱신
**대상 파일:**
- `backend/tests/test_developer_a_npc_dialogue.py`
- `backend/tests/test_developer_a_prompt_rendering.py`
- `docs/handoff.md` (Developer A 섹션 추가만, 다른 섹션 건드리지 말 것)
- `backend/app/agents/agent_a/npc_implementation_plan.md` (메모리/꼬리물기 절 추가)

구현 명세:
- 새 단위 테스트:
  1. `session_context_card`가 history → confirmed_facts/forbidden 변환을 잘 하는지.
  2. 프롬프트 렌더가 `confirmed_facts`, `open_hooks` 변수를 안전하게 직렬화하는지.
  3. 후처리 가드 `repeats_confirmed_fact`, `weak_followup_no_hook`이 실제로
     트리거되어 fallback으로 전환되는지.
- 기존 테스트 중 깨지는 게 있으면 **테스트 의도가 유지되도록 수정**하되, 다른
  개발자가 작성한 fixture는 변경하지 않는다.
- `docs/handoff.md`에 한 단락 추가:
  ```
  ## Developer A 2026-06-19
  - NPC 세션 메모리(Session Context Card) 도입 및 꼬리물기 가드 추가.
  - 입출력 계약 변경 없음.
  - 변경된 파일: ...
  - 실행한 검증: uv run pytest / ruff / mypy
  - 알려진 이슈: open_hooks 추출이 stop-word 필터링을 단순 길이≥3으로만 함 → 후속에서 보강 예정.
  ```

---

## 4. 실행 순서 권장

1. A-1 → A-2 (메모리 카드를 만들고 에이전트가 받게 한다)
2. A-3 → A-4 (프롬프트가 카드/정책을 활용하게 한다)
3. A-5 → A-6 (가드와 fallback을 강화한다)
4. A-7 → A-8 (모델 학습 시그널과 변주를 강화한다)
5. A-9 (테스트/문서 마무리)

각 단계 후 `uv run pytest -k developer_a` 만 먼저 돌리고, 마지막에 전체 스위트와
`ruff`, `mypy`를 돌린다.

---

## 5. 검증 체크리스트

- [ ] `uv sync` 성공
- [ ] `uv run pytest` 전체 그린 (실제 API 키 없이)
- [ ] `uv run ruff check .` 그린
- [ ] `uv run mypy .` 그린
- [ ] Developer B/C 소유 파일에 diff 없음 (`git diff --name-only` 로 확인)
- [ ] `dev_a_npc_dialogue_client.py` 가 보는 입력/출력 키 구조 변경 없음
- [ ] `docs/handoff.md` Developer A 섹션 갱신
- [ ] 새 few-shot이 ASCII-only, 영어 전용 규칙을 어기지 않음

---

## 6. 후속 (이번 작업 범위 밖, 별도 요청 사항)

다음 항목은 Developer B/C 영역에 걸치므로 코드 변경 없이
`docs/contracts/change_requests.md`에 요청 형태로 기록만 한다.

- (요청 B) `dialogue_seed.dialogue_history`의 `max_entries`를 5 → 8로 늘리는
  옵션 협의.
- (요청 C) `TurnHistoryEntry`에 `surface_goal`, `npc_emotion`, `branch_type`을
  포함시켜 A가 더 풍부한 메모리를 받을 수 있도록 계약 확장 협의.
- (요청 B) Understanding 결과의 `extracted_slots` 정규화 (소문자/공백 트리밍) 합의.

위 요청들은 본 작업 종료 후 `docs/handoff.md`에 한 줄로 요약한다.
