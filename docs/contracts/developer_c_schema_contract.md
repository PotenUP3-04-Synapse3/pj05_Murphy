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
| `GEMMA4_VLLM_BASE_URL` | `http://100.95.34.69:8001/v1` | Academy vLLM OpenAI-compatible base URL |
| `GEMMA4_VLLM_MODEL` | `google/gemma-4-26B-A4B-it` | Gemma4 fallback model |
| `GEMMA4_VLLM_API_KEY` | `dummy` | vLLM fallback API key placeholder |
| `MURPHY_UNDERSTANDING_MODE` | `rule` | `rule` is deterministic; `llm` enables LLM-assisted semantic analysis |
| `MURPHY_UNDERSTANDING_LLM_PROVIDER` | `openai` | Primary Understanding Agent LLM provider |
| `MURPHY_UNDERSTANDING_LLM_FALLBACK` | `none` | `none` or `gemma4_vllm` |
| `MURPHY_UNDERSTANDING_LLM_MODEL` | `gpt-4o-mini` | Primary Understanding Agent LLM model |
| `MURPHY_UNDERSTANDING_LLM_TIMEOUT_SECONDS` | `10` | Understanding Agent LLM timeout |
| `ELEVENLABS_API_KEY` | unset | Server-side key for ElevenLabs realtime STT relay |
| `ELEVENLABS_REALTIME_STT_ENDPOINT` | `wss://api.elevenlabs.io/v1/speech-to-text/realtime` | ElevenLabs realtime STT WSS endpoint |
| `ELEVENLABS_REALTIME_STT_MODEL` | `scribe_v2_realtime` | ElevenLabs realtime STT model id |
| `ELEVENLABS_REALTIME_AUDIO_FORMAT` | `pcm_16000` | Audio format sent to ElevenLabs |
| `ELEVENLABS_REALTIME_COMMIT_STRATEGY` | `manual` | ElevenLabs commit strategy, `manual` or `vad` |
| `ELEVENLABS_REALTIME_RECEIVE_TIMEOUT_S` | `0.2` | Short drain timeout for provider events after each audio chunk |
| `ELEVENLABS_REALTIME_COMMIT_TIMEOUT_S` | `3.0` | Longer drain timeout while waiting for a committed provider final transcript |
| `ELEVENLABS_REALTIME_ESTIMATED_COST_PER_MINUTE_USD` | `0` | Optional local estimate used only for realtime STT debug cost logs |
| `MURPHY_STT_DEBUG_LOG_MODE` | `off` | `debug` appends realtime STT AgentRun records to unified C logs |

This keeps the Unreal request simple while still satisfying the Developer B
`dev_b_policy.v1` input contract.

Alpha adds an optional C-owned interaction context to the same turn envelope so
Unreal can tell the backend whether the current speech turn started from an NPC
prompt or from the player walking up and speaking first. The field is additive;
when omitted, Developer C treats the turn as an NPC-initiated quest dialogue to
preserve the current prototype behavior.

## Contract Versions

| Contract | Version | Owner | Purpose |
| --- | --- | --- | --- |
| Unreal turn request | `dev_c_unreal_turn.v1` | Developer C | Public request envelope from Unreal to Developer C |
| Internal turn context | `dev_c_internal_turn.v1` | Developer C | Orchestrator state shared between C-owned workflow nodes |
| Realtime STT stream | `dev_c_realtime_stt.v1` | Developer C | WebSocket transcript event contract for Unreal subtitle previews |
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

## Realtime STT Stream

Alpha 3C adds a C-owned WebSocket surface for realtime transcript events:

```text
WebSocket /api/game/ai/stt/stream
```

The stream is additive and does not replace `POST /api/game/ai/respond`.
It supports two Alpha paths:

1. Provider-neutral transcript echo, where Unreal or a safe STT bridge sends
   already-transcribed `partial_transcript` and `final_transcript` events.
2. C backend relay mode, where Unreal sends `audio_chunk` events with
   `provider = "elevenlabs_relay"` and Developer C relays audio to ElevenLabs
   with the server-side `ELEVENLABS_API_KEY`.
   If ElevenLabs fails on a committed chunk, or commit returns no provider final
   transcript, Developer C wraps the buffered PCM chunks as a wav and runs the
   existing local Whisper batch STT runtime as `local_batch_fallback`.

```text
Unreal microphone
  -> Developer C WebSocket /api/game/ai/stt/stream
  -> ElevenLabs WSS /v1/speech-to-text/realtime
  -> Developer C subtitle event mapping
  -> Unreal subtitle UI
```

Partial transcripts are subtitle previews only. They must not call the
Understanding Agent, Developer B, Developer A, or TTS. A final transcript is a
committed transcript candidate that Unreal can send into the existing
`/respond` fallback path through the deterministic `audio.transcript` shortcut
until a future streaming-to-orchestrator commit endpoint is approved.

Client event:

```json
{
  "contract_version": "dev_c_realtime_stt.v1",
  "event_type": "audio_chunk",
  "request_id": "req_realtime_0001",
  "session_id": "session_realtime_001",
  "turn_index": 3,
  "sequence": 1,
  "provider": "elevenlabs_relay",
  "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
  "commit": false,
  "sample_rate_hz": 16000
}
```

Server event:

```json
{
  "contract_version": "dev_c_realtime_stt.v1",
  "event_type": "partial_transcript",
  "request_id": "req_realtime_0001",
  "session_id": "session_realtime_001",
  "turn_index": 3,
  "sequence": 1,
  "provider": "elevenlabs_relay",
  "subtitle": {
    "text": "I will stay",
    "is_final": false,
    "display_mode": "replace"
  },
  "committed": false
}
```

Final server events set `event_type = "final_transcript"`,
`subtitle.is_final = true`, `committed = true`, and
`target_endpoint = "POST /api/game/ai/respond"`.

Rules:

- The first client event in a connection must be `session_start`.
- `sequence` must increase monotonically per WebSocket connection.
- `partial_transcript` and `final_transcript` events must include non-empty
  `transcript`.
- `audio_chunk` events must include non-empty `audio_base64` and use
  `provider = "elevenlabs_relay"`.
- In manual commit mode, Unreal and smoke-test clients should set
  `commit = true` on the final real audio chunk for the utterance. Do not send
  a separate silence-only sentinel chunk as the commit message.
- Developer C waits up to `ELEVENLABS_REALTIME_COMMIT_TIMEOUT_S` for the
  committed provider final before using the local batch fallback.
- ElevenLabs realtime relay uses `xi-api-key` only from the C backend
  environment. Unreal must not receive or send the API key.
- The existing local Whisper STT runtime is retained as a batch fallback for
  committed realtime chunks. It is not a partial-streaming engine.
- When `MURPHY_STT_DEBUG_LOG_MODE=debug`, each realtime STT session appends a
  `realtime_stt_relay` Developer C AgentRun record to
  `backend/runtime/generated/agent_runs/unified_agent_runs.jsonl` and `.md`.
  STT token counts are logged as zero because audio STT providers do not report
  LLM token usage; cost is an estimate from
  `ELEVENLABS_REALTIME_ESTIMATED_COST_PER_MINUTE_USD` and measured audio bytes.
- Invalid events return `event_type = "contract_error"` instead of entering the
  C orchestrator.
- Provider values are currently `unreal_bridge`, `stt_provider_websocket`,
  `elevenlabs_relay`, `local_batch_fallback`, or `mock`.

## Unreal Turn Request

Canonical `turn` payload:

```json
{
  "contract_version": "dev_c_unreal_turn.v1",
  "request_id": "req_imm_0001",
  "session": {
    "session_id": "session_001",
    "player_id": "player_001",
    "chapter_id": "CH0_03_IMMIGRATION_CHECK",
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
  "interaction": {
    "contract_version": "dev_c_interaction_context.v1",
    "initiator": "npc",
    "interaction_type": "quest",
    "quest_id": null,
    "interaction_id": null,
    "time_limit_s": null,
    "first_contact": false,
    "npc_can_initiate": null,
    "player_can_initiate": null
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
    "current_objective": "State the visit purpose",
    "random_customs_item": null
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
| `interaction` | no | Alpha metadata for NPC-first/player-first and quest/ambient turns |
| `player_profile` | yes | Used by Developer B hint and strictness policy |
| `scenario_state` | yes | Used by Developer B state delta policy |
| `game_state` | yes | Used by Developer C and for B input enrichment |
| `previous_node_results` | no | Used for final decision and reports |
| `client_allowed_next_nodes` | no | Extra client-side branch guard |
| `client_context` | no | Debug and compatibility metadata |

### Alpha Random Customs Item Context

`game_state.random_customs_item` is optional and additive. Unreal can include it
when the baggage/customs sequence reveals a random item in the suitcase. The
object is not branch authority; Developer C preserves it so Understanding,
Developer B, and Developer A can talk about the same item.

Example:

```json
{
  "item_id": "medicine_red_ginseng_extract",
  "item_name": "red ginseng extract",
  "item_category": "medicine",
  "item_description": "Small bottles of Korean red ginseng extract.",
  "visit_location": "Queens",
  "declared": false,
  "source": "unreal_csv"
}
```

Fields:

| Field | Required | Notes |
| --- | --- | --- |
| `item_id` | no | Stable local id from Unreal or a CSV table |
| `item_name` | yes | Player-facing item name |
| `item_category` | no | Broad category such as `medicine`, `food`, or `souvenir` |
| `item_description` | no | Short description for A-facing dialogue context |
| `visit_location` | no | Optional location context tied to the random setup |
| `declared` | no | Whether the player declared the item before inspection |
| `source` | no | Debug/source tag such as `unreal_csv` |

### Alpha Interaction Context

`interaction` uses `dev_c_interaction_context.v1` and is Developer C-owned.
It does not grant branch authority to Unreal, Developer A, or an LLM. It is
metadata used for routing, logs, timing analysis, and future A/B contract
coordination.

Allowed values:

| Field | Values | Notes |
| --- | --- | --- |
| `initiator` | `npc`, `player` | Who started the speech turn |
| `interaction_type` | `quest`, `ambient`, `tutorial`, `system` | Gameplay category |
| `quest_id` | string or null | Stable quest id when the turn belongs to a quest |
| `interaction_id` | string or null | Client trace id for the interactable or encounter |
| `time_limit_s` | positive integer or null | Example: 30 for timed immigration answers |
| `first_contact` | boolean | True when this is the first line of the encounter |
| `npc_can_initiate` | boolean or null | Client-side capability metadata |
| `player_can_initiate` | boolean or null | Client-side capability metadata |

Default when omitted:

```json
{
  "contract_version": "dev_c_interaction_context.v1",
  "initiator": "npc",
  "interaction_type": "quest",
  "quest_id": null,
  "interaction_id": null,
  "time_limit_s": null,
  "first_contact": false,
  "npc_can_initiate": null,
  "player_can_initiate": null
}
```

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
  "chapter_id": "CH0_03_IMMIGRATION_CHECK",
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
- OpenAI strict structured output requires every object to set
  `additionalProperties: false` and every property to be listed in `required`.
  Developer C keeps legacy nullable `extracted_slots.visit_purpose` and
  `extracted_slots.stay_duration` fields for backwards compatibility, but new
  Alpha slots should travel through generic `slot_evidence` items.
- When OpenAI Responses API returns `usage`, Developer C stores those token
  counts in the Understanding trace and in the C unified AgentRun `model`
  object. `estimated_cost_usd` is a runtime estimate for C-owned LLM calls, not
  an invoice source of truth.
- Rule fallback maps visit purpose keywords to allowed slot values:
  `family_visit` for uncle, aunt, cousin, parents, family, relative;
  `friend_visit` for friend; `business` for business, meeting, conference;
  `study` for study, school; `transit` for transit, layover; and `tourism` for
  tourism, travel, vacation, sightseeing.
- Rule fallback and LLM postprocessing fill `stay_duration` for duration
  answers such as `5 days`, `five days`, `one week`, and `until Friday` when
  the current node requires `stay_duration`.
- Alpha 2 uses a generic slot evidence contract. The LLM may propose slot
  evidence for `node_context.required_slots`, `node_context.optional_slots`, and
  `node_context.critical_slots`. Developer C filters that evidence to allowed
  node slots, drops forbidden or unrelated slot names, and then builds
  `extracted_slots` for Developer B. Developer B remains the only branch and
  progression authority.

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
  "slot_evidence": [
    {
      "slot": "visit_purpose",
      "value": "tourism",
      "confidence": 0.94,
      "evidence_text": "tourism"
    }
  ],
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
  "chapter_id": "CH0_03_IMMIGRATION_CHECK",
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
- `report_seed_summary` and `dialogue_seed` are optional Developer B seed
  metadata. They may be validated or logged by Developer C, but they are not a
  final result screen payload and they do not introduce NPC final text fields.
- Tests and deterministic flows must pass with `feedback_generation.mode` set
  to `rule` or `fallback` and without real API keys.

## Internal Turn Context

The orchestrator may keep this Developer C-owned shape while a turn is being
processed.

Runtime note: Developer C now carries this state through the LangGraph
workflow in `backend/app/graphs/graph.py`. This is internal C runtime data and
does not change the public Unreal request or response contracts.

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
  "transition": null,
  "interaction": {
    "contract_version": "dev_c_interaction_context.v1",
    "initiator": "npc",
    "interaction_type": "quest",
    "quest_id": null,
    "interaction_id": null,
    "time_limit_s": null,
    "first_contact": false,
    "npc_can_initiate": null,
    "player_can_initiate": null
  },
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
    "emotion": "Nomal",
    "tone": "formal_neutral",
    "animation": "officer_check_passport",
    "audio_url": "/runtime/audio/edge/IMM_002_PURPOSE_stay_duration_success_am_michael_abcd1234.wav"
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
  "flow": {
    "contract_version": "dev_c_unreal_flow.v1",
    "transition_type": "none",
    "transition_id": null,
    "from_scene_id": "JFK_IMMIGRATION_HALL",
    "to_scene_id": "JFK_IMMIGRATION_HALL",
    "cinematic_id": null,
    "skip_allowed": false,
    "show_scoreboard": false
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
      "dev_c_interaction_context.v1",
      "dev_c_unreal_flow.v1",
      "dev_b_policy.v1",
      "dev_a_dialogue.v1",
      "dev_c_unreal_response.v1"
    ],
    "timing_ms": {
      "total_ms": 2150,
      "stt_ms": 620,
      "openkb_ms": 2,
      "understanding_ms": 140,
      "developer_b_ms": 20,
      "logging_ms": 1,
      "developer_a_ms": 1310,
      "response_build_ms": 1,
      "validation_ms": 1
    },
    "diagnostics": []
  }
}
```

Rules:

- `next_node_id` must be validated against `node_context.allowed_next_nodes`.
- `transition` is `null` for ordinary dialogue responses.
- When `next_action` is `COMPLETE_CHAPTER`, `transition` is required and
  contains `status`, `completed_chapter_id`, `next_chapter_id`,
  `entry_node_id`, `unreal_event`, and `requires_player_input=false`.
  Unreal uses this object to stop the current NPC dialogue and enter the next
  gameplay phase.
- `stt.player_text` is the normalized transcript passed into the Understanding
  Agent and Developer B policy adapter.
- `stt.primary_runtime` and `stt.fallback_runtime` expose the local-first
  runtime policy for demo/debug visibility.
- `stt.runtime_used` must be `local` unless the API fallback actually produced
  the transcript.
- `state_delta` must come from Developer B output after validation.
- `interaction` echoes the C-owned request interaction context so Unreal can
  correlate NPC-first, player-first, quest, ambient, and timed turns.
- `flow` is C-owned Unreal presentation metadata for scene/cutscene/scoreboard
  transitions. It does not grant branch authority and must not override
  Developer B `next_node_id` or `next_action`.
- Flow metadata is now derived from `transition.unreal_event` where possible.
  Current flow ids emitted by Developer C are `flight_to_arrival_tutorial`,
  `immigration_to_baggage_claim`, and `alpha_final_scoreboard`.
- NPC text and `npc.audio_url` must come from Developer A output through the
  Developer C adapter, not directly from Developer B.
- `npc.audio_url` points to a Developer C-served runtime artifact under
  `/runtime/audio/...` in the pre-prototype.
- `debug` may be omitted in production.
- `debug.timing_ms` is diagnostic latency metadata and must not drive gameplay
  branch decisions.
- `debug.diagnostics` is an additive C-owned warning list for integration
  issues such as an A-returned speaker that does not match the requested NPC
  context. Diagnostics are not branch authority and must not override
  Developer B policy.
- Developer C may redact, omit, or transform internal fields before returning
  to Unreal.
- On final-branch responses, `report.final_result` may include Developer B's
  validated final score payload. Developer C does not calculate the score.
- On the dedicated result endpoint, `out_game_feedback` may include Developer
  B's Focus-on-Form learning-card payload. Developer C treats this object as
  additive learning metadata only; it must not affect branch, verdict, score,
  next node, or state delta authority.

Dedicated result UI endpoint:

```text
GET /api/game/ai/result/{session_id}
```

Response envelope:

```json
{
  "contract_version": "dev_c_unreal_result.v1",
  "session_id": "session_001",
  "final_result": {
    "final_recommendation": "PASS",
    "rank": "Silver Pass",
    "final_score_100": 87,
    "reason_tags": ["score_at_least_80"],
    "quantitative_scores": {
      "overall": 87,
      "comprehension": 90,
      "fluency": 80,
      "grammar_accuracy": 80,
      "vocabulary_range": 90,
      "clarity": 90,
      "interaction_problem_solving": 90,
      "scoring_policy": "scene_normalized_dimension_average"
    },
    "report_summary": {
      "overall": "You passed the immigration check with clear, usable travel English.",
      "best_node": "IMM_003_DURATION",
      "weakest_node": "IMM_002_PURPOSE",
      "main_improvement": "Keep answers concise and polite.",
      "focus_on_form_targets": [],
      "included_node_count": 6
    }
  },
  "out_game_feedback": {
    "report_mode": "focus_on_form",
    "overall_summary_kr": "이번 플레이에서 반복된 영어 표현 이슈를 복습해 보세요.",
    "focus_on_form_items": [
      {
        "focus_on_form_target": "purpose_statement",
        "title_kr": "방문 목적 말하기",
        "rule_summary_kr": "입국 목적은 짧고 명확한 문장으로 말합니다.",
        "original_utterances": ["Tour."],
        "suggested_expressions": ["I'm here for tourism."],
        "practice_prompt_kr": "입국 목적을 한 문장으로 말해보세요.",
        "answer_example": "I'm here for tourism.",
        "priority": "high",
        "source_node_ids": ["IMM_002_PURPOSE"]
      }
    ],
    "personalized_next_step": {
      "target": "purpose_statement",
      "practice_prompt_kr": "입국 목적을 다시 말해보세요.",
      "answer_example": "I'm here for tourism."
    }
  }
}
```

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
16. Unreal `flow.contract_version` must be `dev_c_unreal_flow.v1`, scoreboard
    flow must set `show_scoreboard`, and non-scoreboard flow must not set it.
17. Developer B optional `final_result.final_score_100` is 0-100 and must match
    `final_result.quantitative_scores.overall`.
18. Developer B optional `final_result.quantitative_scores.scoring_policy` must
    be `simple_average` or `scene_normalized_dimension_average`.
19. `ALPHA_999_FINAL_SCOREBOARD` is the Alpha final-result trigger.
    `IMM_007_FINAL_DECISION` is an immigration-clearance transition into
    baggage claim, not an Alpha final-result trigger.
20. Developer C may expose `final_result` inside `/respond` on final branches
    and through `GET /api/game/ai/result/{session_id}`.
21. Developer C may expose B-owned `out_game_feedback` through
    `GET /api/game/ai/result/{session_id}` as learning metadata only.
22. Realtime STT WebSocket events must use `dev_c_realtime_stt.v1`, start with
    `session_start`, keep monotonically increasing `sequence`, and never route
    partial transcript events into Developer B, Developer A, or TTS.
