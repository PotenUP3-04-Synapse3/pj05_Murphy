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
