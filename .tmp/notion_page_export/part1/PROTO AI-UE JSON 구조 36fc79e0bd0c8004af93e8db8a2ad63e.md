# PROTO: AI-UE JSON 구조

담당자: Sean Han
상태: Archive
시작일: 05/29/2026
마감일: 06/01/2026
우선순위: 높음
작업 유형: Data
마감기한: 프로토
요약:   • Unreal ↔ AI Backend JSON 통신 명세 (프로토타입)

## 1. 기본 통신 구조

```
POST /api/game/ai/respond
Content-Type: application/json
```

역할은 이렇게 나누면 돼.

| 주체 | 역할 |
| --- | --- |
| Unreal Client | 현재 노드, 플레이어 입력, 게임 상태 전달 |
| AI Backend | 의도 분석, 콩글리쉬 해석, 점수 계산, 분기 결정 |
| Unreal Client | 응답 JSON의 `commands`만 보고 UI/NPC/씬 실행 |

---

# 2. Unreal → AI Backend Request JSON

## 2.1 전체 구조

```json
{
  "request_id": "req_20260529_0001",
  "session": {
    "session_id": "session_001",
    "player_id": "player_001",
    "chapter_id": "CHAPTER_0_IMMIGRATION",
    "scene_id": "JFK_IMMIGRATION_HALL",
    "current_node_id": "IMM_002_PURPOSE"
  },
  "npc": {
    "npc_id": "OFFICER_MILLER",
    "npc_role": "immigration_officer",
    "last_npc_message": "What is the purpose of your visit?"
  },
  "player_input": {
    "input_type": "text",
    "text": "Travel이요. Trouble 아니에요. 진짜 clean human입니다.",
    "language_hint": "ko_en_mixed",
    "stt_confidence": null
  },
  "player_profile": {
    "nickname": "Sean",
    "english_confidence": "beginner",
    "chaos_konglish_mode": true
  },
  "player_state": {
    "confidence": 45,
    "stress": 68,
    "energy": 82,
    "focus": 60
  },
  "game_state": {
    "inventory": [
      "passport",
      "boarding_pass",
      "return_ticket"
    ],
    "flags": [
      "arrived_at_jfk",
      "passport_submitted"
    ],
    "completed_intents": [
      "passport_submit"
    ],
    "risk_score": 0,
    "retry_count": 0,
    "current_objective": "방문 목적을 말하기"
  },
  "allowed_next_nodes": [
    "IMM_003_DURATION",
    "IMM_002_RETRY_PURPOSE",
    "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "END_BAD_HANDCUFF"
  ],
  "client_context": {
    "platform": "windows",
    "input_device": "keyboard",
    "locale": "ko-KR",
    "build_version": "0.1.0"
  }
}
```

---

# 3. Request 필드 설명

## 3.1 `session`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `session_id` | string | O | 플레이 세션 ID |
| `player_id` | string | O | 플레이어 ID |
| `chapter_id` | string | O | 현재 챕터 ID |
| `scene_id` | string | O | 현재 씬 ID |
| `current_node_id` | string | O | 현재 시나리오 노드 ID |

예시:

```json
{
  "session_id": "session_001",
  "player_id": "player_001",
  "chapter_id": "CHAPTER_0_IMMIGRATION",
  "scene_id": "JFK_IMMIGRATION_HALL",
  "current_node_id": "IMM_002_PURPOSE"
}
```

---

## 3.2 `npc`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `npc_id` | string | O | NPC 고유 ID |
| `npc_role` | string | O | NPC 역할 |
| `last_npc_message` | string | O | 직전 NPC 질문 |

예시:

```json
{
  "npc_id": "OFFICER_MILLER",
  "npc_role": "immigration_officer",
  "last_npc_message": "What is the purpose of your visit?"
}
```

---

## 3.3 `player_input`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `input_type` | `"text"` | `"voice"` | O | 입력 타입 |
| `text` | string | O | 플레이어 발화 텍스트 |
| `language_hint` | string | X | 언어 힌트 |
| `stt_confidence` | number | null | X | 음성 인식 신뢰도 |

예시:

```json
{
  "input_type": "text",
  "text": "Travel이요. Trouble 아니에요. 진짜 clean human입니다.",
  "language_hint": "ko_en_mixed",
  "stt_confidence": null
}
```

---

## 3.4 `player_profile`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `nickname` | string | O | 닉네임 |
| `english_confidence` | string | O | 사용자가 선택한 영어 자신감 |
| `chaos_konglish_mode` | boolean | O | 콩글리쉬 모드 여부 |

추천 enum:

```json
{
  "english_confidence": "beginner"
}
```

사용 가능 값:

```
beginner
survival
confident
```

---

## 3.5 `player_state`

예시 상태 값)

```json
{
  "confidence": 45,
  "stress": 68,
  "energy": 82,
  "focus": 60
}
```

| 필드 | 범위 | 설명 |
| --- | --- | --- |
| `confidence` | 0~100 | 자신감 |
| `stress` | 0~100 | 스트레스 |
| `energy` | 0~100 | 에너지 |
| `focus` | 0~100 | 집중도 |

---

## 3.6 `game_state`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `inventory` | string[] | 보유 아이템 |
| `flags` | string[] | 현재까지 발생한 상태 플래그 |
| `completed_intents` | string[] | 이미 성공한 의도 |
| `risk_score` | number | 현재 위험도 점수 |
| `retry_count` | number | 현재 노드 재시도 횟수 |
| `current_objective` | string | 현재 목표 문구 |

예시:

```json
{
  "inventory": [
    "passport",
    "boarding_pass",
    "return_ticket"
  ],
  "flags": [
    "arrived_at_jfk",
    "passport_submitted"
  ],
  "completed_intents": [
    "passport_submit"
  ],
  "risk_score": 0,
  "retry_count": 0,
  "current_objective": "방문 목적을 말하기"
}
```

---

## 3.7 `allowed_next_nodes`

이게 아주 중요해.

AI가 아무 노드로나 이동시키면 안 돼.

언리얼이 허용 가능한 다음 노드 후보를 보내고, AI는 이 안에서만 골라야 해.

```json
[
  "IMM_003_DURATION",
  "IMM_002_RETRY_PURPOSE",
  "IMM_EXTRA_001_CLARIFY_PURPOSE",
  "END_BAD_HANDCUFF"
]
```

---

# 4. AI Backend → Unreal Response JSON

## 4.1 전체 구조

```json
{
  "request_id": "req_20260529_0001",
  "session_id": "session_001",
  "status": "success",
  "analysis": {
    "intent": "visit_purpose_travel",
    "intent_success": true,
    "confidence": 0.94,
    "meaning_summary_kr": "플레이어는 여행 목적으로 미국에 방문했다고 말했습니다.",
    "emotion": "nervous_humor",
    "konglish_detected": true,
    "english_level_signal": "beginner",
    "risk_delta": 0,
    "risk_reason": "위험한 의도 없이 여행 목적을 명확히 전달함",
    "extracted_slots": {
      "visit_purpose": "travel"
    }
  },
  "score_update": {
    "meaning_delivery": 92,
    "grammar": 58,
    "confidence": 70,
    "survival": 96
  },
  "state_update": {
    "player_state_delta": {
      "confidence": 5,
      "stress": -4,
      "energy": 0,
      "focus": 2
    },
    "game_state_delta": {
      "add_flags": [
        "purpose_confirmed"
      ],
      "remove_flags": [],
      "add_completed_intents": [
        "visit_purpose_travel"
      ],
      "risk_score_delta": 0,
      "retry_count_delta": 0
    }
  },
  "npc_response": {
    "speaker": "Officer Miller",
    "text": "Travel. Okay. How long will you stay?",
    "tone": "formal_neutral",
    "animation": "officer_check_passport",
    "facial_expression": "neutral"
  },
  "feedback": {
    "message_kr": "의미 전달 성공! 표현은 혼돈이지만 방문 목적은 명확했습니다.",
    "better_expression": "I'm here for travel.",
    "tip_kr": "입국심사에서는 짧고 명확하게 말하는 것이 좋습니다."
  },
  "branch": {
    "next_node_id": "IMM_003_DURATION",
    "branch_type": "success",
    "reason": "방문 목적이 명확하게 확인됨"
  },
  "commands": [
    {
      "type": "SHOW_SUBTITLE",
      "payload": {
        "speaker": "Officer Miller",
        "text": "Travel. Okay. How long will you stay?",
        "duration": 3.0
      }
    },
    {
      "type": "PLAY_NPC_ANIMATION",
      "payload": {
        "npc_id": "OFFICER_MILLER",
        "animation": "officer_check_passport"
      }
    },
    {
      "type": "SHOW_FEEDBACK",
      "payload": {
        "text": "의미 전달 성공! Better: I'm here for travel.",
        "duration": 4.0
      }
    },
    {
      "type": "UPDATE_OBJECTIVE",
      "payload": {
        "text": "체류 기간을 말하기"
      }
    },
    {
      "type": "LOAD_NODE",
      "payload": {
        "node_id": "IMM_003_DURATION"
      }
    }
  ],
  "debug": {
    "model": "gpt-response-agent",
    "validator_passed": true,
    "selected_from_allowed_nodes": true
  }
}
```

---

# 5. Response 필드 설명

## 5.1 `analysis`

AI가 플레이어 발화를 어떻게 이해했는지 담는 영역이야.

언리얼이 꼭 전부 쓸 필요는 없지만, 디버깅과 결과창에 유용해.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `intent` | string | 인식된 의도 |
| `intent_success` | boolean | 현재 노드 성공 여부 |
| `confidence` | number | AI 판정 신뢰도 |
| `meaning_summary_kr` | string | 한국어 의미 요약 |
| `emotion` | string | 감정 상태 |
| `konglish_detected` | boolean | 콩글리쉬 감지 여부 |
| `english_level_signal` | string | 영어 수준 추정 |
| `risk_delta` | number | 이번 발화로 증가한 위험도 |
| `risk_reason` | string | 위험도 판단 이유 |
| `extracted_slots` | object | 추출된 정보 |

예시:

```json
{
  "intent": "visit_purpose_travel",
  "intent_success": true,
  "confidence": 0.94,
  "meaning_summary_kr": "플레이어는 여행 목적으로 미국에 방문했다고 말했습니다.",
  "emotion": "nervous_humor",
  "konglish_detected": true,
  "english_level_signal": "beginner",
  "risk_delta": 0,
  "risk_reason": "위험한 의도 없이 여행 목적을 명확히 전달함",
  "extracted_slots": {
    "visit_purpose": "travel"
  }
}
```

---

## 5.2 `score_update`

결과창 점수 계산에 사용해.

```json
{
  "meaning_delivery": 92,
  "grammar": 58,
  "confidence": 70,
  "survival": 96
}
```

| 항목 | 설명 |
| --- | --- |
| `meaning_delivery` | 질문에 맞는 의미 전달 여부 |
| `grammar` | 문법적 자연스러움 |
| `confidence` | 답변 명확성 |
| `survival` | 콩글리쉬라도 상황 해결에 성공했는지 |

---

## 5.3 `state_update`

언리얼 쪽 상태값을 얼마나 변경할지 알려주는 영역이야.

```json
{
  "player_state_delta": {
    "confidence": 5,
    "stress": -4,
    "energy": 0,
    "focus": 2
  },
  "game_state_delta": {
    "add_flags": [
      "purpose_confirmed"
    ],
    "remove_flags": [],
    "add_completed_intents": [
      "visit_purpose_travel"
    ],
    "risk_score_delta": 0,
    "retry_count_delta": 0
  }
}
```

주의할 점은 AI가 최종 상태값을 직접 덮어쓰는 것보다, **delta 값만 반환**하는 게 안전해.

예를 들어:

```
현재 stress = 68
AI 응답 stress delta = -4
언리얼 최종 stress = 64
```

---

## 5.4 `npc_response`

NPC 대사, 톤, 애니메이션 정보를 담아.

```json
{
  "speaker": "Officer Miller",
  "text": "Travel. Okay. How long will you stay?",
  "tone": "formal_neutral",
  "animation": "officer_check_passport",
  "facial_expression": "neutral"
}
```

추천 enum:

```
tone:
- formal_neutral
- suspicious
- annoyed
- friendly
- warning

facial_expression:
- neutral
- slight_smile
- suspicious
- serious
- confused
```

---

## 5.5 `branch`

다음 노드 결정 정보야.

```json
{
  "next_node_id": "IMM_003_DURATION",
  "branch_type": "success",
  "reason": "방문 목적이 명확하게 확인됨"
}
```

추천 `branch_type`:

```
success
retry
clarify
warning
bad_ending
happy_ending
```

---

## 5.6 `commands`

언리얼이 실제로 실행할 명령 목록이야.

프로토타입에서는 언리얼이 **이 commands만 믿고 실행**하면 돼.

```json
[
  {
    "type": "SHOW_SUBTITLE",
    "payload": {
      "speaker": "Officer Miller",
      "text": "Travel. Okay. How long will you stay?",
      "duration": 3.0
    }
  },
  {
    "type": "LOAD_NODE",
    "payload": {
      "node_id": "IMM_003_DURATION"
    }
  }
]
```

---

# 6. Command JSON 명세

## 6.1 추천 Command 타입

| Command | 설명 |
| --- | --- |
| `SHOW_SUBTITLE` | NPC 자막 출력 |
| `SHOW_FEEDBACK` | 학습 피드백 출력 |
| `SHOW_HINT` | 힌트 출력 |
| `UPDATE_OBJECTIVE` | 현재 목표 변경 |
| `UPDATE_PLAYER_STATE` | Confidence, Stress 등 UI 변경 |
| `PLAY_NPC_ANIMATION` | NPC 애니메이션 실행 |
| `PLAY_SOUND` | 효과음 재생 |
| `LOAD_NODE` | 다음 시나리오 노드 로드 |
| `TRIGGER_ENDING` | 엔딩 컷신 실행 |
| `SHOW_RESULT_SCREEN` | 결과창 출력 |

---

## 6.2 `SHOW_SUBTITLE`

```json
{
  "type": "SHOW_SUBTITLE",
  "payload": {
    "speaker": "Officer Miller",
    "text": "How long will you stay?",
    "duration": 3.0
  }
}
```

---

## 6.3 `SHOW_FEEDBACK`

```json
{
  "type": "SHOW_FEEDBACK",
  "payload": {
    "text": "의미 전달 성공! Better: I will stay for five days.",
    "duration": 4.0
  }
}
```

---

## 6.4 `SHOW_HINT`

```json
{
  "type": "SHOW_HINT",
  "payload": {
    "hint_kr": "얼마나 머무를 예정인지 말해보세요.",
    "example_en": "I will stay for five days."
  }
}
```

---

## 6.5 `UPDATE_OBJECTIVE`

```json
{
  "type": "UPDATE_OBJECTIVE",
  "payload": {
    "text": "체류 기간을 말하기"
  }
}
```

---

## 6.6 `UPDATE_PLAYER_STATE`

```json
{
  "type": "UPDATE_PLAYER_STATE",
  "payload": {
    "confidence": 50,
    "stress": 64,
    "energy": 82,
    "focus": 62
  }
}
```

단, 이 방식은 최종값을 직접 주는 방식이야.

안전하게 가려면 아래처럼 delta 방식이 더 좋아.

```json
{
  "type": "UPDATE_PLAYER_STATE_DELTA",
  "payload": {
    "confidence": 5,
    "stress": -4,
    "energy": 0,
    "focus": 2
  }
}
```

---

## 6.7 `PLAY_NPC_ANIMATION`

```json
{
  "type": "PLAY_NPC_ANIMATION",
  "payload": {
    "npc_id": "OFFICER_MILLER",
    "animation": "officer_check_passport"
  }
}
```

---

## 6.8 `LOAD_NODE`

```json
{
  "type": "LOAD_NODE",
  "payload": {
    "node_id": "IMM_003_DURATION"
  }
}
```

---

## 6.9 `TRIGGER_ENDING`

```json
{
  "type": "TRIGGER_ENDING",
  "payload": {
    "ending_id": "END_HAPPY_BURGER",
    "cutscene_id": "CUTSCENE_HAPPY_BURGER"
  }
}
```

---

## 6.10 `SHOW_RESULT_SCREEN`

```json
{
  "type": "SHOW_RESULT_SCREEN",
  "payload": {
    "tier": "silver",
    "total_score": 82,
    "scores": {
      "meaning_delivery": 92,
      "grammar": 68,
      "confidence": 74,
      "survival": 95
    },
    "best_expression": "Travel이요. Trouble 아니에요.",
    "recommended_expression": "I'm here for travel.",
    "message": "영어는 흔들렸지만 의미 전달에는 성공했습니다."
  }
}
```

---

# 7. 노드별 Request / Response 예시

## 7.1 방문 목적 성공 예시

### Request

```json
{
  "request_id": "req_001",
  "session": {
    "session_id": "session_001",
    "player_id": "player_001",
    "chapter_id": "CHAPTER_0_IMMIGRATION",
    "scene_id": "JFK_IMMIGRATION_HALL",
    "current_node_id": "IMM_002_PURPOSE"
  },
  "npc": {
    "npc_id": "OFFICER_MILLER",
    "npc_role": "immigration_officer",
    "last_npc_message": "What is the purpose of your visit?"
  },
  "player_input": {
    "input_type": "text",
    "text": "Travel이요. Trouble 아니에요.",
    "language_hint": "ko_en_mixed",
    "stt_confidence": null
  },
  "player_profile": {
    "nickname": "Sean",
    "english_confidence": "beginner",
    "chaos_konglish_mode": true
  },
  "player_state": {
    "confidence": 45,
    "stress": 68,
    "energy": 82,
    "focus": 60
  },
  "game_state": {
    "inventory": [
      "passport",
      "return_ticket"
    ],
    "flags": [
      "arrived_at_jfk",
      "passport_submitted"
    ],
    "completed_intents": [
      "passport_submit"
    ],
    "risk_score": 0,
    "retry_count": 0,
    "current_objective": "방문 목적을 말하기"
  },
  "allowed_next_nodes": [
    "IMM_003_DURATION",
    "IMM_002_RETRY_PURPOSE",
    "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "END_BAD_HANDCUFF"
  ]
}
```

### Response

```json
{
  "request_id": "req_001",
  "session_id": "session_001",
  "status": "success",
  "analysis": {
    "intent": "visit_purpose_travel",
    "intent_success": true,
    "confidence": 0.95,
    "meaning_summary_kr": "플레이어는 여행 목적으로 방문했다고 말했습니다.",
    "emotion": "nervous_humor",
    "konglish_detected": true,
    "english_level_signal": "beginner",
    "risk_delta": 0,
    "risk_reason": "위험 표현 없음",
    "extracted_slots": {
      "visit_purpose": "travel"
    }
  },
  "score_update": {
    "meaning_delivery": 94,
    "grammar": 55,
    "confidence": 72,
    "survival": 96
  },
  "state_update": {
    "player_state_delta": {
      "confidence": 5,
      "stress": -3,
      "energy": 0,
      "focus": 2
    },
    "game_state_delta": {
      "add_flags": [
        "purpose_confirmed"
      ],
      "remove_flags": [],
      "add_completed_intents": [
        "visit_purpose_travel"
      ],
      "risk_score_delta": 0,
      "retry_count_delta": 0
    }
  },
  "npc_response": {
    "speaker": "Officer Miller",
    "text": "Travel. Okay. How long will you stay?",
    "tone": "formal_neutral",
    "animation": "officer_check_passport",
    "facial_expression": "neutral"
  },
  "feedback": {
    "message_kr": "의미 전달 성공! 표현은 혼돈이지만 목적은 명확했습니다.",
    "better_expression": "I'm here for travel.",
    "tip_kr": "입국심사에서는 짧고 명확하게 답변하는 것이 좋습니다."
  },
  "branch": {
    "next_node_id": "IMM_003_DURATION",
    "branch_type": "success",
    "reason": "방문 목적 확인 완료"
  },
  "commands": [
    {
      "type": "SHOW_SUBTITLE",
      "payload": {
        "speaker": "Officer Miller",
        "text": "Travel. Okay. How long will you stay?",
        "duration": 3.0
      }
    },
    {
      "type": "SHOW_FEEDBACK",
      "payload": {
        "text": "의미 전달 성공! Better: I'm here for travel.",
        "duration": 4.0
      }
    },
    {
      "type": "UPDATE_OBJECTIVE",
      "payload": {
        "text": "체류 기간을 말하기"
      }
    },
    {
      "type": "LOAD_NODE",
      "payload": {
        "node_id": "IMM_003_DURATION"
      }
    }
  ]
}
```

---

## 7.2 애매한 답변 예시

플레이어가 방문 목적 질문에 이렇게 답한 경우:

```
America.
```

### Response

```json
{
  "request_id": "req_002",
  "session_id": "session_001",
  "status": "success",
  "analysis": {
    "intent": "unknown_or_incomplete",
    "intent_success": false,
    "confidence": 0.42,
    "meaning_summary_kr": "플레이어가 미국이라고만 답해 방문 목적이 명확하지 않습니다.",
    "emotion": "confused",
    "konglish_detected": false,
    "english_level_signal": "beginner",
    "risk_delta": 1,
    "risk_reason": "핵심 정보가 부족함",
    "extracted_slots": {}
  },
  "score_update": {
    "meaning_delivery": 25,
    "grammar": 40,
    "confidence": 30,
    "survival": 35
  },
  "state_update": {
    "player_state_delta": {
      "confidence": -3,
      "stress": 6,
      "energy": 0,
      "focus": -2
    },
    "game_state_delta": {
      "add_flags": [
        "purpose_unclear"
      ],
      "remove_flags": [],
      "add_completed_intents": [],
      "risk_score_delta": 1,
      "retry_count_delta": 1
    }
  },
  "npc_response": {
    "speaker": "Officer Miller",
    "text": "Are you here for travel, business, or something else?",
    "tone": "formal_neutral",
    "animation": "officer_ask_again",
    "facial_expression": "confused"
  },
  "feedback": {
    "message_kr": "방문 목적이 부족합니다. 여행인지, 출장인지, 친구 방문인지 말해야 합니다.",
    "better_expression": "I'm here for travel.",
    "tip_kr": "장소가 아니라 목적을 말해야 합니다."
  },
  "branch": {
    "next_node_id": "IMM_002_RETRY_PURPOSE",
    "branch_type": "retry",
    "reason": "방문 목적 정보 부족"
  },
  "commands": [
    {
      "type": "SHOW_SUBTITLE",
      "payload": {
        "speaker": "Officer Miller",
        "text": "Are you here for travel, business, or something else?",
        "duration": 3.5
      }
    },
    {
      "type": "SHOW_HINT",
      "payload": {
        "hint_kr": "미국에 온 목적을 말해보세요.",
        "example_en": "I'm here for travel."
      }
    },
    {
      "type": "LOAD_NODE",
      "payload": {
        "node_id": "IMM_002_RETRY_PURPOSE"
      }
    }
  ]
}
```

---

## 7.3 위험 답변 예시

플레이어가 이렇게 말한 경우:

```
I will stay forever. No return ticket.
```

### Response

```json
{
  "request_id": "req_003",
  "session_id": "session_001",
  "status": "success",
  "analysis": {
    "intent": "suspicious_answer",
    "intent_success": false,
    "confidence": 0.91,
    "meaning_summary_kr": "플레이어가 영구 체류 의도와 귀국 항공권 없음에 해당하는 위험 답변을 했습니다.",
    "emotion": "unaware_humor",
    "konglish_detected": false,
    "english_level_signal": "beginner",
    "risk_delta": 6,
    "risk_reason": "forever 표현과 return ticket 없음이 동시에 감지됨",
    "extracted_slots": {
      "stay_duration": "forever",
      "return_ticket": false
    }
  },
  "score_update": {
    "meaning_delivery": 40,
    "grammar": 75,
    "confidence": 65,
    "survival": 10
  },
  "state_update": {
    "player_state_delta": {
      "confidence": -10,
      "stress": 20,
      "energy": -5,
      "focus": -8
    },
    "game_state_delta": {
      "add_flags": [
        "suspicious_answer_detected",
        "return_ticket_missing"
      ],
      "remove_flags": [],
      "add_completed_intents": [],
      "risk_score_delta": 6,
      "retry_count_delta": 1
    }
  },
  "npc_response": {
    "speaker": "Officer Miller",
    "text": "Please step aside for a moment.",
    "tone": "warning",
    "animation": "officer_call_security",
    "facial_expression": "serious"
  },
  "feedback": {
    "message_kr": "위험한 답변입니다. 입국심사에서는 forever, no return ticket 같은 표현을 피해야 합니다.",
    "better_expression": "I will stay for five days, and I have a return ticket.",
    "tip_kr": "체류 기간과 귀국 계획은 명확하게 말해야 합니다."
  },
  "branch": {
    "next_node_id": "END_BAD_HANDCUFF",
    "branch_type": "bad_ending",
    "reason": "위험도 점수가 배드엔딩 기준을 초과함"
  },
  "commands": [
    {
      "type": "SHOW_SUBTITLE",
      "payload": {
        "speaker": "Officer Miller",
        "text": "Please step aside for a moment.",
        "duration": 3.0
      }
    },
    {
      "type": "PLAY_NPC_ANIMATION",
      "payload": {
        "npc_id": "OFFICER_MILLER",
        "animation": "officer_call_security"
      }
    },
    {
      "type": "PLAY_SOUND",
      "payload": {
        "sound_id": "warning_beep"
      }
    },
    {
      "type": "TRIGGER_ENDING",
      "payload": {
        "ending_id": "END_BAD_HANDCUFF",
        "cutscene_id": "CUTSCENE_HANDCUFF_AIRPORT"
      }
    }
  ]
}
```

---

# 8. 추천 Intent 목록

## 8.1 입국심사 MVP Intent

| Intent | 설명 | 대상 노드 |
| --- | --- | --- |
| `passport_submit` | 여권 제출 | `IMM_001_PASSPORT` |
| `visit_purpose_travel` | 여행 목적 | `IMM_002_PURPOSE` |
| `visit_purpose_vacation` | 휴가 목적 | `IMM_002_PURPOSE` |
| `visit_purpose_visit_friend` | 친구 방문 | `IMM_002_PURPOSE` |
| `state_stay_duration` | 체류 기간 답변 | `IMM_003_DURATION` |
| `state_stay_location` | 숙소 위치 답변 | `IMM_004_STAY_LOCATION` |
| `has_return_ticket` | 귀국 항공권 있음 | `IMM_005_RETURN_TICKET` |
| `unknown_or_incomplete` | 애매하거나 부족한 답변 | 공통 |
| `suspicious_answer` | 위험하거나 수상한 답변 | 공통 |
| `off_topic` | 질문과 무관한 답변 | 공통 |

---

# 9. 추천 Slot 목록

| Slot | 설명 | 예시 |
| --- | --- | --- |
| `visit_purpose` | 방문 목적 | `travel`, `vacation`, `visit_friend` |
| `stay_duration` | 체류 기간 | `five days`, `one week` |
| `stay_until` | 체류 종료일 | `next Monday` |
| `stay_location` | 숙소명 또는 주소 | `Sunset Hotel` |
| `stay_location_type` | 숙소 유형 | `hotel`, `friend_house`, `airbnb` |
| `stay_city` | 도시 | `New York`, `LA` |
| `return_ticket` | 귀국 항공권 여부 | `true`, `false` |
| `return_date` | 귀국일 | `next Monday` |
| `danger_keyword` | 위험 키워드 | `forever`, `illegal`, `secret` |

---

# 10. 추천 노드 ID 구조

```
IMM_001_PASSPORT
IMM_002_PURPOSE
IMM_002_RETRY_PURPOSE
IMM_003_DURATION
IMM_003_RETRY_DURATION
IMM_004_STAY_LOCATION
IMM_004_RETRY_STAY_LOCATION
IMM_005_RETURN_TICKET
IMM_005_RETRY_RETURN_TICKET
IMM_EXTRA_001_CLARIFY_PURPOSE
IMM_EXTRA_002_CLARIFY_HOTEL
IMM_EXTRA_003_CLARIFY_RETURN
END_HAPPY_BURGER
END_RETRY
END_BAD_HANDCUFF
```

---

# 11. Validator 규칙

AI 백엔드에서 반드시 검증해야 하는 규칙이야.

## 11.1 필수 검증

| 검증 항목 | 규칙 |
| --- | --- |
| `next_node_id` | 반드시 `allowed_next_nodes` 안에 있어야 함 |
| `commands[].type` | 등록된 command 타입만 허용 |
| `animation` | 언리얼에 존재하는 애니메이션 ID만 허용 |
| `ending_id` | 미리 정의된 엔딩 ID만 허용 |
| `risk_score_delta` | 허용 범위 안에서만 증가 |
| `npc_response.text` | 너무 길지 않게 제한 |
| `feedback.better_expression` | 위험하거나 부적절한 표현 금지 |

---

## 11.2 실패 시 에러 Response

AI 응답 생성 또는 검증 실패 시에는 이렇게 반환하면 좋아.

```json
{
  "request_id": "req_004",
  "session_id": "session_001",
  "status": "error",
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "AI selected a next_node_id that is not allowed.",
    "fallback_node_id": "IMM_002_RETRY_PURPOSE"
  },
  "commands": [
    {
      "type": "SHOW_SUBTITLE",
      "payload": {
        "speaker": "Officer Miller",
        "text": "Could you say that again?",
        "duration": 3.0
      }
    },
    {
      "type": "LOAD_NODE",
      "payload": {
        "node_id": "IMM_002_RETRY_PURPOSE"
      }
    }
  ]
}
```

---

# 12. MVP에서 가장 현실적인 최소 JSON

처음부터 너무 복잡하게 만들기 부담된다면, MVP 1차는 이것만 구현해도 돼.

## Unreal → Backend 최소 Request

```json
{
  "session_id": "session_001",
  "player_id": "player_001",
  "current_node_id": "IMM_002_PURPOSE",
  "scene_id": "JFK_IMMIGRATION_HALL",
  "npc_id": "OFFICER_MILLER",
  "player_text": "Travel이요. Trouble 아니에요.",
  "player_state": {
    "confidence": 45,
    "stress": 68
  },
  "game_state": {
    "risk_score": 0,
    "retry_count": 0,
    "completed_intents": [
      "passport_submit"
    ]
  },
  "allowed_next_nodes": [
    "IMM_003_DURATION",
    "IMM_002_RETRY_PURPOSE",
    "END_BAD_HANDCUFF"
  ]
}
```

## Backend → Unreal 최소 Response

```json
{
  "intent": "visit_purpose_travel",
  "success": true,
  "meaning_summary_kr": "여행 목적으로 방문했다고 말했습니다.",
  "npc_text": "Travel. Okay. How long will you stay?",
  "feedback_kr": "의미 전달 성공! Better: I'm here for travel.",
  "next_node_id": "IMM_003_DURATION",
  "risk_score_delta": 0,
  "commands": [
    {
      "type": "SHOW_SUBTITLE",
      "payload": {
        "speaker": "Officer Miller",
        "text": "Travel. Okay. How long will you stay?"
      }
    },
    {
      "type": "LOAD_NODE",
      "payload": {
        "node_id": "IMM_003_DURATION"
      }
    }
  ]
}
```

---

# 13. 최종 추천

프로토타입에서는 아래 구조로 시작하는 게 제일 좋아.

```
1차 MVP:
단일 엔드포인트
+ current_node_id
+ player_text
+ allowed_next_nodes
+ intent 판정
+ next_node_id
+ commands 반환

2차 확장:
+ score_update
+ state_update
+ risk_score
+ result_screen

3차 확장:
+ 음성 STT confidence
+ 감정 분석
+ 콩글리쉬 분석 로그
+ 오케스트레이터/서브에이전트 분리
```

한마디로 정리하면:

> **언리얼은 “현재 상황과 플레이어 발화”를 보내고, AI 백엔드는 “판정 결과와 실행 가능한 commands”만 돌려준다.**
>