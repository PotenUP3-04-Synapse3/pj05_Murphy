# Orchestrator 입출력 데이터

담당자: Sean Han
상태: 시작 전
시작일: 06/02/2026
마감일: 06/04/2026
우선순위: 높음
작업 유형: Data, Orchestrator
마감기한: 프로토
요약:   • 필요한 데이터와 출력

## 입력

| 데이터 | 필요 이유 |
| --- | --- |
| `request_id` | 전체 요청 추적 |
| `session` | 현재 플레이 세션, 노드, 씬 확인 |
| `npc` | 직전 NPC 질문과 speaker 정보 확인 |
| `player_input` | text인지 voice인지 구분 |
| `audio` | voice 입력일 경우 STT 실행 |
| `player_profile` | 콩글리쉬 모드, 영어 자신감 반영 |
| `player_state` | stress/confidence 등 상태 UI 업데이트에 활용 |
| `game_state` | risk_score, retry_count, completed_intents 반영 |
| `client_allowed_next_nodes` | Validator에서 노드 이동 안전성 확인 |
| `client_context` | 플랫폼/로케일/빌드 디버깅 |

## 출력

Orchestrator는 이 데이터를 받아서 내부적으로 이렇게 바꿔.

```json
{
  "normalized_input": {
    "input_type": "voice",
    "text": "Travel이요. Trouble 아니에요.",
    "stt_confidence": 0.87,
    "language_detected": "ko_en_mixed",
    "needs_repeat": false
  },
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "npc_question": "What is the purpose of your visit?",
    "success_intents": [
      "visit_purpose_travel",
      "visit_purpose_vacation",
      "visit_purpose_visit_friend"
    ],
    "required_slots": [
      "visit_purpose"
    ],
    "risk_keywords": [
      "illegal",
      "forever",
      "secret",
      "disappear",
      "no return ticket"
    ],
    "allowed_next_nodes": [
      "IMM_003_DURATION",
      "IMM_002_RETRY_PURPOSE",
      "IMM_EXTRA_001_CLARIFY_PURPOSE",
      "END_BAD_HANDCUFF"
    ]
  }
}
```