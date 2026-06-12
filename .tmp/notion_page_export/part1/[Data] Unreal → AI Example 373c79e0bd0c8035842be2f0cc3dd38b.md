# [Data] Unreal → AI Example

담당자: Sean Han
상태: Archive
시작일: 06/02/2026
마감일: 06/04/2026
우선순위: 높음
작업 유형: Data, Network
마감기한: 프프로토
요약:   • Unreal에서 wav 파일과 함께 보내야 하는 데이터

## 추천 방식: `multipart/form-data`

음성 입력은 JSON만으로 보내기 어렵기 때문에, 프로토타입에서는 이 방식이 제일 현실적이야.

```json
POST /api/game/ai/respond
Content-Type: multipart/form-data
```

보내는 필드:

```html
audio: player_voice.wav
payload: JSON string
```

즉, `audio`에는 wav 바이너리 파일, `payload`에는 현재 게임 상태 JSON을 넣는다.

### Unreal → Backend voice request 예시

```json
{
  "request_id": "req_imm_0001",
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
    "input_type": "voice",
    "text": null,
    "language_hint": "ko_en_mixed",
    "stt_confidence": null
  },
  "audio": {
    "file_field": "audio",
    "mime_type": "audio/wav",
    "sample_rate_hz": 16000,
    "channels": 1,
    "duration_ms": 2800
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
  "client_allowed_next_nodes": [
    "IMM_003_DURATION",
    "IMM_002_RETRY_PURPOSE",
    "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "END_BAD_HANDCUFF"
  ],
  "client_context": {
    "platform": "windows",
    "input_device": "microphone",
    "locale": "ko-KR",
    "build_version": "0.1.0"
  }
}
```