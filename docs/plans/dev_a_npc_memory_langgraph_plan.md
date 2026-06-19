# [DEPRECATED] Developer A — NPC별 단기 메모리 (LangGraph Checkpointer) 작업계획서

> ⚠️ **이 계획서는 `docs/plans/dev_a_unified_memory_plan.md`로 통합되었습니다.**
> 신규 작업은 통합본만 참조하세요. 본 파일은 기록 보존 목적으로만 유지됩니다.

---



작성일: 2026-06-19
대상 실행 에이전트: **Gemini (Developer A 페르소나)**
구현 옵션: **옵션 2 — LangGraph 1.2 `InMemorySaver` checkpointer 사용**
선행 문서:
- `AGENTS.md`
- `docs/plans/dev_a_memory_followup_plan.md` (세션 컨텍스트 카드 신설)
- `docs/plans/dev_a_imm_slots_v2_plan.md` (신규 슬롯/27노드 대응)

본 계획서는 위 두 선행 계획에서 만든 "세션 컨텍스트 카드"의 **입력 소스를
OpenKB dialogue_history → Agent A 자체 보관 NPC별 단기 메모리**로 교체하는
작업을 다룬다.

---

## 0. 작업 가드레일 (필독)

### 0.1 수정 가능 파일 (Developer A 소유 한정)
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/agents/agent_a/npc_llm_client.py`
- `backend/app/agents/agent_a/schemas.py`
- `backend/app/services/service_a/*.py` (특히
  `session_context_card_service.py`, 신규
  `npc_short_term_memory_service.py`)
- `backend/app/tools/tool_a/*.py`
- `backend/app/middleware/middleware_a/*.py`
- `backend/app/prompts/npc_dialogue_prompt.md`,
  `npc_dialogue_prompt.short.md`,
  `npc_dialogue_few_shots.md`
- 본 계획서 (`docs/plans/dev_a_npc_memory_langgraph_plan.md`)
- Developer A 테스트:
  `backend/tests/test_developer_a_npc_dialogue.py`,
  `backend/tests/test_developer_a_prompt_rendering.py`

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
- `backend/app/kb/**` (`kb/dev_b/` 포함)
- `backend/runtime/openkb/**`
- `backend/app/prompts/english_level_hint_prompt.md`,
  `backend/app/prompts/understanding_prompt.md`
- 위 영역에 속하는 모든 테스트

위 영역의 동작 변경이 꼭 필요하다고 판단되면, **코드는 만지지 말고**
`docs/contracts/change_requests.md`에 항목을 추가하고
`docs/handoff.md`에 한 줄 요약만 남긴다.

### 0.3 의존성 / 검증 규약
- `langchain==1.3.2`, `langgraph==1.2.2` 고정. 본 작업은 **이미 사용 중인
  langgraph만 사용**한다. 신규 패키지 추가 금지.
- 테스트는 실제 OpenAI 키 / TTS / Unreal / 원격 OpenKB 없이 통과해야 한다.

### 0.4 핵심 원칙 — Fail-fast (코드 청결도 보호)

본 계획서의 모든 작업은 **silently 폴백 동작을 만들지 않는다**. 의도와 다른
입력이 들어오면 그 자리에서 오류를 발생시켜 호출자(C)가 보게 한다. 코드가
"어떻게든 돌아가도록" 분기를 덧붙여 더러워지는 것을 막기 위해서다.

구체 규칙:
1. **thread_id 누락 금지.** `session_id`나 `npc_id`가 빈 값이면
   `build_thread_id`는 `ValueError("session_id and npc_id are required for memory isolation")`
   를 던진다. `"anon"`/`"unknown"` 같은 폴백 키를 만들지 않는다.
2. **메모리 키 충돌 금지.** 같은 thread_id에 대해 동시 호출이 들어오면
   InMemorySaver는 직렬화하므로 race는 없지만, 호출자가 명백히 잘못된
   thread_id를 강제로 넣는 경로는 만들지 않는다.
3. **알 수 없는 슬롯 / surface_goal 무시 금지.** 세션 컨텍스트 카드 빌드
   시 `SLOT_TO_PHRASE`에 없는 슬롯이 메모리에 들어 있으면 logger.warning을
   남기고 skip한다. 단, 테스트는 strict=True 모드로 카드를 빌드해 누락 시
   `ValueError`로 잡는다.
4. **LangGraph import 실패 시 명시 오류.** import fallback이 모두 실패하면
   `RuntimeError("langgraph checkpointer unavailable; required for NPC memory")`
   를 던지고, 그래프 컴파일 자체를 막는다. checkpointer 없는 모드로 우회 금지.
5. **state 키 누락 금지.** `node_persist_memory`가 `state["result"]`나
   `payload`에서 필수 필드(`npc_text`, `npc_id`)를 못 찾으면 `KeyError`를
   던진다. 빈 문자열로 채우지 않는다.

위 규칙은 §4 각 작업에 구체적으로 반영되어 있다.

---

## 1. 문제 정의

### 1.1 현재 메모리 구조의 한계
- Agent A는 자체 메모리를 갖지 않는다. Developer C가 OpenKB에서 만든
  `dialogue_seed.dialogue_history`(최근 5턴, 120자 preview)를 받아서만 과거를
  본다.
- 이 메모리는 세션 전체를 한 통에 누적하므로, **다른 NPC(예: 기내 승객
  Arabella)와 나눈 대사를 입국심사관(Hale)이 볼 수 있다.** 게임 설정상
  비현실적이며, NPC 페르소나 일관성을 깨뜨린다.
- 5턴 / 120자 제한으로 같은 NPC와의 긴 대화도 잘림.
- 줄글 형태라 LLM이 "어떤 슬롯이 확정됐는지" 같은 의미적 사실을 잘 추출하지
  못한다.

### 1.2 본 작업의 방향
- A는 OpenKB를 보지 않는다. 대신 **A 내부에 `(session_id, npc_id)` 키로 분리된
  단기 메모리**를 둔다.
- 구현 수단은 LangGraph 1.2의 `InMemorySaver` checkpointer. 이미 의존성에
  포함되어 있고, 그래프 상태 자체를 자동 보존하므로 별도 push/load 코드를 줄일
  수 있다.
- 메모리는 in-process(휘발성)로 충분하다. "한 NPC와의 대화" 단위라 영속화가
  당장 필요하지 않다. 추후 필요해지면 같은 인터페이스로 백엔드만 교체한다.

---

## 2. 아키텍처 개요

### 2.1 데이터 모델
- 메모리 키: `thread_id = f"{session_id}:{npc_id}"`.
  - `session_id`는 `payload.get("session_id")` 또는
    `payload.get("turn", {}).get("session", {}).get("session_id")`에서 추출.
    빈 값이면 `"anon"`으로 폴백.
  - `npc_id`는 `npc_roster_service.resolve_npc_profile(...).npc_id`로 정규화된
    값.
- 그래프 상태(`NPCDialogueState`)에 메모리 필드 신설:
  - `turn_buffer: list[dict]` — 그 NPC와 나눈 모든 턴의 압축 기록.
    한 엔트리는 다음과 같다:
    ```python
    {
      "turn_index": int,
      "node_id": str,
      "surface_goal": str,
      "branch_type": str,
      "player_text": str,
      "npc_text": str,
      "filled_slots": dict[str, str],
      "npc_emotion": str,
    }
    ```
  - `accumulated_slots: dict[str, str]` — 그 NPC 컨텍스트에서 확정된 슬롯 누적.
  - `forbidden_questions: list[str]` — 이미 던진 질문 패턴 (소문자/구두점 제거).
  - `last_npc_intent: str` — 직전 NPC 발화의 surface_goal 또는 첫 문장.

### 2.2 그래프 라이프사이클
- 현재 `generate_npc_dialogue_from_level_design`은 매 호출 그래프를 **새로
  컴파일**하고 초기 상태로 호출한다. 본 작업 이후:
  1. 그래프는 **모듈 레벨 싱글톤**으로 한 번만 컴파일한다 (`InMemorySaver`
     포함).
  2. 호출 시 `config={"configurable": {"thread_id": thread_id}}`를 전달한다.
  3. LangGraph는 thread_id별 상태를 자동으로 보존·재주입한다.
  4. 새 호출에서 입력 payload는 그래프의 entry node에서 병합되어 메모리 필드와
     공존한다.

### 2.3 노드 단위 책임
- `node_initialize_state` (기존): payload 정규화, NPC 프로필 로드, 정책 빌드.
  메모리 필드는 이미 thread_id 상태로 복원되어 있으므로 **읽기만** 한다.
- `node_load_memory` (신규, initialize 직후): 안전망. checkpointer가 비어
  있거나 키 불일치 시 빈 메모리로 초기화.
- `node_build_session_context_card` (기존 로직 분리): 메모리 필드를 입력으로
  카드 생성.
- `node_generate_dialogue_llm` (기존): 카드 + payload로 LLM 호출.
- `node_persist_memory` (신규, 종료 직전): 이번 턴 결과를 `turn_buffer`,
  `accumulated_slots`, `forbidden_questions`에 누적. LLM 실패해도 fallback
  결과로 push.

### 2.4 외부 의존성 격리
- A는 OpenKB를 **읽지도 쓰지도 않는다.** `OpenKBFinalResultRecordReader` 호출
  코드 (smalltalk_diagnostic 분기) 는 제거하지 않고 **deprecation TODO**만
  표시하고, 본 메모리가 동일 정보를 대체하는지 확인 후 다음 PR에서 제거한다.
- C가 페이로드로 보내는 `dialogue_seed.dialogue_history`는 **무시한다** (혹은
  fallback용 보조 신호로만 사용). A의 메모리가 비어 있는 경우(예: 첫 호출이
  서버 재시작 직후)에 한해 dialogue_history를 1회성 시드로 활용한다.

---

## 3. 목표 (Definition of Done)

1. NPC별 단기 메모리가 `(session_id, npc_id)` 키로 격리된다.
2. 같은 세션 안에서 NPC가 바뀌면 메모리도 자동으로 새로 시작된다.
3. 같은 NPC와의 대화는 5턴 제한 없이 누적된다 (in-process 한도 내).
4. LLM 프롬프트에는 그 NPC의 메모리만 흘러간다. 다른 NPC와의 대화는 새지 않는다.
5. `dev_a_npc_dialogue_client.py`가 보는 입력/출력 키 구조 변경 없음.
6. `uv run pytest`, `uv run ruff check .`, `uv run mypy .` 전부 통과.

---

## 4. 작업 항목

### 작업 M2-1. 메모리 서비스 신설
**파일 (신규):** `backend/app/services/service_a/npc_short_term_memory_service.py`

구현 명세:
- LangGraph checkpointer를 직접 만지지 않고, **그래프 상태 위에서 동작하는
  헬퍼 함수 묶음**으로 둔다. checkpointer는 그래프가 들고 있고, 본 모듈은
  상태 dict를 입력받아 update/read 하는 순수 함수만 제공.
- 공개 API:
  ```python
  def build_thread_id(session_id: str | None, npc_id: str | None) -> str: ...
  def empty_memory_state() -> dict[str, Any]: ...
  def append_turn(
      memory: dict[str, Any],
      *,
      node_id: str,
      surface_goal: str,
      branch_type: str,
      player_text: str,
      npc_text: str,
      filled_slots: dict[str, str],
      npc_emotion: str,
  ) -> dict[str, Any]: ...
  def derive_forbidden_questions(slots: dict[str, str]) -> list[str]: ...
  def merge_slots(
      existing: dict[str, str], incoming: dict[str, str]
  ) -> dict[str, str]: ...
  ```
- `build_thread_id` 규칙 (fail-fast):
  - `session_id`나 `npc_id`가 빈 값(`None`, `""`, 공백만)이면
    `ValueError("session_id and npc_id are required for memory isolation")`
    을 던진다. 폴백 키를 만들지 않는다.
  - 둘 다 trim/lower 후 `:`로 결합. 길이 제한 256자(초과 시
    `ValueError`).
- `derive_forbidden_questions`는 §`session_context_card_service.SLOT_TO_FORBIDDEN_QUESTIONS`
  를 참조해 슬롯별 패턴을 합친다. 정렬·중복 제거.
- 모든 함수에 한국어 docstring (Developer A 컨벤션).

검증 단위 테스트:
- `build_thread_id("S1", "hale") == "s1:hale"`
- `build_thread_id(None, "hale")` → `ValueError`.
- `build_thread_id("S1", "")` → `ValueError`.
- `append_turn`이 turn_index를 자동 증가시키는지.
- `merge_slots`가 동일 키에 대해 incoming을 우선하되 빈 값은 무시하는지.

### 작업 M2-2. 그래프 상태 스키마 확장
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

구현 명세:
- `NPCDialogueState`에 다음 필드를 추가 (모두 `NotRequired`):
  ```python
  turn_buffer: NotRequired[list[dict[str, Any]]]
  accumulated_slots: NotRequired[dict[str, str]]
  forbidden_questions: NotRequired[list[str]]
  last_npc_intent: NotRequired[str]
  ```
- 기존 키는 모두 유지 (하위 호환).

### 작업 M2-3. 그래프 싱글톤 + Checkpointer 구성
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

구현 명세:
- 모듈 상단에 `_GRAPH_SINGLETON: Any | None = None` 캐시를 둔다.
- 새 함수 `def _get_compiled_graph()`:
  ```python
  from langgraph.checkpoint.memory import InMemorySaver
  global _GRAPH_SINGLETON
  if _GRAPH_SINGLETON is None:
      workflow = StateGraph(NPCDialogueState)
      # ... 기존 add_node / add_edge / conditional ...
      checkpointer = InMemorySaver()
      _GRAPH_SINGLETON = workflow.compile(checkpointer=checkpointer)
  return _GRAPH_SINGLETON
  ```
- `build_npc_dialogue_graph()`는 그대로 유지하되 내부에서
  `_get_compiled_graph()`를 반환하도록 변경 (외부 호출자 호환).
- 테스트가 깨끗한 메모리에서 시작할 수 있도록 함수
  `def reset_graph_singleton_for_testing() -> None`를 추가 (테스트 픽스처용).

주의:
- `InMemorySaver` import 경로: `from langgraph.checkpoint.memory import InMemorySaver`.
  버전이 맞지 않아 import 실패 시 `from langgraph.checkpoint import MemorySaver`
  를 fallback으로 시도하고, 둘 다 실패하면 명시적 RuntimeError를 던진다.
- checkpointer 사용 시 `config["configurable"]["thread_id"]`가 반드시 필요.

### 작업 M2-4. invoke 진입점 변경
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

구현 명세:
- `generate_npc_dialogue_from_level_design`를 다음과 같이 수정:
  ```python
  def generate_npc_dialogue_from_level_design(
      payload, use_llm=False, llm_client=None, callbacks=None
  ):
      graph = _get_compiled_graph()
      session_id = (
          payload.get("session_id")
          or payload.get("turn", {}).get("session", {}).get("session_id")
          or ""
      )
      npc_id = _npc_id_from_payload(payload) or ""
      thread_id = build_thread_id(session_id, npc_id)
      config = {"configurable": {"thread_id": thread_id}}
      if callbacks:
          config["callbacks"] = callbacks

      initial_state = {
          "payload": payload,
          "use_llm": use_llm,
          "llm_client": llm_client,
      }
      final_state = graph.invoke(initial_state, config=config)
      return final_state["result"]
  ```
- 메모리 필드는 그래프가 thread_id 상태에서 복원하므로 initial_state에 넣지
  않는다. (LangGraph는 신규 키만 merge, 기존 키는 보존.)

### 작업 M2-5. 메모리 로드 / 카드 빌드 / 메모리 저장 노드 분리
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

구현 명세:
- `node_load_memory(state)` 신규: 안전망. 누락 필드를 `empty_memory_state()`
  으로 채운다.
- `node_initialize_state` 끝부분에서 `session_context_card`를 빌드할 때
  입력 소스를 `dialogue_history` 대신
  `state["turn_buffer"]`, `state["accumulated_slots"]`,
  `state["forbidden_questions"]`로 교체한다.
  - `session_context_card_service.build_session_context_card`의 시그니처에
    `npc_memory: dict | None = None` 옵션 인자를 추가하고, 주어지면 그것을
    우선 사용. (시그니처 확장은 하위 호환 가능.)
- `node_persist_memory(state)` 신규, END 직전:
  - 이번 턴 결과(`state["result"]`)에서 `npc_text`, `tone`,
    `npc_emotion`을 꺼내 `append_turn`으로 메모리에 push.
  - `payload.get("understanding", {}).get("extracted_slots", {})`이 있으면
    `merge_slots`로 합치고, `derive_forbidden_questions`로
    `forbidden_questions` 갱신.
  - `last_npc_intent`은 현재 호출의 `dialogue_seed.surface_goal`로 갱신.
- 그래프 edge 재구성:
  ```
  START → load_memory → initialize_state
       → (if use_llm) generate_dialogue_llm → (if error) apply_fallback → persist_memory → END
       → (else)                                             persist_memory → END
  ```
- `persist_memory`는 LLM 성공/실패 양쪽 경로 모두 통과한다.

### 작업 M2-6. 세션 컨텍스트 카드 서비스 시그니처 확장
**파일:** `backend/app/services/service_a/session_context_card_service.py`

구현 명세:
- `build_session_context_card(normalized, npc_profile, payload, npc_memory=None)`
  로 변경 (기본 인자 추가, 하위 호환).
- `npc_memory`가 주어지면 dialogue_history 대신:
  - `confirmed_facts` ← `accumulated_slots` 자연어 변환
  - `forbidden_repeat_questions` ← `forbidden_questions`
  - `last_npc_intent` ← `last_npc_intent`
  - `recent_turns_compact` ← `turn_buffer`에서 최근 8턴 압축
  - `open_hooks` ← `turn_buffer[-1].player_text`에서 추출 (기존 로직 유지)
  - `topic_thread` ← `turn_buffer[*].surface_goal` dedup 시간순
- `npc_memory`가 없으면 기존 dialogue_history 경로 유지 (fallback).

### 작업 M2-7. dialogue_history 의존성 축소
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`,
`backend/app/services/service_a/developer_a_input_service.py`

구현 명세:
- `developer_a_input_service.normalize_level_design_payload`에서
  `dialogue_history`를 파싱하는 부분은 유지 (B/C가 보내주는 신호).
- `node_generate_dialogue_llm`이 LLM에 넘기는 `llm_payload`에서
  `dialogue_history` 키는 그대로 두되, **본 작업 이후 LLM 프롬프트는
  세션 컨텍스트 카드 변수를 우선 신뢰하도록** 가이드를 추가 (작업 M2-9).
- smalltalk_diagnostic 분기의 `OpenKBFinalResultRecordReader` 호출 블록
  (`npc_dialogue_agent.py` 부근) 은 다음 처리:
  - `# TODO(dev-a): replace with internal NPC memory once verified` 주석 추가.
  - 호출은 유지하되 결과는 메모리 카드와 dedup해서 사용.
  - 본 PR에서는 제거하지 않는다.

### 작업 M2-8. NPC 전환 / 챕터 종료 시 메모리 정리
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`,
`backend/app/services/service_a/npc_short_term_memory_service.py`

구현 명세:
- `node_persist_memory`에서, `payload.get("transition", {}).get("status")`가
  `complete_chapter`이거나 `payload.get("next_action") == "COMPLETE_CHAPTER"`
  이면 push 후 다음 처리:
  - **메모리 정리 신호만 기록**한다: 상태에 `_memory_cleanup_pending=True`를
    세팅하고 종료. LangGraph checkpointer는 thread_id 단위라 직접 삭제 대신
    빈 상태로 덮어쓰면 효과적이다.
  - 추가 함수 `def clear_memory_state(state) -> dict`를 메모리 서비스에 두고,
    호출 즉시 turn_buffer/accumulated_slots/forbidden_questions를 빈 값으로
    초기화한다.
  - 챕터 종료 턴의 결과(인사말)는 메모리에 push되었지만, 다음 NPC 호출에서
    어차피 다른 thread_id로 가므로 누적은 의미 없다. 다만 같은 NPC를 챕터 후에
    다시 만나는 경우를 위해 명시 정리는 한다.

검증: 단위 테스트 — `transition.status=complete_chapter`인 호출 후
다음 호출에서 메모리가 비어 있는지.

### 작업 M2-9. 프롬프트 메모리 섹션 정렬
**파일:** `backend/app/prompts/npc_dialogue_prompt.md`,
`npc_dialogue_prompt.short.md`

구현 명세:
- 기존 `## SESSION MEMORY` 블록(작업계획서 §A-3에서 신설 예정)이 사용하는 변수
  바인딩은 동일하다 (`confirmed_facts`, `open_hooks`, `forbidden_repeat_questions`,
  `last_npc_intent`, `recent_turns_compact`). 카드의 입력 소스만 바뀌므로
  프롬프트 변경 최소.
- 다만 LLM 혼란을 막기 위해 헤더에 한 줄 추가:
  ```
  > NOTE: SESSION MEMORY below is THIS NPC's private memory of this player.
  > Do NOT reference events that did not happen between you and this player.
  ```
- short 프롬프트에도 같은 의미를 한 줄 추가:
  ```
  SESSION MEMORY = this NPC's private memory. Do not invent unseen turns.
  ```

### 작업 M2-10. 테스트 / 문서 갱신
**파일:**
- `backend/tests/test_developer_a_npc_dialogue.py`
- `backend/tests/test_developer_a_prompt_rendering.py`
- `docs/handoff.md` (Developer A 섹션 append만)
- `backend/app/agents/agent_a/npc_implementation_plan.md` (메모리 절 추가)

구현 명세:
- 새 단위 테스트 (모두 `reset_graph_singleton_for_testing` 픽스처로 시작):
  1. **NPC별 격리**: 같은 session_id, 다른 npc_id로 두 번 호출 시
     `turn_buffer`가 서로 분리되는지.
  2. **같은 NPC 누적**: 같은 thread_id로 5회 호출 시 turn_buffer 길이가
     5인지.
  3. **메모리 카드 입력 소스 변경**: dialogue_history는 비어 있고
     turn_buffer만 있을 때 confirmed_facts가 정상 산출되는지.
  4. **챕터 종료 후 정리**: complete_chapter 호출 후 같은 thread_id로 다시
     호출 시 turn_buffer가 비어 있는지.
  5. **회귀**: 기존 invoke 시그니처 / 출력 키가 그대로 유지되는지
     (`speaker`, `npc_text`, `tts_text`, `tone`, `animation`, `feedback_kr`,
     `npc_emotion`, `llm`, `generation_profile`).

`docs/handoff.md` append 예시:
```
## Developer A 2026-06-19 — NPC별 단기 메모리 도입 (LangGraph checkpointer)
- LangGraph InMemorySaver로 (session_id, npc_id) 단위 메모리 격리.
- 세션 컨텍스트 카드의 입력 소스를 OpenKB dialogue_history → 자체 NPC 메모리로 교체.
- B/C 페이로드 dialogue_history는 cold-start 시드용 fallback으로만 사용.
- 입출력 계약 변경 없음.
- 알려진 한계: in-process 휘발성. 서버 재시작 시 메모리 손실. 추후 옵션 1(외부 저장) 검토 가능.
- 검증: uv run pytest / ruff / mypy 통과.
```

---

## 5. 위험 요소 및 완화책

### 5.1 LangGraph 버전 호환
- LangGraph 1.2.2의 checkpointer import 경로가 사양과 다를 가능성.
- 완화: 작업 M2-3의 import fallback과 명시적 RuntimeError로 빠르게 실패하게 한다.
- 검증: `python -c "from langgraph.checkpoint.memory import InMemorySaver"` 통과.

### 5.2 in-process 휘발성
- 멀티 워커(uvicorn --workers > 1) 환경에서 워커별로 메모리가 다름.
- 완화: 본 PR 범위는 단일 워커 가정. `docs/handoff.md`에 한계 명시.
  추후 옵션 1(모듈 dict + 외부 백엔드 교체 가능 인터페이스)로 갈 길 열어 둠.

### 5.3 메모리 무한 성장
- `InMemorySaver`는 thread별 상태를 무기한 보존.
- 완화: M2-8 정리 노드 + 다음 후속 작업으로 turn_buffer는 최근 N턴(예: 20)만
  유지하도록 `append_turn`에서 슬라이딩 윈도우 적용. 현재 PR은 N=20.

### 5.4 회귀 위험
- `generate_npc_dialogue` (룰 기반 단순 진입점) 와의 동작 차이.
- 완화: 룰 기반 진입점은 그래프를 거치지 않으므로 메모리 영향을 받지 않는다.
  변경 없음. 테스트로 확인.

### 5.5 thread_id 누락
- session_id가 빈 값으로 들어오면 메모리 격리가 깨질 위험.
- 완화: §0.4 fail-fast 원칙에 따라 `build_thread_id`가 즉시 `ValueError`를
  던진다. 호출자(C)는 이를 그래프 컴파일 단계 직전에 명시적으로 보게 된다.
  단위 테스트로 다양한 빈 값(`None`, `""`, 공백)에서 `ValueError`가 나는지
  확인. 폴백 키를 만들지 않는다.

---

## 6. 실행 순서 권장

1. M2-1 (메모리 서비스 신설, 순수 함수)
2. M2-2 (그래프 상태 스키마 확장)
3. M2-3 (그래프 싱글톤 + checkpointer)
4. M2-4 (invoke 진입점에 thread_id)
5. M2-5 (load/build/persist 노드 분리, edge 재구성)
6. M2-6 (카드 서비스 시그니처 확장)
7. M2-7 (dialogue_history 의존성 축소)
8. M2-8 (챕터 종료 정리)
9. M2-9 (프롬프트 가드 한 줄 추가)
10. M2-10 (테스트 / 문서)

각 단계 후 `uv run pytest -k developer_a` 빠른 회귀, 마지막에 전체 스위트 +
`ruff` + `mypy`.

---

## 7. 검증 체크리스트

- [ ] `uv sync` 성공.
- [ ] `from langgraph.checkpoint.memory import InMemorySaver` 임포트 가능.
- [ ] `uv run pytest` 전체 그린 (실제 API 키 없이).
- [ ] `uv run ruff check .` 그린.
- [ ] `uv run mypy .` 그린.
- [ ] `git diff --name-only`로 확인 시 변경 파일이 §0.1 화이트리스트 내부만.
- [ ] 같은 session_id 다른 npc_id 호출이 메모리 격리됨.
- [ ] 같은 npc_id 반복 호출이 누적됨.
- [ ] complete_chapter 후 같은 NPC 메모리가 정리됨.
- [ ] `dev_a_npc_dialogue_client.py`가 보는 입출력 키 구조 변화 없음.

---

## 8. 후속 (이번 범위 밖, change_requests.md에만 기록)

용어 정리:
- **session_id**: 한 명의 플레이어가 게임을 시작해서 끝낼 때까지의 한 판을
  식별하는 ID. Unreal → Developer C 요청 페이로드의
  `turn.session.session_id`에 들어온다. 같은 플레이어가 새 게임을 시작하면
  바뀐다. Agent A는 이 값과 `npc_id`를 묶어 메모리 thread_id를 만든다.

후속:
- (요청 C) 페이로드에 `session_id`가 **항상** 포함되도록 계약 명시 요청.
  현재 optional이라 누락 시 본 계획서는 명시적 오류를 던지는 정책이다(§10
  fail-fast). C가 보장해 주면 클라이언트 측 오류 핸들링이 단순해진다.
- (요청 C) `dialogue_seed.dialogue_history` 의무 전송 폐지 검토. A가 자체
  메모리를 들고 가면 C가 이걸 만들 필요가 없다. 데이터 사이즈 절감.

---

## 9. 기존 계획서와의 관계

본 계획서는 다음 두 선행 계획과 **직렬로** 수행되는 것을 가정한다.

1. `dev_a_memory_followup_plan.md`: 세션 컨텍스트 카드 신설 (입력 소스 =
   dialogue_history).
2. `dev_a_imm_slots_v2_plan.md` (슬림판): 신규 9 슬롯 매핑 + fail-fast 가드.
   압박 톤 연출은 분리되어 본 PR 범위 밖.
3. **본 계획서**: 카드의 입력 소스를 자체 NPC 메모리로 교체. fail-fast 원칙
   적용.

1→2→3 순서를 권장한다. 1번이 카드 인터페이스를 정의하고, 2번이 신규 슬롯/
surface_goal을 등록하고, 3번이 입력 소스를 교체한다. 세 계획 모두 §0.4
fail-fast 원칙을 공유한다.
