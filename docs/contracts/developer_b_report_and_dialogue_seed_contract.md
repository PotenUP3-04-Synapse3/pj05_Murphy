# Developer B Report and Dialogue Seed Contract

## 1. Purpose

This document defines optional Developer B seed metadata on
`DevBPolicyOutput`.

It is not a final result screen UI payload contract. Developer B provides
learning, feedback, and dialogue-generation seeds only. Final screen rendering
belongs to Unreal UI or a future final report assembler. Developer C remains
responsible for adapter validation, response assembly, logging, and returning an
Unreal-safe response.

Scenario node expansion, Chapter renaming, and IMM node-id changes are outside
this contract.

## 2. Ownership

| Area | Owner | Responsibility |
| --- | --- | --- |
| `report_seed_summary` | Developer B | Candidate report metadata, feedback focus, score candidates, reusable patterns |
| `out_game_feedback_seed` | Developer B | OpenKB retrieval tags and Focus-on-Form target ids |
| `dialogue_seed` | Developer B | Purpose, assessment targets, slots, difficulty cue, and follow-up intents |
| NPC dialogue text | Developer A | Final NPC line, tone realization, TTS/audio, and voice output |
| Adapter and validation | Developer C | Validate B output, preserve branch authority, assemble response |
| Final UI layout | Unreal or final report assembler | Compose final screen from validated seeds |

Developer B must not produce `npc_text`, `npc_utterance`, or
`final_dialogue_line`.

## 3. Report Seed Fields

`report_seed_summary` is optional at the `DevBPolicyOutput` top level. When
present, its nested fields are required unless marked optional below.

| Field | Required when present | UI-displayable | Internal/debug | Meaning |
| --- | --- | --- | --- | --- |
| `estimated_level` | yes | yes | no | Candidate English level: `beginner`, `intermediate`, `advanced` |
| `tier` | yes | yes | no | Player tier: `Bronze`, `Silver`, `Gold` |
| `scenario_result` | yes | yes | no | Candidate result: `passed`, `conditional_pass`, `failed` |
| `overall_score_candidate` | yes | yes | no | 0-100 candidate score, not a final certified score |
| `category_scores` | yes | yes | no | 0-100 candidate scores for task success, clarity, grammar, vocabulary, politeness, and problem solving |
| `strengths` | yes | yes | no | Positive evidence items, ordered by `ui_priority` |
| `critical_breakdowns` | yes | yes | no | Up to the most important communication-blocking issues |
| `corrected_examples` | yes | yes | no | Original utterance, safer correction, brief explanation, reusable pattern |
| `reusable_sentence_patterns` | yes | yes | no | Sentence frames that can be practiced again |
| `next_practice_goal` | yes | yes | no | Short goal derived from the B report item |
| `feedback_focus` | yes | optional | yes | Tags or dimensions useful for UI grouping and report assembly |
| `ui_priority_order` | yes | optional | yes | Recommended display ordering for a final screen assembler |
| `display_policy_by_tier` | yes | optional | yes | Density guidance for Bronze, Silver, and Gold displays |

Tier display guidance:

| Tier | Display policy |
| --- | --- |
| Bronze | Show simple corrections and reusable sentence patterns first |
| Silver | Show correction, reason, and one grammar explanation |
| Gold | Show naturalness, politeness, and contextual nuance |

## 4. Dialogue Seed Fields

`dialogue_seed` is optional at the `DevBPolicyOutput` top level. It is metadata
for Developer A's Dialogue Agent. It is not a script and must not be treated as
final NPC wording.

| Field | Required when present | Use |
| --- | --- | --- |
| `scene` | yes | Scene id or scene key that frames the interaction |
| `npc_role` | yes | Role cue such as `immigration_officer`, `seatmate_passenger`, or `baggage_service_agent` |
| `surface_goal` | yes | What the NPC appears to be trying to accomplish |
| `hidden_assessment_goal` | yes | Learning/diagnostic purpose behind the exchange |
| `opening_intent` | yes | Initial intent the Dialogue Agent may realize in its own words |
| `assessment_targets` | yes | Intents, slots, and risk targets B needs evidence for |
| `required_slots` | yes | Slots that determine B's rule-based task evaluation |
| `max_turns` | yes | Suggested turn budget for this local exchange |
| `difficulty_profile` | yes | Difficulty cue. Current value is `auto`; detailed metadata remains in `difficulty_profile` |
| `feedback_focus` | yes | Dimensions the Dialogue Agent can preserve while generating prompts |
| `tone_guidance` | yes | Tone cue, not final wording |
| `allowed_followup_intents` | yes | Follow-up intent ids Developer A may realize in dialogue |
| `stop_condition` | yes | Condition for stopping local dialogue collection |

Developer B controls assessment targets and slots. Developer A controls actual
NPC text, tone realization, TTS text, audio, and animation.

For Alpha flight small talk, Developer B now provides three 5-turn diagnostic
route candidates:

```text
Route A:
FLIGHT_A_001_SEATMATE_SMALLTALK
-> FLIGHT_A_002_TRAVEL_PURPOSE
-> FLIGHT_A_003_STAY_PLAN
-> FLIGHT_A_004_CLARIFY_OR_ASK_BACK
-> FLIGHT_A_005_WRAP_UP

Route B:
FLIGHT_B_001_DESTINATION_CHAT
-> FLIGHT_B_002_COMPANION_OR_VISIT
-> FLIGHT_B_003_STAY_PLACE
-> FLIGHT_B_004_TRIP_PLANS
-> FLIGHT_B_005_LANDING_CLOSE

Route C:
FLIGHT_C_001_FORM_HELP_REQUEST
-> FLIGHT_C_002_FIRST_TIME_ENTRY
-> FLIGHT_C_003_ADDRESS_HELP
-> FLIGHT_C_004_HOTEL_HOSTEL_REPAIR
-> FLIGHT_C_005_FORM_CLOSE
```

Each route uses `dialogue_seed.max_turns = 5` and should be realized by
Developer A as natural seatmate small talk. Developer B still provides only
goals, slots, assessment targets, and follow-up intents.

## 5. UI Assembly Guide

The default final-screen composition can use these seeds as follows:

| Screen area | Candidate fields |
| --- | --- |
| Top | `scenario_result`, `tier`, `overall_score_candidate` |
| Middle | `category_scores` |
| Bottom | `strengths`, `critical_breakdowns`, `corrected_examples`, `next_practice_goal` |
| Detail view | `user_utterance`, `corrected`, `brief_explanation`, `reusable_pattern` |

The default screen should expose at most three critical feedback items. Additional
items can be placed behind a detail view. The final assembler may combine these
seeds with OpenKB Focus-on-Form records, previous node results, and final score
policy output.

## 6. Sample Payloads

Beginner report seed sample:

```json
{
  "report_seed_summary": {
    "estimated_level": "beginner",
    "tier": "Bronze",
    "scenario_result": "passed",
    "overall_score_candidate": 72,
    "category_scores": {
      "task_success": 100,
      "clarity": 67,
      "grammar": 33,
      "vocabulary": 67,
      "politeness": 100,
      "problem_solving": 67
    },
    "strengths": [
      {
        "title": "Core answer understood",
        "evidence": "The required immigration answer was understood.",
        "ui_priority": 1
      }
    ],
    "critical_breakdowns": [
      {
        "user_utterance": "Travel. New York.",
        "issue_type": "grammar",
        "why_it_matters": "A clearer complete sentence helps the listener understand the travel answer quickly.",
        "better_version": "I'm here for tourism.",
        "reusable_pattern": "I'm here for ___.",
        "ui_priority": 1
      }
    ],
    "corrected_examples": [
      {
        "original": "Travel. New York.",
        "corrected": "I'm here for tourism.",
        "brief_explanation": "Use a complete sentence for a more natural answer.",
        "pattern": "I'm here for ___."
      }
    ],
    "reusable_sentence_patterns": [
      "I'm here for ___.",
      "I'm here for tourism."
    ],
    "next_practice_goal": "Use a complete sentence for a more natural answer.",
    "feedback_focus": [
      "visit_purpose",
      "sentence_completion"
    ],
    "ui_priority_order": [
      "scenario_result",
      "overall_score_candidate",
      "category_scores",
      "strengths",
      "critical_breakdowns",
      "corrected_examples",
      "next_practice_goal"
    ],
    "display_policy_by_tier": {
      "Bronze": "show simple correction and reusable sentence patterns first",
      "Silver": "show correction, reason, and one grammar explanation",
      "Gold": "show naturalness, politeness, and contextual nuance"
    }
  }
}
```

Intermediate report seed sample:

```json
{
  "report_seed_summary": {
    "estimated_level": "intermediate",
    "tier": "Silver",
    "scenario_result": "conditional_pass",
    "overall_score_candidate": 78,
    "category_scores": {
      "task_success": 67,
      "clarity": 67,
      "grammar": 67,
      "vocabulary": 67,
      "politeness": 100,
      "problem_solving": 67
    },
    "strengths": [
      {
        "title": "Required information provided",
        "evidence": "stay_duration",
        "ui_priority": 1
      }
    ],
    "critical_breakdowns": [
      {
        "user_utterance": "Maybe five days, I think.",
        "issue_type": "clarity",
        "why_it_matters": "A clearer complete sentence helps the listener understand the travel answer quickly.",
        "better_version": "I will stay for five days.",
        "reusable_pattern": "I will stay for ___ days.",
        "ui_priority": 1
      }
    ],
    "corrected_examples": [
      {
        "original": "Maybe five days, I think.",
        "corrected": "I will stay for five days.",
        "brief_explanation": "Answer the exact question with a complete stay-duration sentence.",
        "pattern": "I will stay for ___ days."
      }
    ],
    "reusable_sentence_patterns": [
      "I will stay for ___ days."
    ],
    "next_practice_goal": "Give the duration directly before adding extra details.",
    "feedback_focus": [
      "stay_duration"
    ],
    "ui_priority_order": [
      "scenario_result",
      "overall_score_candidate",
      "category_scores",
      "strengths",
      "critical_breakdowns",
      "corrected_examples",
      "next_practice_goal"
    ],
    "display_policy_by_tier": {
      "Bronze": "show simple correction and reusable sentence patterns first",
      "Silver": "show correction, reason, and one grammar explanation",
      "Gold": "show naturalness, politeness, and contextual nuance"
    }
  }
}
```

Dialogue seed sample. This is not production NPC text:

```json
{
  "dialogue_seed": {
    "scene": "JFK_IMMIGRATION_HALL",
    "npc_role": "immigration_officer",
    "surface_goal": "state_visit_purpose",
    "hidden_assessment_goal": "estimate_user_travel_speaking_level",
    "opening_intent": "ask_visit_purpose",
    "assessment_targets": [
      "state_visit_purpose",
      "visit_purpose",
      "illegal_work_intent"
    ],
    "required_slots": [
      "visit_purpose"
    ],
    "max_turns": 4,
    "difficulty_profile": "auto",
    "feedback_focus": [
      "visit_purpose",
      "sentence_completion"
    ],
    "tone_guidance": "neutral_official",
    "allowed_followup_intents": [
      "ask_visit_purpose",
      "advance_to_next_prompt",
      "offer_reassurance"
    ],
    "stop_condition": "required_slots_filled_or_retry_policy_triggered"
  }
}
```

## 7. Migration and Future Work

- Current implementation is a seed-providing phase, not final report generation.
- A future Developer C service or separate Final Report Assembler may aggregate
  these seeds across turns and combine them with final score policy output.
- `ALPHA_999_FINAL_SCOREBOARD` is the Dev B final-branch seed point for Alpha
  scenario-end reporting. Dev C still needs to adopt that runtime trigger.
- Existing `dialogue_directive` remains for backward compatibility. New
  integrations should prefer `dialogue_seed` for A-facing generation metadata.
- LLM-assisted Developer B output may enrich hint text, feedback text, rubric
  candidates, report seed candidates, and dialogue seed candidates only.
- LLM-assisted output must not override `branch`, `next_node_id`, `next_action`,
  `evaluation.verdict`, `state_delta`, Unreal commands, final NPC text, TTS,
  audio, tone realization, or animation.
