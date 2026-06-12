from __future__ import annotations

from time import perf_counter
from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.schemas.game_turn import (
    DevADialogueOutput,
    DevBPolicyInput,
    DevBPolicyOutput,
    NodeContext,
    NormalizedInput,
    PrePrototypeRequest,
    RecordedErrorSummary,
    TransitionContext,
    UnderstandingOutput,
    UnrealResponse,
)
from backend.app.tools.tool_c.developer_c_graph_tools import (
    DEVELOPER_C_GRAPH_NODE_NAMES as _DEVELOPER_C_GRAPH_NODE_NAMES,
    DeveloperCGraphTools,
)


DEVELOPER_C_GRAPH_NODE_NAMES = _DEVELOPER_C_GRAPH_NODE_NAMES


class DeveloperCTurnState(TypedDict):
    """Shared state that flows through the Developer C LangGraph.

    Beginner mental model:
    - Each graph node receives this state.
    - The node reads the fields it needs.
    - The node returns only the new or changed fields.
    - LangGraph merges those returned fields back into the state for the next
      node.

    Developer C keeps branch authority out of this state.  Developer B still
    decides policy/branch inside `dev_b_output`; Developer C only validates and
    assembles the safe Unreal response.
    """

    request: PrePrototypeRequest
    tools: DeveloperCGraphTools
    turn_started: float
    timing_ms: dict[str, int]
    agent_run: NotRequired[dict[str, Any]]
    normalized_input: NotRequired[NormalizedInput]
    node_context: NotRequired[NodeContext]
    understanding: NotRequired[UnderstandingOutput]
    dev_b_input: NotRequired[DevBPolicyInput]
    dev_b_output: NotRequired[DevBPolicyOutput]
    transition: NotRequired[TransitionContext | None]
    logging_summary: NotRequired[RecordedErrorSummary]
    dev_a_output: NotRequired[DevADialogueOutput]
    response: NotRequired[UnrealResponse]


def build_initial_developer_c_state(
    *,
    request: PrePrototypeRequest,
    tools: DeveloperCGraphTools,
) -> DeveloperCTurnState:
    """Build the only state object the public Orchestrator needs to create."""

    return {
        "request": request,
        "tools": tools,
        "turn_started": perf_counter(),
        "timing_ms": _empty_timing_ms(),
    }


def build_developer_c_graph() -> Any:
    """Compile the Developer C turn graph.

    The graph is intentionally linear for the Alpha refactor.  LangGraph still
    gives us an explicit state contract, named nodes, and a safe place to add
    conditional branches later without hiding that Developer B remains the
    branch authority.
    """

    graph = StateGraph(DeveloperCTurnState)
    graph.add_node("start_agent_run", _start_agent_run)
    graph.add_node("transcribe_audio", _transcribe_audio)
    graph.add_node("load_node_context", _load_node_context)
    graph.add_node("understand_player_text", _understand_player_text)
    graph.add_node("evaluate_dev_b_policy", _evaluate_dev_b_policy)
    graph.add_node("validate_dev_b_policy", _validate_dev_b_policy)
    graph.add_node("record_error_capture", _record_error_capture)
    graph.add_node("generate_dev_a_dialogue", _generate_dev_a_dialogue)
    graph.add_node("build_unreal_response", _build_unreal_response)
    graph.add_node("validate_unreal_response", _validate_unreal_response)
    graph.add_node("finish_agent_run", _finish_agent_run)

    graph.add_edge(START, "start_agent_run")
    graph.add_edge("start_agent_run", "transcribe_audio")
    graph.add_edge("transcribe_audio", "load_node_context")
    graph.add_edge("load_node_context", "understand_player_text")
    graph.add_edge("understand_player_text", "evaluate_dev_b_policy")
    graph.add_edge("evaluate_dev_b_policy", "validate_dev_b_policy")
    graph.add_edge("validate_dev_b_policy", "record_error_capture")
    graph.add_edge("record_error_capture", "generate_dev_a_dialogue")
    graph.add_edge("generate_dev_a_dialogue", "build_unreal_response")
    graph.add_edge("build_unreal_response", "validate_unreal_response")
    graph.add_edge("validate_unreal_response", "finish_agent_run")
    graph.add_edge("finish_agent_run", END)
    return graph.compile()


def _start_agent_run(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].start_agent_run_tool(state)


def _transcribe_audio(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].transcribe_audio_tool(state)


def _load_node_context(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].load_node_context_tool(state)


def _understand_player_text(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].understand_player_text_tool(state)


def _evaluate_dev_b_policy(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].evaluate_dev_b_policy_tool(state)


def _validate_dev_b_policy(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].validate_dev_b_policy_tool(state)


def _record_error_capture(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].record_error_capture_tool(state)


def _generate_dev_a_dialogue(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].generate_dev_a_dialogue_tool(state)


def _build_unreal_response(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].build_unreal_response_tool(state)


def _validate_unreal_response(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].validate_unreal_response_tool(state)


def _finish_agent_run(state: DeveloperCTurnState) -> dict[str, Any]:
    return state["tools"].finish_agent_run_tool(state)


def _empty_timing_ms() -> dict[str, int]:
    return {
        "stt_ms": 0,
        "openkb_ms": 0,
        "understanding_ms": 0,
        "developer_b_ms": 0,
        "logging_ms": 0,
        "developer_a_ms": 0,
        "response_build_ms": 0,
        "validation_ms": 0,
    }
