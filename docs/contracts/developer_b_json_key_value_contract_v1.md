# Developer B JSON Key-Value Contract v1

> AGENTS.md ?뺥빀??硫붾え: ??臾몄꽌??Developer B ?뚯쑀??JSON key-value 怨꾩빟 臾몄꽌?대떎. Developer B???됯?, ?덈꺼/?뚰듃, ?멸쾶???쇰뱶諛??꾨왂, ?ㅻ쪟 湲곕줉 ?꾨낫, ?꾩썐寃뚯엫 Focus on Form ?쇰뱶諛?payload, rule-based branch recommendation???뺤쓽?쒕떎. FastAPI endpoint, STT/TTS, NPC 理쒖쥌 ????앹꽦, Validator, Unreal response assembly, markdown ?뚯씪 ????ㅽ뻾, OpenKB retrieval ?ㅽ뻾? Developer C ?먮뒗 ?ㅻⅨ ?대떦 踰붿쐞?대떎.

## 1. 臾몄꽌 紐⑹쟻

??臾몄꽌???꾩뾽?먯꽌 API/adapter 怨꾩빟??留욎텧 ???ъ슜?섎뒗 ?뺤떇?쇰줈 Developer B policy??JSON key-value ?쎌냽???뺤쓽?쒕떎.

??臾몄꽌???ㅼ쓬 ?ъ슜?먮? ??곸쑝濡??쒕떎.

- Developer B 援ы쁽??- Developer C adapter 援ы쁽??- Developer A NPC dialogue 援ы쁽??- Unreal UI ?곕룞 ?대떦??- QA / test case ?묒꽦??- LLM agent媛 怨꾩빟??李멸퀬??payload瑜??앹꽦?섍굅??寃?좏븯??寃쎌슦

??臾몄꽌???ㅻ챸??湲고쉷?쒓? ?꾨땲??怨꾩빟 臾몄꽌?대떎. ?곕씪??媛?key???대쫫, ??? ?꾩닔 ?щ?, ?덉슜 enum, ?앹꽦 二쇱껜, ?뚮퉬 二쇱껜, 寃利?洹쒖튃??怨좎젙?쒕떎.

## 2. Scope

### 2.1 In Scope

Developer B媛 ?뺤쓽?섍굅??諛섑솚?섎뒗 ?곗씠??

- `evaluation`
- `level_hint`
- `in_game_feedback`
- `error_capture`
- `out_game_feedback_seed`
- `report_seed_summary`
- `dialogue_seed`
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

Developer B媛 留뚮뱾吏 ?딅뒗 ?곗씠??

- raw audio / wav binary
- STT provider result ?먮낯
- NPC 理쒖쥌 ???蹂몃Ц
- TTS voice id
- Unreal command
- animation / camera event
- final API response envelope
- validator result
- markdown ?뚯씪 ?ㅼ젣 ???- OpenKB 寃???ㅽ뻾
- DB write

## 3. Naming Convention

| ??ぉ | 洹쒖튃 |
| --- | --- |
| JSON key | `snake_case` |
| ID value | ?臾몄옄 prefix + underscore 沅뚯옣. ?? `IMM_002_PURPOSE` |
| enum value | 湲곗〈 寃뚯엫 enum怨?留욎텧 ?뚮뒗 `UPPER_SNAKE_CASE`, B ?대? branch type? `lower_snake_case` |
| boolean key | `is_`, `has_`, `needs_`, `should_`, `can_` 以??섎굹濡??쒖옉 |
| timestamp | ISO-8601 string. ?? `2026-06-02T10:30:00+09:00` |
| nullable | optional怨?null??援щ텇?쒕떎. key媛 ?섎????꾩슂?섏?留?媛믪씠 ?놁쑝硫?`null`, ?섎?媛 ?놁쑝硫?key ?앸왂 媛??|
| score | 0-3 scale ?먮뒗 0-100 scale 以??꾨뱶蹂꾨줈 怨좎젙?쒕떎 |
| text language suffix | ?쒓뎅???ъ슜???쒖떆臾몄? `_kr`, ?곸뼱 ?덈Ц? `_en` suffix ?ъ슜 |

## 4. Contract Versioning

紐⑤뱺 Developer B policy input/output?먮뒗 媛?ν븯硫?`contract_version`???ы븿?쒕떎.

```json
{
  "contract_version": "dev_b_policy.v1",
  "schema_owner": "developer_b",
  "schema_status": "draft"
}
```

Versioning 洹쒖튃:

- patch 蹂寃? ?꾨뱶 ?ㅻ챸, ?덉떆 異붽?, optional field 異붽?
- minor 蹂寃? enum 異붽?, optional object 異붽?
- major 蹂寃? required field ??젣/?대쫫 蹂寃????蹂寃?
## 5. Developer B Policy Input

Developer C adapter媛 Developer B policy???꾨떖?섎뒗 canonical input?대떎.

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
    "base_hint_kr": "誘멸뎅????紐⑹쟻??留먰빐蹂댁꽭??",
    "hint_policy": {
      "keyword": [
        "tourism",
        "business",
        "vacation"
      ],
      "sentence_pattern": "I'm here for ___.",
      "situation_hint": "諛⑸Ц 紐⑹쟻??留먰빐???⑸땲??",
      "action_hint": "諛⑸Ц 紐⑹쟻??癒쇱? 留먰븯怨? ?꾩슂?섎㈃ ?댁쑀瑜?吏㏐쾶 ?㏓텤?낅땲??"
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
| `chapter_id` | string | yes | Unreal/C | Scenario phase id. Alpha immigration value: `CH0_03_IMMIGRATION_CHECK` |
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
    "feedback_note": "諛⑸Ц 紐⑹쟻? ?꾨떖?먯?留??꾩쟾??臾몄옣?쇰줈 留먰븯硫????먯뿰?ㅻ읇?듬땲??"
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
        "intended_meaning_kr": "愿愿?紐⑹쟻?쇰줈 ?붾떎怨?留먰븯?ㅺ퀬 ?덉뒿?덈떎.",
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
    "markdown_entry": "### IMM_002_PURPOSE - err_imm_002_001\n- NPC Question: What is the purpose of your visit?\n- Original: I here tourism.\n- Intended Meaning: 愿愿?紐⑹쟻?쇰줈 ?붾떎怨?留먰븯?ㅺ퀬 ?덉뒿?덈떎.\n- Error Type: grammar\n- Focus on Form: be_verb_in_self_introduction\n- Suggested: I'm here for tourism.\n- Severity: minor"
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
    "summary": "諛⑸Ц 紐⑹쟻???꾨떖?덉뒿?덈떎.",
    "improvement": "?⑥뼱 ?섎굹蹂대떎 ?꾩쟾??臾몄옣?쇰줈 留먰븯硫????먯뿰?ㅻ읇?듬땲??",
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

### 7.6A `report_seed_summary`

`report_seed_summary` is optional and additive. It is seed metadata for a final
report assembler or Unreal UI, not a completed final result UI payload.

| Key | Type | Required when present | Description |
| --- | --- | --- | --- |
| `estimated_level` | string | yes | Candidate level: `beginner`, `intermediate`, `advanced` |
| `tier` | string | yes | `Bronze`, `Silver`, or `Gold` |
| `scenario_result` | string | yes | Candidate result: `passed`, `conditional_pass`, `failed` |
| `overall_score_candidate` | integer | yes | 0-100 score candidate, not a certified final score |
| `category_scores` | object | yes | 0-100 task, clarity, grammar, vocabulary, politeness, problem-solving candidates |
| `strengths` | array<object> | yes | Positive evidence ordered by `ui_priority` |
| `critical_breakdowns` | array<object> | yes | Most important communication-blocking issues only |
| `corrected_examples` | array<object> | yes | Original utterance, corrected sentence, short explanation, reusable pattern |
| `reusable_sentence_patterns` | array<string> | yes | Practice patterns for the result screen |
| `next_practice_goal` | string | yes | Next short learning goal |
| `feedback_focus` | array<string> | yes | Tags or dimensions for report assembly |
| `ui_priority_order` | array<string> | yes | Recommended display ordering |
| `display_policy_by_tier` | object | yes | Bronze/Silver/Gold density guidance |

### 7.6B `dialogue_seed`

`dialogue_seed` is optional and additive. It gives Developer A purpose, target,
slot, and tone metadata for dialogue generation. It must not contain final NPC
utterance text.

Forbidden keys in Developer B output include `npc_text`, `npc_utterance`, and
`final_dialogue_line`.

| Key | Type | Required when present | Description |
| --- | --- | --- | --- |
| `scene` | string | yes | Scene id or scene key |
| `npc_role` | string | yes | Role cue for Developer A |
| `surface_goal` | string | yes | Visible interaction goal |
| `hidden_assessment_goal` | string | yes | Learning/diagnostic goal |
| `opening_intent` | string | yes | Intent id that A may realize in its own wording |
| `assessment_targets` | array<string> | yes | Intents, slots, and critical targets B needs evidence for |
| `required_slots` | array<string> | yes | Slots that drive rule-based B evaluation |
| `max_turns` | integer | yes | Suggested local exchange turn budget |
| `difficulty_profile` | string | yes | Current value: `auto` |
| `feedback_focus` | array<string> | yes | Feedback dimensions to preserve |
| `tone_guidance` | string | yes | Tone cue, not final wording |
| `allowed_followup_intents` | array<string> | yes | Follow-up intent ids A may realize |
| `stop_condition` | string | yes | Stop condition for the local exchange |

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
  "chapter_id": "CH0_03_IMMIGRATION_CHECK",
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
      "rule_summary_kr": "?곸뼱?먯꽌 ?먯떊??紐⑹쟻?대굹 ?곹깭瑜?留먰븷 ?뚮뒗 二쇱뼱 ?ㅼ뿉 be ?숈궗瑜??ｌ뼱 臾몄옣???꾩꽦?⑸땲??",
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
    "overall_summary_kr": "?낃뎅?ъ궗 吏덈Ц???듭떖 ?섎????꾨떖?덉?留? 吏㏃? ?듬??먯꽌 be ?숈궗 ?꾨씫??諛섎났?섏뿀?듬땲??",
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
        "title_kr": "I'm here for ___ ?⑦꽩",
        "original_utterance": "I here tourism.",
        "corrected_expression": "I'm here for tourism.",
        "explanation_kr": "諛⑸Ц 紐⑹쟻??留먰븷 ?뚮뒗 `I'm here for + 紐⑹쟻` ?⑦꽩???곕㈃ ?먯뿰?ㅻ읇?듬땲??",
        "openkb_source_tags": [
          "immigration_visit_purpose",
          "be_verb",
          "travel_purpose_expression"
        ],
        "micro_practice": {
          "prompt_kr": "異쒖옣 紐⑹쟻?쇰줈 ?붾떎怨?留먰빐蹂댁꽭??",
          "answer_example": "I'm here for a business meeting."
        }
      }
    ],
    "personalized_next_step": {
      "focus_kr": "吏㏃? ?⑥뼱 ?듬????꾩쟾??臾몄옣?쇰줈 ?뺤옣?섍린",
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
    "summary": "諛⑸Ц 紐⑹쟻???꾨떖?덉뒿?덈떎.",
    "improvement": "?꾩옱 ?듬?? 吏꾪뻾??異⑸텇?⑸땲??",
    "example_answer": "I'm here for tourism.",
    "score_tags": [
      "task_success_good"
    ]
  }
}
```

## 14. Alpha Dev B Scenario Node Flow

Developer B owns the Alpha scenario node definitions for language assessment and
branch recommendation only. Menu screens, cutscenes, movement, Unreal UI, final
NPC utterances, and TTS remain outside this node contract.

Current Alpha Dev B scenario-node file contract is
`dev_b_scenario_nodes.v2`. The top-level `scenario_id` is
`ALPHA_AIRPORT_ARRIVAL`; `chapter_id` is now the ordered in-scenario phase
boundary rather than a whole-scenario namespace.

Chapter order:

```text
CH0_01_FLIGHT_SMALLTALK
-> CH0_02_ARRIVAL_TUTORIAL
-> CH0_03_IMMIGRATION_CHECK
-> CH0_04_BAGGAGE_CLAIM
-> CH0_05_RESULT
```

`CH0_01_FLIGHT_SMALLTALK` has three 5-turn diagnostic route candidates. The
current default `entry_node_id` remains `FLIGHT_A_001_SEATMATE_SMALLTALK` for
backward compatibility, and `entry_node_ids` lists all supported route starts:

```text
FLIGHT_A_001_SEATMATE_SMALLTALK
FLIGHT_B_001_DESTINATION_CHAT
FLIGHT_C_001_FORM_HELP_REQUEST
```

Current Alpha Dev B node flow:

```text
Route A - Friendly Seatmate:
FLIGHT_A_001_SEATMATE_SMALLTALK
-> FLIGHT_A_002_TRAVEL_PURPOSE
-> FLIGHT_A_003_STAY_PLAN
-> FLIGHT_A_004_CLARIFY_OR_ASK_BACK
-> FLIGHT_A_005_WRAP_UP
-> FLIGHT_999_COMPLETE

Route B - Curious Seatmate:
FLIGHT_B_001_DESTINATION_CHAT
-> FLIGHT_B_002_COMPANION_OR_VISIT
-> FLIGHT_B_003_STAY_PLACE
-> FLIGHT_B_004_TRIP_PLANS
-> FLIGHT_B_005_LANDING_CLOSE
-> FLIGHT_999_COMPLETE

Route C - Travel Form Help:
FLIGHT_C_001_FORM_HELP_REQUEST
-> FLIGHT_C_002_FIRST_TIME_ENTRY
-> FLIGHT_C_003_ADDRESS_HELP
-> FLIGHT_C_004_HOTEL_HOSTEL_REPAIR
-> FLIGHT_C_005_FORM_CLOSE
-> FLIGHT_999_COMPLETE

After flight completion:
FLIGHT_999_COMPLETE
-> Unreal airport-arrival tutorial/movement
-> IMM_001_PASSPORT
-> existing IMM_* route
-> IMM_007_FINAL_DECISION
-> IMM_999_CLEARED
-> BAG_001_REPORT_MISSING_AT_DESK
-> BAG_002_PROVIDE_CLAIM_TAG
-> BAG_003_CONFIRM_SEARCHED_CAROUSEL
-> BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD
-> BAG_005_CUSTOMS_HOLD_EXPLANATION
-> Unreal unlock/open suitcase + random customs item reveal
-> BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM
-> BAG_007_CUSTOMS_CLEARANCE
-> BAG_999_COMPLETE
-> ALPHA_999_FINAL_SCOREBOARD
```

Flight nodes are diagnostic samples. They should advance to the next evidence
node even when the answer needs retry, clarification, or a hint. Immediate
out-game feedback remains disallowed for the flight scene; records are deferred
to the final Alpha report.

`FLIGHT_999_COMPLETE`, `IMM_999_CLEARED`, and `BAG_999_COMPLETE` have
`node_type = transition`. They are not speech-turn targets. When a dialogue
node branches to one of them, Developer B returns `next_action =
COMPLETE_CHAPTER`, and Developer C exposes the transition metadata to Unreal.

`IMM_007_FINAL_DECISION` is an immigration-clearance dialogue node that now
branches to `IMM_999_CLEARED` on success. `ALPHA_999_FINAL_SCOREBOARD` is the
Dev B final-branch node for scenario-end scoring.

## 15. Change Control

## 15.1 Final Result Score Payload

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

- Each rubric dimension is converted from 0-2 to 0-100.
- Alpha v1 uses scene-normalized dimension averages with default weights:
  flight 20%, immigration 50%, baggage 30%.
- `IMM_007_FINAL_DECISION` and `ALPHA_999_FINAL_SCOREBOARD` are excluded when
  earlier scored nodes exist.
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
