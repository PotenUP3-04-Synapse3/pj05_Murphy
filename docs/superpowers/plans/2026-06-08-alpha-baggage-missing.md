# Alpha Scenario: BAGGAGE_MISSING

## Status

Scenario design draft for Alpha. This document is a Markdown scenario artifact only; it does not modify implementation files.

## Scenario ID

`BAGGAGE_MISSING`

## Placement

This is the common post-immigration Alpha scene. It happens after the player passes immigration and reaches baggage claim.

```text
IMMIGRATION_ALPHA
  -> BAGGAGE_MISSING
  -> optional Alpha event route
```

Optional events after this scene may include:

- customs declaration problem
- stolen passport
- meeting the airplane seatmate again

Those optional events are future work and should not block the base baggage-missing scene.

## Core Purpose

Create a realistic travel problem after immigration: the player's checked luggage does not arrive at the baggage carousel. The player must find an airport/baggage service staff member and explain the situation clearly enough to start a missing baggage report.

This scene shifts the English task from immigration interview answers to practical problem solving.

## Player Situation

The player has passed immigration and walks to baggage claim. Other passengers collect their luggage, but the player's suitcase never appears. The carousel slows down, then stops.

The player needs to:

- notice that their bag is missing
- approach the correct staff member or baggage service desk
- explain that their luggage did not arrive
- describe the suitcase
- provide flight or baggage tag information
- give contact or delivery information
- understand the next-step instruction from staff

## NPC Profile

- NPC name: `Dana Brooks`
- Role: airline baggage service staff
- Personality: professional, practical, neutral-helpful
- Tone: calm, procedural, not overly friendly
- Speaking style: clear airport service English
- Narrative function: help the player file a missing baggage report if they provide enough information

## Base Flow

Suggested node sequence:

```text
BAG_001_NOTICE_BAG_MISSING
  -> BAG_002_FIND_STAFF
  -> BAG_003_REPORT_MISSING_BAG
  -> BAG_004_DESCRIBE_BAG
  -> BAG_005_PROVIDE_FLIGHT_OR_TAG
  -> BAG_006_CONTACT_AND_DELIVERY
  -> BAG_007_RESOLUTION
```

### BAG_001_NOTICE_BAG_MISSING

Scene beat:

- The carousel is nearly empty.
- The player's bag has not appeared.
- UI objective: find someone who can help.

No major English response is required here unless the player speaks to themselves or asks another passenger.

### BAG_002_FIND_STAFF

Objective:

- Approach baggage service staff or information desk.

NPC starter line:

```text
Hi. Do you need help with your baggage?
```

Expected player intent:

- ask for help
- state that their luggage is missing

Recommended expression:

```text
My suitcase didn't arrive.
```

### BAG_003_REPORT_MISSING_BAG

Objective:

- Clearly report the missing bag problem.

NPC line:

```text
Which flight were you on, and when did you last see your bag?
```

Expected player information:

- flight route or flight number
- the bag was checked before departure
- the bag did not appear at baggage claim

Recommended expression:

```text
I checked it in before my flight, but it didn't come out here.
```

### BAG_004_DESCRIBE_BAG

Objective:

- Describe the suitcase.

NPC line:

```text
Can you describe the bag for me?
```

Expected player information:

- color
- size
- type
- distinctive mark, tag, sticker, lock, strap, or damage

Recommended expression:

```text
It's a black medium-sized suitcase with a red luggage tag.
```

### BAG_005_PROVIDE_FLIGHT_OR_TAG

Objective:

- Provide baggage tag, boarding pass, or flight information.

NPC line:

```text
Do you have your baggage claim tag or boarding pass?
```

Expected player information:

- yes/no
- baggage tag status
- boarding pass status
- where the document is

Recommended expression:

```text
Yes, here is my baggage claim tag.
```

### BAG_006_CONTACT_AND_DELIVERY

Objective:

- Provide contact details or delivery location.

NPC line:

```text
If we find it, where should we send it?
```

Expected player information:

- hotel or address
- phone number or email
- length of stay if relevant

Recommended expression:

```text
Please send it to my hotel. I'm staying there for five days.
```

### BAG_007_RESOLUTION

Objective:

- Understand the staff member's next-step instruction.

NPC line:

```text
We'll file a report and contact you when the bag arrives. Please keep this reference number.
```

Expected player response:

- acknowledge instruction
- ask a practical follow-up if needed

Recommended expression:

```text
Thank you. When should I expect an update?
```

## Tier Policy

### Bronze / Low Level

NPC behavior:

- use shorter questions
- ask one piece of information at a time
- accept broken English when the problem is clear
- offer practical clarification quickly
- allow the player to use simple noun phrases

Example simplified lines:

```text
What color is your bag?
```

```text
Small, medium, or large?
```

```text
Do you have the baggage tag?
```

Bronze success can be based on core meaning:

```text
My bag no come.
```

This should be understood as an attempt to report missing luggage, then clarified gently.

### Silver / Mid Level

NPC behavior:

- use normal service-desk English
- require the main facts but tolerate grammar issues
- ask natural follow-up questions
- provide a clear resolution after sufficient information

Silver success requires:

- missing bag problem
- bag description
- flight/tag or boarding pass information
- contact/delivery location

### Gold / High Level

NPC behavior:

- use faster and more procedural language
- combine questions
- expect clearer sequence and specificity
- react strictly to vague descriptions or missing facts

Example Gold line:

```text
I'll need your flight number, baggage tag, and a detailed description of the suitcase, including any identifying marks.
```

Gold challenge options:

- staff asks whether the bag contains urgent medication or valuables
- staff asks for a local delivery address and backup contact
- staff asks the player to clarify whether the bag was checked through to JFK or another destination

Gold success should require a more complete report and clearer handling of follow-up questions.

## Final Report Inputs

`BAGGAGE_MISSING` should contribute practical problem-solving items to the final Alpha report. Unlike the flight small-talk scene, baggage is an explicit task scene, so it can safely produce Focus-on-Form report seeds for the later out-game report.

Recommended Focus-on-Form targets:

- `problem_statement`: player does not clearly say the luggage is missing
- `bag_description`: player cannot describe color, size, type, or identifying mark
- `flight_or_tag_statement`: player cannot provide baggage tag, boarding pass, or flight information clearly
- `delivery_request`: player cannot provide hotel/address/contact information clearly
- `follow_up_question`: player misses the chance to ask when or how they will receive an update

Each final-report seed should preserve:

- scene ID: `BAGGAGE_MISSING`
- node ID
- original player utterance
- focus target key
- suggested English expression
- short Korean explanation
- whether the report was complete or partial

Example report seed:

```json
{
  "scene_id": "BAGGAGE_MISSING",
  "node_id": "BAG_003_REPORT_MISSING_BAG",
  "focus_target": "problem_statement",
  "original_text": "my bag no come",
  "suggested_expression": "My suitcase didn't arrive.",
  "explanation_kr": "문제 상황을 짧고 직접적인 문장으로 말하면 공항 직원이 바로 처리할 수 있습니다.",
  "include_in_final_report": true
}
```

The final report should be able to show baggage-specific practice such as:

```text
My suitcase didn't arrive.
```

```text
It's a black medium-sized suitcase with a red luggage tag.
```

```text
Please send it to my hotel.
```

## Failure And Recovery

This scene should not immediately hard-fail because it is a service problem, not a security interview.

Possible recovery behavior:

- If the player cannot describe the bag, staff asks simpler attributes: color, size, tag.
- If the player does not know the flight number, staff asks for boarding pass or airline.
- If the player does not have the baggage tag, staff asks for passport and flight details.
- If the player gives only Korean/Konglish, the system tries to infer intent and asks a simpler follow-up.
- If the player repeatedly cannot provide required details, the report remains incomplete and the staff gives a limited next step.

Potential partial resolution:

```text
I can start the report, but I'll need more information before we can deliver the bag.
```

## Required Derived Implementation

Dev B-owned work:

- Add baggage-missing scenario node definitions when implementation begins.
- Define required intents and slots for missing-bag report, bag description, tag/flight information, and contact/delivery.
- Add tier-specific hint policy and evaluation strictness.
- Add focus-on-form targets for practical service-desk expressions.
- Add tests for Bronze recovery, Silver normal completion, and Gold procedural challenge.
- Ensure branch policy can produce complete, partial, retry, and clarify outcomes without using LLM-generated branch control.
- Add final-report seed capture for problem statements, bag descriptions, tag/flight information, and delivery requests.
- Ensure optional LLM wording support is limited to hint/report text and cannot change scenario branch authority.

Cross-team coordination needed:

- Developer A should generate the baggage staff's final dialogue and voice style.
- Developer C should orchestrate the scene transition after immigration and any optional event routing after baggage.
- If new scenario IDs or response fields are added, update or request updates to the shared contracts before implementation.

## Acceptance Criteria

- The player reaches this scene after passing `IMMIGRATION_ALPHA`.
- The core problem is always that checked luggage does not arrive.
- The player must explain the missing-bag problem to staff.
- The staff asks for a bag description, flight/tag information, and contact/delivery details.
- Bronze can progress with broken but understandable English.
- Gold receives more procedural, stricter follow-up questions.
- The scene can resolve with a filed missing-baggage report or a partial/incomplete report state.
- Optional events remain future hooks and do not block this base scenario.
- Baggage turns can produce Focus-on-Form final-report seeds for the final Alpha report.
