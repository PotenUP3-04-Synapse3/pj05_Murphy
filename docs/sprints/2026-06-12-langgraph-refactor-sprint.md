# Sprint LG - Developer C LangGraph Refactor

## Goal

Refactor Developer C orchestration from a hardcoded procedural method into a
LangGraph v1.2.2 workflow while preserving the existing public API,
Developer A/B adapter boundaries, unified AgentRun append behavior, and test
safe runtime modes.

## Scope

- C-owned graph state and compiled graph live in `backend/app/graphs/graph.py`.
- C-owned graph tool wrappers live in
  `backend/app/tools/tool_c/developer_c_graph_tools.py`.
- `Orchestrator.run_turn()` remains the stable public entry point, but now
  invokes the compiled graph.
- Developer A and Developer B implementation files remain read-only. C calls
  them only through existing adapters.

## Sprint Items

| Item | Status | Notes |
| --- | --- | --- |
| LG-0 Contract alignment | Done | C graph keeps B branch authority and C validation ownership. |
| LG-1 State and graph.py | Done | `DeveloperCTurnState` carries request, tool object, intermediate outputs, transition, response, and timing. |
| LG-2 tool_c graph tools | Done | STT, OpenKB, Understanding, B adapter, validation, logging, A adapter, response build, and final validation run through C tool wrappers. Each wrapper is now exposed as a LangChain `StructuredTool`. |
| LG-3 Orchestrator replacement | Done | The procedural `run_turn()` body was removed; `run_turn()` now invokes LangGraph. |
| LG-4 Alpha transition alignment | Done | C tests and flow metadata now follow current B transition nodes such as `IMM_999_CLEARED` and `BAG_001_REPORT_MISSING_AT_DESK`. |
| LG-5 StructuredTool compatibility | Done | `DeveloperCGraphTools` exposes `structured_tools`, invokes nodes through `.invoke(...)`, and provides `as_tool_node_tools()` for future LangGraph `ToolNode` mounting. |
| LG-6 A/B follow-up | Open | A/B may later refactor their own internals into LangGraph without changing C adapter calls. |

## Current Graph Nodes

```text
start_agent_run
-> transcribe_audio
-> load_node_context
-> understand_player_text
-> evaluate_dev_b_policy
-> validate_dev_b_policy
-> record_error_capture
-> generate_dev_a_dialogue
-> build_unreal_response
-> validate_unreal_response
-> finish_agent_run
```

## Verification

Latest verification is recorded in `docs/handoff.md` for the implementation
commit that includes this sprint update.
