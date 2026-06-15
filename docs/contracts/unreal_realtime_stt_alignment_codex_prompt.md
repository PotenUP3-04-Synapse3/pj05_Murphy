# Unreal Realtime STT Alignment Codex Prompt

Use this prompt for the Unreal developer who owns AI communication. It explains
how Unreal should align with the current Developer C realtime STT WebSocket and
the existing final AI turn endpoint.

````text
당신은 Murphy's Trippin 프로젝트에서 Unreal Engine 클라이언트의 AI 통신을 담당하는 개발자입니다.
현재 AI 백엔드는 Developer C가 담당하며, 실시간 STT 자막 경로가 WebSocket 방식으로 추가되었습니다.

목표:
- Unreal 마이크 녹음 chunk를 Developer C realtime STT WebSocket으로 보내서 실시간 자막을 띄운다.
- partial transcript는 UI 자막 표시용으로만 사용한다.
- final transcript가 확정되면 기존 AI 턴 엔드포인트 `POST /api/game/ai/respond`로 전체 턴 JSON과 함께 보낸다.
- 현재 AI 백엔드 구현과 맞지 않는 직접 호출, 중복 호출, 잘못된 JSON 소비 흐름을 만들지 않는다.

반드시 먼저 확인할 파일:
- `docs/contracts/developer_c_schema_contract.md`
- `backend/app/schemas/game_turn.py`
- `backend/app/api/ai_respond.py`
- `scripts/smoke_elevenlabs_realtime_stt_relay.py`

현재 AI 백엔드의 핵심 구조:
1. Realtime STT WebSocket:
   - URL: `WebSocket /api/game/ai/stt/stream`
   - Contract: `dev_c_realtime_stt.v1`
   - 역할: 마이크 음성을 실시간 transcript/subtitle 이벤트로 바꾼다.
   - 이 WebSocket은 Understanding Agent, Developer B, Developer A, TTS를 직접 실행하지 않는다.

2. Final AI turn endpoint:
   - URL: `POST /api/game/ai/respond`
   - Contract: `dev_c_unreal_turn.v1` inside a `PrePrototypeRequest`
   - 역할: 최종 플레이어 발화 1개를 가지고 STT, OpenKB, Understanding, Developer B, Developer A,
     response builder, validator 전체 턴을 실행한다.
   - 현재 최종 transcript는 이 엔드포인트의 JSON fallback 형태인 `audio.transcript`로 넣을 수 있다.

현재 권장 통신 흐름:
1. Unreal은 NPC 질문이 시작되거나 플레이어가 상호작용을 시작할 때, 현재 턴의 전체 `turn` JSON을
   메모리에 준비해 둔다. 이 JSON은 아직 WebSocket audio chunk마다 보내지 않는다.
2. 플레이어가 말하기 시작하면 Unreal은 `ws://<backend>/api/game/ai/stt/stream`을 연다.
3. 첫 번째 WebSocket 메시지는 반드시 `session_start`다.
4. Unreal은 마이크에서 얻은 16 kHz mono PCM chunk를 base64로 인코딩해서 `audio_chunk` 이벤트로 보낸다.
5. AI 백엔드는 서버에 보관된 `ELEVENLABS_API_KEY`로 ElevenLabs realtime STT WSS에 연결한다.
   Unreal은 ElevenLabs API key를 절대 받거나 보내지 않는다.
6. AI 백엔드는 ElevenLabs의 partial/final transcript를 `dev_c_realtime_stt.v1` 서버 이벤트로 다시 보낸다.
7. Unreal은 `partial_transcript` 이벤트를 자막 UI에 replace 방식으로 표시한다.
8. 마지막 실제 음성 chunk에는 `commit = true`를 넣는다. 별도 무음 sentinel chunk로 commit하지 않는다.
9. AI 백엔드가 `final_transcript`와 `committed = true`를 보내면 Unreal은 해당 텍스트를 최종 발화로 확정한다.
10. Unreal은 준비해 둔 전체 `turn` JSON과 final transcript를 합쳐 `POST /api/game/ai/respond`를 호출한다.

WebSocket client event 예시:
```json
{
  "contract_version": "dev_c_realtime_stt.v1",
  "event_type": "session_start",
  "request_id": "req_turn_0001",
  "session_id": "session_001",
  "turn_index": 3,
  "sequence": 0,
  "chapter_id": "CH0_03_IMMIGRATION_CHECK",
  "scene_id": "JFK_IMMIGRATION_HALL",
  "current_node_id": "IMM_003_DURATION",
  "provider": "elevenlabs_relay",
  "language_hint": "en"
}
```

```json
{
  "contract_version": "dev_c_realtime_stt.v1",
  "event_type": "audio_chunk",
  "request_id": "req_turn_0001",
  "session_id": "session_001",
  "turn_index": 3,
  "sequence": 1,
  "provider": "elevenlabs_relay",
  "audio_base64": "<base64 pcm16 chunk>",
  "commit": false,
  "sample_rate_hz": 16000
}
```

마지막 실제 음성 chunk 예시:
```json
{
  "contract_version": "dev_c_realtime_stt.v1",
  "event_type": "audio_chunk",
  "request_id": "req_turn_0001",
  "session_id": "session_001",
  "turn_index": 3,
  "sequence": 14,
  "provider": "elevenlabs_relay",
  "audio_base64": "<base64 final pcm16 chunk>",
  "commit": true,
  "sample_rate_hz": 16000
}
```

WebSocket server event 처리:
```json
{
  "contract_version": "dev_c_realtime_stt.v1",
  "event_type": "partial_transcript",
  "request_id": "req_turn_0001",
  "session_id": "session_001",
  "turn_index": 3,
  "sequence": 4,
  "provider": "elevenlabs_relay",
  "subtitle": {
    "text": "I will stay",
    "is_final": false,
    "display_mode": "replace"
  },
  "committed": false
}
```

```json
{
  "contract_version": "dev_c_realtime_stt.v1",
  "event_type": "final_transcript",
  "request_id": "req_turn_0001",
  "session_id": "session_001",
  "turn_index": 3,
  "sequence": 14,
  "provider": "elevenlabs_relay",
  "subtitle": {
    "text": "I will stay for five days.",
    "is_final": true,
    "display_mode": "replace"
  },
  "committed": true,
  "target_endpoint": "POST /api/game/ai/respond"
}
```

final transcript 이후 `/respond` JSON 예시:
```json
{
  "turn": {
    "contract_version": "dev_c_unreal_turn.v1",
    "request_id": "req_turn_0001",
    "session": {
      "session_id": "session_001",
      "player_id": "player_001",
      "chapter_id": "CH0_03_IMMIGRATION_CHECK",
      "scene_id": "JFK_IMMIGRATION_HALL",
      "current_node_id": "IMM_003_DURATION",
      "turn_index": 3
    },
    "npc": {
      "npc_id": "hale",
      "npc_role": "immigration_officer",
      "last_npc_message": "How long will you stay?"
    },
    "audio": {
      "mime_type": "audio/wav",
      "sample_rate_hz": 16000,
      "channels": 1,
      "duration_ms": 3200,
      "language_hint": "en"
    },
    "interaction": {
      "contract_version": "dev_c_interaction_context.v1",
      "initiator": "npc",
      "interaction_type": "quest",
      "quest_id": "immigration_check",
      "interaction_id": "imm_duration_turn",
      "time_limit_s": 30,
      "first_contact": false
    },
    "player_profile": {
      "nickname": "Player",
      "english_confidence": "beginner",
      "tier": "Bronze",
      "travel_speaking_level": "TSL_1_SURVIVAL"
    },
    "scenario_state": {
      "patience": 100,
      "suspicion": 0,
      "retry_count": 0,
      "hint_count": 0,
      "previous_fail_count": 0,
      "completed_intents": []
    },
    "game_state": {
      "inventory": [],
      "flags": [],
      "completed_intents": [],
      "current_objective": "Answer the officer's question."
    },
    "previous_node_results": [],
    "client_allowed_next_nodes": ["IMM_004_DECLARATION"]
  },
  "audio": {
    "transcript": "I will stay for five days."
  }
}
```

중요한 경계:
- `partial_transcript`는 자막 UI 전용이다. partial마다 `/respond`를 호출하지 않는다.
- WebSocket으로 보내는 `audio_chunk`에는 전체 Unreal turn JSON을 넣지 않는다.
- 전체 Unreal turn JSON은 final transcript가 확정된 뒤 `/respond`에서 소비된다.
- 현재 WebSocket final event는 orchestrator를 직접 호출하지 않고,
  `target_endpoint = "POST /api/game/ai/respond"`로 다음 호출 위치를 알려준다.
- sequence는 WebSocket 연결 안에서 단조 증가해야 한다.
- 첫 이벤트는 항상 `session_start`여야 한다.
- `audio_chunk`는 `provider = "elevenlabs_relay"`여야 한다.
- provider 오류 또는 계약 오류가 오면 Unreal은 자막 UI에 실패 상태를 표시하고,
  필요하면 기존 배치 WAV `/respond` fallback 플로우를 사용한다.

구현 산출물:
1. Unreal AI 통신 코드에서 realtime STT WebSocket 클라이언트 구현.
2. 마이크 PCM 16 kHz mono chunk 캡처 및 base64 `audio_chunk` 전송.
3. partial transcript 자막 UI replace 표시.
4. final transcript 수신 시 기존 `dev_c_unreal_turn.v1` JSON과 합쳐 `/respond` 호출.
5. `request_id`, `session_id`, `turn_index`, `chapter_id`, `scene_id`, `current_node_id`를
   WebSocket과 `/respond` 사이에서 일관되게 유지.
6. ElevenLabs API key를 Unreal에 넣지 않는지 확인.
7. `contract_error`, `provider_error`, `session_cancelled` 처리.
8. 로컬 테스트 방법을 문서화:
   - FastAPI backend 실행
   - `scripts/smoke_elevenlabs_realtime_stt_relay.py`로 WebSocket 이벤트 확인
   - Unreal 마이크 입력으로 같은 이벤트 구조 재현

코드를 수정하기 전에 현재 백엔드 파일을 읽고, 위 계약과 맞지 않는 부분이 있으면
Unreal 코드 쪽에서 맞출 수 있는지 먼저 판단해 주세요. 백엔드 계약 변경이 필요하면
Developer C에게 change request로 요청해야 합니다.
````

## Notes for Developer C

- Current implementation uses backend relay mode:
  `Unreal -> Developer C WebSocket -> ElevenLabs WSS -> Developer C -> Unreal`.
- The provider-neutral transcript bridge is still supported through
  `partial_transcript` and `final_transcript` client events, but the preferred
  solo test path is `provider = "elevenlabs_relay"` with `audio_chunk` events.
- Direct final-transcript-to-orchestrator commit is intentionally not active.
  The committed transcript enters the existing `/respond` path.
