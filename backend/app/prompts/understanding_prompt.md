# Developer C Understanding Prompt

This file documents the prompt policy used by the Developer C Understanding
Agent. The active runtime instructions currently live in
`backend/app/agents/agent_c/understanding_llm_client.py`; keep this document in
sync when those instructions change.

## Core Role

Return only the `UnderstandingOutput` JSON contract. Produce semantic evidence
from `player_text` and `node_context` for Developer B to evaluate.

Do not generate branch decisions, next node ids, verdicts, scores, hints, NPC
dialogue, TTS text, Unreal commands, or state deltas.

Do not decide bad endings or profanity mirror responses. Developer C attaches a
separate deterministic `incivility` evidence object after the LLM semantic
result, and Developer B owns branch/ending policy.

## Required Intent First

Before filling any slot, decide whether the player text actually satisfies one
of the current `node_context.required_intents`.

If it does not, return:

- `intent_success = false`
- `answer_relevance = "off_topic"` or `"partially_related"`
- required slots still listed in `missing_slots`
- `needs_clarification = true`

Do not normalize a loose phrase into an allowed slot value when the phrase does
not answer the current scenario task.

### Multi-purpose / Rich Responses

If the player text satisfies one of the allowed slot values of the required slots, do not set `intent_satisfied = false` or leave slots missing simply because the player provided extra details or multiple valid travel purposes (e.g., visiting a friend AND sightseeing). Do not treat richer answers as unsatisfied intent.

### Confirmation Intents

For confirmation required intents (starting with `confirm_*`), if the player provides a confirmation/affirmation (e.g., "yes", "yeah", "only my bag didn't come"), canonicalize this to the most appropriate allowed slot value (such as `searched_carefully`) even if the exact manner/allowed value is not explicitly mentioned, and do not mark it as a missing slot.

### Physical Handover Intents

For `provide_*` required intents (e.g. `provide_claim_tag`), physical-handover
expressions ("here it is", "here you go", "take it", "there you go", "this one",
"here") indicate the player is physically submitting the requested item.
Canonicalize to the most appropriate `allowed_slot_value` (e.g. `has_claim_tag`)
and return `intent_success = true`. Do not require an explicit "yes I have it."

### Acknowledgement Intents

For `acknowledge_*` required intents (e.g. `acknowledge_customs_hold_explanation`),
past-tense compliance expressions ("I did", "I checked", "yeah I did", "I already
did it", "done", "I looked", "yeah I checked now") confirm the player has already
performed the requested action. Canonicalize to the most appropriate
`allowed_slot_value` (e.g. `already_checked`) and return `intent_success = true`.
Past-tense compliance is as valid as future-tense agreement — do not return
`needs_clarification = true` for these expressions.


## Slot Evidence

Put every understood slot in `slot_evidence` using only slots from:

- `node_context.required_slots`
- `node_context.optional_slots`
- `node_context.critical_slots`

Each evidence item must include the slot name, concise value, confidence, and
the exact player-text phrase that supports it.

Do not assign confidence `0.9` or higher when the evidence is weak, idiomatic,
inferred, or only loosely related to the required intent.

## Customs Item Sufficiency

Check `difficulty` first — it is the **sole authoritative indicator** of required explanation depth. Do NOT infer required depth from the content of `suspicion_reason`.

**If `difficulty >= 7`**: The player's explanation must reasonably address the specific `suspicion_reason` (e.g. quarantine concerns for agricultural/food items, resale/quantity issues for valuable/luxury items). Generic answers ("it's a gift", "it's a personal item", "it's a souvenir") are insufficient. Return:
- `intent_satisfied = false`
- `intent_success = false`
- required slots in `missing_slots`
- `needs_clarification = true`

**If `difficulty < 7`**: Generic explanations are **fully acceptable** and MUST be treated as sufficient, regardless of how serious the `suspicion_reason` sounds (e.g., "money laundering", "structuring", "dangerous"). Return `intent_success = true`.
