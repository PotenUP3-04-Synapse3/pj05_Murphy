# Agent A — LangChain 1.0+ 마이그레이션 작업계획서

> 작성일: 2026-06-15
> 대상: `backend/app/agents/agent_a`, `backend/app/middleware/middleware_a`, 그리고 이와 연관된 `service_a` / `tool_a` 진입점
> 현재 의존성: `langchain==1.3.2`, `langgraph==1.2.2` (pyproject.toml 기준 — 패키지는 1.x이나 코드에는 0.x 시대 패턴이 다수 잔존)

---

## 0. 요약

`pyproject.toml`은 이미 LangChain 1.3 / LangGraph 1.2를 요구하지만, `agent_a`와 그 클라이언트 코드는 LangChain 0.x 시절의 관용구를 그대로 사용하고 있습니다. 핵심 잔존 패턴은 ① `httpx`로 OpenAI API를 직접 호출하는 커스텀 `BaseChatModel`, ② `with_structured_output` 대신 수기로 작성한 JSON Schema, ③ `with_fallbacks` 대신 수기로 만든 `FallbackNPCDialogueLLMClient`, ④ `RunnableConfig` 대신 `inspect.signature`로 callbacks 인자를 분기하는 핵, ⑤ LangGraph `StateGraph`와 `AgentMiddleware`가 분리되어 실제로는 미들웨어 훅이 호출되지 않는 구조입니다. 본 문서는 이를 **LangChain 1.0 표준(LCEL Runnable + `create_agent` + `with_structured_output` + `with_fallbacks` + RunnableConfig 기반 callbacks)** 으로 일관되게 정렬하기 위한 작업 계획입니다.

---

## 1. 구버전 패턴 식별 결과

### 1-1. `backend/app/agents/agent_a/npc_llm_client.py`

| 위치 | 현재(0.x 잔존) | 1.0+ 권장 |
|---|---|---|
| L95–162 | `_OpenAINPCDialogueChatModel(BaseChatModel)` — `httpx.post`로 `/v1/responses` 호출하는 자작 모델 | `langchain-openai`의 `ChatOpenAI(model=..., use_responses_api=True).with_structured_output(NPCDialogueSchema)` |
| L215–273 | `_OpenAICompatibleNPCDialogueChatModel(BaseChatModel)` — vLLM용 자작 Chat Completions 호출 | `ChatOpenAI(base_url=..., api_key=...)` 로 동일 추상화 (vLLM/Ollama OpenAI 호환 서버 모두 지원) |
| L108–162 / L233–273 | `_generate(messages, stop, run_manager: Any = None, **kwargs)` — `run_manager` 타입 누락, stop 미사용, 동기 only | 1.0+ 권장 시그니처: `run_manager: CallbackManagerForLLMRun \| None = None`, 가능하면 `_agenerate`도 함께 구현 (또는 `ChatOpenAI`로 대체해 제거) |
| L143–151 | `text.format.json_schema` (Responses API JSON Schema) 수기 작성 | Pydantic 모델 + `.with_structured_output(schema, method="json_schema", strict=True)` |
| L198–212 / L290–304 | `def generate(self, payload, callbacks=...)` — Runnable이 아닌 커스텀 메서드 | `prompt | model.with_structured_output(...)` 체인을 Runnable로 노출하고, 호출 측은 `chain.invoke(payload, config={"callbacks": [...]})` 통일 |
| L308–334 | `FallbackNPCDialogueLLMClient` 데코레이터를 손으로 구현 (try/except로 분기) | `primary.with_fallbacks([fallback])` Runnable 빌트인 사용 |
| L319–332 | `inspect.signature(...).parameters` 로 callbacks 지원 여부 분기 — 0.x 잔재 | RunnableConfig 표준으로 통일했으므로 분기 자체 제거 |
| L82–91 | `_UnavailableNPCDialogueLLMClient`로 빌드 실패를 더미 객체로 위장 | `RunnableLambda(lambda _: (_ for _ in ()).throw(...))` 또는 빌드 시점 `NPCDialogueLLMUnavailable` 즉시 raise → fallback 체인은 `with_fallbacks(exceptions_to_handle=(NPCDialogueLLMUnavailable,))` 로 처리 |
| L491–563 | `_extract_structured_json`, `_extract_chat_completion_structured_json`, `_extract_usage`, `_extract_chat_completion_usage` | 1.0+ `AIMessage.usage_metadata` 가 표준화되어 있음. `ChatOpenAI` 도입 시 전부 제거 |
| L156–162 / L267–273 | `AIMessage(content=json.dumps(result_dict))` 로 JSON을 문자열로 한 번 더 직렬화 후 호출 측에서 `json.loads` | `with_structured_output` 사용 시 Pydantic 객체가 직접 반환됨 |
| L585–587 | `OpenAICompatibleNPCDialogueLLMClient = ...` 하위 호환 별칭 | 더 이상 사용처가 없으면 deprecate 후 제거 |
| L20–63 | `NPCDialogueCallbackHandler(BaseCallbackHandler)` — 미들웨어를 직접 주입받아 print 대용으로 사용 | 표준 callbacks는 `RunnableConfig.callbacks` 로 자동 전달되므로 핸들러는 유지하되, 미들웨어 인스턴스 의존은 끊고 ‘이벤트 어댑터’ 형태로 단순화 |

### 1-2. `backend/app/agents/agent_a/npc_dialogue_agent.py`

| 위치 | 현재(0.x 잔존) | 1.0+ 권장 |
|---|---|---|
| L162 | `NPCDialogueState`에 `callbacks: NotRequired[list[Any]]` 를 state로 들고 다님 | callbacks는 **state가 아닌 `RunnableConfig`** 로 흐르도록 변경. 노드는 `def node(state, config: RunnableConfig)` 시그니처 사용 |
| L161 | `llm_client: Any` 를 state에 주입 | DI 컨테이너/팩토리에서 한 번 만들어 클로저 또는 Runtime context로 전달 (LangGraph 1.x `Runtime[Context]`) |
| L242–279 | `inspect.signature(client.generate)` 분기 + 두 갈래 호출 | Runnable 체인이므로 `chain.invoke(payload, config=config)` 한 줄로 통일 |
| L280 | `except (NPCDialogueLLMUnavailable, httpx.HTTPError, ...)` 광역 캐치 | `with_fallbacks` + `with_retry(stop_after_attempt=N)` 로 대체. 잔존 예외만 `node_apply_fallback` 으로 라우팅 |
| L283 | `llm_result.get("__llm_usage", {})` | `AIMessage.usage_metadata` 사용 (`input_tokens`, `output_tokens`, `total_tokens`) |
| L347–375 | `StateGraph(NPCDialogueState)` + 수기 노드 (룰베이스 → LLM → fallback) | 현재 워크플로는 “룰 기반 시드 → LLM 보정”이라 ReAct-style tool agent가 아님. **StateGraph는 유지**하되 1.x 시그니처 (`Runtime`, `RunnableConfig`)로 정렬. 또는 단순한 `tool_a`(artifact/evidence/cost) 를 `@tool` 데코레이터로 노출하고 `create_agent(model, tools=[...], middleware=[...])` 로 재구성하는 옵션도 검토 |

### 1-3. `backend/app/middleware/middleware_a/npc_dialogue_agent_run_middleware.py`

| 위치 | 현재(0.x 잔존) | 1.0+ 권장 |
|---|---|---|
| L5 | `from langchain.agents import AgentState` | 1.3 기준 위치는 동일하나 사용처가 없음 (StateGraph가 `NPCDialogueState`만 사용) |
| L14 | `class NPCDialogueAgentRunMiddleware(AgentMiddleware[AgentState, Any, Any])` | 이미 1.x 시그니처. 단, **실제 `create_agent`에 등록되지 않아** `before_model/after_model` 훅이 절대 호출되지 않음 → ① `create_agent` 도입과 함께 미들웨어로 정상 등록하거나, ② AgentMiddleware 상속을 끊고 순수 “AgentRun 로거” 클래스로 단순화 |
| L17 | `self.tools = []` 빈 리스트 | tool_a 의 evidence/cost/artifact 빌더를 `@tool` 로 래핑해 등록 (선택) |
| L22 / L27 | `print(...)` 디버그 stub | 표준 `logging.getLogger(__name__)` 또는 `record_event` 호출로 일관화 |
| L29–60 | `start_run` — agent 실행과 무관하게 `voice_output_service`에서 직접 호출되는 비표준 API | 미들웨어 본분(훅 기반)으로 일원화하거나, 별도 모듈 `agent_run_recorder.py`로 분리해 미들웨어와 책임 분리 |
| L62–96 | `record_event` 도 동일하게 외부에서 직접 호출됨 | 위와 동일하게 분리/리네이밍 권고 |

### 1-4. 호출자 측 (`services/service_a/voice_output_service.py`)

| 위치 | 현재(0.x 잔존) | 1.0+ 권장 |
|---|---|---|
| L83 | `agent_run_middleware = NPCDialogueAgentRunMiddleware()` 후 `record_event` 직접 호출 | 미들웨어 분리 후 `AgentRunRecorder()` 사용. `create_agent` 도입 시 미들웨어는 등록만 하고 호출은 LangChain 런타임이 담당 |
| L122–130 | `NPCDialogueCallbackHandler(middleware=..., metadata=...)` 인스턴스를 만들어 callbacks 리스트로 주입 | `chain.invoke(payload, config={"callbacks": [recorder_callback], "run_name": "npc_dialogue", "tags": [...]})` 형태로 표준화 |
| L121 | `from backend.app.agents.agent_a.npc_llm_client import NPCDialogueCallbackHandler` 함수 내부 지연 import | 상단 모듈 import으로 이동 (순환 의존성 없으면) |

### 1-5. pyproject 의존성

| 항목 | 현재 | 1.0+ 권장 |
|---|---|---|
| langchain | `==1.3.2` | 그대로 유지 가능 |
| langgraph | `==1.2.2` | 그대로 유지 가능 |
| langchain-openai | **미포함** | 추가 필요 (`>=0.3` 등 1.x 호환 라인) |
| langchain-core | langchain에 동봉 | 명시적 핀 권장 (`langchain-core>=0.3`) |
| httpx | `>=0.28.1` | 유지 (TTS/외부 호출에 사용) |

---

## 2. 마이그레이션 목표 아키텍처

```
LCEL Runnable 체인 (1.0+ 표준)
└─ prompt (ChatPromptTemplate)
   └─ ChatOpenAI(model=...)            # /v1/responses 또는 OpenAI 호환 서버
        .with_structured_output(NPCDialogueSchema, method="json_schema", strict=True)
        .with_fallbacks([ChatOpenAI(base_url=vllm_url).with_structured_output(...)])
        .with_retry(stop_after_attempt=2)

LangGraph StateGraph
├─ Runtime[NPCDialogueContext]  (llm_client, recorder 등 DI)
├─ node_initialize_state(state, config)
├─ node_generate_dialogue_llm(state, config)  ─ chain.invoke(payload, config=config)
└─ node_apply_fallback(state, config)

콜백/로깅
└─ NPCDialogueAgentRunRecorder  (구 middleware의 record_event/start_run/complete_run/fail_run)
   └─ NPCDialogueCallbackHandler(recorder)  → RunnableConfig.callbacks 로 주입
```

선택지(고려): tool_a(evidence/cost/artifact)를 LangChain `@tool` 로 래핑하고 `create_agent(model, tools=[...], middleware=[NPCDialogueAgentRunMiddleware()])` 로 재구성하면 미들웨어 훅이 정상 작동합니다. 다만 현재 워크플로는 “룰베이스 → LLM 보정”이 결정적이라 ReAct가 과한 추상이 될 수 있으므로 **Phase 5 선택 작업**으로 분리합니다.

---

## 3. 작업 계획 (Phased)

각 Phase는 독립적으로 머지 가능하도록 분리. Phase가 끝날 때마다 `voice_output_service` 의 통합 테스트가 그린이어야 함.

### Phase 0 — 사전 점검 (0.5d)
1. `pyproject.toml` 에 `langchain-openai`, `langchain-core` 명시 핀 추가 후 `uv lock`.
2. **의존성 그래프 충돌 사전 검증 (review feedback ③):**
   - 현재 `langchain==1.3.2` 가 내부적으로 요구하는 `langchain-core` 호환 범위 확인 (`uv tree | grep langchain-core` 또는 `pip show langchain | grep Requires`).
   - `langchain-openai` 의 최소 `langchain-core` 요구 버전이 위 범위와 겹치는 라인을 선택 (예: `langchain-openai>=0.3,<0.4`, `langchain-core>=0.3.21,<0.4` 등 — `uv lock` 결과로 확정).
   - `uv lock --upgrade-package langchain-openai` 실행 후 lock 파일의 `langchain-core` 단일 버전 해결 확인. 충돌 시 pyproject 핀 재조정.
3. 기존 회귀 테스트 목록 정리: `backend/tests/dev_b/test_developer_b_agent_run_log.py` 외에 agent_a 관련 회귀 테스트 추가가 필요한지 확인 (현재 누락).
4. `samples/`, `demo/` 시나리오로 룰베이스/LLM/Fallback 3개 경로의 베이스라인 출력을 스냅샷 저장.
5. **산출물:** baseline snapshot JSON, 의존성 락 파일, 회귀 테스트 인벤토리, **의존성 그래프 충돌 검증 보고(텍스트 1매)**.

### Phase 1 — Pydantic 스키마 & 구조화 출력 도입 (1d)
1. `npc_llm_client.py`의 `_dialogue_schema()` JSON을 **Pydantic 모델**로 옮긴다. 파일 신설: `agents/agent_a/schemas.py`
   - `NPCDialogueLLMResult(BaseModel)`: `speaker`, `npc_text`, `tts_text`, `feedback_kr`, `tone(Literal[...])`, `animation`, `npc_emotion(Literal[...])`, `stability`, `style`, `speed`, `similarity_boost`, `llm_reason`.
   - 길이 제약은 `Field(min_length=..., max_length=...)` 로 표현.
2. `_extract_structured_json`, `_extract_chat_completion_structured_json`, `_extract_usage`, `_extract_chat_completion_usage`, `_strip_json_fence`, `_int_value` 제거 예정으로 표시 (`# TODO(phase-2)`).
3. **수용 기준(Acceptance):**
   - 스키마가 단위 테스트로 검증된다 (모든 enum/필드 길이 한계 케이스).
   - 기존 `_dialogue_schema()` 와 Pydantic.model_json_schema() 가 동등함을 확인하는 비교 테스트.

### Phase 2 — `ChatOpenAI`로 BaseChatModel 자작 코드 제거 (1.5d)
1. `langchain-openai`의 `ChatOpenAI` 도입.
2. `OpenAINPCDialogueChatModel` → 다음으로 대체:
   ```python
   ChatOpenAI(
       model=model_name,
       api_key=api_key,
       timeout=timeout_seconds,
       use_responses_api=True,
   ).with_structured_output(NPCDialogueLLMResult, method="json_schema", strict=True)
   ```
3. `OpenAICompatibleNPCDialogueChatModel` (vLLM) → 동일하게 `ChatOpenAI(base_url=..., api_key=..., model=...)` 로 대체. `_strip_json_fence` 같은 핸들링은 `with_structured_output(method="json_mode")` 로 대체 가능.
4. 자작 클래스 `_OpenAINPCDialogueChatModel`, `_OpenAICompatibleNPCDialogueChatModel`, `OpenAINPCDialogueChatModel`, `OpenAICompatibleNPCDialogueChatModel`, 하위 호환 별칭 2종 제거.
5. **수용 기준:**
   - 동일 입력에 대해 Phase 0 스냅샷과 출력 동등 (tone/emotion/텍스트 길이 ±허용 오차).
   - 토큰 사용량은 `AIMessage.usage_metadata.input_tokens / output_tokens / total_tokens` 로 추출.

### Phase 3 — `with_fallbacks` / `with_retry` 도입 & `inspect.signature` 핵 제거 (1d)
1. `FallbackNPCDialogueLLMClient` (수기 데코레이터) 폐기 → Runnable 메서드 사용.
2. **Primary / Fallback 구조화 출력 방식 이원화 (review feedback ②):**
   vLLM의 OpenAI 호환 엔드포인트는 `response_format: json_schema` (strict) 모드를 정상 처리하지 못하거나 enum/중첩 스키마에서 예기치 않은 오류가 빈번합니다. 따라서 Primary는 strict `json_schema`, Fallback은 `json_mode` 또는 명시적 `JsonOutputParser`로 분기:
   ```python
   from langchain_core.output_parsers import JsonOutputParser

   # Primary (OpenAI Responses API + strict JSON Schema)
   primary_model = ChatOpenAI(
       model=primary_model_name,
       api_key=openai_api_key,
       timeout=timeout_seconds,
       use_responses_api=True,
   ).with_structured_output(
       NPCDialogueLLMResult,
       method="json_schema",
       strict=True,
   ).with_retry(stop_after_attempt=2, wait_exponential_jitter=True)

   # Fallback (vLLM/Ollama 등 OpenAI 호환 서버)
   # — 1순위: json_mode 시도
   # — 2순위: parser 기반 (모델이 json_mode조차 미지원할 때)
   fallback_method = os.getenv("NPC_DIALOGUE_FALLBACK_OUTPUT_METHOD", "json_mode")
   if fallback_method == "json_mode":
       fallback_runnable = ChatOpenAI(
           base_url=vllm_base_url,
           api_key=vllm_api_key,
           model=vllm_model_name,
           timeout=timeout_seconds,
       ).with_structured_output(NPCDialogueLLMResult, method="json_mode")
   else:  # "parser"
       fallback_runnable = (
           ChatOpenAI(base_url=vllm_base_url, api_key=vllm_api_key, model=vllm_model_name)
           | JsonOutputParser(pydantic_object=NPCDialogueLLMResult)
       )

   chain = (prompt | primary_model).with_fallbacks(
       [prompt | fallback_runnable],
       exceptions_to_handle=(
           NPCDialogueLLMUnavailable,
           json.JSONDecodeError,
           httpx.HTTPError,
           ValueError,
       ),
   )
   ```
3. `build_npc_dialogue_llm_client_from_environment` 는 "Runnable을 빌드해 돌려주는 팩토리"로 의미 변경. 반환 타입은 `Runnable[dict, NPCDialogueLLMResult]`. 위 `fallback_method` 같은 환경 분기는 팩토리 인자/환경변수로 열어둔다.
4. `_UnavailableNPCDialogueLLMClient` 제거. 빌드 실패 → `NPCDialogueLLMUnavailable` 즉시 raise. 호출 측은 `chain.with_fallbacks([...])` 로 흡수.
5. `npc_dialogue_agent.py` `node_generate_dialogue_llm` 안의 `inspect.signature` 분기와 두 갈래 호출 → 한 줄 `chain.invoke(payload, config=config)` 로 단순화.
6. `npc_llm_client.py`의 자체 `FallbackNPCDialogueLLMClient.generate` 내부 `inspect.signature` 분기 동시 제거.
7. **수용 기준:**
   - `inspect.signature` 검색 결과 0건 (agent_a 영역).
   - Primary 강제 실패 테스트가 vLLM fallback(`json_mode`/`parser` 두 모드 모두)으로 라우팅됨을 통합 테스트로 검증.
   - vLLM이 strict `json_schema` 를 거부하는 경우에도 Fallback 경로는 그린.

### Phase 4 — `RunnableConfig` 기반 callbacks/state 정리 (1d)
1. `NPCDialogueState` 에서 `callbacks: NotRequired[list[Any]]` 제거. `llm_client: Any` 도 state에서 제외.
2. **DI 표준 통일 — `RunnableConfig.configurable` 사전 채택 (review feedback ①):**
   런타임에 가변적인 의존성(LLM 체인, API 키, 모델 설정 등)은 state가 아닌 **`config["configurable"]` 사전**으로 흘려보낸다. LangGraph 1.x 권장 패턴.
   ```python
   from langchain_core.runnables import RunnableConfig

   def node_generate_dialogue_llm(
       state: NPCDialogueState,
       config: RunnableConfig,
   ) -> dict[str, Any]:
       configurable = config.get("configurable") or {}
       llm_chain = configurable.get("llm_chain")
       if llm_chain is None:
           # 팩토리에서 못 만든 경우 — fallback 노드로 라우팅
           return {"error": "llm_chain_not_configured"}
       result: NPCDialogueLLMResult = llm_chain.invoke(_payload(state), config=config)
       ...
   ```
3. `generate_npc_dialogue_from_level_design(payload, use_llm, llm_client, callbacks)` 시그니처:
   - 외부 API 시그니처는 유지하되 내부에서 RunnableConfig로 정규화:
   ```python
   chain = llm_client or build_npc_dialogue_llm_chain_from_environment()
   config: RunnableConfig = {
       "callbacks": callbacks or [],
       "run_name": "npc_dialogue",
       "tags": ["agent_a"],
       "configurable": {
           "llm_chain": chain,
           "use_llm": use_llm,
       },
   }
   return graph.invoke({"payload": payload}, config=config)["result"]
   ```
4. 호출자 `voice_output_service.build_voice_output_from_level_design` 도 동일하게 `RunnableConfig` 기반으로 정렬. 함수 내 지연 import 제거.
5. **수용 기준:**
   - state TypedDict에 `callbacks` / `llm_client` 키 없음.
   - 노드는 `config["configurable"]` 만으로 LLM 체인을 획득.
   - 콜백 핸들러는 모든 노드/체인에서 `on_chain_start/end`, `on_llm_start/end` 이벤트를 정상 수신.

### Phase 5 — 미들웨어 책임 분리 (또는 `create_agent` 도입) (1.5d)
**옵션 A (권장, 작은 변경):** `NPCDialogueAgentRunMiddleware` 의 `start_run / record_event / complete_run / fail_run` 을 신규 `services/service_a/agent_run_recorder.py` 의 `NPCDialogueAgentRunRecorder` 로 이전. 미들웨어 클래스는 폐기. `voice_output_service`는 recorder를 직접 사용. `NPCDialogueCallbackHandler` 는 recorder를 받도록 단순화.

**옵션 B (선택, 더 큰 변경):** `langchain.agents.create_agent(model, tools=[evidence_tool, cost_tool, artifact_tool], middleware=[NPCDialogueAgentRunMiddleware()])` 로 통째 재구성. 이 경우 `tool_a` 의 빌더 3종을 `@tool` 로 래핑하고 미들웨어 훅(before_model/after_model)이 실제 호출되도록 한다. ⚠ ReAct loop 도입은 결정적 응답 보장에 영향이 있으므로 별도 PR + 부하/회귀 테스트 권장.

본 계획서 기본은 **옵션 A**. 옵션 B는 후속 RFC로 분리.

1. (A) `agent_run_recorder.py` 신설 — `start_run`, `record_event`, `complete_run`, `fail_run` 이전.
2. (A) `middleware/middleware_a/` 디렉터리 deprecate 안내. import 호환 shim 1리스 유지 후 1주 뒤 삭제.
3. (A) `NPCDialogueCallbackHandler` 가 받는 인자를 `middleware`→`recorder` 로 리네이밍 + 타입.
4. (A) `voice_output_service` 의 모든 `agent_run_middleware.record_event(...)` → `recorder.record_event(...)`.
5. **수용 기준:**
   - `before_model/after_model` print 제거 (또는 옵션 B에서 정상 호출 검증).
   - 미들웨어를 import하지 않아도 agent_a 동작이 변하지 않음.

### Phase 6 — 정리 & 회귀 (0.5d)
1. 데드 코드 제거: `_developer_instructions` 안 중복 문장, 별칭 `OpenAICompatibleNPCDialogueLLMClient`/`OpenAINPCDialogueLLMClient`, 미사용 `_int_value` 등.
2. mypy/ruff 통과 (`backend/app/agents/agent_a`, `backend/app/middleware/middleware_a` 한정).
3. Phase 0 스냅샷 대비 비교 테스트 통과.
4. 문서 갱신: `docs/agent_a_structure.md` 의 LLM Client 섹션을 새 Runnable 체인 구조로 다시 그리기.

---

## 4. 위험 요소 및 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| `ChatOpenAI(use_responses_api=True)` 와 자작 Responses 호출의 JSON Schema 응답 형식 차이 | 출력 누락/형식 깨짐 | Phase 0 스냅샷 비교 + 슈도 단위 테스트로 schema → AIMessage → Pydantic 라운드트립 검증 |
| vLLM 서버가 `with_structured_output(method="json_schema")` strict 모드를 부분만 지원하거나 enum/중첩에서 실패 | Fallback 경로 실패 | **Phase 3에서 명시적으로 이원화** — Primary는 strict `json_schema`, Fallback은 `json_mode` 또는 `JsonOutputParser` 분기. `NPC_DIALOGUE_FALLBACK_OUTPUT_METHOD` 환경변수로 운영 중 토글 가능 |
| `langchain==1.3.2` 가 요구하는 `langchain-core` 범위와 신규 `langchain-openai` 의 요구가 충돌해 `uv lock` 실패 | Phase 0 자체 진행 불가 | **Phase 0 step 2**에서 lock 단계 사전 검증. 충돌 시 `langchain-openai` 호환 라인 하향, 그래도 안 되면 `langchain` 자체 마이너 업/다운그레이드 검토 |
| `with_fallbacks` 가 처리하는 예외 집합이 기존 try/except 보다 좁아 운영 중 알 수 없는 예외에 의해 fallback이 안 탈 가능성 | 운영 안정성 저하 | `exceptions_to_handle` 에 기존 캐치 목록과 동일한 5종 유지. 추가로 `Exception` 광역 fallback은 마지막 단에 `node_apply_fallback` 로 보존 |
| `create_agent`(옵션 B) 도입 시 ReAct loop가 결정적 응답을 비결정적으로 만들 위험 | 게임 로직 회귀 | 옵션 B는 별도 RFC, 별도 PR. 본 계획에서는 미수행 |
| 미들웨어 책임 분리로 외부에서 `NPCDialogueAgentRunMiddleware` 를 import하던 코드가 깨질 가능성 | 빌드 실패 | Phase 5에서 한시적 import shim (`from .npc_dialogue_agent_run_middleware import NPCDialogueAgentRunRecorder as NPCDialogueAgentRunMiddleware`) 유지 후 deprecation warning |
| `callbacks` 가 state에서 빠지면서 기존 호출자(테스트 포함)가 깨질 가능성 | 회귀 | Phase 4 PR에 호출자 일괄 수정 포함, 그리고 `generate_npc_dialogue_from_level_design`의 외부 API 시그니처는 유지 |

---

## 5. 일정 요약

| Phase | 산출물 | 예상 공수 |
|---|---|---|
| 0. 사전 점검 | baseline snapshot, 의존성 락 | 0.5d |
| 1. Pydantic 스키마 | `agents/agent_a/schemas.py`, 단위 테스트 | 1.0d |
| 2. `ChatOpenAI` 치환 | 자작 BaseChatModel 제거, 사용량 표준화 | 1.5d |
| 3. `with_fallbacks` / `with_retry` | `inspect.signature` 완전 제거 | 1.0d |
| 4. RunnableConfig 정리 | state에서 callbacks/llm_client 제거 | 1.0d |
| 5. 미들웨어 분리 | `agent_run_recorder.py` 신설 | 1.5d |
| 6. 정리/회귀 | 데드코드 정리, 문서 갱신 | 0.5d |
| **합계** | | **~7d (영업일)** |

---

## 6. 체크리스트 (PR 머지 전)

- [ ] `grep -rn "inspect.signature" backend/app/agents/agent_a` → 0건
- [ ] `grep -rn "httpx.post" backend/app/agents/agent_a` → 0건 (httpx는 tts 쪽만 잔존)
- [ ] `grep -rn "BaseChatModel" backend/app/agents/agent_a` → 0건 (또는 `langchain_openai.ChatOpenAI` 만 import)
- [ ] `grep -rn "FallbackNPCDialogueLLMClient\|_UnavailableNPCDialogueLLMClient" backend/app` → 0건
- [ ] `grep -rn "callbacks:" backend/app/agents/agent_a/npc_dialogue_agent.py` → state 키 없음
- [ ] `NPCDialogueAgentRunMiddleware.before_model` 가 print 없이 정상 동작하거나 클래스 자체가 제거됨
- [ ] `samples/`, `demo/` 시나리오 baseline snapshot 비교 그린
- [ ] `pytest backend/tests` 그린, mypy/ruff 그린

---

## 7. 검토 피드백 반영 이력 (2026-06-15)

본 계획서는 1차 작성 후 코드 리뷰를 받아 다음 세 항목을 반영했습니다.

| # | 피드백 요지 | 반영 위치 | 변경 요약 |
|---|---|---|---|
| ① | DI는 `RunnableConfig.configurable` 사전으로 흘려보내라 | Phase 4 step 2 | `state["llm_chain"]` 대신 `config["configurable"]["llm_chain"]` 경유로 명시. 노드 예제 코드 갱신, 수용 기준에 "노드는 `config["configurable"]` 만으로 LLM 체인을 획득" 추가 |
| ② | vLLM Fallback은 strict `json_schema` 대신 `json_mode`/`JsonOutputParser` 이원화 | Phase 3 step 2 + 위험 표 | Primary/Fallback 구조화 출력 메서드를 분리하는 예제 코드 삽입. `NPC_DIALOGUE_FALLBACK_OUTPUT_METHOD` 환경변수로 운영 중 토글 가능. 수용 기준에 "vLLM이 strict json_schema 를 거부하는 경우에도 Fallback 경로는 그린" 추가 |
| ③ | `langchain==1.3.2` ↔ `langchain-openai`/`langchain-core` 핀 충돌 사전 검증 | Phase 0 step 2 + 위험 표 | `uv tree`/`uv lock` 단계에서 호환 범위 확인 절차 추가. 충돌 시 대응(라이브러리 라인 하향 → langchain 자체 마이너 조정)까지 명문화 |

세 항목 모두 본문 표/예제에 직접 반영되었으며, 별도 후속 RFC가 아니라 **본 계획의 Phase 0/3/4 안에서 처리**됩니다.

---

## 8. 후속(별도 RFC) 항목

1. **옵션 B: `create_agent` 도입.** tool_a를 `@tool` 로 노출하고 미들웨어 훅을 정식 사용. 결정적 응답 보장 검증 포함.
2. **비동기화 (`ainvoke`/`astream`).** FastAPI 경로에서 비동기 호출로 전환 시 처리량 개선 여지.
3. **LangSmith/Tracing 연동.** `RunnableConfig` 가 정렬되었으므로 trace export가 1줄로 가능. 운영 모니터링 단계로 분리.
