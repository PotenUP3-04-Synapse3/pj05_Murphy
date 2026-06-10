# Alpha Scenario: FLIGHT_001_SEATMATE_SMALLTALK

## Status

Scenario design draft for Alpha. This document is a Markdown scenario artifact only; it does not modify implementation files.

## Scenario ID

`FLIGHT_001_SEATMATE_SMALLTALK`

## Placement

This is the opening Alpha scene. The player starts inside an airplane before arriving in the United States. The scene happens before the immigration hall and before any immediate tutorial or feedback screen. Developer B still records deferred evaluation and `out_game_feedback_seed` data for the scenario-end report.

```text
Alpha start
  -> FLIGHT_001_SEATMATE_SMALLTALK
  -> cutscene: arrival / airport transition
  -> IMMIGRATION_ALPHA
```

## Core Purpose

Measure the player's English level through natural small talk with the passenger seated next to them. The scene does not have a pass/fail success condition. Whether the conversation is smooth, awkward, incomplete, or broken, Developer B should still collect enough language signals to estimate the player's tier and Travel Speaking Level.

The player should feel like they are casually talking to a friendly stranger, not being tested.

## NPC Profile

- NPC name: `Emily Carter`
- Role: adjacent passenger on the flight to the United States
- Identity: American white blonde woman
- Personality: very friendly, warm, patient, and socially easygoing
- Tone: casual, gentle, encouraging, never mocking
- Speaking style: clear everyday English, natural but not fast
- Narrative function: create a low-pressure first conversation that lets the system observe comprehension, fluency, grammar, vocabulary, clarity, and interaction problem solving

The NPC's identity is a character setting, not a stereotype. Her behavior should be driven by friendliness and warmth, not by race or appearance.

## Scene Rules

In this document, one "turn" means one player response after an NPC line.

- Minimum required length: 3 player turns
- Minimum exchange pattern:

```text
NPC -> player -> NPC -> player -> NPC -> player
```

- If the conversation naturally continues for 5 or more player turns, show a `skip` button at the bottom right of the screen.
- The skip button should let the player move to the next scene without penalizing them.
- There is no immediate out-game feedback screen after this scene.
- Developer B should create a deferred `out_game_feedback_seed` for the final scenario-end report.
- The player should not see a score, grade, correction screen, or focus-on-form report immediately after the flight small talk.
- The measured tier should silently affect later Alpha difficulty, especially `IMMIGRATION_ALPHA`.

## Opening Beat

The seatmate starts the interaction, so the player does not need to initiate.

Example opening line:

```text
Hi there. Long flight, huh? Are you heading to New York for a trip?
```

Alternative opening lines:

```text
Hi. I think we're almost there. Is this your first time flying to the States?
```

```text
Hey, sorry to bother you. Are you visiting New York, or just connecting through?
```

The first line should invite a short answer but also leave room for the player to expand.

## Dynamic Conversation Policy

This scene should not be implemented as a fixed dialogue script. The NPC should continue the conversation by responding to the player's actual content.

Expected behavior:

- If the player says they are traveling for tourism, ask about places, food, plans, or whether it is their first visit.
- If the player says they are visiting family or friends, ask where they live or whether the player has visited before.
- If the player says they are traveling for business or study, ask about the work, school, city, or length of stay.
- If the player answers with very short English, keep the conversation easy and supportive.
- If the player uses Korean or Konglish, infer intent where possible and keep the conversation moving.
- If the player gives a confident longer answer, the NPC can ask richer follow-up questions.
- If the player gives an unclear answer, the NPC should ask a simple clarification instead of ending the scene.

The NPC should avoid interrogating the player like an officer. This is small talk, so the emotional pacing should be relaxed.

## Fallback Question Pool

The scene needs fallback questions because Developer B may need more language evidence for level measurement. Use these when the conversation stalls, the player gives only one-word answers, or the NPC cannot find a natural follow-up.

```text
Is this your first time in America?
```

```text
How long will you stay?
```

```text
Are you traveling alone?
```

```text
What food do you want to try?
```

```text
Do you have any plans after you land?
```

```text
Are you nervous about immigration?
```

```text
Do you speak English often in Korea?
```

Fallback rules:

- Use short questions first.
- Do not repeat the same fallback question in one run.
- Do not ask more than one fallback question per NPC line.
- If the player is struggling, prefer concrete topics: first visit, food, hotel, plans.
- If the player is fluent, prefer open-ended topics: travel expectations, previous experiences, what they are looking forward to.

## Level Measurement Signals

Developer B should treat this scene as a diagnostic sample. It should collect language signals without using a strict scenario success gate.

Primary signals:

- Comprehension: does the player answer the question being asked?
- Fluency: can the player produce more than isolated words?
- Grammar accuracy: are errors understandable, minor, or disruptive?
- Vocabulary range: can the player discuss travel, plans, time, purpose, and feelings?
- Clarity: can the system understand the player's intent?
- Interaction problem solving: can the player recover when asked a follow-up or clarification?

Suggested broad interpretation:

- Bronze: short or broken English, partial answers, high reliance on simple prompts, intent still recoverable
- Silver: mostly understandable travel small talk, some grammar issues, can answer follow-ups with moderate support
- Gold: natural multi-clause responses, can answer unexpected follow-ups, low ambiguity, no repeated support needed

The result should update the player's internal profile before immigration. It should not display a rating to the player at this point.

## Final Report And Feedback Policy

This scene has a strict no-immediate-feedback-display rule and a required deferred-feedback-seed rule.

After `FLIGHT_001_SEATMATE_SMALLTALK`, the player must not see:

- an out-game feedback screen
- Focus-on-Form cards
- grammar corrections
- a score screen
- a visible tier or TSL result

Developer B must still keep diagnostic evidence internally so the later Alpha flow can adapt and the scenario-end report can include the small-talk sample. That evidence is not shown immediately. It is written as a deferred `out_game_feedback_seed` and consumed only when the full Alpha scenario ends.

Because the player is not told this is a test during the flight scene, the final report should present this evidence as a gentle calibration sample, not as a surprise grading event. The report tone should emphasize practical travel communication, for example whether the player could answer casual questions clearly and keep a friendly exchange moving.

Allowed final-report use:

- update the player's silent `tier`
- update `travel_speaking_level`
- update aggregate rubric evidence
- contribute to scenario-end `evaluation`
- contribute to scenario-end `out_game_feedback`
- explain the final Alpha difficulty selection if the final report needs a short level summary

Disallowed immediate use:

- do not create a visible `out_game_feedback` response after this scene
- do not show correction cards immediately after this scene
- do not interrupt the cutscene transition with a learning report

Scenario-end use:

- create an `out_game_feedback_seed` target such as `smalltalk_response_clarity`
- include the small-talk record in scene-normalized rubric scoring so longer small-talk runs do not dominate the final score
- show the player the final `evaluation` and `out_game_feedback` only after the full scenario has ended
- keep the final report tone broad and practical, for example "You handled casual travel small talk with short but understandable answers."
- prefer a summary-style final note over correction-heavy cards unless the same small-talk issue appears repeatedly across later scenes

## Exit Conditions

The scene can end when one of the following is true:

- The player has completed at least 3 player turns and the system has enough evidence for level estimation.
- The player has completed 5 or more player turns and chooses the skip button.
- The conversation reaches a natural closing line after enough diagnostic evidence has been collected.

Example closing line:

```text
Well, I hope you have a great trip. Looks like we're landing soon.
```

After exit, play the arrival/cutscene transition and move into `IMMIGRATION_ALPHA`.

## Required Derived Implementation

Dev B-owned work:

- Add a flight small-talk scenario definition when implementation begins.
- Add diagnostic evaluation behavior: no pass/fail branch, deferred `out_game_feedback_seed`, and updated tier/TSL evidence.
- Add tests that verify the minimum 3 player turns, 5-turn skip eligibility, fallback question behavior, and deferred `out_game_feedback_seed` output.
- Ensure the policy output can carry a measured `tier`, `travel_speaking_level`, `rubric_scores`, and `difficulty_profile` into later scenes.
- Ensure Dev B self-checks allow deferred final-report seeds but do not imply immediate feedback display.
- Ensure AgentRun logging marks this scene as diagnostic-only so later debugging can distinguish it from scored scenario nodes.

Cross-team coordination needed:

- Developer A should generate the actual NPC lines from the small-talk policy and NPC profile.
- Developer C should orchestrate the cutscene transition, skip button signal, and scene transition into immigration.
- Developer C should show scenario-end `evaluation` and `out_game_feedback` after the full Alpha scenario, not after this scene.
- If new request/response fields are required for skip eligibility, silent level carryover, scenario-end `evaluation`, or scenario-end `out_game_feedback`, document them in `docs/contracts/change_requests.md` before changing contracts.

## Acceptance Criteria

- The scene starts with a friendly seatmate line.
- The player must answer at least 3 times before normal completion.
- Conversation follow-ups are dynamic and based on player content.
- Fallback questions are available when the conversation stalls.
- A skip button becomes eligible only after 5 or more player turns.
- No immediate out-game feedback appears after the scene.
- A deferred `out_game_feedback_seed` is available for the final scenario-end report.
- A player level estimate is available for `IMMIGRATION_ALPHA`.
- Final-report use of this scene is delayed until the full Alpha scenario ends.
- Final-report wording treats this scene as a low-pressure calibration sample, not as an immediate pass/fail test.
