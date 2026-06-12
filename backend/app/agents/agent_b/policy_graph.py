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
