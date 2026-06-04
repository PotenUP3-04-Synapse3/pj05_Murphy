# Developer C Schema Contract

## Purpose

This document defines the Developer C side schemas for the Chapter 0
Immigration Check backend. It is the contract Developer C will use to receive
Unreal audio turns, normalize speech input, build internal workflow payloads,
call Developer A and Developer B adapters, validate results, and return
Unreal-safe JSON.

Developer C owns this contract. Developer A and Developer B outputs are
consumed through adapters and remain replaceable behind their own contracts.

## Core Assumption

For the current prototype, Unreal always sends a wav file for each player turn.
The public Unreal request does not include `input_type`.

Developer C always runs STT first and then sets the downstream normalized input
metadata as:

```json
{
  "input_source": {
    "input_type": "voice"
  }
}
```

The STT runtime policy is local-first:

- Primary runtime: local `whisper-large-v3-turbo`.
- Fallback runtime: OpenAI Transcriptions API.
- Tests and deterministic demo paths must pass without requiring a local model
  download or API key.

Runtime configuration is loaded from process environment variables and `.env`
through `backend/app/services/service_c/settings_service.py`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MURPHY_STT_MODE` | `local` | `local` runs local Whisper first; `mock` uses deterministic demo transcription |
| `MURPHY_STT_LOCAL_MODEL` | `turbo` | `openai-whisper` local model alias for Whisper large-v3-turbo |
| `MURPHY_STT_API_MODEL` | `whisper-1` | OpenAI Transcriptions API fallback model |
| `OPENAI_API_KEY` | unset | Required only when API fallback is needed |
| `MURPHY_UNDERSTANDING_MODE` | `rule` | `rule` is deterministic; `llm` enables OpenAI-assisted semantic analysis |
| `MURPHY_UNDERSTANDING_LLM_MODEL` | `gpt-4o-mini` | Understanding Agent LLM model |
| `MURPHY_UNDERSTANDING_LLM_TIMEOUT_SECONDS` | `10` | Understanding Agent LLM timeout |

This keeps the Unreal request simple while still satisfying the Developer B
`dev_b_policy.v1` input contract.

## Contract Versions

| Contract | Version | Owner | Purpose |
| --- | --- | --- | --- |
| Unreal turn request | `dev_c_unreal_turn.v1` | Developer C | Public request envelope from Unreal to Developer C |
| Internal turn context | `dev_c_internal_turn.v1` | Developer C | Orchestrator state shared between C-owned workflow nodes |
| Developer B policy | `dev_b_policy.v1` | Developer B | Evaluation, hint, feedback, state, and branch policy |
| Developer A dialogue | `dev_a_dialogue.v1` | Developer C adapter / Developer A consumer | NPC dialogue generation adapter contract |
| Unreal response | `dev_c_unreal_response.v1` | Developer C | Final validated JSON returned to Unreal |

## Public Endpoint

Target endpoint:

```text
POST /api/game/ai/respond
```

Expected transport for the wav prototype:

```text
multipart/form-data
```

Required parts:

| Part | Type | Required | Owner | Notes |
| --- | --- | --- | --- | --- |
| `turn` | JSON object or JSON string | yes | Unreal | Turn metadata and game state |
| `audio` | wav file | yes | Unreal | Player voice input |

Developer C should reject the request before orchestration when `audio` is
missing, is not wav-compatible, or required `turn` metadata is missing.

Pre-prototype transport:

```text
application/json
```

During the AI-only pre-prototype, Unreal is not connected yet. Developer C may
accept a JSON test harness payload shaped as:

```json
{
  "turn": {
    "contract_version": "dev_c_unreal_turn.v1"
  },
  "audio": {
    "mock_wav_path": "mock://immigration/purpose_tourism.wav",
    "transcript": "I'm here for tourism."
  }
}
```

The mock payload still represents a wav turn. The `transcript` field is a test
harness shortcut used by the deterministic local Whisper service boundary and
should be removed or ignored when real wav bytes are connected to the local
runtime.

## Unreal Turn Request

Canonical `turn` payload:

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
      "submit_passport"
    ],
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

### Required Root Fields

| Field | Required | Notes |
| --- | --- | --- |
| `contract_version` | yes | Must be `dev_c_unreal_turn.v1` |
| `request_id` | yes | Stable trace id for one turn |
| `session` | yes | Session and current node identity |
| `npc` | yes | Last NPC prompt context |
| `audio` | yes | Audio metadata, separate from uploaded wav bytes |
| `player_profile` | yes | Used by Developer B hint and strictness policy |
| `scenario_state` | yes | Used by Developer B state delta policy |
| `game_state` | yes | Used by Developer C and for B input enrichment |
| `previous_node_results` | no | Used for final decision and reports |
| `client_allowed_next_nodes` | no | Extra client-side branch guard |
| `client_context` | no | Debug and compatibility metadata |

## STT Normalized Input

Developer C converts the uploaded wav into normalized text before calling the
Understanding Agent.

```json
{
  "player_text": "I'm here for tourism.",
  "input_source": {
    "input_type": "voice",
    "stt_confidence": 0.87,
    "language_detected": "en-US",
    "needs_repeat": false
  },
  "stt_model": "whisper-large-v3-turbo",
  "stt_primary_runtime": "local",
  "stt_fallback_runtime": "api",
  "stt_runtime_used": "local"
}
```

Rules:

- `input_source.input_type` is always `voice` for the current prototype.
- The configured STT model name is `whisper-large-v3-turbo`.
- `stt_primary_runtime` is always `local` for the current prototype.
- `stt_fallback_runtime` is always `api`; it is used only when the local
  runtime is unavailable or fails in a non-test environment.
- `stt_runtime_used` records the runtime that produced the transcript for the
  current turn.
- `stt_confidence` may be `null` only when the mock STT cannot estimate it.
- `needs_repeat` must be true when STT confidence or audio quality is too low
  for safe evaluation.
- Tests must pass with deterministic mock STT and no local model download or
  external provider keys.

## OpenKB Node Context

Developer C loads node context from local OpenKB data before calling the
Understanding Agent and Developer B adapter. Developer B owns content authoring
and runtime feedback/error writes under the OpenKB `dev_b` namespace; Developer
C owns retrieval, validation, and final response assembly.

```json
{
  "node_id": "IMM_002_PURPOSE",
  "chapter_id": "CH0_IMMIGRATION",
  "npc_question": "What is the purpose of your visit?",
  "npc_question_goal": "ask_visit_purpose",
  "objective_kr": "방문 목적 말하기",
  "required_intents": [
    "state_visit_purpose"
  ],
  "required_slots": [
    "visit_purpose"
  ],
  "optional_slots": [
    "destination",
    "activity",
    "duration"
  ],
  "critical_slots": [
    "illegal_work_intent",
    "unclear_purpose",
    "suspicious_purpose"
  ],
  "allowed_slot_values": {
    "visit_purpose": [
      "tourism",
      "business",
      "family_visit",
      "friend_visit",
      "study",
      "transit"
    ]
  },
  "risk_keywords": [
    "illegal",
    "forever",
    "secret",
    "disappear",
    "no return ticket"
  ],
  "recommended_expression": "I'm here for tourism.",
  "base_hint_kr": "Tell the purpose of your visit.",
  "hint_policy": {
    "keyword": [
      "tourism",
      "business",
      "vacation"
    ],
    "sentence_pattern": "I'm here for ___.",
    "situation_hint": "Say why you are visiting.",
    "action_hint": "Say the purpose first, then add a short reason if needed."
  },
  "success_next_node": "IMM_003_DURATION",
  "retry_next_node": "IMM_002_RETRY_PURPOSE",
  "clarify_next_node": "IMM_EXTRA_001_CLARIFY_PURPOSE",
  "hint_next_node": "IMM_002_RETRY_PURPOSE",
  "warning_next_node": "END_SECONDARY_INSPECTION",
  "allowed_next_nodes": [
    "IMM_003_DURATION",
    "IMM_002_RETRY_PURPOSE",
    "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "END_SECONDARY_INSPECTION"
  ]
}
```

Rules:

- `node_context.node_id` must equal `session.current_node_id`.
- `required_intents` is the canonical key. Do not use `success_intents` in new
  Developer C schemas.
- `objective_kr` is optional scenario content for Korean UI objective display.
  It is not NPC dialogue and should not replace Developer A dialogue output.
- `allowed_next_nodes` is the branch safety boundary used by Developer C
  validation.

## Understanding Agent Output

Developer C Understanding Agent returns semantic evidence only. It must not
create final branches, scores, hints, or NPC dialogue.

Runtime modes:

- `rule`: deterministic local analyzer used by tests and contract demos.
- `llm`: OpenAI-assisted semantic analyzer. Invalid, unavailable, or forbidden
  LLM output falls back to `rule`.
- The LLM mode is allowed to fill only the fields in `UnderstandingOutput`.
  It must not emit branch, next-node, state-delta, score, hint, NPC dialogue,
  TTS, or Unreal command fields.

```json
{
  "intent": "state_visit_purpose",
  "intent_success": true,
  "confidence": 0.94,
  "meaning_summary_kr": "The player said they are visiting for tourism.",
  "emotion": "nervous_humor",
  "answer_relevance": "on_topic",
  "ambiguity_type": "none",
  "risk_delta": 0,
  "risk_reason": "The purpose is clear and no risk expression was found.",
  "risk_tags": [],
  "extracted_slots": {
    "visit_purpose": "tourism"
  },
  "missing_slots": [],
  "needs_clarification": false
}
```

## Developer B Policy Input Built By Developer C

Developer C maps the Unreal request, STT result, OpenKB context, and
Understanding output into `dev_b_policy.v1`.

```json
{
  "contract_version": "dev_b_policy.v1",
  "request_id": "req_imm_0001",
  "session_id": "session_001",
  "player_id": "player_001",
  "chapter_id": "CH0_IMMIGRATION",
  "scene_id": "JFK_IMMIGRATION_HALL",
  "current_node_id": "IMM_002_PURPOSE",
  "turn_index": 2,
  "player_text": "I'm here for tourism.",
  "input_source": {
    "input_type": "voice",
    "stt_confidence": 0.87,
    "language_detected": "en-US",
    "needs_repeat": false
  },
  "player_profile": {
    "nickname": "Sean",
    "english_confidence": "beginner",
    "tier": "Bronze",
    "travel_speaking_level": "TSL_1_SURVIVAL"
  },
  "scenario_state": {
    "retry_count": 0,
    "hint_count": 0,
    "patience": 100,
    "suspicion": 0,
    "previous_fail_count": 0,
    "completed_intents": [
      "submit_passport"
    ]
  },
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "npc_question": "What is the purpose of your visit?",
    "required_intents": [
      "state_visit_purpose"
    ],
    "required_slots": [
      "visit_purpose"
    ],
    "recommended_expression": "I'm here for tourism.",
    "hint_policy": {
      "sentence_pattern": "I'm here for ___."
    },
    "success_next_node": "IMM_003_DURATION",
    "retry_next_node": "IMM_002_RETRY_PURPOSE",
    "clarify_next_node": "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "hint_next_node": "IMM_002_RETRY_PURPOSE",
    "warning_next_node": "END_SECONDARY_INSPECTION",
    "allowed_next_nodes": [
      "IMM_003_DURATION",
      "IMM_002_RETRY_PURPOSE",
      "IMM_EXTRA_001_CLARIFY_PURPOSE",
      "END_SECONDARY_INSPECTION"
    ]
  },
  "understanding": {
    "intent": "state_visit_purpose",
    "intent_success": true,
    "confidence": 0.94,
    "answer_relevance": "on_topic",
    "ambiguity_type": "none",
    "risk_delta": 0,
    "risk_tags": [],
    "extracted_slots": {
      "visit_purpose": "tourism"
    },
    "missing_slots": [],
    "needs_clarification": false
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
```

Developer C must validate Developer B output before applying `state_delta`,
using `branch.next_node_id`, consuming OpenKB write references, or building an
Unreal response.

Developer B may return this optional additive write reference:

```json
{
  "openkb_write": {
    "attempted": true,
    "succeeded": true,
    "namespace": "dev_b",
    "record_id": "dev_b_0123456789abcdef",
    "jsonl_path": "backend/runtime/openkb/dev_b/session_001.jsonl",
    "markdown_path": "backend/runtime/openkb/dev_b/dev_b_0123456789abcdef.md",
    "error_message": null
  }
}
```

Rules:

- The field is optional and additive.
- `namespace` must be `dev_b` when present.
- Successful write references must stay under the B-owned OpenKB runtime
  namespace.
- Developer C should avoid duplicate error markdown storage when
  `openkb_write.succeeded` is true.

Developer B may also return optional learning-feedback metadata:

```json
{
  "rubric_scores": {
    "comprehension": 2,
    "fluency": 1,
    "grammar_accuracy": 1,
    "vocabulary_range": 1,
    "clarity": 2,
    "interaction_problem_solving": 2,
    "total": 9
  },
  "difficulty_profile": {
    "travel_speaking_level": "TSL_3_INDEPENDENT",
    "npc_speech_speed": "normal",
    "question_complexity": "expanded",
    "hint_frequency": "medium",
    "pressure_level": "medium"
  },
  "feedback_generation": {
    "mode": "llm",
    "model": "gpt-4o-mini",
    "used_llm": true,
    "fallback_reason": null
  }
}
```

Rules:

- These fields are optional and additive.
- They are learning metadata only.
- They must not override `evaluation.verdict`, `branch`, `next_node_id`, or
  `state_delta`.
- Tests and deterministic flows must pass with `feedback_generation.mode` set
  to `rule` or `fallback` and without real API keys.

## Internal Turn Context

The orchestrator may keep this Developer C-owned shape while a turn is being
processed.

```json
{
  "contract_version": "dev_c_internal_turn.v1",
  "turn": {},
  "audio_ref": {
    "field_name": "audio",
    "mime_type": "audio/wav"
  },
  "normalized_input": {},
  "node_context": {},
  "understanding": {},
  "developer_b_policy": {},
  "developer_a_dialogue": {},
  "validation": {
    "is_valid": true,
    "issues": []
  }
}
```

This is not a public response shape. It is a workflow envelope for C-owned
services, graph nodes, tests, and mocks.

## Unreal Response

Developer C returns only validated, Unreal-safe data.

```json
{
  "contract_version": "dev_c_unreal_response.v1",
  "request_id": "req_imm_0001",
  "session_id": "session_001",
  "turn_index": 2,
  "current_node_id": "IMM_002_PURPOSE",
  "next_node_id": "IMM_003_DURATION",
  "next_action": "ADVANCE",
  "stt": {
    "model": "whisper-large-v3-turbo",
    "primary_runtime": "local",
    "fallback_runtime": "api",
    "runtime_used": "local",
    "player_text": "I'm here for tourism.",
    "confidence": 0.87,
    "language_detected": "en-US",
    "needs_repeat": false
  },
  "npc": {
    "speaker": "Officer Miller",
    "text": "You're here for tourism. How long will you stay?",
    "tone": "formal_neutral",
    "animation": "officer_check_passport",
    "audio_url": "/runtime/audio/kokoro/IMM_002_PURPOSE_stay_duration_success_am_michael_abcd1234.wav"
  },
  "ui": {
    "show_hint": false,
    "hint_kr": null,
    "recommended_expression": "I'm here for tourism.",
    "in_game_feedback": {
      "show": true,
      "feedback_strategy": "recast",
      "priority": "low"
    }
  },
  "state_delta": {
    "patience_delta": 0,
    "suspicion_delta": 0,
    "retry_count_delta": 0,
    "hint_count_delta": 0
  },
  "evaluation": {
    "verdict": "SUCCESS",
    "scores": {
      "task_success": 3,
      "clarity": 2,
      "grammar": 1,
      "vocabulary": 2,
      "problem_solving": 2,
      "politeness": 3
    },
    "feedback_tags": [
      "intent_matched",
      "required_slot_filled"
    ]
  },
  "report": {
    "recorded_error_count": 1,
    "report_item": {
      "summary": "Visit purpose was understood.",
      "example_answer": "I'm here for tourism."
    }
  },
  "debug": {
    "stt_confidence": 0.87,
    "understanding_confidence": 0.94,
    "contract_versions": [
      "dev_c_unreal_turn.v1",
      "dev_b_policy.v1",
      "dev_a_dialogue.v1",
      "dev_c_unreal_response.v1"
    ]
  }
}
```

Rules:

- `next_node_id` must be validated against `node_context.allowed_next_nodes`.
- `stt.player_text` is the normalized transcript passed into the Understanding
  Agent and Developer B policy adapter.
- `stt.primary_runtime` and `stt.fallback_runtime` expose the local-first
  runtime policy for demo/debug visibility.
- `stt.runtime_used` must be `local` unless the API fallback actually produced
  the transcript.
- `state_delta` must come from Developer B output after validation.
- NPC text and `npc.audio_url` must come from Developer A output through the
  Developer C adapter, not directly from Developer B.
- `npc.audio_url` points to a Developer C-served runtime artifact under
  `/runtime/audio/...` in the pre-prototype.
- `debug` may be omitted in production.
- Developer C may redact, omit, or transform internal fields before returning
  to Unreal.

## Validator Requirements

Developer C validator must enforce at least these rules:

1. Public request includes a wav audio part.
2. `turn.session.current_node_id` exists and matches `node_context.node_id`.
3. STT result has `player_text` unless `needs_repeat` is true.
4. Understanding output does not include branch, score, hint, or NPC final text.
5. Developer B output uses `contract_version = dev_b_policy.v1`.
6. Developer B `node_id` equals input `current_node_id`.
7. Developer B `branch.next_node_id` is in `node_context.allowed_next_nodes`.
8. If `client_allowed_next_nodes` is present, B `branch.next_node_id` is also
   in that list.
9. Developer B output does not include Unreal commands, animation commands, or
   final API response envelope data.
10. Developer A output does not alter `branch`, `next_node_id`, or
    `state_delta`.
11. Final response includes only Unreal-safe fields and valid enum values.
12. Pre-prototype final response includes `npc.audio_url` under
    `/runtime/audio/...`.
13. Developer B `openkb_write` references, when present, use namespace `dev_b`
    and do not point outside the B-owned OpenKB runtime path.
14. Developer B optional `rubric_scores.total` stays in the 0-12 range.
15. Developer B optional `feedback_generation` is trace metadata only and does
    not grant LLM branch or state authority.
