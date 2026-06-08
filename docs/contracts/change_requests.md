# Change Requests

No cross-owner change requests have been filed.

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

### Requested By
Developer B

### Affected Owner
Developer C / Sean Han

### Reason
Developer B now exposes a real deterministic `dev_b_policy.v1` policy engine
under `backend/app/agents/agent_b/` and `backend/app/services/service_b/`.
The current runtime still calls the C-owned mock adapter at
`backend/app/integrations/dev_b_level_hint_client.py`.

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
