# Developer A Agent Specification

## NPC Roster Contract

Developer A는 NPC 표시 이름, 기본 animation, mock voice, Kokoro voice 후보를
`backend/app/services/service_a/npc_roster_service.py`에서 조회한다.

Developer C adapter가 전달하는 payload는 다음 `npc` 필드를 포함할 수 있다.

```json
{
  "npc": {
    "npc_id": "OFFICER_MILLER",
    "npc_role": "immigration_officer",
    "last_npc_message": "What is the purpose of your visit?"
  }
}
```

규칙은 다음과 같다.

- `npc.npc_id`는 내부에서 lowercase로 정규화(normalize)한다. 예: `OFFICER_MILLER` -> `officer_miller`.
- 알 수 없거나 누락된 `npc_id`는 안전 기본값인 `officer_miller` profile로 fallback한다.
- NPC별 speaker 표시 이름, 기본 animation, mock voice id, Kokoro voice 후보는 roster에서 가져온다.
- `kokoro_voices`에는 설치된 Kokoro 모델이 실제 지원하는 voice id만 넣는다.
- 새 NPC를 추가할 때는 각 NPC의 `kokoro_voices` tuple 옆에 그 voice 후보를 선택한 의도를 한국어 주석으로 남긴다.
- Developer A unified AgentRun metadata는 `dialogue_source_trace`를 포함한다.
- `dialogue_source_trace`는 node context, player text preview, Developer B feedback/directive, branch, NPC profile, voice profile 중 어떤 데이터가 다음 NPC 대사와 TTS 선택에 사용됐는지 설명한다.
- Developer C는 adapter를 통해 NPC context를 전달할 수 있지만, 최종 NPC 대사와 voice style 결정은 Developer A 소유다.

## 목적

Developer A는 Murphy's Trippin Chapter 0, Immigration Check 장면에서
NPC 대사와 음성 출력 인터페이스를 담당한다.

Developer A의 핵심 산출물은 Developer C adapter가 호출할 수 있는
대체 가능한 NPC Dialogue Agent 결과다. 이 결과는 최종 Unreal response
JSON의 일부로 조립될 수 있어야 하지만, Developer A는 Unreal response를 직접
조립하지 않는다.

## 소유 범위

Developer A가 소유하는 기능은 다음과 같다.

- NPC Dialogue Agent
- Officer Miller 대사 스타일
- NPC feedback tone
- TTS 요청/응답 인터페이스
- voice output payload 구성
- Developer A prompt
- Developer A 범위 테스트와 명세

현재 Developer A 소유 파일은 다음과 같다.

- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/services/service_a/tts_service.py`
- `backend/app/services/service_a/voice_output_service.py`
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/tests/test_developer_a_npc_dialogue.py`
- `docs/contracts/developer_a_agent_spec.md`

## 비소유 범위

Developer A는 다음을 구현하거나 결정하지 않는다.

- Developer C orchestrator
- Developer C validator
- Developer C Unreal response assembler
- Developer C STT/OpenKB/understanding pipeline
- Developer B scenario state machine
- Developer B branch policy
- Developer B level adaptation
- Developer B hint policy
- 실제 외부 TTS provider 호출을 필수로 요구하는 로직
- 실제 외부 LLM provider 호출을 필수로 요구하는 로직

## 입력 계약

Developer C adapter는 Developer A에게 다음 형태의 payload를 전달한다.

```json
{
  "player_text": "Travel. Trouble no.",
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "npc_question": "What is the purpose of your visit?"
  },
  "understanding": {
    "intent": "visit_purpose_travel",
    "intent_success": true,
    "emotion": "nervous_humor",
    "konglish_detected": true
  },
  "level_hint": {
    "english_level": "beginner",
    "recommended_expression": "I'm here for travel."
  },
  "branch": {
    "branch_type": "success",
    "next_node_id": "IMM_003_DURATION"
  }
}
```

입력 필드의 책임은 다음과 같다.

- `player_text`: 플레이어가 말하거나 입력한 원문이다.
- `node_context`: 현재 immigration scenario node의 NPC 질문과 node id다.
- `understanding`: Developer C가 분석한 intent, 성공 여부, 감정, Konglish 여부다.
- `level_hint`: Developer B가 제공한 영어 레벨과 추천 표현이다.
- `branch`: Developer B/C가 결정한 분기 결과다.

Developer A는 `branch.branch_type`을 참고해 대사 톤을 고르지만, 새 분기를
결정하지 않는다.

## 출력 계약

Developer A는 다음 형태의 NPC dialogue result를 반환한다.

```json
{
  "speaker": "Officer Miller",
  "text": "Travel. Okay. How long will you stay?",
  "tone": "formal_neutral",
  "animation": "officer_check_passport",
  "feedback_kr": "좋아요. 더 자연스럽게는: I'm here for travel."
}
```

출력 필드의 의미는 다음과 같다.

- `speaker`: NPC 이름이다. Chapter 0 기본값은 `Officer Miller`다.
- `text`: NPC가 플레이어에게 말할 영어 대사다.
- `tone`: 음성 및 연기 방향을 위한 톤 값이다.
- `animation`: Unreal에서 선택할 수 있는 animation hint다.
- `feedback_kr`: 플레이어 학습을 위한 한국어 피드백이다.

## 톤 정책

현재 허용하는 tone 값은 다음과 같다.

- `formal_neutral`: 정상 진행 또는 성공 분기에서 사용하는 차분한 심사관 톤
- `formal_firm`: 답변이 불명확해 재시도가 필요할 때 사용하는 단호한 톤
- `formal_stern`: 반복 재시도 후 더 짧고 딱딱하게 압박하는 톤
- `formal_warning`: 진행 차단이나 실패 직전 상황에서 추가 심사 가능성을 암시하는 경고 톤
- `formal_supportive`: 기본 fallback 또는 당황한 플레이어를 질서 있게 돕는 톤

톤은 감정 연출을 위한 값이다. 톤 값이 scenario branch를 변경해서는 안 된다.

## Officer Miller 스타일

Officer Miller는 다음 기준으로 작성한다.

- 대사는 짧고 명확해야 한다.
- 실제 입국 심사관처럼 공식적인 말투를 유지한다.
- 플레이어를 조롱하지 않는다.
- 코미디는 NPC가 과장해서 만드는 것이 아니라, 플레이어의 혼란스러운 답변과
  심사관의 건조한 반응 사이의 대비에서 발생해야 한다.
- 플레이어가 답을 이어갈 수 있도록 다음 질문을 분명히 제시한다.

## Feedback 정책

`feedback_kr`은 한국어로 작성한다.

피드백은 다음 원칙을 따른다.

- 플레이어를 평가하되 모욕하지 않는다.
- 성공 시 짧게 긍정하고 더 자연스러운 표현을 제안한다.
- 재시도 시 불안감을 낮추고 바로 따라 말할 수 있는 표현을 제안한다.
- 추천 표현이 입력에 없으면 짧고 분명하게 다시 말하라는 일반 피드백을 제공한다.

## TTS / Voice Output 정책

현재 TTS는 실제 provider를 호출하지 않는 mock metadata를 반환한다.

이 정책의 이유는 다음과 같다.

- 테스트가 외부 credential 없이 통과해야 한다.
- Developer C backend harness가 로컬에서 재현 가능해야 한다.
- 실제 provider는 이후 adapter 또는 service 교체로 연결할 수 있어야 한다.

TTS 출력은 다음 정보를 포함한다.

- `provider`: 현재는 `mock`
- `audio_url`: mock에서는 `null`
- `voice_id`: NPC voice style 식별자
- `duration_ms`: UI/Unreal timing 확인을 위한 deterministic duration

## 실패 및 fallback 정책

알 수 없는 `branch_type`이 들어오면 Developer A는 예외를 던지지 않고
`neutral` fallback 대사를 반환한다.

fallback 대사는 다음 조건을 만족해야 한다.

- speaker는 `Officer Miller`를 유지한다.
- 대사는 안전하고 일반적인 재답변 요청이어야 한다.
- tone은 `formal_supportive`를 사용한다.
- Developer B/C의 branch 결정을 임의로 변경하지 않는다.

## 테스트 요구사항

Developer A 테스트는 다음을 검증해야 한다.

- success branch에서 Officer Miller가 짧고 공식적인 다음 질문을 반환한다.
- retry branch에서 단호하지만 무례하지 않은 재답변 요청을 반환한다.
- `feedback_kr`이 한국어 피드백과 추천 영어 표현을 포함한다.
- TTS service가 실제 provider 없이 deterministic mock metadata를 반환한다.
- voice output service가 dialogue result와 TTS metadata를 결합한다.

테스트는 실제 API key, 실제 TTS provider, 실제 LLM provider, Unreal Engine
runtime 없이 통과해야 한다.

## 통합 방향

Developer C는 향후 `backend/app/integrations/dev_a_npc_dialogue_client.py`를
통해 Developer A 구현을 호출할 수 있다.

Developer C adapter는 다음을 책임진다.

- Developer C 내부 schema와 Developer A 입력 계약 사이의 변환
- Developer A 결과를 Unreal-safe response builder에 전달
- validator 통과 여부 확인

Developer A는 adapter 내부 구현이나 최종 response JSON 조립을 책임지지 않는다.

## 변경 관리

이 명세의 입력/출력 계약을 변경해야 하는 경우 다음을 수행한다.

1. 변경 이유와 정확한 필드 변경을 문서화한다.
2. 기존 Developer A 테스트를 업데이트한다.
3. Developer C adapter에 영향이 있으면 `docs/contracts/change_requests.md`에
   변경 요청을 남긴다.
4. 필요한 경우 handoff 문서에 변경 요약을 남긴다.
