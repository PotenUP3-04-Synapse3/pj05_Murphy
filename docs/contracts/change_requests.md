# Change Requests

Cross-owner change requests are listed below. Status lines describe the current
repository state as of the latest handoff entry.

## Change Request - 2026-06-03 - Developer A NPC Dialogue/TTS Implementation

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer C / Sean Han

### Reason

Developer A needs to implement NPC dialogue and TTS output while preserving Developer C ownership of orchestration, tests, dependency contracts, adapters, and runtime response assembly.

### Proposed Contract Change

1. Allow Developer A to add focused tests for Developer A owned services.
   - Proposed location: `backend/tests/developer_a/`
   - Reason: `backend/tests/` is currently Developer C owned, but Developer A needs isolated verification for dialogue/TTS services.

2. Approve Kokoro runtime dependencies after fake provider is verified.
   - Proposed dependencies: `kokoro`, `soundfile`, `torch`, and Windows espeak runtime helper packages if required.
   - Reason: real wav generation requires these dependencies, but dependency contract must be updated first.

3. Confirm Developer A output fields consumed by Developer C adapter.
   - Proposed fields: `speaker`, `npc_text`, `feedback_kr`, `tone`, `animation`, `tts`, `fallback`.

4. Confirm runtime audio serving policy.
   - Proposed local path: `backend/runtime/audio/kokoro/<cache_key>.wav`
   - Proposed URL field: `audio_url`, nullable until Developer C static serving is ready.

### Compatibility Impact

No existing Developer C mock should break if Developer C keeps using its current adapter behavior. Developer A will keep legacy `text` fields where useful and add `npc_text` for the new contract shape.

### Temporary Workaround

Developer A will implement a fake Kokoro provider that creates valid local wav files without adding external dependencies. Real Kokoro integration and Developer A test placement will wait for contract approval.

Use this format for future requests:

```markdown
## Change Request - YYYY-MM-DD - Short Title

### Requested By

Developer C / Sean Han

### Affected Owner

Developer A or Developer B

### Reason

Why this change is needed.

### Proposed Contract Change

Exact input/output or behavior change.

### Compatibility Impact

Does this break existing mocks or tests?

### Temporary Workaround

What Developer C will do until the change is accepted.
```

## Change Request - 2026-06-04 - Wire Developer B Policy Engine

Status: Resolved in the integrated pre-prototype. Keep this entry for contract
history.

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B exposes a real deterministic `dev_b_policy.v1` policy engine
under `backend/app/agents/agent_b/` and `backend/app/services/service_b/`.
At the time this request was filed, the runtime still called the C-owned mock
adapter at `backend/app/integrations/dev_b_level_hint_client.py`.

### Proposed Contract Change

Keep the existing `DevBPolicyInput` and `DevBPolicyOutput` schemas unchanged.
Update `DevBPolicyClient.evaluate_turn()` to delegate to
`backend.app.agents.agent_b.EnglishLevelHintAgent.evaluate_turn()` after
Developer C approves importing the B-owned package from the adapter.

Also sync or consume `backend/app/data/scenario_nodes.json` in the C-owned
OpenKB runtime so all Chapter 0 immigration nodes are available beyond
`IMM_002_PURPOSE`.

### Compatibility Impact

No schema-breaking change is requested. Existing mock tests may need expectation
updates if they depend on the previous simplified C mock behavior, especially
`dialogue_directive.do_not_generate_npc_text`, `error_capture`, and warning or
hint branch behavior.

### Temporary Workaround

Developer C can keep using the existing mock adapter until the adapter handoff is
accepted. Developer B tests call the B engine directly.

## Change Request - 2026-06-04 - Consume Developer B OpenKB Write References

Status: Partially resolved. Developer B writes local `dev_b` OpenKB records and
Developer C can read B session records for `final_result`, but C-owned
validation of successful `openkb_write.namespace` and path references is still
not implemented.

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B now owns feedback/error/focus-on-form runtime writes under the
OpenKB `dev_b` namespace. The B policy output includes an optional
`openkb_write` reference so C can validate and later retrieve the record without
creating duplicate log entries.

### Proposed Contract Change

Keep the existing `DevBPolicyOutput` fields and add the optional
`openkb_write` field:

- `attempted: bool`
- `succeeded: bool`
- `namespace: str`
- `record_id: str | None`
- `jsonl_path: str | None`
- `markdown_path: str | None`
- `error_message: str | None`

Developer C should update logging/validator/final-report code so that:

1. C does not create a duplicate runtime error record when
   `dev_b_policy.openkb_write.succeeded == true`.
2. C validator checks that successful B write references use namespace `dev_b`
   and point to expected local OpenKB runtime paths.
3. Final report retrieval can consume B-authored feedback/error records by
   `record_id`.

### Compatibility Impact

The field is additive and optional, so existing response assembly can continue
to work. Tests that compare the full `DevBPolicyOutput` dump may need to accept
the new optional `openkb_write` object.

### Temporary Workaround

Until C updates logging and final report retrieval, Developer B writes records
under `backend/runtime/openkb/dev_b/` and C can continue using existing response
payload fields. Any duplicate C-side markdown logging should be treated as a
known integration cleanup item.

## Change Request - 2026-06-04 - Consume Developer B LLM Feedback Metadata

Status: Partially resolved. Developer C accepts the additive B metadata and
validates final-result output, but C-owned validation of `feedback_generation`
and `difficulty_profile` metadata is still not implemented.

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B now exposes optional LLM-assisted learning feedback metadata while
keeping branch, verdict, next-node, and state-delta decisions rule-based. The
metadata helps C validator, final report, and future UI/debug views distinguish
rule, LLM, and fallback feedback.

### Proposed Contract Change

Keep all existing `DevBPolicyOutput` fields and add optional fields:

- `rubric_scores`
- `difficulty_profile`
- `feedback_generation`

Developer C should update validator/final-report consumers so that:

1. `feedback_generation.mode` is one of `rule`, `llm`, or `fallback`.
2. `feedback_generation.used_llm` is debug/trace metadata only and never branch
   authority.
3. `rubric_scores.total` stays in the 0-12 range.
4. `difficulty_profile.travel_speaking_level` is treated as learning
   difficulty metadata, not Unreal branch authority.
5. Any LLM-generated feedback must not override `branch`, `next_node_id`,
   `state_delta`, or `evaluation.verdict`.

### Compatibility Impact

The fields are optional and additive. Existing C response assembly can ignore
them until validator/final-report integration is ready.

### Temporary Workaround

Developer B stores these fields in the B-owned OpenKB `dev_b` runtime record.
C can continue consuming the existing `level_hint`, `evaluation`,
`report_item`, and `openkb_write` fields.

## Change Request - 2026-06-04 - Expose OpenKB objective_kr to Unreal UI

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B now defines `objective_kr` in Chapter 0 scenario node content so the
current node's Korean objective can be shown consistently in Unreal UI.

### Proposed Contract Change

`NodeContext.objective_kr` is an optional field populated from
`backend/app/data/scenario_nodes.json`. Developer C may expose it through the
final Unreal UI response when the response contract is ready for objective
display.

### Compatibility Impact

The field is optional and additive. Existing Understanding, Developer B policy,
Developer A dialogue, and response builder behavior can ignore it.

### Temporary Workaround

Until C adds a UI response field, `objective_kr` is available in the internal
node context only.

## Change Request - 2026-06-08 - Expose Developer B Focus-on-Form Report v1

### Requested By

Developer B

### Affected Owner

Developer C / Sean Han

### Reason

Developer B now has a B-owned `FocusOnFormReportPolicy` that can build an
out-game Focus-on-Form report from B-owned OpenKB `dev_b` records and static
B-owned learning cards. Developer C owns final result endpoint shape and Unreal
response assembly, so Developer B cannot expose this report directly.

### Proposed Contract Change

Add an optional `out_game_feedback` object to the C-owned final result response
or a C-owned result detail endpoint. Treat it as learning feedback metadata
only. It must not affect branch, verdict, next node, state delta, or numeric
score authority.

### Compatibility Impact

Additive optional field only. Existing clients may ignore it.

### Temporary Workaround

Developer B keeps the report builder as a directly tested B-owned service.
Developer C can continue returning the existing final result payload until the
response surface is ready.

## Change Request - 2026-06-09 - Support Alpha Scene Flow Beyond Immigration

Status: Open.

Developer C Alpha 1 update, 2026-06-10: C added an additive
`dev_c_interaction_context.v1` request/response context for NPC-first vs
player-first and quest vs ambient turns, plus diagnostic response timing. This
does not yet implement the full Alpha scene flow, but it gives Unreal and A/B/C
logs a stable metadata surface for the next scenario-flow phase.

Developer C Alpha 3A update, 2026-06-12: C adopted the B-owned Alpha node
expansion at the runtime boundary for the base route. `IMM_007_FINAL_DECISION`
now remains a transition into `BAG_001_NOTICE_BAG_MISSING`, final-result
attachment is limited to `ALPHA_999_FINAL_SCOREBOARD`, C accepts
`scene_normalized_dimension_average` as a final score policy name, and rule-mode
Understanding can consume B-authored generic slot metadata for flight/BAG-style
nodes. Cutscene/skip orchestration, Unreal scene-state wiring, and final
`out_game_feedback` UI exposure remain open.

Developer C Alpha 3B update, 2026-06-12: C added additive
`dev_c_unreal_flow.v1` response metadata for the base Alpha presentation
transitions. Current flow ids are `flight_to_immigration_arrival` with
`CIN_FLIGHT_ARRIVAL_JFK` and skip eligibility, `immigration_to_baggage_claim`,
and `alpha_final_scoreboard`. Unreal still owns playing the actual cinematics,
moving scene state, and rendering scoreboard UI. Final `out_game_feedback` UI
exposure remains open.

Developer C Alpha 3C update, 2026-06-12: C added the provider-neutral
`dev_c_realtime_stt.v1` WebSocket contract at `/api/game/ai/stt/stream`.
The endpoint accepts `session_start`, `partial_transcript`, `final_transcript`,
and `cancel` events from Unreal or a safe STT bridge, returns subtitle-ready
events for Unreal, and marks final transcript events as committed candidates
for `POST /api/game/ai/respond`. Partial transcripts remain UI-only and do not
call Understanding, Developer B, Developer A, or TTS. Actual provider auth,
short-lived token issuance, and direct streaming-to-orchestrator commit remain
future integration work.

Developer C Alpha 3D update, 2026-06-12: C added the backend relay path for
ElevenLabs realtime STT. `session_start.provider = "elevenlabs_relay"` opens a
server-side WSS connection to ElevenLabs `/v1/speech-to-text/realtime` using
`ELEVENLABS_API_KEY` from the backend environment, `audio_chunk` events are
forwarded as ElevenLabs `input_audio_chunk` messages, and ElevenLabs
`partial_transcript` / `committed_transcript` messages are mapped back to
`dev_c_realtime_stt.v1` subtitle events. Unreal still must capture and send
base64 audio chunks, and direct final-transcript-to-orchestrator commit remains
future work.

### Requested By

Developer B

### Affected Owner

Developer A and Developer C / Sean Han

### Reason

Developer B now has Alpha scenario plan artifacts and B-owned baggage policy
nodes, but the integrated runtime still primarily behaves like an immigration
prototype. Alpha requires the scene order
`FLIGHT_A_001_SEATMATE_SMALLTALK -> IMMIGRATION_ALPHA -> BAGGAGE_MISSING`, silent
level carryover from flight small talk, no immediate out-game feedback after
small talk, cutscene/skip signals, non-immigration NPC roles, and a final
scenario-end result UI containing B-owned `evaluation` plus `out_game_feedback`.

### Proposed Contract Change

Developer C should add or approve request/response fields and orchestration for:

- Alpha scene transitions, including cutscene and skip eligibility.
- Silent carryover of the B-measured `tier`, `travel_speaking_level`,
  `rubric_scores`, and `difficulty_profile` from flight into immigration.
- Rule or LLM Understanding coverage for non-purpose slots such as
  `stay_duration`, `return_ticket_status`, baggage report details, baggage
  description, tag/flight info, delivery contact, and resolution acknowledgement.
- Final result or result-detail exposure of B-owned
  `FocusOnFormReportPolicy.build_report(...)` output as optional
  `out_game_feedback`.
- Final scenario-end `evaluation` payload from Developer B using
  `scene_normalized_dimension_average`:
  - convert each rubric dimension from 0..2 to 0..100,
  - average each dimension inside each scene first,
  - combine present Alpha scenes with default weights: flight 20%,
    immigration 50%, baggage 30%,
  - compute `overall` as the average of the weighted dimension scores,
  - keep optional events out of numeric scoring unless a later explicit weight
    is added.
- Update C-owned schema/validator acceptance for the new score policy name when
  C adopts the contract. Developer C now accepts both `simple_average` and
  `scene_normalized_dimension_average`.

Developer A should consume B difficulty metadata and scene/NPC role context for:

- Friendly seatmate small-talk dialogue.
- Tier-aware immigration officer response speed/strictness.
- Baggage service staff dialogue.

### Compatibility Impact

All fields should be additive until Alpha scene contracts are finalized. Existing
Chapter 0 immigration tests should continue to pass.

### Temporary Workaround

Developer B can keep authoring B-owned scenario nodes, hint policy, diagnostic
policy, and report seeds. Base C runtime routing and flow metadata now exist;
integrated Alpha behavior still depends on Unreal scene-state wiring and A-owned
dialogue support.

## Change Request - 2026-06-09 - Remove Developer B NPC Wording From A Adapter Payload

Status: Open.

Developer C Alpha 3A update, 2026-06-12: C adopted the base runtime routing
portion of this request. `ALPHA_999_FINAL_SCOREBOARD` is now the only C adapter
trigger for attached `final_result`; `IMM_007_FINAL_DECISION` advances to
`BAG_001_NOTICE_BAG_MISSING`; the A adapter can seed next-node prompts for
non-`IMM_` nodes through OpenKB; and C rule Understanding has generic
B-metadata slot coverage for the new flight/BAG-style nodes. Unreal cutscene
state wiring and A-owned generated dialogue/TTS polish remain separate follow-up
work.

Developer C Alpha 3B update, 2026-06-12: C now emits `flow` metadata for
flight-to-immigration cutscene, immigration-to-baggage transition, and Alpha
scoreboard display. This gives Unreal a stable backend hint surface while
keeping actual scene/cinematic execution outside the backend.

Developer C Alpha 3C update, 2026-06-12: C now exposes
`/api/game/ai/stt/stream` for realtime STT subtitle events. This does not
change the A-facing dialogue payload yet; it only gives Unreal a stable C-owned
surface for partial and final transcript events while preserving the existing
`/respond` orchestration path.

Developer C Alpha 3D update, 2026-06-12: C now supports `elevenlabs_relay` as a
server-side realtime STT provider mode. This still does not alter the A-facing
dialogue payload; it only changes how subtitle transcripts can be produced
before the committed `/respond` turn.

### Requested By

Developer B

### Affected Owner

Developer A and Developer C / Sean Han

### Reason

Developer B should not author final NPC dialogue. The current integrated path
allows C to pass `node_context.npc_question` and generated next-question text to
Developer A as candidate dialogue, which makes B-owned scenario data behave like
NPC utterance text. This blocks tier-aware and emotionally dynamic NPC dialogue
because Developer A receives text to polish instead of metadata to generate
from.

### Proposed Contract Change

Developer C should update the internal C-to-A adapter payload only. Do not
change the external Unreal request/response contract for this migration.

Remove these fields from the A-facing payload:

- `node_context.npc_question`
- `in_game_feedback.npc_recast_line_candidate` when it contains next-question
  text derived from `npc_question`
- `dialogue_directive.do_not_generate_npc_text`
- A-facing `hint_frequency`
- A-facing `pressure_level`

Keep or pass these metadata fields instead:

| Key                   | Value                              | Meaning                                                                 |
| --------------------- | ---------------------------------- | ----------------------------------------------------------------------- |
| `npc_question_goal`   | string such as `ask_stay_duration` | Communicative goal for Developer A generation                           |
| `required_slots`      | list of strings                    | Information Developer A should prompt for                               |
| `target_slot`         | string or null                     | Primary slot for the current dialogue turn                              |
| `npc_speech_speed`    | integer `0-10`                     | `0` = very slow and learner-friendly, `10` = near-native fast           |
| `question_complexity` | integer `0-10`                     | `0` = very simple one-part question, `10` = complex multi-part question |
| `emotion_change`      | `positive`, `neutral`, `negative`  | NPC emotional/tone direction caused by the current turn                 |

`hint_frequency` remains Developer B feedback policy and should not be passed
as Developer A NPC-generation input.

`pressure_level` should be replaced by word-only `emotion_change` for
A/Unreal-facing tone and facial-expression direction. `emotion_change` is not a
numeric score and should not allow an LLM to manage score state.

Developer A owns final NPC utterance generation and TTS wording. Developer B
provides scenario goal, required intent/slot, difficulty policy, emotion-change
direction, hint policy, scoring policy, and report seeds only.

### Compatibility Impact

This is an internal adapter contract change. External Unreal payloads do not
need to change. Existing deterministic A/C tests that assert exact static
`npc_question` output will need to be updated to assert goal/slot metadata and
A-owned generated text behavior instead.

### Temporary Workaround

Until C updates the adapter and schema, Developer B may keep `npc_question` in
`scenario_nodes.json` as legacy node context required by current schemas, but it
must be treated as fallback/debug context rather than final NPC dialogue
authority.

## Change Request - 2026-06-11 - Adopt Alpha Scenario Node Expansion Across A/C/Unreal

Status: Open.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Reason

Developer B expanded the Alpha scenario node sequence to support five-turn
flight small-talk diagnostics, immigration-to-baggage transition, missing-bag
problem solving, and a dedicated Alpha final-scoreboard node. Dev B can author
and validate node policy, but integrated runtime behavior requires A/C/Unreal
ownership changes.

### Proposed Contract Change

Developer C should adopt the following runtime flow:

```text
FLIGHT_A_001_SEATMATE_SMALLTALK
-> FLIGHT_A_002_TRAVEL_PURPOSE
-> FLIGHT_A_003_STAY_PLAN
-> FLIGHT_A_004_CLARIFY_OR_ASK_BACK
-> FLIGHT_A_005_WRAP_UP
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

Developer C follow-up:

- Treat `ALPHA_999_FINAL_SCOREBOARD`, not `IMM_007_FINAL_DECISION`, as the
  Alpha scenario-end final-result trigger.
- Treat `IMM_007_FINAL_DECISION` as an immigration-clearance transition into
  baggage claim.
- Preserve silent flight-to-immigration carryover of B-measured `tier`,
  `travel_speaking_level`, `rubric_scores`, and `difficulty_profile`.
- Orchestrate flight exit, arrival/cutscene transition, baggage claim entry,
  and final scoreboard/result retrieval.
- Add Understanding coverage for the new flight and customs-hold baggage slots.

Developer A follow-up:

- Generate actual NPC dialogue/TTS for the five `FLIGHT_*` seatmate nodes from
  `dialogue_seed`, not from B-authored final lines.
- Generate baggage service and customs-officer dialogue for the new
  `BAG_001_REPORT_MISSING_AT_DESK` through `BAG_007_CUSTOMS_CLEARANCE` route
  from role/goal/slot metadata.
- Keep final NPC utterances, tone realization, voice, and animation A-owned.

Unreal follow-up:

- Connect the flight small-talk scene to the airport arrival/cutscene and then
  to immigration.
- Connect immigration clearance to baggage claim, then to the Alpha final
  scoreboard and ending cinematic.
- Do not show immediate out-game feedback after flight small talk; consume
  deferred feedback only at the Alpha scenario end.

### Compatibility Impact

The Dev B node expansion is additive for node data but changes semantic routing:
`IMM_007_FINAL_DECISION` is no longer the Alpha scenario-end terminal in B
policy. Existing C-owned final-result adapter behavior may keep treating
`IMM_007_FINAL_DECISION` as a legacy final trigger until C adopts this request.

### Temporary Workaround

Developer B keeps `IMM_007_FINAL_DECISION` in the node set and documents the
legacy C adapter mismatch. Integrated runtime can continue using the legacy
result endpoint while A/C/Unreal migrate to `ALPHA_999_FINAL_SCOREBOARD`.

## Change Request - 2026-06-12 - Adopt Alpha Chapter Boundary Transition Nodes

Status: Implemented in B/C pre-prototype runtime; Developer A and Unreal should
consume the additive metadata when their integration surfaces are ready.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Reason

`chapter_id` previously acted like a whole-scenario namespace and did not tell
Unreal when a major NPC interaction was complete. Alpha needs explicit boundary
signals so Unreal can stop the current NPC dialogue and enter the airport
arrival tutorial, baggage claim, or result screen.

### Proposed Contract Change

Adopt `dev_b_scenario_nodes.v2`:

- `scenario_id = ALPHA_AIRPORT_ARRIVAL`.
- `chapter_id` is the ordered Alpha phase:
  `CH0_01_FLIGHT_SMALLTALK`, `CH0_02_ARRIVAL_TUTORIAL`,
  `CH0_03_IMMIGRATION_CHECK`, `CH0_04_BAGGAGE_CLAIM`, `CH0_05_RESULT`.
- Add transition nodes:
  `FLIGHT_999_COMPLETE`, `IMM_999_CLEARED`, and `BAG_999_COMPLETE`.
- Add `next_action = COMPLETE_CHAPTER`.
- Add optional Unreal response `transition` metadata containing
  `status`, `completed_chapter_id`, `next_chapter_id`, `entry_node_id`,
  `unreal_event`, and `requires_player_input=false`.
- Developer C passes additive `transition` metadata to the A-facing dialogue
  adapter payload on chapter-complete branches.

Developer A follow-up:

- Treat `COMPLETE_CHAPTER` as a closing-dialogue context.
- Do not generate the next chapter's opening question from transition metadata.
- Keep final NPC utterance, tone, TTS, and animation realization A-owned.

Unreal follow-up:

- Stop current NPC voice-turn capture when `next_action=COMPLETE_CHAPTER`.
- Use `transition.unreal_event` and `transition.next_chapter_id` to drive the
  next gameplay phase.
- Use `transition.entry_node_id` when the next phase starts with an AI dialogue
  node; allow `entry_node_id=null` for the airport-arrival tutorial phase.

### Compatibility Impact

This is a breaking semantic change for callers that still send
`CH0_IMMIGRATION`. Current immigration dialogue requests must send
`CH0_03_IMMIGRATION_CHECK`. The response `transition` field is additive and
nullable for normal dialogue responses.

### Temporary Workaround

Unreal can continue ordinary dialogue turns by using the node's new chapter id.
Until Unreal consumes the transition payload, chapter-complete responses can be
handled by checking `next_action == COMPLETE_CHAPTER` and reading
`transition.unreal_event`.

## Change Request - 2026-06-12 - Add Alpha Flight Smalltalk Route Variants

Status: Implemented in B-owned scenario node data; Developer A and Unreal should
consume the additive route metadata when they select or render the flight
small-talk opening.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Reason

The previous flight chapter was one fixed 5-turn stream. Alpha needs multiple
natural small-talk variants so the flight scene can feel less scripted while
still collecting a stable 5-turn level diagnostic sample.

### Proposed Contract Change

`CH0_01_FLIGHT_SMALLTALK` now has three route starts in chapter metadata:

- `FLIGHT_A_001_SEATMATE_SMALLTALK` for Friendly Seatmate.
- `FLIGHT_B_001_DESTINATION_CHAT` for Curious Seatmate.
- `FLIGHT_C_001_FORM_HELP_REQUEST` for Travel Form Help.

Each route has five dialogue nodes and then branches to the shared
`FLIGHT_999_COMPLETE` transition node. The default `entry_node_id` remains
`FLIGHT_A_001_SEATMATE_SMALLTALK`, and all flight dialogue route IDs now use
the same `FLIGHT_A_*`, `FLIGHT_B_*`, or `FLIGHT_C_*` naming pattern.

Developer A follow-up:

- Generate natural seatmate dialogue for the new `FLIGHT_B_*` and `FLIGHT_C_*`
  node metadata, and treat the former default route as `FLIGHT_A_*`.
- Keep each route as a 5-turn diagnostic conversation and close before
  `FLIGHT_999_COMPLETE`.

Unreal follow-up:

- Select one route start from `entry_node_ids` when beginning the flight
  chapter, or keep using `entry_node_id` to preserve the default route.
- Do not mix nodes across routes once a route is selected.

## Change Request - 2026-06-12 - Align Developer A/C NPC Routing for Alpha Non-Immigration Nodes

Status: Requested after integrated `/respond-dialog` testing. Developer B data
is ready; Developer A and Developer C follow-up is required for natural Flight
and Baggage testing.

### Requested By

Developer B

### Affected Owner

Developer A and Developer C / Sean Han

### Reason

`/respond-dialog` now correctly starts `CH0_01_FLIGHT_SMALLTALK` at
`FLIGHT_A_001_SEATMATE_SMALLTALK`, but the first integrated test response still
returned:

- `Officer Miller`
- `Okay. Please continue.`

Runtime logs confirmed the scenario state was correct:

- request chapter: `CH0_01_FLIGHT_SMALLTALK`
- request node: `FLIGHT_A_001_SEATMATE_SMALLTALK`
- B branch: `SUCCESS -> FLIGHT_A_002_TRAVEL_PURPOSE`

The mismatch occurs after B:

- Developer C's A adapter only loads next-question seeds for `IMM_` nodes, so
  `FLIGHT_A_002_TRAVEL_PURPOSE` is not passed as an A candidate line.
- Developer A's NPC roster currently falls unknown NPC ids back to
  `officer_miller`, so `SEATMATE_A_01` resolves to `Officer Miller`.
- Developer A's text fallback is Officer Miller-specific:
  `Okay. Please continue.`

### Requested Contract / Runtime Change

Developer C follow-up:

- Update `backend/app/integrations/dev_a_npc_dialogue_client.py` so
  `_next_node_question()` can resolve supported Alpha dialogue nodes beyond
  `IMM_`, including `FLIGHT_` and `BAG_`.
- Preserve `payload.npc.npc_id`, `npc_role`, and `node_context.chapter_id` in
  the A-facing payload for all Alpha chapters.
- Add validation or diagnostic logging when the requested NPC id/role and
  Developer A response speaker/animation clearly mismatch.
- Add regression coverage for
  `FLIGHT_A_001_SEATMATE_SMALLTALK -> FLIGHT_A_002_TRAVEL_PURPOSE` verifying
  the A seed is the next seatmate line, not an Officer Miller fallback.

Developer A follow-up:

- Add roster profiles for the Alpha non-immigration NPCs used by B scenario
  nodes:
  `SEATMATE_A_01`, `SEATMATE_B_01`, `SEATMATE_C_01`, and
  baggage service/customs officer roles.
- Make text fallback, default animation, display name, and voice profile derive
  from the resolved NPC profile instead of Officer Miller-only defaults.
- Generate seatmate-style dialogue/TTS for `FLIGHT_A_*`, `FLIGHT_B_*`, and
  `FLIGHT_C_*` nodes and baggage-service dialogue/TTS for `BAG_*` nodes.
- Treat `COMPLETE_CHAPTER` as a closing line context, not as a prompt to ask
  the next chapter's first question.

### Compatibility Impact

This change does not alter B scenario branching. It fixes A/C integration for
non-immigration chapters so existing `chapter_id`, `node_id`, `npc_id`, and
`next_node_id` values produce the correct speaker and dialogue style.

### Temporary Workaround

Until A/C complete this request, `/respond-dialog` can validate STT,
Understanding, B branching, transition behavior, and payload generation, but
NPC speaker/text quality for Flight and Baggage may still show Officer Miller
fallback output.

## Change Request - 2026-06-12 - Replace Baggage Missing-Bag Route with Customs Hold Required Flow

Status: Implemented in B-owned scenario node data; Developer A, Developer C,
and Unreal follow-up is required for natural integrated play.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Reason

The previous baggage route treated the missing suitcase as a service-desk report
and delivery-resolution flow. Alpha now requires a more natural airport flow:
the service desk confirms the bag is being held, the player returns to baggage
claim, a customs officer unlocks the suitcase, Unreal reveals a random item,
and the player explains that item before clearance.

### Proposed Contract Change

`CH0_04_BAGGAGE_CLAIM.entry_node_id` is now
`BAG_001_REPORT_MISSING_AT_DESK`, and the required baggage route is:

```text
BAG_001_REPORT_MISSING_AT_DESK
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

New required slots:

- `missing_bag_statement`
- `claim_tag_status`
- `carousel_search_confirmation`
- `customs_hold_redirect_acknowledgement`
- `customs_hold_acknowledgement`
- `customs_item_explanation`
- `customs_clearance_acknowledgement`

Developer A follow-up:

- Generate service-desk dialogue for `BAG_001` through `BAG_004`.
- Generate customs-officer dialogue for `BAG_005` through `BAG_007`.
- Add or map roster/voice profiles for baggage service staff and customs
  officer roles so the route does not fall back to Officer Miller.
- Keep final NPC wording, tone, animation, and TTS A-owned.

Developer C follow-up:

- Add Understanding coverage for all new baggage intents and slots.
- Route the correct A-facing NPC role by BAG node phase: service staff for
  `BAG_001` through `BAG_004`, customs officer for `BAG_005` through
  `BAG_007`.
- Ensure `BAG_999_COMPLETE` still returns `next_action=COMPLETE_CHAPTER` with
  `transition.unreal_event = SHOW_ALPHA_SCOREBOARD`.
- Accept or pass through Unreal-provided random item context for
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` if available.

Unreal follow-up:

- After `BAG_005_CUSTOMS_HOLD_EXPLANATION`, stop dialogue capture and run the
  required interaction: show locked suitcase, unlock it, add suitcase to
  inventory, open suitcase UI, and reveal the random customs item.
- Start `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` only after the item is visible to
  the player.
- Use `BAG_999_COMPLETE.transition.unreal_event = SHOW_ALPHA_SCOREBOARD` for
  the final scoreboard transition.

### Compatibility Impact

This replaces the old `BAG_001_NOTICE_BAG_MISSING` through
`BAG_007_RESOLUTION` route. Any caller or test fixture still using the old BAG
IDs must migrate to the new route IDs above.

### Temporary Workaround

Until A/C/Unreal complete their follow-up, `/respond-dialog` can validate B
branching and response structure, but custom service-desk/customs NPC voice and
the suitcase unlock/random-item interaction remain integration work.

## Change Request - 2026-06-12 - Consolidated Alpha Follow-up for Developer A, Developer C, and Unreal

Status: Open. This consolidates the latest Alpha scenario-node changes after
chapter transitions, flight route variants, `/respond-dialog` chapter starts,
and the required baggage customs-hold route.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Current Implemented State

Developer B/C pre-prototype data now uses:

- `scenario_id = ALPHA_AIRPORT_ARRIVAL`.
- Ordered chapter IDs:
  `CH0_01_FLIGHT_SMALLTALK`,
  `CH0_02_ARRIVAL_TUTORIAL`,
  `CH0_03_IMMIGRATION_CHECK`,
  `CH0_04_BAGGAGE_CLAIM`,
  `CH0_05_RESULT`.
- Transition nodes:
  `FLIGHT_999_COMPLETE`,
  `IMM_999_CLEARED`,
  `BAG_999_COMPLETE`.
- `next_action = COMPLETE_CHAPTER` with optional `transition` metadata for
  Unreal state changes.
- Flight has three 5-turn route starts:
  `FLIGHT_A_001_SEATMATE_SMALLTALK`,
  `FLIGHT_B_001_DESTINATION_CHAT`,
  `FLIGHT_C_001_FORM_HELP_REQUEST`.
- Baggage claim now starts at `BAG_001_REPORT_MISSING_AT_DESK` and requires
  the customs-hold/random-item explanation route:
  `BAG_001_REPORT_MISSING_AT_DESK -> BAG_002_PROVIDE_CLAIM_TAG ->
BAG_003_CONFIRM_SEARCHED_CAROUSEL ->
BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD ->
BAG_005_CUSTOMS_HOLD_EXPLANATION ->
BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM -> BAG_007_CUSTOMS_CLEARANCE ->
BAG_999_COMPLETE`.
- `/respond-dialog` can start Flight, Immigration, Baggage, and Result from
  buttons without uploading a JSON turn file. The first turn can be submitted
  with WAV upload or browser recording.

### Developer A Required Follow-up

- Add or map NPC roster/voice profiles for:
  seatmate route A/B/C, baggage service staff, and customs officer.
- Stop falling unknown non-immigration NPCs back to Officer Miller.
- Generate natural seatmate dialogue/TTS for `FLIGHT_A_*`, `FLIGHT_B_*`, and
  `FLIGHT_C_*`.
- Generate service-desk dialogue/TTS for `BAG_001` through `BAG_004`.
- Generate customs-officer dialogue/TTS for `BAG_005` through `BAG_007`.
- Treat `next_action=COMPLETE_CHAPTER` as a closing-line context only; do not
  ask the next chapter's first question from transition metadata.

### Developer C Required Follow-up

- Extend the Developer A adapter so next-question seeds work for `FLIGHT_` and
  `BAG_` nodes, not only `IMM_` nodes.
- Preserve and validate A-facing `npc_id`, `npc_role`, `chapter_id`, and
  `node_id` for all Alpha chapters.
- Add diagnostics or validation when requested NPC role and A returned speaker
  clearly mismatch.
- Add Understanding coverage for new Flight route slots and the new baggage
  customs-hold slots, especially:
  `missing_bag_statement`,
  `claim_tag_status`,
  `carousel_search_confirmation`,
  `customs_hold_redirect_acknowledgement`,
  `customs_hold_acknowledgement`,
  `customs_item_explanation`,
  `customs_clearance_acknowledgement`.
- Route A-facing NPC context by BAG phase: service staff for `BAG_001` through
  `BAG_004`, customs officer for `BAG_005` through `BAG_007`.
- Keep `BAG_999_COMPLETE` returning `next_action=COMPLETE_CHAPTER` with
  `transition.unreal_event = SHOW_ALPHA_SCOREBOARD`.
- Pass through Unreal-provided random item context to
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` when available.

### Unreal Required Follow-up

- Start Alpha from chapter metadata:
  default Flight start is `FLIGHT_A_001_SEATMATE_SMALLTALK`; optional route
  starts are listed in `entry_node_ids`.
- Do not send player speech turns for `node_type=transition`.
- On `COMPLETE_CHAPTER`, stop current NPC voice capture and consume
  `transition.unreal_event`, `transition.next_chapter_id`, and
  `transition.entry_node_id`.
- Handle transition events:
  `START_AIRPORT_ARRIVAL_TUTORIAL`,
  `ENTER_BAGGAGE_CLAIM`,
  `SHOW_ALPHA_SCOREBOARD`.
- After `BAG_005_CUSTOMS_HOLD_EXPLANATION`, run the required non-dialogue
  interaction: show locked suitcase, unlock it, add suitcase to inventory, open
  suitcase UI, reveal random customs item, then start
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`.

### Compatibility Impact

Old callers using `CH0_IMMIGRATION`, `FLIGHT_001_*`, or the previous baggage
route `BAG_001_NOTICE_BAG_MISSING` through `BAG_007_RESOLUTION` must migrate
to the current chapter IDs and node IDs.

### Current Verification

- `uv sync` completed.
- `uv run pytest` passed with 201 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

## Change Request - 2026-06-12 - Propagate Developer B NPC Emotion Enum

Status: Implemented in B/C pre-prototype runtime; Developer A and Unreal should
consume the additive field when ready.

### Requested By

Developer B

### Affected Owner

Developer A, Developer C / Sean Han, and Unreal

### Proposed Contract Change

Developer B now returns `npc_emotion` on `DevBPolicyOutput`. Allowed values are:

```text
Nomal
Joy
Anger
Sadness
Panic
Suspicion
Disgust
Fear
Smirk
Surprise
Pain
Confusion
Boredom
```

Current rule mapping:

- Normal successful progress: `Nomal`.
- Clarify, retry, or hint branches: `Confusion`.
- Warning, bad-end, or critical-risk branches: `Suspicion`.

Developer C follow-up already implemented in the pre-prototype:

- Pass `DevBPolicyOutput.npc_emotion` to Developer A as A-facing
  `npc.emotion`.
- Return the same value in the Unreal response as `npc.emotion`.

Developer A follow-up:

- Use A-facing `npc.emotion` as the preferred emotion cue when selecting NPC
  facial expression, TTS style, animation tone, or fallback behavior.
- Keep dialogue text generation A-owned; B only supplies the enum cue.

Unreal follow-up:

- Treat response `npc.emotion` as the current NPC emotion state for the turn.
- Map the enum values above to available facial expression/animation states.

### Compatibility Impact

This is an additive field. Existing clients that ignore `npc_emotion` or
response `npc.emotion` can continue using `npc.tone` and `npc.animation`.

### Current Verification

- `uv sync` completed.
- `uv run pytest` passed with 201 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

## Change Request - 2026-06-12 - Expand NPC Dialogue Client Payload for Dynamic Emotion & Audio Parameters

Status: Open.

### Requested By

Developer A

### Affected Owner

Developer C / Sean Han, and Developer B

### Reason

Developer A is refactoring the NPC Dialogue generation flow to use a dynamic, unified single agent design. Under this design:

1. ElevenLabs TTS parameters (stability, style, speed, similarity_boost) will be dynamically calculated by the LLM based on emotion and context, rather than hardcoded in the service layer.
2. The Level Design Agent will provide one of 13 official emotion types (`joy`, `panic`, `sad`, `suspicion`, `disgust`, `fear`, `smirk`, `normal`, `anger`, `surprise`, `pain`, `confusion`, `boredom`) in its payload to Developer A.
3. Roster-defined personas (e.g. `persona_instruction`) will be resolved and injected dynamically into the system prompt.
   This requires Developer C adapters and schemas to support the expanded output fields.

### Proposed Contract Change

Developer C should update the `dev_a_npc_dialogue_client.py` adapter and the shared Pydantic response schemas to accept the following fields returned by the Developer A dialogue agent:

```json
{
  "speaker": "Arabella",
  "npc_text": "Hi there! Welcome to the flight.",
  "tts_text": "Hi there! ... Welcome to the flight.",
  "feedback_kr": "반갑습니다! 편안한 비행 되세요.",
  "tone": "formal_neutral",
  "animation": "move",
  "npc_emotion": "joy",
  "stability": 0.75,
  "style": 0.45,
  "speed": 1.0,
  "similarity_boost": 0.85
}
```

Developer C follow-up:

- Update the Pydantic validator schemas in `backend/app/schemas/` to allow these new fields (or relax strict schema validation temporarily).
- Forward these audio tuning parameters to the TTS service wrapper for ElevenLabs invocation.
- Integrate the LangChain-based NPC Dialogue Agent as a **single node/subgraph** inside the main orchestrator graph (`developer_c_graph.py`).

Developer B follow-up:

- Update payloads to ensure the `npc_emotion` field from the Level Design Agent contains one of the 13 supported emotion strings.
- Pass the correct `npc_id` and player `tier` inside the payload.

### Compatibility Impact

This change is additive for schema fields. The fallback and legacy adapters can safely default to standard parameters if the new fields are not populated.

## Change Request - 2026-06-13 - Update Developer C Tests to Support TTS Slimming Refactor

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer C / Sean Han

### Reason

Developer A is executing the cleanup and TTS slimming refactor plan (removing Chatterbox/Kokoro packages and unifying fallback to Edge TTS).
Since the default fallback provider changes from `kokoro` to `edge`, integrated test cases owned by Developer C that assert or mock the `kokoro` audio URL path will fail.
Specifically:
- `backend/tests/test_preprototype_flow.py` (L840) expects `/runtime/audio/kokoro/` URL prefix.
- `backend/tests/test_demo_ai_respond_page.py` (L404) uses `/runtime/audio/kokoro/demo.wav` as mock data.
- `backend/tests/test_final_result_payload.py` (L243) uses `/runtime/audio/kokoro/final.wav` as mock data.

### Proposed Contract Change

1. Update `backend/tests/test_preprototype_flow.py` to assert the `edge` audio URL path prefix instead of `kokoro` (e.g. `assert body["npc"]["audio_url"].startswith("/runtime/audio/edge/")`).
2. Update mock URL configurations in `backend/tests/test_demo_ai_respond_page.py` and `backend/tests/test_final_result_payload.py` to point to `/runtime/audio/edge/` paths.
3. This aligns with Developer A's refactored `voice_output_service.py` where the default fallback and served directory name is changed from `kokoro` to `edge`.

### Compatibility Impact

This change will resolve failing assertions in Developer C's integration tests after Developer A finishes removing the `kokoro` and `chatterbox` libraries. Until this change is made, `pytest` will fail during the integration validation phase.

### Temporary Workaround

Developer A can temporarily comment out or bypass these assertions during local development of Service A services, but the repository main branch tests will remain broken until Developer C applies these updates to the test assertions.

## Change Request - 2026-06-13 - Remove Deprecated Miller NPC and Update Default NPC to Hale

### Requested By

Developer C / Sean Han

### Affected Owner

Developer A / kimyonghee

### Reason

1. 기획 사양(스토리보드)에서 제외된 레거시 캐릭터인 `miller`를 완전히 삭제하여 기술적 부채를 청산합니다.
2. 실제 챕터 0의 메인 입국심사관 NPC인 `hale`을 기본(Default) NPC로 설정하여 기획 정합성을 높입니다.
3. 이에 따른 전체 소스코드와 유닛 테스트 코드의 종속성을 해소하여 일관된 에이전트 동작을 보장합니다.

### Proposed Contract Change

1. [npc_roster_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/npc_roster_service.py)에서 `miller` 객체를 삭제하고 `_DEFAULT_NPC_ID`를 `"hale"`로 수정합니다.
2. `_normalize_npc_id` 정규화 함수에 레거시 하위 호환 매핑 로직을 추가하여, 외부(Unreal) 또는 테스트에서 구 규격인 `"miller"`나 `"officer_miller"`를 참조해 통신을 시도해도 자동으로 `"hale"` 프로필로 변환 및 리턴하도록 조치합니다.
3. [voice_profile_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/voice_profile_service.py)에서 `miller` 음성 설정을 지웁니다.
4. 백엔드 및 전체 유닛 테스트 코드에서 `miller`를 기용한 Assertion 및 Mock 설정을 `hale`로 통일 및 갱신합니다.

### Compatibility Impact

레거시 `officer_miller` 혹은 `miller` 데이터가 전달되더라도 백엔드에서 자체적으로 `hale`로 안전하게 리다이렉트 처리(하위 호환)하기 때문에, 언리얼 엔진의 통신이나 외부 API 연동 흐름이 깨지지 않습니다.

### Temporary Workaround

해당 없음 (전면 리팩터링 적용 완료).

## Change Request - 2026-06-15 - Deprecate NPCDialogueAgentRunMiddleware and Transition to NPCDialogueAgentRunRecorder

### Requested By

Developer A / kimyonghee

### Affected Owner

Developer C / Sean Han

### Reason

LangChain 1.0+ 및 LCEL 체인 호출 구조 하에서 기존의 LangChain 0.x 방식 콜백/미들웨어 훅 작동 방식이 표준 규격에 어긋나 타입 경고 및 런타임 오류가 유발될 수 있습니다. 이를 해소하기 위해 상태 기계 및 서비스 내에서 명시적으로 동작하는 `NPCDialogueAgentRunRecorder`를 신설하고, 기존 미들웨어 클래스 `NPCDialogueAgentRunMiddleware`를 Deprecated 처리했습니다.

### Proposed Contract Change

1. Developer C는 향후 A/B/C 통합 레이어 및 오케스트레이터에서 `NPCDialogueAgentRunMiddleware`를 활용하여 callback 형태로 로깅 이벤트를 캡처하는 대신, `NPCDialogueAgentRunRecorder`를 직접 또는 오케스트레이터의 RunnableConfig/Callbacks 설정 내에서 호출하도록 교체할 것을 제안합니다.
2. 현재의 하위 호환성을 보장하기 위해 `NPCDialogueAgentRunMiddleware`는 Shim 형태로 남겨두어 `warnings.warn` 경고를 출력하며 내부적으로 `NPCDialogueAgentRunRecorder`로 작업을 위임하도록 처리했습니다. 향후 완전한 통합 정리를 위해 호출 부분의 마이그레이션이 필요합니다.

### Compatibility Impact

Shim 클래스가 존재하므로 당장의 통합 테스트 및 실행은 깨지지 않으나, 컴파일/정적 분석 경고(DeprecationWarning)가 콘솔에 찍히게 됩니다.

### Temporary Workaround

현재 구현된 Shim 미들웨어가 자동으로 새 기록기를 대리 호출하므로, 즉각적인 수정은 불필요하지만 중장기적으로 `NPCDialogueAgentRunRecorder` 직접 사용으로의 전환을 권장합니다.

### Current Verification

- `uv sync` 완료.
- `uv run pytest` 결과 231개 전체 테스트 성공 (Shim 미들웨어가 정상적으로 경고를 출력하며 이벤트를 위임하여 로깅되는 것 확인).
- `uv run ruff check .` 및 `uv run mypy .` 무오류 통과.
