# Alpha Scenario: IMMIGRATION_ALPHA

## Status

Scenario design draft for Alpha. This document describes how to extend the current immigration prototype; it is not a replacement scene and does not modify implementation files.

## Scenario ID

`IMMIGRATION_ALPHA`

## Placement

This scene follows the flight small-talk diagnostic and an arrival/cutscene transition.

```text
FLIGHT_001_SEATMATE_SMALLTALK
  -> cutscene: arrival / JFK airport transition
  -> IMMIGRATION_ALPHA
  -> BAGGAGE_MISSING
```

## Core Purpose

Use the already implemented immigration prototype as the Alpha immigration scene, but make the NPC behavior and difficulty adapt to the player's measured tier.

The current prototype already covers the immigration hall and baseline immigration questions. The Alpha work should preserve that foundation and add tier-sensitive behavior instead of creating a new unrelated flow.

## Existing Prototype To Preserve

The current immigration scenario should remain the base route:

```text
IMM_001_PASSPORT
  -> IMM_002_PURPOSE
  -> IMM_003_DURATION
  -> IMM_004_STAY_LOCATION
  -> IMM_005_RETURN_TICKET
  -> declaration / packed bag / final immigration resolution nodes
```

Preserve:

- current node IDs where possible
- current rule-based branch control
- current Developer B ownership of scenario progression and hint policy
- current Developer C validation and response assembly boundary
- current Developer A ownership of final NPC dialogue and TTS output

The Alpha change is difficulty adaptation, not a rewrite of the immigration flow.

## Input From Previous Scene

`IMMIGRATION_ALPHA` should receive the player's measured profile from `FLIGHT_001_SEATMATE_SMALLTALK`.

Expected profile fields:

- `tier`: `Bronze`, `Silver`, or `Gold`
- `travel_speaking_level`: `TSL_1_SURVIVAL`, `TSL_2_FUNCTIONAL`, `TSL_3_INDEPENDENT`, or `TSL_4_STRATEGIC`
- `difficulty_profile.npc_speech_speed`
- `difficulty_profile.question_complexity`
- `difficulty_profile.hint_frequency`
- `difficulty_profile.pressure_level`
- recent rubric score evidence, if available

This profile should affect NPC question style, follow-up strictness, hint frequency, and optional challenge injection. It should not bypass rule-based branch validation.

## Tier Policy Overview

### Bronze / Low Level

Bronze players should experience a version close to the current prototype's baseline difficulty.

NPC behavior:

- speak clearly and slightly slower than natural
- use short sentences and common words
- ask one clear question at a time
- avoid surprise hard situations
- accept broken English when the meaning is understandable
- tolerate minor grammar mistakes
- use clarification and hints earlier

Example NPC lines:

```text
Passport, please.
```

```text
What is the purpose of your visit?
```

```text
How many days will you stay?
```

```text
Where will you stay? Hotel? Friend's house?
```

Evaluation style:

- prioritize intent and required slot recovery
- allow partial success when the core meaning is clear
- use `clarify` or `hint` before high-pressure failure
- treat Korean/Konglish as recoverable if intent can be inferred

Bronze should not receive the sudden bag-content challenge unless another scenario flag makes it necessary.

### Silver / Mid Level

Silver players should receive the current immigration structure with moderate naturalness.

NPC behavior:

- speak at normal clear speed
- use normal travel English
- ask standard follow-up questions when answers are incomplete
- allow minor grammar errors if the answer is clear
- require key facts for purpose, duration, stay location, and return ticket

Example NPC lines:

```text
What is the purpose of your visit?
```

```text
How long will you be staying?
```

```text
Where are you staying while you're in New York?
```

```text
Do you have a return ticket?
```

Evaluation style:

- require the required intent and required slot
- use clarification for vague answers
- use retry when the player does not answer the question
- allow small errors if they do not change the meaning

Silver may receive mild follow-up questions, but not the strict Gold challenge chain by default.

### Gold / High Level

Gold players should receive a stricter and more realistic immigration interaction.

NPC behavior:

- speak at near-native, slightly fast speed
- use longer sentence structures
- ask direct follow-up questions
- introduce a moderately difficult situation when appropriate
- react strictly to vague, inconsistent, or evasive answers
- tolerate fewer mistakes, especially mistakes that affect facts or credibility

Example NPC lines:

```text
What exactly is the purpose of your visit, and how long do you plan to stay?
```

```text
Where will you be staying, and can you confirm whether you have a return flight booked?
```

```text
You said you're here for vacation, but your itinerary sounds unclear. Can you explain your plan more specifically?
```

```text
I'm going to ask you about your bags. What did you pack, and are you carrying anything you need to declare?
```

Evaluation style:

- require clear factual answers
- stricter handling of contradictions
- stricter handling of vague purpose, unclear duration, unknown accommodation, or no return plan
- small grammar mistakes are acceptable only when the facts remain clear
- repeated ambiguity should increase suspicion or trigger secondary inspection risk

Gold may receive the sudden bag-content challenge or declaration follow-up. This should feel like a realistic hard situation, not random punishment.

## Dynamic NPC Response Requirement

The current issue is that NPC replies are too fixed. Alpha immigration needs NPC replies to vary by tier and by player answer.

Required behavior:

- The officer's next line should reflect the player's actual answer, not only the node's static `npc_question`.
- If the player gives a clear answer, the officer should advance or ask a relevant next question.
- If the player gives a vague answer, the officer should ask for specificity.
- If the player gives a risky answer, the officer should become more formal or strict.
- If the player struggles at Bronze, the officer should simplify the question.
- If the player performs well at Gold, the officer can combine related checks or ask more natural follow-ups.

Developer B should provide the policy context that tells Developer A how strict, fast, complex, and hint-heavy the NPC line should be. Developer A should still generate the final dialogue and TTS style.

## Final Report Inputs

`IMMIGRATION_ALPHA` is the primary Alpha source for the out-game Focus-on-Form final report because it is structured, high-stakes, and already maps cleanly to Dev B's rubric and scenario nodes.

Developer B should capture final-report seeds from immigration turns when the player makes a meaningful form or clarity error. The capture should not change branch authority; it only feeds the later report service.

Recommended Focus-on-Form targets:

- `sentence_completion`: player answers with only a noun or fragment when a full sentence would be safer
- `purpose_statement`: player does not clearly state the visit purpose
- `duration_statement`: player gives vague stay length such as "maybe long"
- `stay_location_statement`: player cannot clearly say hotel, address, or host
- `return_ticket_statement`: player cannot confirm return ticket or return date clearly
- `declaration_explanation`: player gives an unclear explanation for declared item purpose
- `bag_content_explanation`: Gold challenge answer is vague, inconsistent, or missing key facts

Each final-report seed should preserve:

- scene ID: `IMMIGRATION_ALPHA`
- node ID
- original player utterance
- focus target key
- short Korean explanation
- suggested English expression
- severity or priority
- whether it should be included in the final report

Example report seed:

```json
{
  "scene_id": "IMMIGRATION_ALPHA",
  "node_id": "IMM_002_PURPOSE",
  "focus_target": "sentence_completion",
  "original_text": "tourism",
  "suggested_expression": "I'm here for tourism.",
  "explanation_kr": "입국심사에서는 단어만 말하기보다 짧은 완성 문장으로 답하는 것이 더 안전합니다.",
  "include_in_final_report": true
}
```

The final report itself should be generated after the Alpha segment or result screen, not during the immigration conversation.

## Suggested Alpha Route Variants

### Bronze Route

```text
IMM_001_PASSPORT
  -> IMM_002_PURPOSE
  -> IMM_003_DURATION
  -> IMM_004_STAY_LOCATION
  -> IMM_005_RETURN_TICKET
  -> IMM_ALPHA_FINAL_PASS
```

Characteristics:

- no surprise bag-content challenge
- easier vocabulary
- high tolerance for broken English
- hints available early
- pass is possible with simple but clear answers

### Silver Route

```text
IMM_001_PASSPORT
  -> IMM_002_PURPOSE
  -> IMM_003_DURATION
  -> IMM_004_STAY_LOCATION
  -> IMM_005_RETURN_TICKET
  -> IMM_006_DECLARATION_CHECK or final pass
```

Characteristics:

- current prototype baseline
- moderate clarification
- normal evaluation strictness
- optional declaration check if scenario flags require it

### Gold Route

```text
IMM_001_PASSPORT
  -> IMM_002_PURPOSE
  -> IMM_003_DURATION
  -> IMM_004_STAY_LOCATION
  -> IMM_005_RETURN_TICKET
  -> IMM_ALPHA_GOLD_BAG_CONTENT_CHECK
  -> IMM_ALPHA_GOLD_CONSISTENCY_CHECK
  -> IMM_ALPHA_FINAL_PASS or END_SECONDARY_INSPECTION
```

Characteristics:

- slightly fast speech
- more complex sentence structures
- sudden but plausible bag/declaration question
- stricter response to unclear or inconsistent English
- less hinting and more re-questioning

Gold-only nodes can be implemented as tier-gated extensions rather than replacing the existing route.

## Required Derived Implementation

Dev B-owned work:

- Extend scenario node metadata or policy logic so tier can affect question complexity, hint frequency, strictness, and optional challenge selection.
- Add or map tier-gated Alpha immigration challenge nodes, especially a Gold bag-content/declaration check.
- Ensure branch control remains rule-based and never LLM-overridden.
- Add tests for Bronze, Silver, and Gold immigration behavior.
- Add tests proving Bronze does not receive the Gold challenge by default.
- Add tests proving Gold can receive stricter clarification or challenge nodes.
- Add tests that `difficulty_profile` is available in the policy output.
- Add final-report seed capture for immigration form issues and clarity issues.
- Ensure Dev B output self-checks validate final-report seeds before OpenKB writes.
- Ensure optional LLM feedback may suggest report wording only and cannot change branch, verdict, next node, or state delta.

Cross-team coordination needed:

- Developer A needs enough difficulty context to vary NPC wording and TTS speed.
- Developer C needs to preserve and pass `difficulty_profile` from Developer B into the Developer A adapter if that is not already wired.
- If response schema changes are needed for speech speed, challenge metadata, or tier-gated UI cues, document them in `docs/contracts/change_requests.md`.

## Acceptance Criteria

- `IMMIGRATION_ALPHA` extends the current immigration prototype instead of replacing it.
- Bronze players receive easy wording, slower delivery, high tolerance, and no hard surprise challenge by default.
- Silver players receive the current baseline with moderate dynamic follow-ups.
- Gold players receive faster, more complex, stricter, and more realistic questioning.
- NPC replies are no longer only fixed static lines; they are conditioned by tier and player answer.
- Rule-based branch validation remains intact.
- Passing immigration leads to `BAGGAGE_MISSING`.
- Immigration turns can produce Focus-on-Form final-report seeds without showing an immediate out-game report.
