# Alpha Optional Events Dev B Seed Plan

## Scope

This document records Developer B-owned scenario policy seeds for optional Alpha
events after `BAGGAGE_MISSING`. It does not authorize Developer B to edit
Developer A dialogue/TTS runtime or Developer C orchestration, schema,
validator, response assembly, UI, or non-`dev_b` OpenKB runtime code.

The first Alpha pass should enable at most one optional event behind a feature
flag. The recommended first candidate is `SEATMATE_REUNION` because it reuses
the opening flight relationship, has low orchestration risk, and can compare
casual English from the beginning and end of the Alpha flow.

Optional events do not affect numeric `evaluation` by default. They may create
deferred `out_game_feedback_seed` records, but numeric scoring requires a later
explicit scene weight decision.

## Candidate Events

### CUSTOMS_DECLARATION_PROBLEM

- Initial Alpha status: later candidate, not first optional event.
- Trigger: after baggage resolution when the player is routed to customs.
- B-owned required intent: `explain_customs_item`
- B-owned required slot: `customs_item_purpose`
- Focus-on-Form target: `customs_explanation`
- Risk slots: `undeclared_restricted_item`, `commercial_resale`,
  `unknown_item_owner`
- Feedback policy: can create a deferred final `out_game_feedback_seed` for
  explanation clarity if enabled later.

### PASSPORT_STOLEN

- Initial Alpha status: later candidate because it requires higher C-owned
  orchestration and recovery-state support.
- Trigger: after baggage or optional public-area transition.
- B-owned required intent: `report_lost_passport`
- B-owned required slot: `passport_loss_report`
- Focus-on-Form target: `lost_document_report`
- Risk slots: `cannot_identify_self`, `panic_no_details`,
  `refuse_police_report`
- Feedback policy: should emphasize clear reporting, location/time details, and
  follow-up question handling.

### SEATMATE_REUNION

- Initial Alpha status: recommended first optional event behind a feature flag.
- Trigger: after baggage resolution in the arrivals hall.
- B-owned required intent: `continue_casual_conversation`
- B-owned required slot: `reunion_response`
- Focus-on-Form target: `smalltalk_follow_up`
- Feedback policy: can produce a deferred final `out_game_feedback_seed` if the
  product owner enables the event.
- Scenario purpose: compare late casual small talk with the opening flight
  diagnostic sample without adding a high-pressure recovery problem.

## Verification

No tests are required for this design-only seed document. When implementation
starts, add B-owned scenario-node tests before editing
`backend/app/data/scenario_nodes.json`.
