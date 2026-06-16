# Agent A (NPC Dialogue Agent) 구조도

> 개발자 A 소유의 `npc_dialogue_agent` 패키지 전체 구조를 한 눈에 볼 수 있도록 정리한 문서입니다.
> Middleware / Tool / Service / Integrations / LLM Client / LangGraph 노드 흐름을 모두 포함합니다.

---

## 1. 전체 아키텍처 (Mermaid)

```mermaid
flowchart LR
    %% ===== Entry Point =====
    subgraph ENTRY["🟦 진입점 (Integrations)"]
        DEVA_CLIENT["dev_a_npc_dialogue_client.py<br/>DevANpcDialogueClient<br/>• generate_dialogue()<br/>• _build_level_design_payload()<br/>• _llm_candidate_text()<br/>• _candidate_text()<br/>• _next_node_question()"]
    end

    %% ===== Service Orchestration =====
    subgraph SVC["🟩 service_a (오케스트레이션 & 후속 처리)"]
        VOICE_OUTPUT["voice_output_service.py<br/>build_voice_output_from_level_design()<br/>_build_tts_audio()<br/>_record_agent_run()<br/>_record_failed_agent_run()<br/>_dialogue_source_trace()"]
        INPUT_SVC["developer_a_input_service.py<br/>normalize_level_design_payload()"]
        FALLBACK_SVC["developer_a_fallback_service.py<br/>build_text_fallback()<br/>build_audio_fallback()"]
        POLICY_SVC["dialogue_policy_service.py<br/>build_dialogue_policy()"]
        EMOTION_SVC["npc_emotion_service.py<br/>infer_npc_emotion_state()"]
        ROSTER_SVC["npc_roster_service.py<br/>resolve_npc_profile()"]
        LANG_PROFILE["player_language_profile_service.py<br/>build_player_language_profile()"]
        POLISHER["tts_text_polisher_service.py<br/>polish_tts_text()<br/>build_tts_style_metadata()<br/>validate_and_clamp_ssml()"]
        NON_VERBAL["non_verbal_palette.py<br/>get_non_verbal_palette()"]
        PROFANITY_LEX["profanity_lexicon.py<br/>allowed_for()<br/>contains_blocked()"]
        PROFANITY_POL["profanity_response_policy.py<br/>get_profanity_fallback_response()<br/>get_incivility_tts_bias()"]
        VOICE_PROFILE["voice_profile_service.py<br/>resolve_voice_profile(tts_provider)"]
        TTS_SVC["tts_service.py<br/>build_edge_provider_request()<br/>build_elevenlabs_provider_request()<br/>synthesize_speech()"]
        TTS_PROVIDER["tts_provider_service.py<br/>EdgeTTSProvider<br/>ElevenLabsTTSProvider<br/>FakeTTSProvider"]
        AUDIO_QUALITY["audio_quality_service.py<br/>analyze_wav_quality()<br/>build_postprocess_policy()"]
        AUDIO_STORAGE["audio_storage_service.py<br/>build_audio_cache_key()<br/>audio_output_path()"]
        RUN_STORE["npc_dialogue_agent_run_store.py<br/>NPCDialogueAgentRunStore<br/>• append_unified_agent_run()"]
    end

    %% ===== Agent Core (LangGraph) =====
    subgraph AGENT["🟥 agent_a/npc_dialogue_agent.py (LangGraph 코어)"]
        direction TB
        GRAPH_BUILDER["build_npc_dialogue_graph()<br/>generate_npc_dialogue_from_level_design()"]
        subgraph NODES["LangGraph Nodes & Routes"]
            START_N(["START"])
            INIT["node_initialize_state<br/>• 페이로드 정규화<br/>• 프로필/감정/정책 빌드<br/>• 룰베이스 결과 생성"]
            ROUTE1{{"route_after_init<br/>use_llm?"}}
            LLM_NODE["node_generate_dialogue_llm<br/>• LCEL 체인 호출<br/>• 톤·ElevenLabs 파라미터 동적 튜닝"]
            ROUTE2{{"route_after_llm<br/>error?"}}
            FALLBACK_NODE["node_apply_fallback<br/>• 룰베이스 결과로 폴백"]
            END_N(["END"])
            START_N --> INIT --> ROUTE1
            ROUTE1 -- "use_llm=True" --> LLM_NODE --> ROUTE2
            ROUTE1 -- "use_llm=False" --> END_N
            ROUTE2 -- "error" --> FALLBACK_NODE --> END_N
            ROUTE2 -- "ok" --> END_N
        end
        HELPERS["헬퍼 함수<br/>_branch_type / _success_text / _retry_text<br/>_success_feedback / _retry_feedback<br/>_compose_level_design_text / _level_design_feedback<br/>_map_level_design_tone / _apply_npc_profile<br/>_with_generation_metadata / _npc_id_from_payload<br/>_is_safe_english_dialogue_text / _dict_value"]
        LEGACY["레거시 결정 함수<br/>generate_npc_dialogue(NPCDialogueInput)"]
    end

    %% ===== LLM Client =====
    subgraph LLM["🟨 agent_a/npc_llm_client.py (LLM 클라이언트)"]
        FACTORY["build_npc_dialogue_llm_client_from_environment()<br/>_build_gemma4_vllm_client()"]
        OPENAI_CLIENT["OpenAINPCDialogueChatModel<br/>_OpenAINPCDialogueChatModel (BaseChatModel)<br/>• /v1/responses + JSON Schema"]
        VLLM_CLIENT["OpenAICompatibleNPCDialogueChatModel<br/>_OpenAICompatibleNPCDialogueChatModel<br/>• vLLM/Ollama Chat Completions"]
        FALLBACK_LLM["FallbackNPCDialogueLLMClient<br/>(primary→fallback decorator)"]
        UNAVAIL["_UnavailableNPCDialogueLLMClient<br/>(에러 시그널 더미)"]
        CB_HANDLER["NPCDialogueCallbackHandler<br/>(LangChain BaseCallbackHandler)<br/>• on_llm_start/end<br/>• on_chain_start/end"]
        SCHEMA["_dialogue_schema()<br/>_developer_instructions()<br/>_extract_structured_json()<br/>_extract_chat_completion_structured_json()<br/>_extract_usage / _read_env_file"]
    end

    %% ===== Middleware =====
    subgraph MW["🟪 middleware_a"]
        MIDDLEWARE["npc_dialogue_agent_run_middleware.py<br/>NPCDialogueAgentRunMiddleware<br/>(extends AgentMiddleware)<br/>• @hook_config before_model<br/>• after_model<br/>• start_run()<br/>• record_event()<br/>• complete_run()<br/>• fail_run()"]
    end

    %% ===== Tools =====
    subgraph TOOL["🟫 tool_a"]
        ARTIFACT_TOOL["npc_dialogue_artifact_tool.py<br/>build_npc_dialogue_artifact()<br/>build_user_visible_run_summary()"]
        COST_TOOL["npc_dialogue_cost_tool.py<br/>estimate_openai_cost_usd()<br/>(GPT_4O_MINI 단가 상수)"]
        EVIDENCE_TOOL["npc_dialogue_evidence_tool.py<br/>build_npc_dialogue_evidence_summary()"]
    end

    %% ===== Connections =====
    DEVA_CLIENT --> VOICE_OUTPUT

    VOICE_OUTPUT --> INPUT_SVC
    VOICE_OUTPUT --> EVIDENCE_TOOL
    VOICE_OUTPUT --> MIDDLEWARE
    VOICE_OUTPUT --> GRAPH_BUILDER
    VOICE_OUTPUT --> ROSTER_SVC
    VOICE_OUTPUT --> VOICE_PROFILE
    VOICE_OUTPUT --> TTS_SVC
    VOICE_OUTPUT --> TTS_PROVIDER
    VOICE_OUTPUT --> AUDIO_QUALITY
    VOICE_OUTPUT --> AUDIO_STORAGE
    VOICE_OUTPUT --> COST_TOOL
    VOICE_OUTPUT --> ARTIFACT_TOOL
    VOICE_OUTPUT --> FALLBACK_SVC
    VOICE_OUTPUT --> RUN_STORE
    VOICE_OUTPUT --> CB_HANDLER

    GRAPH_BUILDER --> NODES
    INIT --> INPUT_SVC
    INIT --> ROSTER_SVC
    INIT --> LANG_PROFILE
    INIT --> EMOTION_SVC
    INIT --> POLICY_SVC
    INIT --> POLISHER
    INIT --> FALLBACK_SVC
    INIT --> HELPERS

    LLM_NODE --> FACTORY
    LLM_NODE --> HELPERS

    FACTORY --> OPENAI_CLIENT
    FACTORY --> VLLM_CLIENT
    FACTORY --> FALLBACK_LLM
    FACTORY --> UNAVAIL
    OPENAI_CLIENT --> SCHEMA
    VLLM_CLIENT --> SCHEMA
    FALLBACK_LLM --> OPENAI_CLIENT
    FALLBACK_LLM --> VLLM_CLIENT

    CB_HANDLER --> MIDDLEWARE

    %% styling
    classDef entry fill:#1f6feb,color:#fff,stroke:#0b3a82
    classDef svc   fill:#2da44e,color:#fff,stroke:#10532a
    classDef agent fill:#cf222e,color:#fff,stroke:#82071e
    classDef llm   fill:#bf8700,color:#fff,stroke:#5c4000
    classDef mw    fill:#8250df,color:#fff,stroke:#3d1d80
    classDef tool  fill:#9a6700,color:#fff,stroke:#3d2900

    class DEVA_CLIENT entry
    class VOICE_OUTPUT,INPUT_SVC,FALLBACK_SVC,POLICY_SVC,EMOTION_SVC,ROSTER_SVC,LANG_PROFILE,POLISHER,VOICE_PROFILE,TTS_SVC,TTS_PROVIDER,AUDIO_QUALITY,AUDIO_STORAGE,RUN_STORE svc
    class GRAPH_BUILDER,INIT,LLM_NODE,FALLBACK_NODE,HELPERS,LEGACY agent
    class FACTORY,OPENAI_CLIENT,VLLM_CLIENT,FALLBACK_LLM,UNAVAIL,CB_HANDLER,SCHEMA llm
    class MIDDLEWARE mw
    class ARTIFACT_TOOL,COST_TOOL,EVIDENCE_TOOL tool
```

---

## 2. 실행 순서 (Sequence)

```mermaid
sequenceDiagram
    autonumber
    participant Caller as DevANpcDialogueClient
    participant VO as voice_output_service<br/>(build_voice_output_from_level_design)
    participant MW as NPCDialogueAgentRunMiddleware
    participant Evi as evidence_tool
    participant Graph as build_npc_dialogue_graph()
    participant Init as node_initialize_state
    participant LLMN as node_generate_dialogue_llm
    participant LLMC as LLM Client<br/>(OpenAI / vLLM / Fallback)
    participant CB as NPCDialogueCallbackHandler
    participant TTS as tts_service / tts_provider
    participant Store as NPCDialogueAgentRunStore

    Caller->>VO: generate_dialogue(payload)
    VO->>Evi: build_npc_dialogue_evidence_summary()
    VO->>MW: record_event(agent_start)
    VO->>VO: normalize_level_design_payload()
    VO->>Graph: invoke(initial_state)
    Graph->>Init: 룰베이스 결과 + 정책/감정/프로필
    alt use_llm = True
        Graph->>LLMN: route_after_init
        LLMN->>LLMC: build_npc_dialogue_llm_client_from_environment()
        LLMN->>CB: callbacks 등록
        LLMC->>CB: on_llm_start / on_chain_start
        LLMC-->>LLMN: 구조화 JSON 응답
        CB->>MW: record_event(langchain_*)
        opt LLM 오류
            LLMN->>Graph: error 시 apply_fallback
        end
    end
    Graph-->>VO: 최종 dialogue dict
    VO->>VO: resolve_voice_profile(tts_provider)
    VO->>TTS: build_*_provider_request + synthesize
    TTS-->>VO: TTSAudio (audio_url/path)
    VO->>MW: start_run / complete_run / fail_run
    VO->>Store: append_unified_agent_run()
    VO-->>Caller: DevADialogueOutput
```

---

## 3. 모듈 매핑 표

| 계층 | 파일 | 주요 클래스 / 함수 |
|---|---|---|
| **Integrations** | `integrations/dev_a_npc_dialogue_client.py` | `DevANpcDialogueClient.generate_dialogue` |
| **Service (오케스트레이션)** | `services/service_a/voice_output_service.py` | `build_voice_output_from_level_design`, `_build_tts_audio`, `_record_agent_run`, `_record_failed_agent_run` |
| **Service (입력/정책)** | `services/service_a/developer_a_input_service.py` | `normalize_level_design_payload` |
| | `services/service_a/dialogue_policy_service.py` | `build_dialogue_policy` |
| | `services/service_a/npc_emotion_service.py` | `infer_npc_emotion_state` |
| | `services/service_a/player_language_profile_service.py` | `build_player_language_profile` |
| | `services/service_a/npc_roster_service.py` | `resolve_npc_profile`, `NPCProfile` |
| | `services/service_a/developer_a_fallback_service.py` | `build_text_fallback`, `build_audio_fallback` |
| | `services/service_a/tts_text_polisher_service.py` | `polish_tts_text`, `build_tts_style_metadata`, `validate_and_clamp_ssml` |
| | `services/service_a/non_verbal_palette.py` | `get_non_verbal_palette` |
| | `services/service_a/profanity_lexicon.py` | `allowed_for`, `contains_blocked` |
| | `services/service_a/profanity_response_policy.py` | `get_profanity_fallback_response`, `get_incivility_tts_bias` |
| **Service (음성)** | `services/service_a/voice_profile_service.py` | `resolve_voice_profile` |
| | `services/service_a/tts_service.py` | `build_edge_provider_request`, `build_elevenlabs_provider_request`, `synthesize_speech` |
| | `services/service_a/tts_provider_service.py` | `EdgeTTSProvider`, `ElevenLabsTTSProvider`, `FakeTTSProvider` |
| | `services/service_a/audio_quality_service.py` | `analyze_wav_quality`, `build_postprocess_policy` |
| | `services/service_a/audio_storage_service.py` | `build_audio_cache_key`, `audio_output_path` |
| | `services/service_a/npc_dialogue_agent_run_store.py` | `NPCDialogueAgentRunStore.append_unified_agent_run` |
| **Agent 코어** | `agents/agent_a/npc_dialogue_agent.py` | `build_npc_dialogue_graph`, `generate_npc_dialogue_from_level_design`, `node_initialize_state`, `node_generate_dialogue_llm`, `node_apply_fallback`, `route_after_init`, `route_after_llm` |
| **LLM Client** | `agents/agent_a/npc_llm_client.py` | `OpenAINPCDialogueChatModel`, `OpenAICompatibleNPCDialogueChatModel`, `FallbackNPCDialogueLLMClient`, `NPCDialogueCallbackHandler`, `build_npc_dialogue_llm_client_from_environment`, `_render_developer_instructions` |
| **Middleware** | `middleware/middleware_a/npc_dialogue_agent_run_middleware.py` | `NPCDialogueAgentRunMiddleware` (`start_run`, `record_event`, `complete_run`, `fail_run`, `before_model`, `after_model`) |
| **Tool** | `tools/tool_a/npc_dialogue_artifact_tool.py` | `build_npc_dialogue_artifact`, `build_user_visible_run_summary` |
| | `tools/tool_a/npc_dialogue_cost_tool.py` | `estimate_openai_cost_usd` |
| | `tools/tool_a/npc_dialogue_evidence_tool.py` | `build_npc_dialogue_evidence_summary` |
