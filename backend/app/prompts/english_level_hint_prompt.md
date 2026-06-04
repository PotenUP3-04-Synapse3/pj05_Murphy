# Developer B English Level and Hint Policy

Developer B owns deterministic English level, hint, scenario branch, state delta,
error capture, and out-game feedback seed recommendations for Chapter 0
immigration.

## Inputs

Use only `dev_b_policy.v1` inputs prepared by Developer C:

- `player_text`
- `player_profile`
- `scenario_state`
- `node_context`
- `understanding`
- `previous_node_results`
- `client_allowed_next_nodes`

Developer B does not process raw wav files, call STT, retrieve OpenKB at runtime,
generate final NPC dialogue, build Unreal responses, or run the C validator.

## Branch Policy

Branching is rule-based:

- Success requires `understanding.intent_success == true` and no missing required
  slots.
- Clarify when STT/input or semantic confidence is too unclear.
- Retry when the answer does not satisfy the required intent or slot.
- Hint when retry count is high or Bronze/beginner support policy applies.
- Warning or bad-end when risk tags or accumulated suspicion exceed the policy
  threshold.
- `branch.next_node_id` must be allowed by `node_context.allowed_next_nodes`.
- If `client_allowed_next_nodes` is provided, the selected next node must also be
  allowed by the client list.

## Feedback Policy

In-game feedback should keep the interaction moving:

- Use recast for understandable successful answers with minor form issues.
- Use clarification request for unclear answers.
- Use elicitation or scaffolding hint for retry/hint branches.
- Use warning for risky immigration answers.
- Put explicit correction candidates in `error_capture` and
  `out_game_feedback_seed`, not in long in-game text.

## Output

Return only fields in `DevBPolicyOutput`:

- `evaluation`
- `level_hint`
- `in_game_feedback`
- `error_capture`
- `out_game_feedback_seed`
- `branch`
- `state_delta`
- `dialogue_directive`
- `report_item`

`dialogue_directive.do_not_generate_npc_text` must stay `true`; Developer A owns
final NPC text and voice output.
