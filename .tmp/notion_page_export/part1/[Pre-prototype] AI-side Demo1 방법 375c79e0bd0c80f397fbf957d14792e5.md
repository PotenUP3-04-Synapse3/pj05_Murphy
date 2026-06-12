# [Pre-prototype] AI-side Demo1 방법

담당자: Sean Han
상태: 완료
시작일: 06/04/2026
마감일: 06/04/2026
우선순위: 낮음
작업 유형: Network
마감기한: 프프로토
요약:   • 데모 시연 구동방법

**1. Pre-Prototype 데모 방법**
가장 안정적인 데모는 **deterministic mode**입니다. 실제 Whisper/Kokoro 모델 다운로드 없이, sample wav를 multipart로 보내고 backend가 STT transcript, B policy, A NPC voice artifact, `npc.audio_url`까지 반환하는 흐름을 보여줍니다.

```powershell
cd C:\\potenup3\\pj05-Murphy
uv sync
$env:MURPHY_STT_MODE="mock"
uv run uvicorn backend.app.main:app --reload
```

다른 PowerShell 창에서 health check:

```powershell
curl.exe <http://127.0.0.1:8000/health>
```

그다음 demo turn JSON을 만들고 요청합니다.

```powershell
New-Item -ItemType Directory -Force demo\\input

@'
{
  "contract_version": "dev_c_unreal_turn.v1",
  "request_id": "req_imm_0001",
  "session": {
    "session_id": "session_001",
    "player_id": "player_001",
    "chapter_id": "CH0_IMMIGRATION",
    "scene_id": "JFK_IMMIGRATION_HALL",
    "current_node_id": "IMM_002_PURPOSE",
    "turn_index": 2
  },
  "npc": {
    "npc_id": "OFFICER_MILLER",
    "npc_role": "immigration_officer",
    "last_npc_message": "What is the purpose of your visit?"
  },
  "audio": {
    "mime_type": "audio/wav",
    "sample_rate_hz": 16000,
    "channels": 1,
    "duration_ms": 2800,
    "language_hint": "en-US"
  },
  "player_profile": {
    "nickname": "Sean",
    "english_confidence": "beginner",
    "tier": "Bronze",
    "travel_speaking_level": "TSL_1_SURVIVAL"
  },
  "scenario_state": {
    "patience": 100,
    "suspicion": 0,
    "retry_count": 0,
    "hint_count": 0,
    "previous_fail_count": 0
  },
  "game_state": {
    "inventory": ["passport", "boarding_pass", "return_ticket"],
    "flags": ["arrived_at_jfk", "passport_submitted"],
    "completed_intents": ["submit_passport"],
    "current_objective": "State the visit purpose"
  },
  "previous_node_results": [
    {
      "node_id": "IMM_001_PASSPORT",
      "verdict": "SUCCESS",
      "next_action": "ADVANCE"
    }
  ],
  "client_allowed_next_nodes": [
    "IMM_003_DURATION",
    "IMM_002_RETRY_PURPOSE",
    "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "END_SECONDARY_INSPECTION"
  ]
}
'@ | Set-Content demo\\input\\imm_002_purpose.json -Encoding utf8
```

```powershell
curl.exe -X POST <http://127.0.0.1:8000/api/game/ai/respond> `
  -F "turn=<demo/input/imm_002_purpose.json;type=application/json" `
  -F "audio=@samples/utterance-20260603-163237.wav;type=audio/wav"
```

성공하면 응답에서 이걸 확인하면 됩니다.

- `stt.player_text`
- `next_node_id = "IMM_003_DURATION"`
- `evaluation.verdict = "SUCCESS"`
- `npc.text`
- `npc.audio_url`

`npc.audio_url`은 예를 들어 `/runtime/audio/kokoro/...wav` 형태이고, 브라우저나 curl로 열면 generated wav artifact가 나와야 합니다.

실제 Whisper 데모는 다음처럼 바꾸면 됩니다. 첫 실행은 모델 다운로드/ffmpeg가 필요할 수 있습니다.

```powershell
uv sync --extra local-stt
$env:MURPHY_STT_MODE="local"
$env:MURPHY_STT_LOCAL_MODEL="turbo"
uv run uvicorn backend.app.main:app --reload
```