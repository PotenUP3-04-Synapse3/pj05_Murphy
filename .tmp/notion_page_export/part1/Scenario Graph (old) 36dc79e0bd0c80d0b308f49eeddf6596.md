# Scenario Graph (old)

## 아키텍처

```markdown
[Unreal Client]
    ↓
플레이어 음성/텍스트 입력
    ↓
[Game Backend / AI Orchestrator]
    ↓
STT 결과, 현재 노드, 플레이어 상태, 허용 분기 전달
    ↓
[AI Model]
    ↓
의도 판정 / 영어 레벨 평가 / NPC 반응 / 다음 분기 제안
    ↓
[Backend Validator]
    ↓
허용된 JSON인지 검증
    ↓
[Unreal Client]
    ↓
NPC 대사 출력 / UI 갱신 / 다음 시나리오 노드 이동
```

### 중간에 백엔드를 둬야 하는 이유:

```markdown
API Key 보호
AI 응답 검증
세션 상태 저장
시나리오 데이터 관리
모델 교체 가능성 확보
로그/QA/분석 수집
비정상 응답 fallback 처리
```

| 영역 | 누가 담당? | 설명 |
| --- | --- | --- |
| 메인 스토리 구조 | 시나리오 데이터 | 비행기 → 입국심사 → 수하물 → 호텔 |
| 장소/레벨/오브젝트 | 언리얼 | 공항, NPC, UI, 인터랙션 |
| 플레이어 발화 이해 | AI | 사용자가 뭘 말하려 했는지 판정 |
| 영어 레벨 평가 | AI | 의도 전달, 문법, 어휘, 자신감 등 평가 |
| NPC 대사 생성 | AI | 현재 장면에 맞는 자연스러운 반응 |
| 분기 선택 | AI + 룰 엔진 | 허용된 후보 중 다음 노드 선택 |
| 최종 게임 상태 변경 | 언리얼/백엔드 | 퀘스트 완료, 실패, 아이템 추가 등 |

### 언리얼에 전달하는 데이터 예시)

#### Node info

```json
{
  "node_id": "AIR_SMALLTALK_01",
  "scene_id": "AIRPLANE_SEAT",
  "npc_id": "SOFIA",
  "objective": "옆자리 승객의 질문에 답하고 여행 목적을 말한다.",
  "npc_prompt": "Hi, is this your first time visiting the States?",
  "required_intents": [
    "first_time_answer",
    "travel_purpose",
    "destination"
  ],
  "allowed_next_nodes": [
    "LEVEL_TEST_BEGINNER",
    "LEVEL_TEST_INTERMEDIATE",
    "LEVEL_TEST_ADVANCED"
  ],
  "fallback_node": "AIR_SMALLTALK_HINT_01",
  "tags": [
    "scene.airplane",
    "mode.level_test",
    "skill.speaking"
  ]
}
```

#### AI/Backend → Unreal

```json
{
  "understanding": {
    "detected_intent": "first_time_answer",
    "intent_success": true,
    "meaning_summary": "플레이어는 미국이 처음이고 긴장하고 있다.",
    "konglish_detected": true,
    "emotion": "nervous_humor"
  },
  "assessment": {
    "fluency_score": 0.35,
    "grammar_score": 0.28,
    "intent_score": 0.82,
    "recommended_level": "beginner",
    "reason_code": "short_answer_clear_intent_konglish"
  },
  "npc_response": {
    "speaker": "Sofia",
    "text_en": "That’s totally okay. First trips can feel overwhelming.",
    "text_kr": "괜찮아요. 첫 여행은 원래 좀 정신없을 수 있어요.",
    "tone": "friendly",
    "animation": "smile_gentle"
  },
  "player_feedback": {
    "success": true,
    "message_kr": "의미 전달 성공! 영어는 흔들렸지만 진심은 도착했습니다.",
    "better_expression": "Yes, it's my first time, and I'm a little nervous."
  },
  "branch": {
    "next_node_id": "AIR_SMALLTALK_02",
    "confidence": 0.88
  },
  "ue_commands": [
    {
      "type": "SHOW_SUBTITLE",
      "speaker": "Sofia",
      "text": "That’s totally okay. First trips can feel overwhelming."
    },
    {
      "type": "PLAY_NPC_ANIMATION",
      "npc_id": "SOFIA",
      "animation": "smile_gentle"
    },
    {
      "type": "UPDATE_OBJECTIVE",
      "text": "대화를 이어가며 여행 목적을 말해보세요."
    },
    {
      "type": "SET_PLAYER_LEVEL_CANDIDATE",
      "level": "beginner"
    }
  ]
}
```

## 데이터 규칙 :

```json
allowed_next_nodes에 없는 node_id면 거부
존재하지 않는 animation이면 기본 애니메이션으로 대체
존재하지 않는 scene_id면 fallback
JSON schema 불일치면 재요청 또는 안전 응답
AI가 게임 상태를 직접 조작하지 못하게 제한
```