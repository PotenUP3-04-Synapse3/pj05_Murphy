# Murphy AI Architecture

담당자: Sean Han, 용희 김, William Kim
상태: 완료
시작일: 06/04/2026
마감일: 06/04/2026
우선순위: 높음
작업 유형: Architecture
마감기한: 프프로토
요약:   • 전체 아키텍쳐 mermaid

**2. 전체 AI 구조 Mermaid**

```mermaid
flowchart TD
    Unreal["Unreal / Demo Client<br/>turn JSON + player wav"] --> API["Developer C FastAPI<br/>POST /api/game/ai/respond"]

    API --> STT["Developer C STT Service<br/>Whisper large-v3-turbo boundary<br/>mock or local, API fallback"]
    STT --> Norm["Normalized Input<br/>player_text, confidence, language, runtime_used"]

    Norm --> Orch["Developer C Orchestrator"]

    Orch --> OpenKB["Developer C OpenKB Service<br/>reads backend/app/data/scenario_nodes.json"]
    OpenKB --> NodeCtx["Node Context<br/>required intents, slots, hints, allowed_next_nodes"]

    Orch --> UA["Developer C Understanding Agent<br/>intent, slots, relevance, risk"]
    NodeCtx --> UA
    Norm --> UA

    UA --> BInput["C builds dev_b_policy.v1 input"]
    NodeCtx --> BInput
    Norm --> BInput

    BInput --> BAdapter["Developer C B Adapter<br/>DevBPolicyClient"]
    BAdapter --> BAgent["Developer B EnglishLevelHintAgent"]
    BAgent --> BState["ScenarioStateMachine<br/>branch, next_action, state_delta"]
    BAgent --> BLevel["LevelAdaptationController<br/>level, hint, feedback strategy"]
    BState --> BOutput["Developer B Policy Output<br/>evaluation, hint, feedback, branch, error_capture"]
    BLevel --> BOutput

    BOutput --> BValidate["Developer C Validator<br/>branch and B output invariants"]
    BValidate --> Log["Developer C Logging Service<br/>error_capture markdown summary"]

    BValidate --> AInput["C builds dev_a_dialogue.v1 / level-design payload"]
    UA --> AInput
    NodeCtx --> AInput
    Norm --> AInput

    AInput --> AAdapter["Developer C A Adapter<br/>DevANpcDialogueClient"]
    AAdapter --> AAgent["Developer A NPC Dialogue Agent<br/>Officer Miller text, tone, animation"]
    AAgent --> Voice["Developer A Voice Output Service<br/>fake Kokoro artifact now<br/>live TTS later"]
    Voice --> Audio["Generated wav artifact<br/>backend/runtime/generated/audio"]
    Audio --> Static["FastAPI Static Serving<br/>/runtime/audio/..."]

    Voice --> AOutput["Developer A Output<br/>speaker, text, tone, animation, audio_url"]

    AOutput --> Builder["Developer C Response Builder"]
    BOutput --> Builder
    Norm --> Builder
    Log --> Builder

    Builder --> FinalValidate["Developer C Final Validator<br/>Unreal-safe fields, npc.audio_url"]
    FinalValidate --> Response["dev_c_unreal_response.v1<br/>stt, npc, ui, state_delta, evaluation, report, debug"]

    Response --> Unreal
```

핵심은 C가 orchestration/validation/response assembly를 잡고, B는 policy, A는 dialogue/voice만 담당한다는 구조입니다.