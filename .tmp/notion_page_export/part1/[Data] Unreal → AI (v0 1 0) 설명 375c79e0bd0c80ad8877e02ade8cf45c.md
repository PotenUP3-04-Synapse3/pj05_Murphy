# [Data] Unreal → AI (v0.1.0) 설명

담당자: Sean Han
상태: 완료
시작일: 06/04/2026
마감일: 06/04/2026
우선순위: 높음
작업 유형: Data, Network
마감기한: 프프로토
요약:   • 데이터 명세 Pre-prototype

# Unreal ↔ AI Backend JSON 명세 정리

기준 endpoint: `POST /api/game/ai/respond`

현재 권장 transport: `multipart/form-data`

## 1. Unreal → AI Backend

Unreal은 `turn` JSON과 `audio` wav 파일을 함께 보낸다.

| Part | Type | Required | Example | 필요성 |
| --- | --- | --- | --- | --- |
| `turn` | JSON | Yes | `demo/input/imm_002_purpose.json` | 현재 턴, 노드, 플레이어 상태, NPC 질문 맥락 전달 |
| `audio` | wav file | Yes | `player_answer.wav` | 플레이어 음성 입력. AI backend가 STT 수행 |

## 1.1 `turn` Root Fields

| Field | Required | Example | 필요성 |
| --- | --- | --- | --- |
| `contract_version` | Yes | `dev_c_unreal_turn.v1` | 요청 schema 버전 확인 |
| `request_id` | Yes | `req_imm_0001` | 한 턴 추적용 id. 디버깅/log 연결 키 |
| `session` | Yes | `{...}` | 세션, 챕터, 현재 노드 식별 |
| `npc` | Yes | `{...}` | 직전 NPC 질문/역할 맥락 |
| `audio` | Yes | `{...}` | 업로드 wav의 metadata |
| `player_profile` | Yes | `{...}` | 난이도, 힌트, 피드백 조절 |
| `scenario_state` | Yes | `{...}` | patience/suspicion/retry 등 게임 상태 |
| `game_state` | Yes | `{...}` | inventory, flags, objective 등 Unreal 상태 |
| `previous_node_results` | No | `[]` | 이전 노드 결과, final report/분기 참고 |
| `client_allowed_next_nodes` | No | `["IMM_003_DURATION"]` | Unreal 측에서 허용하는 다음 노드 guard |
| `client_context` | No | `{...}` | platform/build/debug 정보 |

## 1.2 `session`

| Field | Required | Example | 필요성 |
| --- | --- | --- | --- |
| `session_id` | Yes | `session_001` | 플레이 세션 식별 |
| `player_id` | No | `player_001` | 플레이어 식별 |
| `chapter_id` | Yes | `CH0_IMMIGRATION` | 챕터 OpenKB/노드 로딩 |
| `scene_id` | Yes | `JFK_IMMIGRATION_HALL` | 현재 Unreal scene 식별 |
| `current_node_id` | Yes | `IMM_002_PURPOSE` | 현재 대화 노드 |
| `turn_index` | Yes | `2` | 턴 순서, 로그/리포트용 |

## 1.3 `npc`

| Field | Required | Example | 필요성 |
| --- | --- | --- | --- |
| `npc_id` | Yes | `OFFICER_MILLER` | NPC 식별 |
| `npc_role` | Yes | `immigration_officer` | NPC 역할/tone 결정 |
| `last_npc_message` | Yes | `What is the purpose of your visit?` | 플레이어 답변이 어떤 질문에 대한 답인지 판단 |

## 1.4 `audio` Metadata

| Field | Required | Example | 필요성 |
| --- | --- | --- | --- |
| `mime_type` | Yes | `audio/wav` | wav 검증 |
| `sample_rate_hz` | Yes | `16000` | STT/audio 처리 참고 |
| `channels` | Yes | `1` | mono/stereo 정보 |
| `duration_ms` | Yes | `2800` | 너무 짧거나 긴 입력 판단 |
| `language_hint` | No | `en-US` | STT 언어 힌트 |

## 1.5 `player_profile`

| Field | Required | Example | 필요성 |
| --- | --- | --- | --- |
| `nickname` | No | `Sean` | 개인화 가능 |
| `english_confidence` | No | `beginner` | 피드백 강도 참고 |
| `tier` | Yes | `Bronze` | 난이도/힌트 빈도 결정 |
| `travel_speaking_level` | Yes | `TSL_1_SURVIVAL` | 여행 영어 레벨 정책 |

## 1.6 `scenario_state`

| Field | Required | Example | 필요성 |
| --- | --- | --- | --- |
| `patience` | Yes | `100` | NPC/상황 인내도 |
| `suspicion` | Yes | `0` | 입국 심사 위험도 |
| `retry_count` | Yes | `0` | 재질문/힌트/실패 분기 |
| `hint_count` | Yes | `0` | 힌트 남발 방지 |
| `previous_fail_count` | Yes | `0` | 누적 실패 판단 |
| `completed_intents` | No | `["submit_passport"]` | 이미 완료한 intent 추적 |

## 1.7 `game_state`

| Field | Required | Example | 필요성 |
| --- | --- | --- | --- |
| `inventory` | No | `["passport", "return_ticket"]` | 소지품 기반 분기/검증 |
| `flags` | No | `["arrived_at_jfk"]` | Unreal gameplay flag |
| `completed_intents` | No | `["submit_passport"]` | 완료한 행동 |
| `current_objective` | Yes | `State the visit purpose` | 현재 UI 목표 |

## 1.8 Minimal Request Example

```json
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
  ],
  "client_context": {
    "platform": "windows",
    "input_device": "microphone",
    "locale": "ko-KR",
    "build_version": "0.1.0"
  }
}
```