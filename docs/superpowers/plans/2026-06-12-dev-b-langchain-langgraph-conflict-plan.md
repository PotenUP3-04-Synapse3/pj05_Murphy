# Developer B LangChain/LangGraph Conflict Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve merge-created functional conflicts in Developer B scope and wrap Developer B's existing policy agent in a B-owned LangGraph/LangChain-style runnable without changing Developer C's adapter contract.

**Architecture:** Keep `DevBPolicyClient.evaluate_turn(payload) -> DevBPolicyOutput` unchanged. Move the internal sequencing currently inside `EnglishLevelHintAgent.evaluate_turn()` into a B-owned linear LangGraph, with concrete service calls in `backend/app/tools/tool_b/`; B remains the only branch, verdict, state-delta, hint, level, and final-score policy authority. Apply the B-owned follow-up from the latest handoff by separating baggage service and customs-officer `dialogue_seed.npc_role` metadata while keeping final NPC wording owned by Developer A.

**Tech Stack:** Python 3.12, uv, Pydantic schemas in `backend/app/schemas/game_turn.py`, `langchain==1.3.2`, `langgraph==1.2.2`, pytest, ruff, mypy.

---

## Scope And Ownership

**B-owned files to modify:**
- `backend/app/agents/agent_b/english_level_hint_agent.py`
- `backend/app/agents/agent_b/policy_graph.py`
- `backend/app/tools/tool_b/__init__.py`
- `backend/app/tools/tool_b/developer_b_policy_graph_tools.py`
- `backend/tests/dev_b/test_developer_b_policy_engine.py`
- `backend/tests/dev_b/test_developer_b_agent_run_log.py`
- `docs/handoff.md`

**Shared contract docs to update carefully if behavior changes are implemented:**
- `docs/contracts/change_requests.md`
- `docs/contracts/developer_b_report_and_dialogue_seed_contract.md`

**Read-only reference files for this work:**
- `backend/app/graphs/graph.py`
- `backend/app/tools/tool_c/developer_c_graph_tools.py`
- `backend/app/services/service_c/orchestrator.py`
- `backend/app/integrations/dev_b_level_hint_client.py`
- Developer A/C implementation files outside B-owned paths.

**Conflict-resolution rules:**
- Prefer current `DevBPolicyInput` / `DevBPolicyOutput` schema compatibility over internal refactor convenience.
- Preserve B's rule-based branch authority in `ScenarioStateMachine`.
- Do not let any LangChain or LLM layer generate or override `branch`, `next_node_id`, `next_action`, `evaluation.verdict`, `state_delta`, Unreal commands, NPC final dialogue, TTS, audio, tone realization, or animation.
- Keep `dialogue_directive.do_not_generate_npc_text` for one compatibility cycle because C still accepts the legacy field; prefer `dialogue_seed` for new A-facing metadata.
- Treat C/A/Unreal follow-ups in `change_requests.md` as coordination items, not B implementation targets, unless they affect B-owned metadata.

---

### Task 1: Baseline Conflict Audit

**Files:**
- Read: all files from `git status --short`
- Read: `docs/handoff.md`
- Read: `docs/contracts/change_requests.md`
- Read: `docs/sprints/2026-06-12-langgraph-refactor-sprint.md`
- Read: `backend/app/agents/agent_b/english_level_hint_agent.py`
- Read: `backend/app/integrations/dev_b_level_hint_client.py`

- [ ] **Step 1: Check for unresolved conflict markers**

Run:

```powershell
git status --short
rg -n "<<<<<<<|=======|>>>>>>>" .
```

Expected: no unresolved conflict markers. If markers exist in A/C-owned files, stop and append a request to `docs/contracts/change_requests.md` instead of resolving inside their implementation.

- [ ] **Step 2: Capture B-owned conflict decisions**

For each conflict in B-owned files, choose the side that satisfies these invariants:

```text
DevBPolicyClient.evaluate_turn(payload) still returns DevBPolicyOutput.
EnglishLevelHintAgent.evaluate_turn(payload) remains the public B agent method.
ScenarioStateMachine.decide(payload) remains rule-based branch authority.
FeedbackHintGenerator may enrich feedback only; it cannot change branch/state/verdict.
OpenKBFeedbackWriter writes only under dev_b namespace.
```

- [ ] **Step 3: Run the current B regression set before refactor**

Run:

```powershell
uv run pytest backend/tests/dev_b -q
```

Expected: pass before implementation. If it fails, classify the failing file by owner and fix only B-owned failures in this plan.

---

### Task 2: Add Tests For The B LangGraph Wrapper

**Files:**
- Modify: `backend/tests/dev_b/test_developer_b_agent_run_log.py`

- [ ] **Step 1: Add graph shape and metadata test**

Add this test near the top of `backend/tests/dev_b/test_developer_b_agent_run_log.py` after `_agent_run_records`:

```python
def test_developer_b_graph_exposes_readable_state_and_compiled_langgraph() -> None:
    from backend.app.agents.agent_b.policy_graph import (
        DEVELOPER_B_POLICY_GRAPH_NODE_NAMES,
        DeveloperBPolicyState,
        build_developer_b_policy_graph,
    )

    graph_app = build_developer_b_policy_graph()

    assert callable(graph_app.invoke)
    assert list(DEVELOPER_B_POLICY_GRAPH_NODE_NAMES) == [
        "start_agent_run",
        "decide_scenario_branch",
        "derive_level_and_hint",
        "derive_feedback_strategy",
        "evaluate_tier_difficulty",
        "build_base_policy_output",
        "generate_feedback_hint",
        "apply_feedback_generation",
        "attach_report_and_dialogue_seeds",
        "validate_policy_output",
        "write_openkb_feedback",
        "finish_agent_run",
    ]
    assert set(DeveloperBPolicyState.__annotations__) >= {
        "payload",
        "tools",
        "agent_run",
        "input_summary",
        "decision",
        "english_level",
        "hint_policy",
        "feedback_strategy",
        "has_form_issue",
        "tier_result",
        "output",
        "feedback_generation",
        "openkb_write",
    }
```

- [ ] **Step 2: Extend the existing AgentRun success test**

In `test_developer_b_appends_unified_agent_run_for_success_turn`, after the existing metadata assertions, add:

```python
    assert record["metadata"]["runtime"] == {
        "policy_engine": "langgraph",
        "graph_name": "developer_b_policy_graph",
        "tool_style": "developer_b_policy_graph_tools",
        "graph_nodes": [
            "start_agent_run",
            "decide_scenario_branch",
            "derive_level_and_hint",
            "derive_feedback_strategy",
            "evaluate_tier_difficulty",
            "build_base_policy_output",
            "generate_feedback_hint",
            "apply_feedback_generation",
            "attach_report_and_dialogue_seeds",
            "validate_policy_output",
            "write_openkb_feedback",
            "finish_agent_run",
        ],
    }
```

- [ ] **Step 3: Verify the tests fail before implementation**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py::test_developer_b_graph_exposes_readable_state_and_compiled_langgraph backend/tests/dev_b/test_developer_b_agent_run_log.py::test_developer_b_appends_unified_agent_run_for_success_turn -q
```

Expected: fail because `backend.app.agents.agent_b.policy_graph` does not exist yet or runtime metadata is missing.

---

### Task 3: Add Tests For Baggage Service Versus Customs Role Metadata

**Files:**
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`

- [ ] **Step 1: Add role-specific dialogue seed regression**

Add this test after `test_dialogue_seed_contains_generation_metadata_without_final_npc_text`:

```python
@pytest.mark.parametrize(
    ("node_id", "expected_role"),
    [
        ("BAG_001_REPORT_MISSING_AT_DESK", "baggage_service_agent"),
        ("BAG_002_PROVIDE_CLAIM_TAG", "baggage_service_agent"),
        ("BAG_003_CONFIRM_SEARCHED_CAROUSEL", "baggage_service_agent"),
        ("BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD", "baggage_service_agent"),
        ("BAG_005_CUSTOMS_HOLD_EXPLANATION", "customs_officer"),
        ("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM", "customs_officer"),
        ("BAG_007_CUSTOMS_CLEARANCE", "customs_officer"),
    ],
)
def test_dialogue_seed_routes_baggage_service_and_customs_roles(
    node_id: str,
    expected_role: str,
    tmp_path: Path,
) -> None:
    context = _node_context(node_id)

    result = _agent(tmp_path).evaluate_turn(
        _policy_input(
            node_context=context,
            player_text=context.recommended_expression,
            intent_success=True,
            confidence=0.92,
            extracted_slots={context.required_slots[0]: "acknowledged"},
            missing_slots=[],
            tier="Silver",
            client_allowed_next_nodes=context.allowed_next_nodes,
        )
    )

    assert result.dialogue_seed is not None
    assert result.dialogue_seed.npc_role == expected_role
```

- [ ] **Step 2: Verify the role test fails before implementation**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_dialogue_seed_routes_baggage_service_and_customs_roles -q
```

Expected: fail for `BAG_005`, `BAG_006`, and `BAG_007` because current `_npc_role()` returns `baggage_service_agent` for all `BAG_*`.

---

### Task 4: Create B-Owned LangGraph Policy Graph

**Files:**
- Create: `backend/app/agents/agent_b/policy_graph.py`

- [ ] **Step 1: Add graph state and node order**

Create `backend/app/agents/agent_b/policy_graph.py`:

```python
from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.schemas.game_turn import DevBPolicyInput, DevBPolicyOutput, OpenKBWriteResult
from backend.app.services.service_b.feedback_hint_generator import FeedbackHintGeneration
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision
from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyResult
from backend.app.tools.tool_b.developer_b_policy_graph_tools import (
    DEVELOPER_B_POLICY_GRAPH_NODE_NAMES as _DEVELOPER_B_POLICY_GRAPH_NODE_NAMES,
    DeveloperBPolicyGraphTools,
)


DEVELOPER_B_POLICY_GRAPH_NODE_NAMES = _DEVELOPER_B_POLICY_GRAPH_NODE_NAMES


class DeveloperBPolicyState(TypedDict):
    payload: DevBPolicyInput
    tools: DeveloperBPolicyGraphTools
    agent_run: NotRequired[dict[str, Any]]
    input_summary: NotRequired[dict[str, Any]]
    decision: NotRequired[ScenarioDecision]
    english_level: NotRequired[str]
    hint_policy: NotRequired[tuple[bool, str, str | None, str | None]]
    feedback_strategy: NotRequired[str]
    has_form_issue: NotRequired[bool]
    tier_result: NotRequired[TierDifficultyResult]
    output: NotRequired[DevBPolicyOutput]
    feedback_generation: NotRequired[FeedbackHintGeneration]
    openkb_write: NotRequired[OpenKBWriteResult]


def build_initial_developer_b_policy_state(
    *,
    payload: DevBPolicyInput,
    tools: DeveloperBPolicyGraphTools,
) -> DeveloperBPolicyState:
    return {"payload": payload, "tools": tools}


def build_developer_b_policy_graph() -> Any:
    graph = StateGraph(DeveloperBPolicyState)
    graph.add_node("start_agent_run", _start_agent_run)
    graph.add_node("decide_scenario_branch", _decide_scenario_branch)
    graph.add_node("derive_level_and_hint", _derive_level_and_hint)
    graph.add_node("derive_feedback_strategy", _derive_feedback_strategy)
    graph.add_node("evaluate_tier_difficulty", _evaluate_tier_difficulty)
    graph.add_node("build_base_policy_output", _build_base_policy_output)
    graph.add_node("generate_feedback_hint", _generate_feedback_hint)
    graph.add_node("apply_feedback_generation", _apply_feedback_generation)
    graph.add_node("attach_report_and_dialogue_seeds", _attach_report_and_dialogue_seeds)
    graph.add_node("validate_policy_output", _validate_policy_output)
    graph.add_node("write_openkb_feedback", _write_openkb_feedback)
    graph.add_node("finish_agent_run", _finish_agent_run)

    graph.add_edge(START, "start_agent_run")
    graph.add_edge("start_agent_run", "decide_scenario_branch")
    graph.add_edge("decide_scenario_branch", "derive_level_and_hint")
    graph.add_edge("derive_level_and_hint", "derive_feedback_strategy")
    graph.add_edge("derive_feedback_strategy", "evaluate_tier_difficulty")
    graph.add_edge("evaluate_tier_difficulty", "build_base_policy_output")
    graph.add_edge("build_base_policy_output", "generate_feedback_hint")
    graph.add_edge("generate_feedback_hint", "apply_feedback_generation")
    graph.add_edge("apply_feedback_generation", "attach_report_and_dialogue_seeds")
    graph.add_edge("attach_report_and_dialogue_seeds", "validate_policy_output")
    graph.add_edge("validate_policy_output", "write_openkb_feedback")
    graph.add_edge("write_openkb_feedback", "finish_agent_run")
    graph.add_edge("finish_agent_run", END)
    return graph.compile()
```

- [ ] **Step 2: Add node functions**

Append to the same file:

```python
def _start_agent_run(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].start_agent_run_tool(state)


def _decide_scenario_branch(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].decide_scenario_branch_tool(state)


def _derive_level_and_hint(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].derive_level_and_hint_tool(state)


def _derive_feedback_strategy(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].derive_feedback_strategy_tool(state)


def _evaluate_tier_difficulty(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].evaluate_tier_difficulty_tool(state)


def _build_base_policy_output(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].build_base_policy_output_tool(state)


def _generate_feedback_hint(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].generate_feedback_hint_tool(state)


def _apply_feedback_generation(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].apply_feedback_generation_tool(state)


def _attach_report_and_dialogue_seeds(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].attach_report_and_dialogue_seeds_tool(state)


def _validate_policy_output(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].validate_policy_output_tool(state)


def _write_openkb_feedback(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].write_openkb_feedback_tool(state)


def _finish_agent_run(state: DeveloperBPolicyState) -> dict[str, Any]:
    return state["tools"].finish_agent_run_tool(state)
```

- [ ] **Step 3: Run the graph import test**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py::test_developer_b_graph_exposes_readable_state_and_compiled_langgraph -q
```

Expected: still fail until `DeveloperBPolicyGraphTools` exists.

---

### Task 5: Create B-Owned Graph Tools And Move Existing Sequencing

**Files:**
- Create: `backend/app/tools/tool_b/__init__.py`
- Create: `backend/app/tools/tool_b/developer_b_policy_graph_tools.py`
- Modify: `backend/app/agents/agent_b/english_level_hint_agent.py`

- [ ] **Step 1: Create the B tool package**

Create `backend/app/tools/tool_b/__init__.py`:

```python
"""Developer B owned graph tool wrappers."""
```

- [ ] **Step 2: Create graph tool constants and constructor**

Create `backend/app/tools/tool_b/developer_b_policy_graph_tools.py` with imports copied from `english_level_hint_agent.py` plus:

```python
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import DevBPolicyInput, DevBPolicyOutput, OpenKBWriteResult
from backend.app.services.service_b.developer_b_agent_run_logger import DeveloperBAgentRunLogger
from backend.app.services.service_b.feedback_hint_generator import FeedbackHintGenerator
from backend.app.services.service_b.level_adaptation_controller import LevelAdaptationController
from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision, ScenarioStateMachine
from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyController


DEVELOPER_B_POLICY_GRAPH_NAME = "developer_b_policy_graph"
DEVELOPER_B_POLICY_GRAPH_TOOL_STYLE = "developer_b_policy_graph_tools"
DEVELOPER_B_POLICY_GRAPH_NODE_NAMES = (
    "start_agent_run",
    "decide_scenario_branch",
    "derive_level_and_hint",
    "derive_feedback_strategy",
    "evaluate_tier_difficulty",
    "build_base_policy_output",
    "generate_feedback_hint",
    "apply_feedback_generation",
    "attach_report_and_dialogue_seeds",
    "validate_policy_output",
    "write_openkb_feedback",
    "finish_agent_run",
)


class DeveloperBPolicyGraphTools:
    def __init__(
        self,
        *,
        state_machine: ScenarioStateMachine | None = None,
        level_controller: LevelAdaptationController | None = None,
        tier_controller: TierDifficultyController | None = None,
        feedback_generator: FeedbackHintGenerator | None = None,
        openkb_writer: Any | None = None,
        agent_run_root: Path | None = None,
        agent_run_logger: DeveloperBAgentRunLogger | None = None,
    ) -> None:
        self.state_machine = state_machine or ScenarioStateMachine()
        self.level_controller = level_controller or LevelAdaptationController()
        self.tier_controller = tier_controller or TierDifficultyController()
        self.feedback_generator = feedback_generator or FeedbackHintGenerator()
        self.openkb_writer = openkb_writer or OpenKBFeedbackWriter()
        self.agent_run_logger = agent_run_logger or DeveloperBAgentRunLogger(agent_run_root)
        self.active_agent_run: dict[str, Any] | None = None
```

- [ ] **Step 3: Move helper functions from `english_level_hint_agent.py`**

Move these methods into `DeveloperBPolicyGraphTools` without changing behavior:

```text
_build_evaluation
_build_in_game_feedback
_build_error_capture
_build_out_game_feedback_seed
_build_report_seed_summary
_report_seed_category_scores
_report_seed_strengths
_report_seed_critical_breakdowns
_report_seed_corrected_examples
_scenario_result_candidate
_build_dialogue_seed
_npc_role
_opening_intent
_allowed_followup_intents
_build_dialogue_directive
_build_npc_emotion
_build_report_item
_feedback_tags
_feedback_note
_avoid_expression
_recast_candidate
_clarification_candidate
_elicitation_candidate
_error_type
_focus_on_form_target
_affected_scores
_focus_on_form_explanation
```

Also move these module-level helpers into `developer_b_policy_graph_tools.py`:

```text
_policy_input_summary
_score_candidate
_average_score_candidate
_unique_non_empty
_report_issue_type
_why_issue_matters
_decision_summary
_feedback_generation_summary
_openkb_write_summary
_policy_output_summary
_feedback_fallback_used
_model_name
_preview
_validate_b_policy_output
_immigration_focus_target
```

Keep `_validate_b_policy_output` import-compatible by re-exporting it from `english_level_hint_agent.py` in Task 6.

- [ ] **Step 4: Add runtime metadata helper**

Add this function to `developer_b_policy_graph_tools.py`:

```python
def _attach_langgraph_runtime_metadata(agent_run: dict[str, Any]) -> None:
    metadata = agent_run.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        agent_run["metadata"] = metadata

    metadata["runtime"] = {
        "policy_engine": "langgraph",
        "graph_name": DEVELOPER_B_POLICY_GRAPH_NAME,
        "tool_style": DEVELOPER_B_POLICY_GRAPH_TOOL_STYLE,
        "graph_nodes": list(DEVELOPER_B_POLICY_GRAPH_NODE_NAMES),
    }
```

- [ ] **Step 5: Add graph tool methods**

Add these methods to `DeveloperBPolicyGraphTools`; their bodies should use the same operations and event names as the current `EnglishLevelHintAgent.evaluate_turn()`:

```python
    def start_agent_run_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        agent_run = self.agent_run_logger.start_run(payload)
        self.active_agent_run = agent_run
        _attach_langgraph_runtime_metadata(agent_run)
        input_summary = _policy_input_summary(payload)
        self.agent_run_logger.record_event(
            agent_run,
            event="agent_start",
            status="started",
            data_loaded=input_summary,
        )
        self.agent_run_logger.record_data_flow(
            agent_run,
            from_node="dev_b_policy_input",
            to_node="scenario_state_machine",
            payload_summary=input_summary,
        )
        return {"agent_run": agent_run, "input_summary": input_summary}

    def decide_scenario_branch_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        agent_run = _require_agent_run(state)
        input_summary = _require_dict(state, "input_summary")
        decision = self.state_machine.decide(payload)
        self.agent_run_logger.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="scenario_state_machine.decide",
            input_summary=input_summary,
            output_summary=_decision_summary(decision),
        )
        return {"decision": decision}
```

Implement the remaining tool methods by moving each matching block from the current `evaluate_turn()`:

```text
derive_level_and_hint_tool:
  english_level = self.level_controller.english_level(payload)
  needs_hint, hint_level, hint_type, hint_kr = self.level_controller.hint_policy(payload, decision)

derive_feedback_strategy_tool:
  feedback_strategy = self.level_controller.feedback_strategy(decision)
  has_form_issue = self.level_controller.has_form_issue(payload)

evaluate_tier_difficulty_tool:
  tier_result = self.tier_controller.evaluate(payload, decision, has_form_issue=has_form_issue)

build_base_policy_output_tool:
  output = DevBPolicyOutput(...) using the existing construction logic

generate_feedback_hint_tool:
  feedback_generation = self.feedback_generator.generate(...)

apply_feedback_generation_tool:
  apply feedback_generation updates to output and tier_result exactly as current code does

attach_report_and_dialogue_seeds_tool:
  output = output.model_copy(update={"report_seed_summary": ..., "dialogue_seed": ...})

validate_policy_output_tool:
  _validate_b_policy_output(payload, output)

write_openkb_feedback_tool:
  call self.openkb_writer.write_policy_output(payload, output), catch failures with failure_result
  return output with openkb_write attached

finish_agent_run_tool:
  record agent_end and complete_and_append using _policy_output_summary, _feedback_fallback_used, _model_name
```

- [ ] **Step 6: Add state validators**

Add these helpers to `developer_b_policy_graph_tools.py`:

```python
def _require_state_value(state: Mapping[str, Any], key: str, expected_type: type[Any]) -> Any:
    value = state.get(key)
    if not isinstance(value, expected_type):
        raise RuntimeError(f"Developer B graph state is missing required value: {key}")
    return value


def _require_agent_run(state: Mapping[str, Any]) -> dict[str, Any]:
    value = state.get("agent_run")
    if isinstance(value, dict):
        return value
    raise RuntimeError("Developer B graph state is missing required value: agent_run")


def _require_dict(state: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = state.get(key)
    if isinstance(value, dict):
        return value
    raise RuntimeError(f"Developer B graph state is missing required dict: {key}")
```

- [ ] **Step 7: Add failure completion method**

Add this method to `DeveloperBPolicyGraphTools`:

```python
    def complete_failed_run(self, payload: DevBPolicyInput, exc: Exception) -> None:
        if self.active_agent_run is None:
            return

        agent_run = self.active_agent_run
        input_summary = _policy_input_summary(payload)
        error_summary = {"error": str(exc), "error_type": exc.__class__.__name__}
        self.agent_run_logger.record_event(
            agent_run,
            event="agent_end",
            status="failed",
            error=str(exc),
        )
        self.agent_run_logger.fail_and_append(
            agent_run,
            error=exc,
            summary={
                "input": input_summary,
                "output": error_summary,
                "fallback_used": False,
                "audio_url": None,
            },
        )
        self.active_agent_run = None
```

- [ ] **Step 8: Run graph import test**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py::test_developer_b_graph_exposes_readable_state_and_compiled_langgraph -q
```

Expected: pass once imports and node constants match.

---

### Task 6: Refactor `EnglishLevelHintAgent` Into A Thin Graph Wrapper

**Files:**
- Modify: `backend/app/agents/agent_b/english_level_hint_agent.py`

- [ ] **Step 1: Replace internal sequencing with graph invocation**

Keep the public constructor signature. Replace `evaluate_turn()` with:

```python
    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        from backend.app.agents.agent_b.policy_graph import build_initial_developer_b_policy_state

        state = build_initial_developer_b_policy_state(payload=payload, tools=self.graph_tools)
        try:
            final_state = self.graph.invoke(state)
        except Exception as exc:
            self.graph_tools.complete_failed_run(payload, exc)
            raise

        output = final_state.get("output")
        if not isinstance(output, DevBPolicyOutput):
            raise RuntimeError("Developer B graph did not produce DevBPolicyOutput")
        return output
```

- [ ] **Step 2: Update the constructor**

Inside `__init__`, instantiate graph tools and compiled graph:

```python
        from backend.app.agents.agent_b.policy_graph import build_developer_b_policy_graph
        from backend.app.tools.tool_b.developer_b_policy_graph_tools import DeveloperBPolicyGraphTools

        self.graph_tools = DeveloperBPolicyGraphTools(
            state_machine=state_machine,
            level_controller=level_controller,
            tier_controller=tier_controller,
            feedback_generator=feedback_generator,
            openkb_writer=openkb_writer,
            agent_run_root=agent_run_root,
            agent_run_logger=agent_run_logger,
        )
        self.graph = build_developer_b_policy_graph()
```

- [ ] **Step 3: Preserve test imports**

At module level in `english_level_hint_agent.py`, re-export the validator:

```python
from backend.app.tools.tool_b.developer_b_policy_graph_tools import _validate_b_policy_output
```

If existing tests or modules import helper functions from `english_level_hint_agent.py`, keep their imports working by re-exporting the same names or adjust only B-owned tests.

- [ ] **Step 4: Run focused B tests**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py backend/tests/dev_b/test_developer_b_policy_engine.py -q
```

Expected: pass except the BAG customs role test, which is fixed in Task 7.

---

### Task 7: Apply B-Owned Handoff Change For BAG NPC Role Metadata

**Files:**
- Modify: `backend/app/tools/tool_b/developer_b_policy_graph_tools.py`
- Modify: `backend/tests/dev_b/test_developer_b_policy_engine.py`

- [ ] **Step 1: Add explicit BAG phase role sets**

Near the graph tool constants, add:

```python
BAGGAGE_SERVICE_NODE_IDS = {
    "BAG_001_REPORT_MISSING_AT_DESK",
    "BAG_002_PROVIDE_CLAIM_TAG",
    "BAG_003_CONFIRM_SEARCHED_CAROUSEL",
    "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD",
}

CUSTOMS_OFFICER_NODE_IDS = {
    "BAG_005_CUSTOMS_HOLD_EXPLANATION",
    "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM",
    "BAG_007_CUSTOMS_CLEARANCE",
}
```

- [ ] **Step 2: Update `_npc_role()`**

Replace the current `BAG_` fallback with:

```python
    def _npc_role(self, payload: DevBPolicyInput) -> str:
        if payload.current_node_id.startswith("FLIGHT_"):
            return "seatmate_passenger"
        if payload.current_node_id in CUSTOMS_OFFICER_NODE_IDS:
            return "customs_officer"
        if payload.current_node_id in BAGGAGE_SERVICE_NODE_IDS or payload.current_node_id.startswith("BAG_"):
            return "baggage_service_agent"
        return "immigration_officer"
```

- [ ] **Step 3: Run the role regression**

Run:

```powershell
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_dialogue_seed_routes_baggage_service_and_customs_roles -q
```

Expected: pass.

---

### Task 8: Verify C Adapter Compatibility After B Refactor

**Files:**
- Read-only: `backend/app/integrations/dev_b_level_hint_client.py`
- Test: `backend/tests/test_preprototype_flow.py`
- Test: `backend/tests/test_developer_c_langgraph_orchestrator.py`

- [ ] **Step 1: Run C/B integration tests**

Run:

```powershell
uv run pytest backend/tests/test_developer_c_langgraph_orchestrator.py backend/tests/test_preprototype_flow.py backend/tests/dev_b -q
```

Expected: pass. `DevBPolicyClient` should not require any code change because it still calls `EnglishLevelHintAgent.evaluate_turn(payload)`.

- [ ] **Step 2: Confirm no C-owned files were edited**

Run:

```powershell
git diff --name-only
```

Expected changed implementation files are B-owned only:

```text
backend/app/agents/agent_b/english_level_hint_agent.py
backend/app/agents/agent_b/policy_graph.py
backend/app/tools/tool_b/__init__.py
backend/app/tools/tool_b/developer_b_policy_graph_tools.py
backend/tests/dev_b/test_developer_b_policy_engine.py
backend/tests/dev_b/test_developer_b_agent_run_log.py
```

Docs may include `docs/handoff.md` and B/shared contract updates.

---

### Task 9: Documentation And Coordination Updates

**Files:**
- Modify: `docs/handoff.md`
- Modify if needed: `docs/contracts/developer_b_report_and_dialogue_seed_contract.md`
- Modify if needed: `docs/contracts/change_requests.md`

- [ ] **Step 1: Add handoff entry**

Append a new section to `docs/handoff.md`:

```markdown
## 2026-06-12 Developer B LangGraph Policy Wrapper

Developer B refactored the internal `EnglishLevelHintAgent.evaluate_turn()` flow
into a B-owned LangGraph policy graph while preserving the public
`DevBPolicyClient.evaluate_turn(payload) -> DevBPolicyOutput` adapter contract.

Changed:

- Added `backend/app/agents/agent_b/policy_graph.py`.
- Added B-owned graph tool wrappers under `backend/app/tools/tool_b/`.
- Kept `ScenarioStateMachine` as the rule-based branch authority.
- Kept LLM-assisted feedback limited to hint, report, feedback, and rubric
  candidate enrichment.
- Added AgentRun metadata showing B policy runtime uses LangGraph.
- Updated B `dialogue_seed.npc_role` so BAG service-desk nodes use
  `baggage_service_agent` and customs-hold nodes use `customs_officer`.

Verification:

- `uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py backend/tests/dev_b/test_developer_b_policy_engine.py -q`: PASS.
- `uv run pytest backend/tests/test_developer_c_langgraph_orchestrator.py backend/tests/test_preprototype_flow.py backend/tests/dev_b -q`: PASS.
- `uv run pytest -q`: PASS.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS.

Known coordination:

- B still emits legacy `dialogue_directive.do_not_generate_npc_text` for adapter
  compatibility. New integration should prefer `dialogue_seed`.
- A/C still own final NPC text, TTS, A-facing adapter payload cleanup, and
  non-immigration NPC roster/voice handling.
```

- [ ] **Step 2: Update B dialogue seed contract if role behavior changed**

In `docs/contracts/developer_b_report_and_dialogue_seed_contract.md`, update the `npc_role` row to include:

```markdown
For `BAG_001` through `BAG_004`, Developer B emits `baggage_service_agent`.
For `BAG_005` through `BAG_007`, Developer B emits `customs_officer`.
```

- [ ] **Step 3: Add change request only if C contract retirement is required**

Do not remove `dialogue_directive.do_not_generate_npc_text` in this implementation. If C asks B to remove it, append a new request or status note in `docs/contracts/change_requests.md`:

```markdown
## Change Request - 2026-06-12 - Retire Legacy Developer B Dialogue Directive Flag

### Requested By
Developer B

### Affected Owner
Developer C / Sean Han

### Reason
Developer B now provides `dialogue_seed` metadata as the preferred A-facing
generation input. The legacy `dialogue_directive.do_not_generate_npc_text`
field should be retired only after the C adapter no longer depends on it.

### Proposed Contract Change
Developer C should confirm that `dialogue_seed` is consumed or preserved for A,
then Developer B can stop emitting `dialogue_directive.do_not_generate_npc_text`
in a later compatibility cleanup.

### Compatibility Impact
No change in the current implementation. This is a future removal request.

### Temporary Workaround
Developer B keeps the legacy flag while also emitting `dialogue_seed`.
```

---

### Task 10: Full Verification

**Files:**
- No edits.

- [ ] **Step 1: Restore environment**

Run:

```powershell
uv sync
```

Expected: completes without dependency changes outside `uv.lock`.

- [ ] **Step 2: Run test suite**

Run:

```powershell
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 3: Run lint**

Run:

```powershell
uv run ruff check .
```

Expected: pass.

- [ ] **Step 4: Run type checking**

Run:

```powershell
uv run mypy .
```

Expected: pass.

- [ ] **Step 5: Check whitespace/conflict artifacts**

Run:

```powershell
git diff --check
rg -n "<<<<<<<|=======|>>>>>>>" .
```

Expected: no diff whitespace errors and no conflict markers.

---

## Self-Review

- Spec coverage: the plan covers merge conflict policy, B-owned LangGraph wrapping, C adapter compatibility, handoff/change-request follow-up, and the C message's required B review points.
- Placeholder scan: implementation steps list exact files, test names, expected commands, and concrete code snippets for new public graph/test surfaces.
- Type consistency: the public B entry point remains `EnglishLevelHintAgent.evaluate_turn(payload: DevBPolicyInput) -> DevBPolicyOutput`; the C adapter remains unchanged.
