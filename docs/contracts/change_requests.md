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
`FLIGHT_001_SEATMATE_SMALLTALK -> IMMIGRATION_ALPHA -> BAGGAGE_MISSING`, silent
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

| Key | Value | Meaning |
| --- | --- | --- |
| `npc_question_goal` | string such as `ask_stay_duration` | Communicative goal for Developer A generation |
| `required_slots` | list of strings | Information Developer A should prompt for |
| `target_slot` | string or null | Primary slot for the current dialogue turn |
| `npc_speech_speed` | integer `0-10` | `0` = very slow and learner-friendly, `10` = near-native fast |
| `question_complexity` | integer `0-10` | `0` = very simple one-part question, `10` = complex multi-part question |
| `emotion_change` | `positive`, `neutral`, `negative` | NPC emotional/tone direction caused by the current turn |

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
FLIGHT_001_SEATMATE_SMALLTALK
-> FLIGHT_002_TRAVEL_PURPOSE
-> FLIGHT_003_STAY_PLAN
-> FLIGHT_004_CLARIFY_OR_ASK_BACK
-> FLIGHT_005_WRAP_UP
-> IMM_001_PASSPORT
-> existing IMM_* route
-> IMM_007_FINAL_DECISION
-> BAG_001_NOTICE_BAG_MISSING
-> existing BAG_* route
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
- Add Understanding coverage for the new flight and `BAG_001` slots.

Developer A follow-up:

- Generate actual NPC dialogue/TTS for the five `FLIGHT_*` seatmate nodes from
  `dialogue_seed`, not from B-authored final lines.
- Generate baggage service dialogue for `BAG_001_NOTICE_BAG_MISSING` and the
  existing missing-bag route from role/goal/slot metadata.
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
