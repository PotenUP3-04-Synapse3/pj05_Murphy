# Developer B JSON Key-Value Contract v1

> AGENTS.md 정합성 메모: 이 문서는 Developer B 소유의 JSON key-value 계약 문서이다. Developer B는 평가, 레벨/힌트, 인게임 피드백 전략, 오류 기록 후보, 아웃게임 Focus on Form 피드백 payload, rule-based branch recommendation을 정의한다. FastAPI endpoint, STT/TTS, NPC 최종 대사 생성, Validator, Unreal response assembly, markdown 파일 저장 실행, OpenKB retrieval 실행은 Developer C 또는 다른 담당 범위이다.

## 1. 문서 목적

이 문서는 현업에서 API/adapter 계약을 맞출 때 사용하는 형식으로 Developer B policy의 JSON key-value 약속을 정의한다.

이 문서는 다음 사용자를 대상으로 한다.

- Developer B 구현자
- Developer C adapter 구현자
- Developer A NPC dialogue 구현자
- Unreal UI 연동 담당자
- QA / test case 작성자
- LLM agent가 계약을 참고해 payload를 생성하거나 검토하는 경우

이 문서는 설명형 기획서가 아니라 계약 문서이다. 따라서 각 key의 이름, 타입, 필수 여부, 허용 enum, 생성 주체, 소비 주체, 검증 규칙을 고정한다.

## 2. Scope

### 2.1 In Scope

Developer B가 정의하거나 반환하는 데이터:

- `evaluation`
- `level_hint`
- `in_game_feedback`
- `error_capture`
- `out_game_feedback_seed`
- `branch`
- `state_delta`
- `dialogue_directive`
- `report_item`
- `openkb_write`
- `rubric_scores`
- `difficulty_profile`
- `feedback_generation`
- `out_game_feedback`
- `final_recommendation`

### 2.2 Out of Scope

Developer B가 만들지 않는 데이터:

- raw audio / wav binary
- STT provider result 원본
- NPC 최종 대사 본문
- TTS voice id
- Unreal command
- animation / camera event
- final API response envelope
- validator result
- markdown 파일 실제 저장
- OpenKB 검색 실행
- DB write

## 3. Naming Convention

| 항목 | 규칙 |
| --- | --- |
| JSON key | `snake_case` |
| ID value | 대문자 prefix + underscore 권장. 예: `IMM_002_PURPOSE` |
| enum value | 기존 게임 enum과 맞출 때는 `UPPER_SNAKE_CASE`, B 내부 branch type은 `lower_snake_case` |
| boolean key | `is_`, `has_`, `needs_`, `should_`, `can_` 중 하나로 시작 |
| timestamp | ISO-8601 string. 예: `2026-06-02T10:30:00+09:00` |
| nullable | optional과 null을 구분한다. key가 의미상 필요하지만 값이 없으면 `null`, 의미가 없으면 key 생략 가능 |
| score | 0-3 scale 또는 0-100 scale 중 필드별로 고정한다 |
| text language suffix | 한국어 사용자 표시문은 `_kr`, 영어 예문은 `_en` suffix 사용 |

## 4. Contract Versioning

모든 Developer B policy input/output에는 가능하면 `contract_version`을 포함한다.

```json
{
  "contract_version": "dev_b_policy.v1",
  "schema_owner": "developer_b",
  "schema_status": "draft"
}
```

Versioning 규칙:

- patch 변경: 필드 설명, 예시 추가, optional field 추가
- minor 변경: enum 추가, optional object 추가
- major 변경: required field 삭제/이름 변경/타입 변경

## 5. Developer B Policy Input

Developer C adapter가 Developer B policy에 전달하는 canonical input이다.

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
  "player_text": "I here tourism.",
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
    "recommended_expression": "I'm here for tourism.",
    "base_hint_kr": "미국에 온 목적을 말해보세요.",
    "hint_policy": {
      "keyword": [
        "tourism",
        "business",
        "vacation"
      ],
      "sentence_pattern": "I'm here for ___.",
      "situation_hint": "방문 목적을 말해야 합니다.",
      "action_hint": "방문 목적을 먼저 말하고, 필요하면 이유를 짧게 덧붙입니다."
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
    "confidence": 0.92,
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

### 5.1 Root Input Fields

| Key | Type | Required | Owner | Description |
| --- | --- | --- | --- | --- |
| `contract_version` | string | yes | Developer C | Contract version. Must be `dev_b_policy.v1` for this document |
| `request_id` | string | yes | Developer C | Single request trace id |
| `session_id` | string | yes | Unreal/C | Player session id |
| `player_id` | string | no | Unreal/C | Player id or nickname id |
| `chapter_id` | string | yes | Unreal/C | Chapter id. MVP value: `CH0_IMMIGRATION` |
| `scene_id` | string | yes | Unreal/C | Scene id |
| `current_node_id` | string | yes | Unreal/C | Current scenario node id |
| `turn_index` | integer | yes | Developer C | 0-based or 1-based is allowed if consistent per session; recommended 1-based |
| `player_text` | string | yes | STT/C | Normalized player utterance |
| `input_source` | object | yes | Developer C | Input metadata |
| `player_profile` | object | yes | Unreal/C | Player level profile |
| `scenario_state` | object | yes | Unreal/C | Current scenario state values |
| `node_context` | object | yes | OpenKB/C | Node rule context |
| `understanding` | object | yes | Understanding Agent | Semantic analysis result |
| `previous_node_results` | array<object> | no | Developer C | Previous B results for final reporting |
| `client_allowed_next_nodes` | array<string> | no | Unreal | Client-side allowed next node guard |

### 5.2 `input_source`

| Key | Type | Required | Allowed Values | Description |
| --- | --- | --- | --- | --- |
| `input_type` | string | yes | `text`, `voice` | Source input mode |
| `stt_confidence` | number or null | voice only | 0.0-1.0 | STT confidence. Null for text input |
| `language_detected` | string or null | no | BCP-47 style string | Example: `en-US`, `ko-KR` |
| `needs_repeat` | boolean | yes | true/false | Whether STT/input requires repeat before evaluation |

### 5.3 `player_profile`

| Key | Type | Required | Allowed Values | Description |
| --- | --- | --- | --- | --- |
| `nickname` | string | no | any | Display name |
| `english_confidence` | string | no | `beginner`, `intermediate`, `advanced` | User self-confidence |
| `tier` | string | yes | `Bronze`, `Silver`, `Gold` | Evaluation strictness tier |
| `travel_speaking_level` | string | yes | `TSL_1_SURVIVAL`, `TSL_2_FUNCTIONAL`, `TSL_3_INDEPENDENT`, `TSL_4_STRATEGIC` | Project-specific speaking level |

### 5.4 `scenario_state`

| Key | Type | Required | Range | Description |
| --- | --- | --- | --- | --- |
| `retry_count` | integer | yes | 0+ | Retry count for current node |
| `hint_count` | integer | yes | 0+ | Hint count for current node/session |
| `patience` | integer | yes | 0-100 | NPC patience state |
| `suspicion` | integer | yes | 0-100 | Immigration suspicion state |
| `previous_fail_count` | integer | yes | 0+ | Accumulated non-critical fail count |
| `completed_intents` | array<string> | no | intent ids | Intents already completed |

### 5.5 `node_context`

| Key | Type | Required | Description |
| --- | --- | --- | --- |
| `node_id` | string | yes | Current node id. Must equal `current_node_id` |
| `npc_question` | string | yes | NPC question text |
| `objective_kr` | string | no | Korean UI objective text for the current node |
| `required_intents` | array<string> | yes | Intents required for success |
| `required_slots` | array<string> | yes | Slots required for success |
| `optional_slots` | array<string> | no | Extra slots that improve clarity |
| `critical_slots` | array<string> | no | Slots or semantic findings that trigger warning/fail |
| `recommended_expression` | string | yes | Recommended answer pattern |
| `base_hint_kr` | string | no | Base Korean hint |
| `hint_policy` | object | yes | Hint content candidates by type |
| `success_next_node` | string | yes | Next node on success |
| `retry_next_node` | string | yes | Next node on retry |
| `clarify_next_node` | string | yes | Next node on clarification |
| `hint_next_node` | string | yes | Next node when hint is provided |
| `warning_next_node` | string | yes | Next node on warning |
| `allowed_next_nodes` | array<string> | yes | Allowed next node ids |

### 5.6 `understanding`

| Key | Type | Required | Description |
| --- | --- | --- | --- |
| `intent` | string | yes | Detected intent |
| `intent_success` | boolean | yes | Whether the semantic goal was met |
| `confidence` | number | yes | Understanding confidence, 0.0-1.0 |
| `answer_relevance` | string | yes | `on_topic`, `partially_related`, `off_topic` |
| `ambiguity_type` | string | yes | `none` or ambiguity reason |
| `risk_delta` | integer | yes | Risk change from current utterance |
| `risk_tags` | array<string> | yes | Risk category tags |
| `extracted_slots` | object | yes | Slot key-value map |
| `missing_slots` | array<string> | yes | Missing required slots |
| `needs_clarification` | boolean | yes | Whether clarification is needed |

## 6. Developer B Policy Output

Canonical output returned by Developer B policy.

```json
{
  "contract_version": "dev_b_policy.v1",
  "node_id": "IMM_002_PURPOSE",
  "evaluation": {
    "verdict": "SUCCESS",
    "detected_intents": [
      "state_visit_purpose"
    ],
    "required_intents_passed": true,
    "filled_slots": {
      "visit_purpose": "tourism"
    },
    "missing_slots": [],
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
      "required_slot_filled",
      "minor_grammar_issue"
    ],
    "feedback_note": "방문 목적은 전달됐지만 완전한 문장으로 말하면 더 자연스럽습니다."
  },
  "level_hint": {
    "english_level": "beginner",
    "travel_speaking_level": "TSL_1_SURVIVAL",
    "cefr_estimate": "A1-A2",
    "needs_hint": false,
    "hint_level": "none",
    "hint_type": null,
    "hint_kr": null,
    "example_en": "I'm here for tourism.",
    "avoid_expression": "I came to work illegally.",
    "recommended_expression": "I'm here for tourism."
  },
  "in_game_feedback": {
    "show": true,
    "feedback_strategy": "recast",
    "timing": "during_dialogue_turn",
    "priority": "low",
    "purpose": "maintain_communication",
    "focus": "sentence_naturalness",
    "npc_recast_line_candidate": "You're here for tourism. How long will you be staying?",
    "clarification_prompt_candidate": null,
    "elicitation_cue_candidate": null,
    "scaffolding_hint": null,
    "recommended_expression": "I'm here for tourism.",
    "display_duration_ms": null,
    "blocks_progression": false
  },
  "error_capture": {
    "should_record": true,
    "storage_format": "markdown",
    "error_items": [
      {
        "error_id": "err_imm_002_001",
        "node_id": "IMM_002_PURPOSE",
        "turn_index": 2,
        "npc_question": "What is the purpose of your visit?",
        "original_utterance": "I here tourism.",
        "intended_meaning_kr": "관광 목적으로 왔다고 말하려고 했습니다.",
        "error_type": "grammar",
        "error_scope": "local",
        "focus_on_form_target": "be_verb_in_self_introduction",
        "suggested_expression": "I'm here for tourism.",
        "severity": "minor",
        "affected_scores": [
          "grammar",
          "clarity"
        ],
        "should_surface_in_game": false,
        "should_surface_out_game": true
      }
    ],
    "markdown_entry": "### IMM_002_PURPOSE - err_imm_002_001\n- NPC Question: What is the purpose of your visit?\n- Original: I here tourism.\n- Intended Meaning: 관광 목적으로 왔다고 말하려고 했습니다.\n- Error Type: grammar\n- Focus on Form: be_verb_in_self_introduction\n- Suggested: I'm here for tourism.\n- Severity: minor"
  },
  "out_game_feedback_seed": {
    "include_in_final_report": true,
    "openkb_query_tags": [
      "be_verb_in_self_introduction",
      "immigration_visit_purpose",
      "sentence_completion"
    ],
    "focus_on_form_targets": [
      "be_verb_in_self_introduction"
    ],
    "report_priority": "medium"
  },
  "branch": {
    "branch_type": "success",
    "next_action": "ADVANCE",
    "next_node_id": "IMM_003_DURATION",
    "branch_reason": "Required intent and visit_purpose slot were satisfied.",
    "allowed_next_node_checked": true
  },
  "state_delta": {
    "patience_delta": 0,
    "suspicion_delta": 0,
    "retry_count_delta": 0,
    "hint_count_delta": 0
  },
  "dialogue_directive": {
    "purpose": "continue_to_next_question",
    "tone_hint": "neutral",
    "target_slot": "stay_duration",
    "do_not_generate_npc_text": true
  },
  "report_item": {
    "summary": "방문 목적을 전달했습니다.",
    "improvement": "단어 하나보다 완전한 문장으로 말하면 더 자연스럽습니다.",
    "example_answer": "I'm here for tourism.",
    "score_tags": [
      "task_success_good",
      "grammar_minor_issue"
    ]
  }
}
```

### 6.1 Root Output Fields

| Key | Type | Required | Owner | Description |
| --- | --- | --- | --- | --- |
| `contract_version` | string | yes | Developer B | Must match input contract version |
| `node_id` | string | yes | Developer B | Evaluated node id |
| `evaluation` | object | yes | Developer B | Verdict, slots, scores, tags |
| `level_hint` | object | yes | Developer B | Level and hint recommendation |
| `in_game_feedback` | object | yes | Developer B | Runtime interaction feedback strategy |
| `error_capture` | object | yes | Developer B | Error log candidate for out-game report |
| `out_game_feedback_seed` | object | yes | Developer B | OpenKB query seed for final feedback |
| `branch` | object | yes | Developer B | Branch recommendation |
| `state_delta` | object | yes | Developer B | Proposed state changes |
| `dialogue_directive` | object | no | Developer B | Advisory metadata for Developer A/C |
| `report_item` | object | yes | Developer B | Legacy/simple report item summary |
| `openkb_write` | object | no | Developer B | B-owned OpenKB `dev_b` namespace write reference |
| `rubric_scores` | object | no | Developer B | 0-12 Travel Speaking Level rubric metadata |
| `difficulty_profile` | object | no | Developer B | Learning difficulty profile metadata |
| `feedback_generation` | object | no | Developer B | Rule/LLM/fallback feedback generation trace |

## 7. Output Object Contracts

### 7.1 `evaluation`

| Key | Type | Required | Allowed Values | Description |
| --- | --- | --- | --- | --- |
| `verdict` | string | yes | `SUCCESS`, `PARTIAL`, `UNCLEAR`, `FAIL`, `CRITICAL_FAIL` | Evaluation result |
| `detected_intents` | array<string> | yes | intent ids | Detected intents |
| `required_intents_passed` | boolean | yes | true/false | Whether required intents are satisfied |
| `filled_slots` | object | yes | slot map | Filled slots |
| `missing_slots` | array<string> | yes | slot ids | Missing slots |
| `scores` | object | yes | 0-3 each | Per-turn rubric scores |
| `feedback_tags` | array<string> | yes | tag ids | Debug/report tags |
| `feedback_note` | string | no | any | Short internal note |

### 7.2 `scores`

Score scale is 0-3 for turn-level scoring.

| Key | Type | Required | Range | Description |
| --- | --- | --- | --- | --- |
| `task_success` | integer | yes | 0-3 | Task solved in current node |
| `clarity` | integer | yes | 0-3 | Meaning clarity |
| `grammar` | integer | yes | 0-3 | Grammar quality |
| `vocabulary` | integer | yes | 0-3 | Context vocabulary |
| `problem_solving` | integer | yes | 0-3 | Situational problem solving |
| `politeness` | integer | yes | 0-3 | Politeness/formality |

### 7.3 `level_hint`

| Key | Type | Required | Allowed Values | Description |
| --- | --- | --- | --- | --- |
| `english_level` | string | yes | `beginner`, `intermediate`, `advanced` | Simple UI level |
| `travel_speaking_level` | string | yes | `TSL_1_SURVIVAL`, `TSL_2_FUNCTIONAL`, `TSL_3_INDEPENDENT`, `TSL_4_STRATEGIC` | Project speaking level |
| `cefr_estimate` | string | no | examples: `A1-A2`, `A2-B1` | Approximate CEFR range |
| `needs_hint` | boolean | yes | true/false | Whether hint should be offered |
| `hint_level` | string | yes | `none`, `low`, `medium`, `high` | Hint strength |
| `hint_type` | string or null | yes | `keyword`, `sentence_pattern`, `situation_hint`, `action_hint`, null | Hint type |
| `hint_kr` | string or null | yes | any | Korean hint text if shown |
| `example_en` | string | yes | any | English example answer |
| `avoid_expression` | string or null | no | any | Expression to avoid |
| `recommended_expression` | string | yes | any | Recommended expression |

### 7.4 `in_game_feedback`

In-game feedback is for maintaining communication and mission flow. It should not be long explicit grammar correction.

| Key | Type | Required | Allowed Values | Description |
| --- | --- | --- | --- | --- |
| `show` | boolean | yes | true/false | Whether feedback should be surfaced |
| `feedback_strategy` | string | yes | `recast`, `clarification_request`, `elicitation`, `scaffolding_hint`, `warning`, `none` | Runtime feedback strategy |
| `timing` | string | yes | `during_dialogue_turn`, `after_player_answer`, `before_retry` | When to surface |
| `priority` | string | yes | `low`, `medium`, `high` | UI/dialogue priority |
| `purpose` | string | yes | `maintain_communication`, `restore_clarity`, `prevent_failure`, `warn_user` | Feedback purpose |
| `focus` | string | yes | tag id | What the feedback targets |
| `npc_recast_line_candidate` | string or null | yes | any | Candidate recast line; Developer A may rewrite |
| `clarification_prompt_candidate` | string or null | yes | any | Candidate clarification prompt |
| `elicitation_cue_candidate` | string or null | yes | any | Candidate cue |
| `scaffolding_hint` | string or null | yes | any | Candidate scaffold |
| `recommended_expression` | string or null | no | any | Suggested expression |
| `display_duration_ms` | integer or null | no | 0+ | UI display duration if UI hint |
| `blocks_progression` | boolean | yes | true/false | Whether progression should wait |

### 7.5 `error_capture`

`error_capture` is the per-turn source for markdown error logs and final Focus on Form feedback.

| Key | Type | Required | Description |
| --- | --- | --- | --- |
| `should_record` | boolean | yes | Whether any error should be recorded |
| `storage_format` | string | yes | Must be `markdown` in v1 |
| `error_items` | array<object> | yes | Structured error items |
| `markdown_entry` | string or null | yes | Markdown entry candidate for Developer C storage |

#### `error_items[]`

| Key | Type | Required | Allowed Values | Description |
| --- | --- | --- | --- | --- |
| `error_id` | string | yes | unique per session | Stable error id |
| `node_id` | string | yes | node id | Node where error occurred |
| `turn_index` | integer | yes | 1+ | Turn index |
| `npc_question` | string | yes | any | NPC question |
| `original_utterance` | string | yes | any | Player original utterance |
| `intended_meaning_kr` | string | no | any | Korean intended meaning |
| `error_type` | string | yes | `grammar`, `vocabulary`, `clarity`, `politeness`, `task_response`, `problem_solving`, `risk_expression` | Error category |
| `error_scope` | string | yes | `local`, `global` | Local does not block meaning; global blocks meaning |
| `focus_on_form_target` | string | yes | tag id | OpenKB Focus on Form target |
| `suggested_expression` | string | yes | any | Suggested expression |
| `severity` | string | yes | `minor`, `moderate`, `major`, `critical` | Error severity |
| `affected_scores` | array<string> | yes | score key ids | Scores affected |
| `should_surface_in_game` | boolean | yes | true/false | Whether to surface during gameplay |
| `should_surface_out_game` | boolean | yes | true/false | Whether to include in final report |

### 7.6 `out_game_feedback_seed`

| Key | Type | Required | Description |
| --- | --- | --- | --- |
| `include_in_final_report` | boolean | yes | Whether this turn contributes to final report |
| `openkb_query_tags` | array<string> | yes | Tags Developer C can use for OpenKB retrieval |
| `focus_on_form_targets` | array<string> | yes | Focus on Form target ids |
| `report_priority` | string | yes | `low`, `medium`, `high` |

### 7.7 `openkb_write`

`openkb_write` is optional and additive. It reports whether Developer B wrote
the policy feedback/error/focus-on-form record to the B-owned OpenKB `dev_b`
namespace.

| Key | Type | Required | Description |
| --- | --- | --- | --- |
| `attempted` | boolean | yes | Whether B attempted a namespace write |
| `succeeded` | boolean | yes | Whether the write completed |
| `namespace` | string | yes | Must be `dev_b` |
| `record_id` | string or null | no | Deterministic B record id |
| `jsonl_path` | string or null | no | Local JSONL record path |
| `markdown_path` | string or null | no | Local markdown record path |
| `error_message` | string or null | no | Failure reason when write failed |

### 7.8 `rubric_scores`

`rubric_scores` is optional metadata for learning difficulty. It must not
override `evaluation.verdict`, `branch`, or `state_delta`.

| Key | Type | Required | Range |
| --- | --- | --- | --- |
| `comprehension` | integer | yes | 0-2 |
| `fluency` | integer | yes | 0-2 |
| `grammar_accuracy` | integer | yes | 0-2 |
| `vocabulary_range` | integer | yes | 0-2 |
| `clarity` | integer | yes | 0-2 |
| `interaction_problem_solving` | integer | yes | 0-2 |
| `total` | integer | yes | 0-12 |

### 7.9 `difficulty_profile`

| Key | Type | Required | Allowed Values |
| --- | --- | --- | --- |
| `travel_speaking_level` | string | yes | `TSL_1_SURVIVAL`, `TSL_2_FUNCTIONAL`, `TSL_3_INDEPENDENT`, `TSL_4_STRATEGIC` |
| `npc_speech_speed` | string | yes | `slow`, `normal`, `natural` |
| `question_complexity` | string | yes | `basic`, `standard`, `expanded`, `complex` |
| `hint_frequency` | string | yes | `high`, `medium`, `low` |
| `pressure_level` | string | yes | `low`, `medium`, `high` |

### 7.10 `feedback_generation`

| Key | Type | Required | Allowed Values |
| --- | --- | --- | --- |
| `mode` | string | yes | `rule`, `llm`, `fallback` |
| `model` | string or null | no | any |
| `used_llm` | boolean | yes | true/false |
| `fallback_reason` | string or null | no | any |

### 7.11 `branch`

| Key | Type | Required | Allowed Values | Description |
| --- | --- | --- | --- | --- |
| `branch_type` | string | yes | `success`, `retry`, `clarify`, `hint`, `warning`, `bad_end`, `final` | Branch recommendation |
| `next_action` | string | yes | `ADVANCE`, `REASK`, `GIVE_HINT`, `WARNING`, `FAIL_END`, `FINAL_DECISION` | Action recommendation |
| `next_node_id` | string | yes | allowed node id | Recommended next node |
| `branch_reason` | string | yes | any | Reason for branch |
| `allowed_next_node_checked` | boolean | yes | true/false | Whether B checked allowed nodes |

### 7.12 `state_delta`

| Key | Type | Required | Range | Description |
| --- | --- | --- | --- | --- |
| `patience_delta` | integer | yes | -100 to 100 | Proposed patience change |
| `suspicion_delta` | integer | yes | -100 to 100 | Proposed suspicion change |
| `retry_count_delta` | integer | yes | 0 or 1 usually | Proposed retry count change |
| `hint_count_delta` | integer | yes | 0 or 1 usually | Proposed hint count change |

## 8. Enum Registry

### 8.1 Verdict

| Value | Meaning |
| --- | --- |
| `SUCCESS` | Required intent and slots are sufficiently satisfied |
| `PARTIAL` | Meaning is partly valid, but slot/detail/form is weak |
| `UNCLEAR` | Meaning or STT result is unclear |
| `FAIL` | Current task is not solved |
| `CRITICAL_FAIL` | Risky or highly suspicious response |

### 8.2 In-game Feedback Strategy

| Value | Meaning |
| --- | --- |
| `recast` | NPC naturally reformulates the player's meaning |
| `clarification_request` | NPC asks for clarification |
| `elicitation` | NPC gives a cue so the player can complete the answer |
| `scaffolding_hint` | UI or short prompt provides word/pattern help |
| `warning` | Situation warning, not grammar correction |
| `none` | No in-game feedback |

### 8.3 Error Type

| Value | Meaning |
| --- | --- |
| `grammar` | Grammar/form error |
| `vocabulary` | Word choice error |
| `clarity` | Meaning clarity issue |
| `politeness` | Register/formality issue |
| `task_response` | Did not answer the question |
| `problem_solving` | Weak situational handling |
| `risk_expression` | Risky immigration-related expression |

## 9. Final Out-Game Feedback Contract

Final out-game feedback is generated after the episode using stored markdown error logs and OpenKB Focus on Form context.

### 9.1 Final Feedback Input

```json
{
  "contract_version": "dev_b_policy.v1",
  "session_id": "session_001",
  "chapter_id": "CH0_IMMIGRATION",
  "error_log_markdown_path": "logs/session_001/error_log.md",
  "error_log_markdown": "### IMM_002_PURPOSE - err_imm_002_001\n- Original: I here tourism.\n- Focus on Form: be_verb_in_self_introduction\n- Suggested: I'm here for tourism.",
  "node_results": [
    {
      "node_id": "IMM_002_PURPOSE",
      "verdict": "SUCCESS",
      "scores": {
        "task_success": 3,
        "clarity": 2,
        "grammar": 1,
        "vocabulary": 2,
        "problem_solving": 2,
        "politeness": 3
      }
    }
  ],
  "openkb_focus_on_form_context": [
    {
      "focus_on_form_target": "be_verb_in_self_introduction",
      "rule_summary_kr": "영어에서 자신의 목적이나 상태를 말할 때는 주어 뒤에 be 동사를 넣어 문장을 완성합니다.",
      "good_examples": [
        "I'm here for tourism.",
        "I'm here for a business meeting."
      ],
      "practice_prompt": "I'm here for ___."
    }
  ]
}
```

### 9.2 Final Feedback Output

```json
{
  "contract_version": "dev_b_policy.v1",
  "out_game_feedback": {
    "report_mode": "focus_on_form",
    "overall_summary_kr": "입국심사 질문의 핵심 의미는 전달했지만, 짧은 답변에서 be 동사 누락이 반복되었습니다.",
    "quantitative_scores": {
      "task_success": 82,
      "clarity": 76,
      "grammar": 64,
      "vocabulary": 70,
      "politeness": 85,
      "problem_solving": 72
    },
    "focus_on_form_items": [
      {
        "target": "be_verb_in_self_introduction",
        "title_kr": "I'm here for ___ 패턴",
        "original_utterance": "I here tourism.",
        "corrected_expression": "I'm here for tourism.",
        "explanation_kr": "방문 목적을 말할 때는 `I'm here for + 목적` 패턴을 쓰면 자연스럽습니다.",
        "openkb_source_tags": [
          "immigration_visit_purpose",
          "be_verb",
          "travel_purpose_expression"
        ],
        "micro_practice": {
          "prompt_kr": "출장 목적으로 왔다고 말해보세요.",
          "answer_example": "I'm here for a business meeting."
        }
      }
    ],
    "personalized_next_step": {
      "focus_kr": "짧은 단어 답변을 완전한 문장으로 확장하기",
      "recommended_card_ids": [
        "FORM_BE_VERB_001",
        "IMM_PURPOSE_PATTERN_001"
      ]
    }
  }
}
```

### 9.3 Final Feedback Field Dictionary

| Key | Type | Required | Owner | Description |
| --- | --- | --- | --- | --- |
| `error_log_markdown_path` | string | yes | Developer C | Stored markdown path |
| `error_log_markdown` | string | yes | Developer C | Markdown content to analyze |
| `openkb_focus_on_form_context` | array<object> | yes | Developer C/OpenKB | Retrieved Focus on Form support |
| `out_game_feedback.report_mode` | string | yes | Developer B | Must be `focus_on_form` in v1 |
| `quantitative_scores` | object | yes | Developer B | 0-100 final scores |
| `focus_on_form_items` | array<object> | yes | Developer B | Explicit correction items |
| `personalized_next_step` | object | no | Developer B | Next learning recommendation |

## 10. Validation Rules

Developer B policy output must satisfy these invariants.

```text
1. output.node_id must equal input.current_node_id.
2. branch.next_node_id must be included in node_context.allowed_next_nodes.
3. If client_allowed_next_nodes is provided, branch.next_node_id must also be included there.
4. If evaluation.verdict is SUCCESS, evaluation.missing_slots should be empty unless tier policy explicitly allows partial slot pass.
5. If evaluation.verdict is CRITICAL_FAIL, state_delta.suspicion_delta must be greater than 0.
6. If level_hint.needs_hint is false, level_hint.hint_type and level_hint.hint_kr should be null.
7. If in_game_feedback.feedback_strategy is recast, npc_recast_line_candidate should be non-null.
8. If in_game_feedback.feedback_strategy is clarification_request, clarification_prompt_candidate should be non-null.
9. If error_capture.should_record is false, error_items must be empty and markdown_entry should be null.
10. If out_game_feedback_seed.include_in_final_report is true, focus_on_form_targets must not be empty.
11. Developer B must not return Unreal commands.
12. Developer B must not mutate game_state directly.
```

## 11. Markdown Error Log Contract

Developer B proposes markdown entries; Developer C stores them.

Recommended markdown format:

```text
### {node_id} - {error_id}
- Turn: {turn_index}
- NPC Question: {npc_question}
- Original: {original_utterance}
- Intended Meaning: {intended_meaning_kr}
- Error Type: {error_type}
- Error Scope: {error_scope}
- Focus on Form: {focus_on_form_target}
- Suggested: {suggested_expression}
- Severity: {severity}
```

Rules:

- One error item should produce one markdown section.
- `error_id` must be stable within a session.
- Markdown is for final feedback analysis, not direct in-game display.
- Developer C owns file path, write timing, retention, and privacy handling.

## 12. LLM Usage Rules

When an LLM uses this contract:

```text
1. Do not invent required fields that are missing from input. Return a validation issue instead.
2. Use only enum values listed in this document.
3. Keep in_game_feedback short and interaction-focused.
4. Put explicit grammar correction into error_capture and out_game_feedback, not in long in-game text.
5. Do not output NPC final dialogue as Developer B.
6. Do not output Unreal commands.
7. Always include branch.next_node_id and branch.branch_reason.
8. Always include score evidence through feedback_tags or error_items.
```

## 13. Minimal Valid Output

This is the minimum shape Developer C can safely consume.

```json
{
  "contract_version": "dev_b_policy.v1",
  "node_id": "IMM_002_PURPOSE",
  "evaluation": {
    "verdict": "SUCCESS",
    "detected_intents": [
      "state_visit_purpose"
    ],
    "required_intents_passed": true,
    "filled_slots": {
      "visit_purpose": "tourism"
    },
    "missing_slots": [],
    "scores": {
      "task_success": 3,
      "clarity": 3,
      "grammar": 2,
      "vocabulary": 2,
      "problem_solving": 2,
      "politeness": 3
    },
    "feedback_tags": [
      "intent_matched",
      "required_slot_filled"
    ],
    "feedback_note": null
  },
  "level_hint": {
    "english_level": "beginner",
    "travel_speaking_level": "TSL_1_SURVIVAL",
    "cefr_estimate": "A1-A2",
    "needs_hint": false,
    "hint_level": "none",
    "hint_type": null,
    "hint_kr": null,
    "example_en": "I'm here for tourism.",
    "avoid_expression": null,
    "recommended_expression": "I'm here for tourism."
  },
  "in_game_feedback": {
    "show": false,
    "feedback_strategy": "none",
    "timing": "after_player_answer",
    "priority": "low",
    "purpose": "maintain_communication",
    "focus": "none",
    "npc_recast_line_candidate": null,
    "clarification_prompt_candidate": null,
    "elicitation_cue_candidate": null,
    "scaffolding_hint": null,
    "recommended_expression": null,
    "display_duration_ms": null,
    "blocks_progression": false
  },
  "error_capture": {
    "should_record": false,
    "storage_format": "markdown",
    "error_items": [],
    "markdown_entry": null
  },
  "out_game_feedback_seed": {
    "include_in_final_report": false,
    "openkb_query_tags": [],
    "focus_on_form_targets": [],
    "report_priority": "low"
  },
  "branch": {
    "branch_type": "success",
    "next_action": "ADVANCE",
    "next_node_id": "IMM_003_DURATION",
    "branch_reason": "Required intent and slot were satisfied.",
    "allowed_next_node_checked": true
  },
  "state_delta": {
    "patience_delta": 0,
    "suspicion_delta": 0,
    "retry_count_delta": 0,
    "hint_count_delta": 0
  },
  "report_item": {
    "summary": "방문 목적을 전달했습니다.",
    "improvement": "현재 답변은 진행에 충분합니다.",
    "example_answer": "I'm here for tourism.",
    "score_tags": [
      "task_success_good"
    ]
  }
}
```

## 14. Change Control

## 13.1 Final Result Score Payload

Developer B owns the final score policy. In implementation v1, B may attach an
optional `final_result` object to `DevBPolicyOutput` when the current branch is
`final`.

Required `final_result` fields:

```json
{
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
    "scoring_policy": "simple_average"
  },
  "report_summary": {
    "overall": "You passed the immigration check with clear, usable travel English.",
    "best_node": "IMM_003_DURATION",
    "weakest_node": "IMM_002_PURPOSE",
    "main_improvement": "Keep answers concise and polite.",
    "focus_on_form_targets": [],
    "included_node_count": 6
  }
}
```

Policy rules:

- Each per-turn `rubric_scores.total` is converted from 0-12 to 0-100.
- Chapter 0 v1 uses simple unweighted average across scored nodes.
- `IMM_007_FINAL_DECISION` is excluded when earlier scored nodes exist.
- feedback/error/focus-on-form records do not add a separate numeric penalty in
  v1; they affect `reason_tags` and `report_summary`.
- `final_score_100` must match `quantitative_scores.overall`.
- Valid recommendations are `PASS`, `CONDITIONAL_PASS`, `SECONDARY_ROOM`,
  `COMIC_FAIL`, and `UNRANKED`.

Contract changes must follow this process.

```text
1. Add new optional fields first.
2. Keep old fields for at least one integration cycle.
3. Record required-field or enum changes in docs/contracts/change_requests.md.
4. Update Developer B tests and sample payloads.
5. Notify Developer C before changing branch, state_delta, or final feedback I/O.
```
