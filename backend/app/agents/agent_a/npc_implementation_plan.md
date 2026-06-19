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
LLM 출력 제어용 JSON 스키마 (`_dialogue_schema`)에 최종 적용될 감정 필드와 4대 오디오 튜닝 필드를 추가하고 필수 (`required`) 항목으로 지정합니다.

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

**Level Design Agent가 전달하는 npc_id와 13종 감정 정보를 기반으로, 단 하나의 Dialogue Agent가 캐릭터의 페르소나 (Persona) 스타일을 동적 결합하여 대사 (텍스트)와 일레븐랩스 (ElevenLabs) 오디오 파라미터를 동시에 일괄 생성**하도록 아키텍처를 단일화합니다.

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
통합 생성을 위해 JSON 스키마 (`_dialogue_schema`)에 감정 필드와 4대 오디오 튜닝 필드를 추가하고 필수 (`required`) 항목으로 지정합니다.

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
모든 NPC 대사 생성은 단일 에이전트 (`NPCDialogueAgent`)를 거치며, 프롬프트 생성 시 `npc_id`에 상응하는 **페르소나 지침 (`persona_instruction`)**을 동적으로 주입하여 성격을 구현합니다.
LLM의 시스템 지침인 `_developer_instructions(persona_instruction: str)` 함수에 다음의 설계 규칙을 적용합니다:

- **공통 규칙**:
  > *"1. Map and output the final 'npc_emotion' and dialogue 'tone' by evaluating the input emotion from the Level Design Agent (selected from: joy, panic, sad, suspicion, disgust, fear, smirk, normal, anger, surprise, pain, confusion, boredom), the player's english tier (Bronze/Silver/Gold), and the player's exact input text ('player_text').*
  > *2. Dynamically calculate and adjust ElevenLabs TTS parameters (stability, style, speed, and similarity_boost) based on the situational context, the player's performance, and the designated input emotion. Output them as floating-point numbers in the specified ranges."*

- **동적 페르소나(Persona) 주입 규칙 (Roster 기반)**:
  `npc_roster_service.py`에 캐릭터별 성격 지침 필드 (`persona_instruction`)를 아래와 같이 정의하고, 시스템 프롬프트 호출 시 결합합니다:
  - **`flight_seatmate_arabella`**: *"very friendly, warm, patient, socially easygoing, and welcoming passenger."*
  - **`flight_seatmate_novak`**: *"polite, slightly quiet, but friendly and helpful passenger."*
  - **`officer_miller`**: *"concise, official, calm, and dry immigration officer."*
  - **`officer_hale`**: *"stern, direct, and authoritative immigration officer."*
  - **`officer_harris`**: *"professional, meticulous, yet supportive immigration officer."*
  - **`officer_dan`**: *"firm, alert, and strict security officer."*
  - **`desk_clerk_brielle`**: *"helpful, bright, polite, and service-oriented baggage claim desk clerk."*

  > 시스템 지침 주입 문구: *"Adopt the following persona style for the NPC dialogue generation: {persona_instruction}"*

### 📞 오케스트레이션 및 TTS 어댑터 연동 (`voice_output_service.py`, `npc_dialogue_agent.py`)
- `npc_dialogue_agent.py`는 Roster에서 매핑된 `persona_instruction`을 조회하여 `generate` 호출 시 전달합니다. 단 한 번의 LLM 호출을 통해 생성된 대사 (`npc_text`, `tts_text`), 감정 (`npc_emotion`), 톤 (`tone`) 및 TTS 4대 파라미터가 포함된 단일 결과를 오케스트레이터로 반환합니다.
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

## 5. LangChain 및 LangGraph 적용 및 구현 완료 (LangChain & LangGraph Implementation Completed)

이번 스프린트에서는 수동 HTTP 통신(httpx.post) 기반의 구조를 완전히 마이그레이션하여, 패키지 스펙 규정에 맞춘 LangChain(1.3.2) 및 LangGraph(1.2.2) 프레임워크 기반의 유연하고 확장성 있는 에이전트 구조로 전면 리팩터링을 완료했습니다.

### 의존성 버전 제약 준수 (Dependency Contract)
- langchain==1.3.2
- langgraph==1.2.2
- 외부 API 키가 없는 환경에서도 모의(Mock) 방식과 룰 기반 폴백(Fallback) 방식을 지원하여 모든 테스트가 무결하게 패스하도록 설계했습니다.

### LangChain 적용 상세 (API 래핑 및 LCEL 체인화)
1. ChatOpenAI 및 Responses API 모델 래핑:
   - OpenAI Responses API 규격과 Chat Completions 규격을 LangChain의 BaseChatModel을 상속하는 내부 챗 모델(_OpenAINPCDialogueChatModel, _OpenAICompatibleNPCDialogueChatModel)로 각각 구현했습니다.
   - 외부에서는 이를 감싸는 OpenAINPCDialogueChatModel 및 OpenAICompatibleNPCDialogueChatModel 래퍼 클래스를 통해 generate 인터페이스와 LCEL 체인 인터페이스를 단일화했습니다.
2. 구조화된 출력 강제 (Structured Output):
   - JSON 스키마 규격(_dialogue_schema)에 13종 감정 enum과 4대 오디오 파라미터(stability, style, speed, similarity_boost)를 필수로 선언하여, LLM이 이를 누락 없이 정량화해 출력하도록 보장했습니다.
3. 프롬프트 템플릿(Prompt Template) 적용:
   - ChatPromptTemplate을 활용하여 시스템 지침 및 NPC Roster의 페르소나 지침(persona_instruction)의 동적 조립 과정을 템플릿화하였습니다.

### LangGraph 도입 상세 (내부 에이전트 상태 기계 설계)
1. 상태(State) 객체 정의:
   - NPCDialogueState를 정의하여 입력 페이로드, 정규화 정보, NPC 프로필, 플레이어 프로필, 감정 상태, 생성 정책, 그리고 최종 결과를 체계적으로 공유 및 갱신합니다.
2. 노드(Node) 및 그래프 구성:
   - initialize_state 노드: 입력 데이터를 정규화하고, NPC 프로필(Roster) 및 플레이어 프로필을 빌드하여 초기 룰 기반 결과를 세팅합니다.
   - generate_dialogue_llm 노드: LangChain 기반 LLM 체인을 구동하여 실시간 대사와 ElevenLabs TTS 파라미터 4종이 포함된 단일 JSON을 산출합니다.
   - apply_fallback 노드: LLM 호출 오류(네트워크 에러, JSON 파싱 실패 등) 발생 시 안전하게 룰 기반 결과에 디버그 플래그(fallback_used = True)를 달아 복원합니다.
3. 그래프 흐름 제어 (Conditional Edge):
   - route_after_init: LLM 사용 설정(use_llm) 여부에 따라 LLM 노드 진입 혹은 즉시 종료(END)를 결정합니다.
   - route_after_llm: LLM 호출 과정에서 예외가 발생했는지(상태 객체 내 error 존재 유무)를 감지하여 정상 종료 혹은 폴백 노드로 흐름을 분기합니다.

### 검증 상태 (Verification Summary)
- uv run pytest -> 223개 유닛 테스트 케이스 전체 통과 확인.
- uv run ruff check . -> Ruff 린터 지적 사항 0건 확인.
- uv run mypy . -> 101개 소스 파일 대상 정적 분석 타입 오류 0건 통과 확인.
- 이에 따라, 원래 추후 계획으로 기재되어 있던 LangChain 및 LangGraph 마이그레이션이 이번 스프린트 구현 범위 내에서 무결하게 완결되었음을 선언합니다.

---

## 6. NPC 메모리 및 꼬리물기 대화 강화 (Session Memory & Follow-up Reinforcement) - 2026-06-19 추가

NPC가 대화 기록을 인지하지 못해 질문을 중복하거나, 플레이어의 답변을 자연스럽게 받아치지 못하는 문제를 해결하기 위해 **세션 컨텍스트 카드(Session Context Card)**와 **후처리 가드(Post-processing Guard)**를 도입했습니다.

### 🗃️ 세션 컨텍스트 카드 빌더 (`session_context_card_service.py`)
- **confirmed_facts**: 플레이어가 기존 턴에서 답한 슬롯(`visit_purpose`, `stay_duration` 등)의 누적 딕셔너리를 자연어 설명문 리스트로 변환해 관리합니다.
- **forbidden_repeat_questions**: 이미 채워진 슬롯에 해당하는 대표 질문 리스트를 수집하여, NPC가 동일한 내용의 질문을 중복 생성하지 못하도록 프롬프트에 제공하고 가드에서 사용합니다.
- **open_hooks**: 플레이어의 직전 발화에서 명사/단어 후보를 3글자 이상이며 중복되지 않는 영어 단어로 추출하여 후속 꼬리물기 질문의 앵커(Anchor)로 삼습니다.
- **last_npc_intent**: 직전 턴 NPC의 `surface_goal` 또는 발화 첫 문장을 통해 직전 NPC 의도를 기록합니다.
- **recent_turns_compact**: 대화 기록 5턴을 한 줄 문자열 포맷(`T-x player='...' npc='...' filled={...}`)으로 단순화하여 가독성 높게 메모리에 주입합니다.
- **topic_thread**: NPC의 누적 `surface_goal` 및 핵심 명사들을 시간 순으로 나열하여 대화 토픽 흐름을 추적합니다.

### 🛡️ 후처리 안전 가드 및 폴백 (Post-processing Guards)
- **재질문 차단 가드 (`repeats_confirmed_fact`)**: LLM이 생성한 `npc_text`가 `forbidden_repeat_questions` 중 어느 하나와 실질적으로 중복되면, 에러를 발생시키고 안전하게 룰베이스 폴백으로 전환합니다.
- **꼬리물기 훅 가드 (`weak_followup_no_hook`)**: 분기가 성공/중립이고, `open_hooks`가 존재하며, 일반 대화 모드(비-diagnostic)일 때, LLM의 응답 문장이 1개 이하면서 `open_hooks` 내 단어를 단 하나도 포함하지 않는 "약한 꼬리물기"를 감지하여 차단하고 폴백으로 우회합니다.
- **룰베이스 폴백 합성 강화 (`synthesize_fallback_next_question`)**: LLM 실패 등으로 룰베이스 폴백으로 빠지는 분기에서도, `open_hooks`의 첫 번째 단어를 접두사(`"You mentioned {hook} — "`)로 활용하여 자연스럽게 대화의 꼬리를 물도록 변주를 이식했습니다.

