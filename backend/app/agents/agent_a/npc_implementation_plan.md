# Alpha Stage NPC Integration & Roster Update Plan (Revised for Dynamic TTS)

이 문서는 **Developer A**의 개발 소유권을 준수하며, 신규 난이도 등급 체계(**Bronze, Silver, Gold**)를 반영하고 감정 튜닝용 TTS 파라미터(Stability, Style Exaggeration, Speed, Similarity Boost)를 미리 하드코딩하지 않고 **LLM이 실시간으로 상황에 맞추어 직접 결정**하도록 아키텍처를 고도화하기 위한 상세 작업 계획서입니다.

---

## 1. Developer A 코드 소유권 범위 (Developer A Ownership Boundary)

`AGENTS.md` 규정에 따라 Developer A는 아래의 파일 및 모듈의 수정권만 가지며, 타 개발자의 코드를 직접 수정하지 않고 어댑터 계약을 통해 상호작용합니다.

- **Developer A 소유 파일**:
  - `backend/app/agents/agent_a/npc_dialogue_agent.py` (및 `npc_llm_client.py`)
  - `backend/app/services/service_a/` (Roster, Emotion, TTS 등 세부 서비스)
- **Developer B/C 소유 파일 (수정 불가)**:
  - `scenario_nodes.json` (Developer B 소유)
  - `orchestrator.py`, `validator.py`, 스키마 파일 등 (Developer C 소유)

---

## 2. 신규 사용자 난이도 등급 체계 반영 정책

기존의 `"beginner"`, `"intermediate"`, `"advanced"` 로 표현되던 학습자의 영어 레벨 진단 정보가 **`Bronze`**, **`Silver`**, **`Gold`**의 등급 체계로 전면 전환됩니다.

### 🔄 등급 매핑 및 파싱 연동 규칙
- **데이터 추출 보강**: `developer_a_input_service.py`에서 `english_level`을 파싱할 때 `level_hint.get("english_level")` 뿐 아니라 `payload.get("player_profile", {}).get("tier")`도 함께 체크하여 등급 데이터를 안정적으로 확보합니다.
- **언어 복잡도(Language Complexity) 매핑**:
  - `Bronze` ──► `simple` (쉬운 단어 및 단문 중심)
  - `Silver` ──► `guided` (기본 문법 제공)
  - `Gold` ──► `natural` (네이티브 수준의 문장 구조)
- **감정 정책 전환**: Level Design Agent(개발자 B/C) 측에서 13가지 감정 목록(`joy`, `panic`, `sad`, `suspicion`, `disgust`, `fear`, `smirk`, `normal`, `anger`, `surprise`, `pain`, `confusion`, `boredom`)을 입력 페이로드(Payload)로 개발자 A에게 전달합니다. 개발자 A의 LLM은 이 입력받은 감정과 대화 상황을 바탕으로 ElevenLabs TTS 파라미터를 유동적으로 계산하고, 예외적인 폴백(Fallback) 상황에서만 기존 `npc_emotion_service.py` 룰 기반 파라미터 코드를 활용합니다.

---

## 3. LLM 동적 감정 및 TTS 파라미터 결정 설계 (Dynamic Emotion & TTS Parameter Design)

**Level Design Agent가 전달하는 13종 감정 정보와 대화 상황(유저 난이도, 유저 대사 등)을 기반으로, LLM이 ElevenLabs TTS 튜닝 파라미터를 동적으로 결정 및 수정**하여 응답 JSON 스키마로 리턴하도록 아키텍처를 설계합니다.

```
┌──────────────────────────────────────────────────────────────────┐
│ NPC LLM Agent                                                    │
│  - Inputs: Player Tier, Player Text,                             │
│            Level Design Emotion (13 types)                       │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ├─► npc_emotion (전달받은 감정을 상황에 맞게 매핑)
                           ├─► tone (formal_neutral, formal_stern 등 톤 결정)
                           └─► TTS Parameters (stability, style, speed, similarity_boost)
                               ※ LLM이 입력 감정과 상황을 분석해 값을 동적 수정
```

### 🎛️ 스키마(Schema) 확장 명세 (`npc_llm_client.py`)
LLM 출력 제어용 JSON 스키마(`_dialogue_schema`)에 최종 적용될 감정 필드와 4대 오디오 튜닝 필드를 추가하고 필수(`required`) 항목으로 지정합니다.

```json
{
  "npc_emotion": { "type": "string", "enum": ["joy", "panic", "sad", "suspicion", "disgust", "fear", "smirk", "normal", "anger", "surprise", "pain", "confusion", "boredom"] },
  "stability": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
  "style": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
  "speed": { "type": "number", "minimum": 0.5, "maximum": 2.0 },
  "similarity_boost": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
}
```

## 3. LLM 동적 감정 및 단일 에이전트 연동 설계 (Dynamic Emotion & Unified Agent Design)

**Level Design Agent가 전달하는 npc_id와 13종 감정 정보를 기반으로, 단 하나의 Dialogue Agent가 캐릭터의 페르소나(Persona) 스타일을 동적 결합하여 대사(텍스트)와 일레븐랩스(ElevenLabs) 오디오 파라미터를 동시에 일괄 생성**하도록 아키텍처를 단일화합니다.

```
┌─────────────────────────┐
│  Level Design Agent     │ ──► npc_id & 13종 감정 전달
└─────────────────────────┘
             │
             ▼
┌─────────────────────────┐      Get persona_instruction
│  NPC Roster Service     │ ──► (e.g., Arabella: "friendly, warm...")
└─────────────────────────┘
             │
             ▼
┌─────────────────────────┐      [Single LLM Call] Generates:
│  NPCDialogueAgent       │ ──►  1. npc_text & tts_text (대사 작문)
└─────────────────────────┘      2. ElevenLabs Parameters ( stability, style, 
                                                           speed, similarity_boost )
                                 ※ 전달받은 감정과 페르소나를 토대로 동적 파라미터 튜닝
```

### 🎛️ 스키마(Schema) 확장 명세 (`npc_llm_client.py`)
통합 생성을 위해 JSON 스키마(`_dialogue_schema`)에 감정 필드와 4대 오디오 튜닝 필드를 추가하고 필수(`required`) 항목으로 지정합니다.

```json
{
  "npc_emotion": { "type": "string", "enum": ["joy", "panic", "sad", "suspicion", "disgust", "fear", "smirk", "normal", "anger", "surprise", "pain", "confusion", "boredom"] },
  "stability": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
  "style": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
  "speed": { "type": "number", "minimum": 0.5, "maximum": 2.0 },
  "similarity_boost": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
}
```

### 🧠 시스템 프롬프트(Instructions) 보강 및 페르소나 분기 설계
모든 NPC 대사 생성은 단일 에이전트(`NPCDialogueAgent`)를 거치며, 프롬프트 생성 시 `npc_id`에 상응하는 **페르소나 지침(`persona_instruction`)**을 동적으로 주입하여 성격을 구현합니다.
LLM의 시스템 지침인 `_developer_instructions(persona_instruction: str)` 함수에 다음의 설계 규칙을 적용합니다:

- **공통 규칙**:
  > *"1. Map and output the final 'npc_emotion' and dialogue 'tone' by evaluating the input emotion from the Level Design Agent (selected from: joy, panic, sad, suspicion, disgust, fear, smirk, normal, anger, surprise, pain, confusion, boredom), the player's english tier (Bronze/Silver/Gold), and the player's exact input text ('player_text').*
  > *2. Dynamically calculate and adjust ElevenLabs TTS parameters (stability, style, speed, and similarity_boost) based on the situational context, the player's performance, and the designated input emotion. Output them as floating-point numbers in the specified ranges."*

- **동적 페르소나(Persona) 주입 규칙 (Roster 기반)**:
  `npc_roster_service.py`에 캐릭터별 성격 지침 필드(`persona_instruction`)를 아래와 같이 정의하고, 시스템 프롬프트 호출 시 결합합니다:
  - **`flight_seatmate_arabella`**: *"very friendly, warm, patient, socially easygoing, and welcoming passenger."*
  - **`flight_seatmate_novak`**: *"polite, slightly quiet, but friendly and helpful passenger."*
  - **`officer_miller`**: *"concise, official, calm, and dry immigration officer."*
  - **`officer_hale`**: *"stern, direct, and authoritative immigration officer."*
  - **`officer_harris`**: *"professional, meticulous, yet supportive immigration officer."*
  - **`officer_dan`**: *"firm, alert, and strict security officer."*
  - **`desk_clerk_brielle`**: *"helpful, bright, polite, and service-oriented baggage claim desk clerk."*

  > 시스템 지침 주입 문구: *"Adopt the following persona style for the NPC dialogue generation: {persona_instruction}"*

### 📞 오케스트레이션 및 TTS 어댑터 연동 (`voice_output_service.py`, `npc_dialogue_agent.py`)
- `npc_dialogue_agent.py`는 Roster에서 매핑된 `persona_instruction`을 조회하여 `generate` 호출 시 전달합니다. 단 한 번의 LLM 호출을 통해 생성된 대사(`npc_text`, `tts_text`), 감정(`npc_emotion`), 톤(`tone`) 및 TTS 4대 파라미터가 포함된 단일 결과를 오케스트레이터로 반환합니다.
- `voice_output_service.py` 내부의 `_build_provider_request` 함수는 전달된 `dialogue` 사전에서 LLM이 동적 산출한 `stability`, `style`, `speed`, `similarity_boost` 값을 꺼내와 ElevenLabs API 호출용 값으로 사용합니다.

---

## 4. 소스 코드 반영 가이드라인 (Developer A Implementation Details)

### 1) `developer_a_input_service.py`
- `english_level` 파싱 시 `tier` 필드 및 Level Design Agent가 제공한 `npc_emotion`(13가지 감정 목록 중 하나)과 payload 내 `npc` 사전의 `npc_id`도 함께 파악하여 LLM 입력 데이터로 포매팅 보강.

### 2) `player_language_profile_service.py`
- `_complexity_for_level`에서 `Bronze`, `Silver`, `Gold` 값을 인식하여 `LanguageComplexity`에 올바르게 매핑.

### 3) `npc_emotion_service.py`
- `infer_npc_emotion_state`를 LLM 호출 실패 시 폴백 대사 생성용 룰 베이스 추론기로 유지하며, `english_level` 비교 시 대소문자를 소문자 정규화하여 `bronze` 인지 확인하여 초보자 룰 적용.

### 4) `npc_dialogue_agent.py`
- `result` 딕셔너리 빌드 시 `npc_emotion` 및 4대 파라미터 기본값을 주입하고, Roster에서 `persona_instruction`을 조회해 LLM 클라이언트에 넘겨주도록 코드를 구성합니다. `_generate_with_llm_or_fallback`에서 LLM 리턴 구조체로부터 이 결과들을 파싱하여 단일 결과로 결합합니다.

### 5) `npc_llm_client.py`
- `_developer_instructions(persona_instruction: str)`가 `persona_instruction` 인자를 받아 페르소나 지침 문자열을 동적으로 조립하도록 로직 보강. `_dialogue_schema`에 13종 감정 enum과 4대 오디오 파라미터를 추가하여 통합 출력 형식을 정의합니다.

### 6) `voice_output_service.py`
- `_build_provider_request`에서 하드코딩 튜닝 함수를 바로 호출하던 방식을, `dialogue` 사전 내의 키가 있으면 우선적으로 적용하는 동적 방식으로 교체.

---

## 5. 추후 LangChain 및 LangGraph 전환 계획 (Future LangChain & LangGraph Migration Plan)

현재 수동 HTTP 통신(`httpx.post`) 기반의 구조를 추후 패키지 스펙 규정에 맞추어 LangChain과 LangGraph 프레임워크 기반의 유연한 에이전트 구조로 마이그레이션하기 위한 설계 로직입니다.

### 📌 의존성 버전 제약 (Dependency Contract)
- `langchain==1.3.2`
- `langgraph==1.2.2`
※ 해당 버전 외 다른 버전으로의 업그레이드/다운그레이드는 금지됩니다.

### ⛓️ LangChain 적용 방안 (API 래핑 및 체인화)
1. **ChatOpenAI 래퍼 도입:**
   - 직접적인 API URL 호출을 생략하고 `langchain_openai.ChatOpenAI` 객체를 통해 API 호출을 관리합니다.
2. **구조화된 출력 강제 (Structured Output):**
   - `.with_structured_output` API를 활용하여 `_dialogue_schema` 형태의 Pydantic 또는 JSON 스키마 규격을 넘겨주어 형식이 맞지 않는 출력이 발생하는 문제를 원천 차단합니다.
3. **프롬프트 템플릿(Prompt Template):**
   - `ChatPromptTemplate.from_messages`를 활용해 공통 규칙 지침과 `persona_instruction` 매개변수를 주입하는 프롬프트 조립 과정을 정형화합니다.
4. **체인 결합 (LCEL Chain):**
   - `prompt | model` 형태로 컴파일하여 가독성을 높이고, 에러 복구 및 재시도 로직을 LangChain 기본 제공 기능으로 대체합니다.

### 🕸️ LangGraph 도입 방안 (에이전트 상태 기계 설계)
1. **상태(State) 객체 모델링:**
   - `TypedDict`를 활용해 단일 에이전트 연동 상태(State)인 `AgentState`를 정의합니다.
   ```python
   class AgentState(TypedDict):
       player_text: str
       english_level: str
       input_emotion: str
       persona_instruction: str
       dialogue_result: dict  # npc_text, tts_text, stability 등 저장
       audio_result: dict     # WAV URL, duration 등 저장
       errors: list[str]
   ```
2. **노드(Node) 및 그래프 구성:**
   - **`resolve_persona` 노드:** Roster를 연동하여 `persona_instruction`을 로드해 State에 채웁니다.
   - **`generate_dialogue` 노드:** LangChain 체인을 실행하여 대사와 ElevenLabs 파라미터를 통합 산출해 State를 갱신합니다.
   - **`synthesize_audio` 노드:** 동적 파라미터를 ElevenLabs TTS 서비스로 넘겨 음성을 생성하고 오디오 정보를 바인딩합니다.
   - **`handle_fallback` 노드:** 생성 단계나 음성 합성 단계에서 예외가 감지되면 룰 베이스 fallback 데이터를 조립해 State에 덮어씁니다.
3. **조건부 엣지(Conditional Edge)를 통한 흐름 제어:**
   - `generate_dialogue` 또는 `synthesize_audio` 실패 시 예외 처리 로직에 따라 `handle_fallback` 노드로 자동 전이(Transition)하는 예외 회복 파이프라인을 구축합니다.

### 🛠️ LangChain Tool (도구) 표준화 방안
1. **`BaseTool` 또는 `@tool` 상속 도입:**
   - 현재 구현된 [npc_roster_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/npc_roster_service.py)의 Roster 조회 로직, 폴리싱 서비스([tts_text_polisher_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/tts_text_polisher_service.py)) 등을 LangChain의 표준 `BaseTool` 클래스를 상속받거나 `@tool` 데코레이터를 붙여 표준 도구로 전환합니다.
2. **도구 바인딩 (Tool Binding):**
   - 변환된 표준 도구들을 LangChain LLM 컴포넌트에 직접 바인딩(`model.bind_tools([resolve_profile, polish_text])`)하여, 에이전트가 상황에 따라 능동적으로 필요한 내부 헬퍼 서비스를 자동 호출하는 구조로 마이그레이션합니다.

### 🛡️ LangChain Middleware (미들웨어 Callback) 표준화 방안
1. **`BaseCallbackHandler` 기반 미들웨어 구현:**
   - 기존의 `developer_a_runtime_log_service.py`와 같이 로깅 및 모니터링을 담당하던 수동 래퍼 모듈을 LangChain의 표준 이벤트 리스너인 `BaseCallbackHandler` 상속 구현체로 마이그레이션합니다.
2. **생명주기 이벤트 트레이싱 (Event Tracing):**
   - `on_llm_start`, `on_llm_end`, `on_tool_start`, `on_tool_end` 등의 콜백 이벤트를 가로채어 토큰(Token) 사용량 계측, 에이전트 실행 시간(Latency) 로깅 및 디버그 기록 생성을 단일 통로로 자동 일원화합니다.

### 📂 소스 코드 파일 변경 방향
- `npc_llm_client.py` ──► LangChain의 `ChatOpenAI` 및 `ChatPromptTemplate` 기반 구현체로 교체.
- `npc_dialogue_agent.py` ──► Developer C가 총괄 소유하여 리팩토링 중인 메인 오케스트레이터 그래프(`developer_c_graph.py`)에 플러그인 형태로 결합 가능한 **단일 NPC Dialogue 노드(Single NPC Dialogue Node, 또는 서브 그래프)**로 리팩토링 및 래핑.
- `developer_a_runtime_log_service.py` ──► `BaseCallbackHandler` 상속 구현체로 마이그레이션하여 체인 호출 시 등록하여 실행.
