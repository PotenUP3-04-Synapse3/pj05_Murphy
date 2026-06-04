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

## Change Request - 2026-06-04 - Shared AgentRun Persistence Contract

### Requested By
Developer A

### Affected Owner
Developer C / Sean Han

### Reason
NPC Dialogue Agent should eventually persist structured execution records in
the same shared AgentRun table pattern used by the Slack Agent. Developer A now
has a temporary JSONL implementation so runs can be inspected during prototype
work, but a shared persistence contract is needed for production integration.

### Proposed Contract Change
Provide or approve a shared AgentRun persistence interface with these fields:

- `agent_run_id`
- `agent_name`
- `prompt_version`
- `status`
- `source_window`
- `cache_key`
- `model_name`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `estimated_cost_usd`
- `permission_level`
- `metadata`
- `created_at`
- `completed_at`

Developer A artifacts should also be linkable by `agent_run_id` and include
`npc_text`, `tts_text`, `feedback_kr`, `audio_url`, `audio_path`, source links,
and source snippets.

### Temporary Workaround
Developer A appends table-like JSONL records under:

- `backend/runtime/agent_runs/npc_dialogue_agent_runs.jsonl`
- `backend/runtime/agent_runs/npc_dialogue_artifacts.jsonl`

### Needed Decision
Developer C should decide whether NPC Dialogue AgentRun records become part of
the shared backend DB, and whether Developer A artifacts are exposed in Unreal
responses or kept as internal operation logs only.

## Change Request - 2026-06-04 - Unified AgentRun JSONL and Markdown Log Contract

### Requested By
Developer A / kimyonghee

### Affected Owner
Developer B, Developer C / Sean Han

### Reason
The demo/debug flow needs one place where a reviewer can see which agent ran,
what input summary it used, which tools/middleware steps executed, what output
was produced, and where the final audio/text artifacts went. Developer A now
appends NPC Dialogue Agent records to the shared log paths, but B/C entrypoints
must opt in from their own owned code to complete the full turn trace.

### Proposed Contract Change
Append one structured record per agent execution to:

- `backend/runtime/generated/agent_runs/unified_agent_runs.jsonl`
- `backend/runtime/generated/agent_runs/unified_agent_runs.md`

Use schema version `unified_agent_run.v1` with these top-level fields:

- `agent_run_id`
- `agent_name`
- `owner`
- `request_id`
- `session_id`
- `turn_index`
- `status`
- `started_at`
- `completed_at`
- `source_window`
- `model`
- `events`
- `summary`
- `metadata`

Each developer should build `events` inside their own agent middleware/service.
The shared writer only appends records and must not inspect or mutate another
developer's business logic.

### Requested Developer B Work
Developer B should append `english_level_hint_agent` records that include:

- agent start/end
- scenario node and policy input summary
- level/hint/scenario-state tool steps
- branch/next-node decision summary
- LLM feedback metadata when enabled
- fallback/skip/failure reason when applicable

### Requested Developer C Work
Developer C should append orchestrator-level records that include:

- request receipt and normalized source window
- STT step result summary
- OpenKB node lookup summary
- Understanding Agent result summary
- Developer B adapter call summary
- Developer A adapter call summary
- response builder and validator summary
- final response/audio trace identifiers

Developer C should also pass stable `request_id`, `session_id`, and
`turn_index` into A/B calls so all agent records from one player turn can be
grouped.

### Compatibility Impact
Additive only. Existing per-agent JSONL logs remain available. The shared JSONL
and Markdown files are prototype runtime artifacts and should not be treated as
authoritative game state.

### Temporary Workaround
Until B/C are connected, Developer A records its own runs in both:

- `npc_dialogue_agent_runs.jsonl`
- `unified_agent_runs.jsonl`
- `unified_agent_runs.md`
