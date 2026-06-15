"""Implement the concrete tool calls used by the Developer C LangGraph.

Beginner guide:
The graph file names the steps, but this file performs the work for each step.
It calls STT, OpenKB, Understanding, Developer B, Developer A, validators, and
AgentRun logging in a controlled order.  Keeping these actions here makes the
graph easy to read and keeps C orchestration logic away from A/B implementation
files.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.integrations.dev_a_npc_dialogue_client import DevANpcDialogueClient
from backend.app.integrations.dev_b_level_hint_client import DevBPolicyClient
from backend.app.middleware.middleware_c.developer_c_agent_run_middleware import DeveloperCAgentRunMiddleware
from backend.app.schemas.game_turn import (
    DevADialogueInput,
    DevADialogueOutput,
    DevBPolicyInput,
    DevBPolicyOutput,
    NodeContext,
    NormalizedInput,
    PrePrototypeRequest,
    RecordedErrorSummary,
    ScenarioState,
    TransitionContext,
    TurnTimingMs,
    UnderstandingOutput,
    UnrealResponse,
)
from backend.app.services.service_c.logging_service import LoggingService
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.services.service_c.response_builder import ResponseBuilder
from backend.app.services.service_c.stt_service import WhisperLargeV3TurboSttService
from backend.app.services.service_c.validator import Validator


DEVELOPER_C_GRAPH_NAME = "developer_c_turn_graph"
DEVELOPER_C_GRAPH_TOOL_STYLE = "langchain_structured_tools"
DEVELOPER_C_GRAPH_NODE_NAMES = (
    "start_agent_run",
    "transcribe_audio",
    "load_node_context",
    "understand_player_text",
    "evaluate_dev_b_policy",
    "validate_dev_b_policy",
    "record_error_capture",
    "generate_dev_a_dialogue",
    "build_unreal_response",
    "validate_unreal_response",
    "finish_agent_run",
)
DEVELOPER_C_STRUCTURED_TOOL_NAMES = tuple(
    f"developer_c_{node_name}" for node_name in DEVELOPER_C_GRAPH_NODE_NAMES
)
DEVELOPER_C_GRAPH_TOOL_METHOD_NAMES = {
    "start_agent_run": "start_agent_run_tool",
    "transcribe_audio": "transcribe_audio_tool",
    "load_node_context": "load_node_context_tool",
    "understand_player_text": "understand_player_text_tool",
    "evaluate_dev_b_policy": "evaluate_dev_b_policy_tool",
    "validate_dev_b_policy": "validate_dev_b_policy_tool",
    "record_error_capture": "record_error_capture_tool",
    "generate_dev_a_dialogue": "generate_dev_a_dialogue_tool",
    "build_unreal_response": "build_unreal_response_tool",
    "validate_unreal_response": "validate_unreal_response_tool",
    "finish_agent_run": "finish_agent_run_tool",
}


class DeveloperCStructuredToolInput(BaseModel):
    """Input model shared by every Developer C LangChain tool wrapper.

    Beginner guide:
    LangGraph passes a single state dictionary from node to node.  LangChain
    `StructuredTool` expects a named input schema, so every C graph tool accepts
    one field named `state`.  The state can contain Pydantic models, services,
    and plain dictionaries because it is an internal backend object rather than
    a public JSON payload.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    state: dict[str, Any] = Field(
        description="Current Developer C LangGraph state for one backend turn."
    )


class DeveloperCGraphTools:
    """Tool wrappers used by the Developer C LangGraph.

    The graph should describe *order*.  This class owns the concrete C-side
    work for each node: calling STT, loading OpenKB, invoking the Understanding
    Agent, calling A/B adapters, building the response, validating it, and
    writing AgentRun logs.  Keeping the work here makes every graph node small
    enough for a beginner to read without losing the existing C ownership
    boundary.
    """

    def __init__(
        self,
        *,
        stt_service: WhisperLargeV3TurboSttService | None = None,
        openkb_service: OpenKBService | None = None,
        understanding_agent: UnderstandingAgent | None = None,
        dev_b_client: DevBPolicyClient | None = None,
        dev_a_client: DevANpcDialogueClient | None = None,
        logging_service: LoggingService | None = None,
        response_builder: ResponseBuilder | None = None,
        validator: Validator | None = None,
        agent_run_middleware: DeveloperCAgentRunMiddleware | None = None,
        agent_run_root: Path | None = None,
    ) -> None:
        self.stt_service = stt_service or WhisperLargeV3TurboSttService()
        self.openkb_service = openkb_service or OpenKBService()
        self.understanding_agent = understanding_agent or UnderstandingAgent()
        self.dev_b_client = dev_b_client or DevBPolicyClient(agent_run_root=agent_run_root)
        self.dev_a_client = dev_a_client or DevANpcDialogueClient()
        self.logging_service = logging_service or LoggingService()
        self.response_builder = response_builder or ResponseBuilder()
        self.validator = validator or Validator()
        self.agent_run_middleware = agent_run_middleware or DeveloperCAgentRunMiddleware(agent_run_root)
        self.active_agent_run: dict[str, Any] | None = None
        self.structured_tools: dict[str, StructuredTool] = self._build_structured_tools()

    def _build_structured_tools(self) -> dict[str, StructuredTool]:
        """Wrap every C graph tool method as a LangChain `StructuredTool`.

        Beginner guide:
        The existing `*_tool()` methods already contain the real work.  This
        method does not change their behavior; it creates LangChain-compatible
        wrappers around them.  That means the current graph can call tools via
        `.invoke(...)`, and a future LangGraph `ToolNode` can receive the same
        tool objects without C rewriting the business logic again.
        """

        return {
            node_name: StructuredTool.from_function(
                name=f"developer_c_{node_name}",
                description=_structured_tool_description(node_name),
                func=self._make_structured_tool_runner(node_name, method_name),
                args_schema=DeveloperCStructuredToolInput,
            )
            for node_name, method_name in DEVELOPER_C_GRAPH_TOOL_METHOD_NAMES.items()
        }

    def _make_structured_tool_runner(
        self,
        node_name: str,
        method_name: str,
    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create the callable used inside one `StructuredTool`.

        Beginner guide:
        LangChain calls this returned function with a validated `state`
        argument.  The function then forwards that state to the matching
        Developer C `*_tool()` method.  Keeping this tiny adapter separate makes
        the graph-tool boundary visible without duplicating any orchestration
        logic.
        """

        def run_structured_tool(state: dict[str, Any]) -> dict[str, Any]:
            result = getattr(self, method_name)(state)
            if not isinstance(result, dict):
                raise RuntimeError(f"Developer C structured tool returned a non-dict result: {node_name}")
            return result

        run_structured_tool.__name__ = f"run_{node_name}_structured_tool"
        run_structured_tool.__doc__ = _structured_tool_description(node_name)
        return run_structured_tool

    def invoke_structured_tool(self, node_name: str, state: Mapping[str, Any]) -> dict[str, Any]:
        """Invoke one C graph step through its LangChain `StructuredTool`.

        Beginner guide:
        Graph nodes call this method instead of directly calling
        `start_agent_run_tool()` or `transcribe_audio_tool()`.  The method keeps
        the graph readable while proving every step can run through LangChain's
        standard `.invoke(...)` tool API.
        """

        structured_tool = self.structured_tools.get(node_name)
        if structured_tool is None:
            raise RuntimeError(f"Unknown Developer C structured tool: {node_name}")

        result = structured_tool.invoke({"state": dict(state)})
        if not isinstance(result, dict):
            raise RuntimeError(f"Developer C structured tool returned a non-dict result: {node_name}")
        return result

    def as_tool_node_tools(self) -> list[StructuredTool]:
        """Return C tools in graph order for future LangGraph `ToolNode` use.

        Beginner guide:
        `ToolNode` accepts a list of LangChain tool objects.  The current C
        graph uses explicit state nodes because its state is richer than a chat
        message tool-call loop, but this ordered list keeps the tools ready for
        a future ToolNode/subgraph migration.
        """

        return [self.structured_tools[node_name] for node_name in DEVELOPER_C_GRAPH_NODE_NAMES]

    def start_agent_run_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Create the C AgentRun record before the first runtime tool call.

        This replaces the old procedural opening block in `Orchestrator`.  The
        returned `agent_run` is carried in LangGraph state so later nodes can
        append timeline events to the same record.
        """

        request = _require_state_value(state, "request", PrePrototypeRequest)
        agent_run = self.agent_run_middleware.start_run(request)
        self.active_agent_run = agent_run
        _attach_langgraph_runtime_metadata(agent_run)
        self.agent_run_middleware.record_event(
            agent_run,
            event="agent_start",
            status="started",
            data_loaded=_request_input_summary(request),
        )
        self.agent_run_middleware.record_data_flow(
            agent_run,
            from_node="unreal_request",
            to_node="stt_service",
            payload_summary=_request_input_summary(request),
        )
        return {"agent_run": agent_run}

    def transcribe_audio_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        request = _require_state_value(state, "request", PrePrototypeRequest)
        agent_run = _require_agent_run(state)
        timing_ms = _state_timing_ms(state)

        stage_started = perf_counter()
        normalized_input = self.stt_service.transcribe_wav(request.audio, request.turn.audio)
        timing_ms["stt_ms"] = _elapsed_ms(stage_started)
        self.agent_run_middleware.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="stt_service.transcribe_wav",
            input_summary=_audio_input_summary(request),
            output_summary=_normalized_input_summary(normalized_input),
        )
        self.agent_run_middleware.record_data_flow(
            agent_run,
            from_node="stt_service",
            to_node="openkb_service",
            payload_summary=_normalized_input_summary(normalized_input),
        )
        return {"normalized_input": normalized_input, "timing_ms": timing_ms}

    def load_node_context_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        request = _require_state_value(state, "request", PrePrototypeRequest)
        normalized_input = _require_state_value(state, "normalized_input", NormalizedInput)
        agent_run = _require_agent_run(state)
        timing_ms = _state_timing_ms(state)

        stage_started = perf_counter()
        node_context = self.openkb_service.get_node_context(
            request.turn.session.chapter_id,
            request.turn.session.current_node_id,
        )
        timing_ms["openkb_ms"] = _elapsed_ms(stage_started)
        self.agent_run_middleware.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="openkb_service.get_node_context",
            input_summary={
                "chapter_id": request.turn.session.chapter_id,
                "node_id": request.turn.session.current_node_id,
            },
            output_summary=_node_context_summary(node_context),
        )
        self.agent_run_middleware.record_data_flow(
            agent_run,
            from_node="openkb_service",
            to_node="understanding_agent",
            payload_summary=_node_context_summary(node_context),
        )
        return {
            "node_context": node_context,
            "normalized_input": normalized_input,
            "timing_ms": timing_ms,
        }

    def understand_player_text_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        normalized_input = _require_state_value(state, "normalized_input", NormalizedInput)
        node_context = _require_state_value(state, "node_context", NodeContext)
        agent_run = _require_agent_run(state)
        timing_ms = _state_timing_ms(state)

        stage_started = perf_counter()
        understanding = self.understanding_agent.analyze_player_text(
            normalized_input.player_text,
            node_context,
        )
        timing_ms["understanding_ms"] = _elapsed_ms(stage_started)
        self.agent_run_middleware.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="understanding_agent.analyze_player_text",
            input_summary={
                "player_text_preview": _preview(normalized_input.player_text),
                "node_id": node_context.node_id,
            },
            output_summary={
                "understanding": _understanding_summary(understanding),
                "understanding_trace": self.understanding_agent.last_trace,
            },
        )
        self.agent_run_middleware.record_data_flow(
            agent_run,
            from_node="understanding_agent",
            to_node="dev_b_client",
            payload_summary=_understanding_summary(understanding),
        )
        return {"understanding": understanding, "timing_ms": timing_ms}

    def evaluate_dev_b_policy_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        request = _require_state_value(state, "request", PrePrototypeRequest)
        normalized_input = _require_state_value(state, "normalized_input", NormalizedInput)
        node_context = _require_state_value(state, "node_context", NodeContext)
        understanding = _require_state_value(state, "understanding", UnderstandingOutput)
        agent_run = _require_agent_run(state)
        timing_ms = _state_timing_ms(state)

        dev_b_input = self.build_dev_b_policy_input(
            request,
            normalized_input,
            node_context,
            understanding,
        )
        stage_started = perf_counter()
        dev_b_output = self.dev_b_client.evaluate_turn(dev_b_input)
        timing_ms["developer_b_ms"] = _elapsed_ms(stage_started)
        self.agent_run_middleware.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="dev_b_client.evaluate_turn",
            input_summary=_dev_b_input_summary(dev_b_input),
            output_summary=_dev_b_output_summary(dev_b_output),
        )
        self.agent_run_middleware.record_data_flow(
            agent_run,
            from_node="dev_b_client",
            to_node="validator",
            payload_summary=_dev_b_output_summary(dev_b_output),
        )
        return {
            "dev_b_input": dev_b_input,
            "dev_b_output": dev_b_output,
            "timing_ms": timing_ms,
        }

    def validate_dev_b_policy_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        request = _require_state_value(state, "request", PrePrototypeRequest)
        node_context = _require_state_value(state, "node_context", NodeContext)
        dev_b_output = _require_state_value(state, "dev_b_output", DevBPolicyOutput)
        agent_run = _require_agent_run(state)
        timing_ms = _state_timing_ms(state)

        stage_started = perf_counter()
        self.validator.validate_dev_b_policy_output(
            dev_b_output,
            current_node_id=request.turn.session.current_node_id,
            allowed_next_nodes=node_context.allowed_next_nodes,
            client_allowed_next_nodes=request.turn.client_allowed_next_nodes,
        )
        timing_ms["validation_ms"] += _elapsed_ms(stage_started)
        transition = self._transition_for_branch(node_context, dev_b_output)
        self.agent_run_middleware.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="validator.validate_dev_b_policy_output",
            input_summary={
                "current_node_id": request.turn.session.current_node_id,
                "next_node_id": dev_b_output.branch.next_node_id,
                "allowed_next_node_checked": dev_b_output.branch.allowed_next_node_checked,
            },
            output_summary={"validated": True},
        )
        return {"transition": transition, "timing_ms": timing_ms}

    def record_error_capture_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        request = _require_state_value(state, "request", PrePrototypeRequest)
        dev_b_output = _require_state_value(state, "dev_b_output", DevBPolicyOutput)
        agent_run = _require_agent_run(state)
        timing_ms = _state_timing_ms(state)

        stage_started = perf_counter()
        logging_summary = self.logging_service.record_error_capture(
            request.turn.session.session_id,
            dev_b_output.error_capture,
        )
        timing_ms["logging_ms"] = _elapsed_ms(stage_started)
        self.agent_run_middleware.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="logging_service.record_error_capture",
            input_summary={
                "should_record": dev_b_output.error_capture.should_record,
                "error_count": len(dev_b_output.error_capture.error_items),
            },
            output_summary=logging_summary.model_dump(),
        )
        return {"logging_summary": logging_summary, "timing_ms": timing_ms}

    def generate_dev_a_dialogue_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        request = _require_state_value(state, "request", PrePrototypeRequest)
        normalized_input = _require_state_value(state, "normalized_input", NormalizedInput)
        node_context = _require_state_value(state, "node_context", NodeContext)
        understanding = _require_state_value(state, "understanding", UnderstandingOutput)
        dev_b_output = _require_state_value(state, "dev_b_output", DevBPolicyOutput)
        transition = _optional_state_value(state, "transition", TransitionContext)
        agent_run = _require_agent_run(state)
        timing_ms = _state_timing_ms(state)

        stage_started = perf_counter()
        dev_a_output = self.dev_a_client.generate_dialogue(
            DevADialogueInput(
                contract_version="dev_a_dialogue.v1",
                request_id=request.turn.request_id,
                session_id=request.turn.session.session_id,
                current_node_id=request.turn.session.current_node_id,
                player_text=normalized_input.player_text,
                npc=request.turn.npc,
                node_context=node_context,
                understanding=understanding,
                developer_b_policy=dev_b_output,
                transition=transition,
            )
        )
        timing_ms["developer_a_ms"] = _elapsed_ms(stage_started)
        self.agent_run_middleware.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="dev_a_client.generate_dialogue",
            input_summary={
                "node_id": node_context.node_id,
                "branch_type": dev_b_output.branch.branch_type,
                "dialogue_directive": _dialogue_directive_summary(dev_b_output),
            },
            output_summary=_dev_a_output_summary(dev_a_output),
        )
        self.agent_run_middleware.record_data_flow(
            agent_run,
            from_node="dev_a_client",
            to_node="response_builder",
            payload_summary=_dev_a_output_summary(dev_a_output),
        )
        return {"dev_a_output": dev_a_output, "timing_ms": timing_ms}

    def build_unreal_response_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        request = _require_state_value(state, "request", PrePrototypeRequest)
        normalized_input = _require_state_value(state, "normalized_input", NormalizedInput)
        understanding = _require_state_value(state, "understanding", UnderstandingOutput)
        dev_b_output = _require_state_value(state, "dev_b_output", DevBPolicyOutput)
        dev_a_output = _require_state_value(state, "dev_a_output", DevADialogueOutput)
        logging_summary = _require_state_value(state, "logging_summary", RecordedErrorSummary)
        transition = _optional_state_value(state, "transition", TransitionContext)
        agent_run = _require_agent_run(state)
        timing_ms = _state_timing_ms(state)
        turn_started = _state_turn_started(state)

        stage_started = perf_counter()
        response = self.response_builder.build_unreal_response(
            request=request,
            normalized_input=normalized_input,
            understanding=understanding,
            dev_b_output=dev_b_output,
            dev_a_output=dev_a_output,
            logging_summary=logging_summary,
            transition=transition,
            timing_ms=_turn_timing_ms(timing_ms, turn_started),
        )
        timing_ms["response_build_ms"] = _elapsed_ms(stage_started)
        response.debug.timing_ms = _turn_timing_ms(timing_ms, turn_started)
        self.agent_run_middleware.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="response_builder.build_unreal_response",
            input_summary={
                "request_id": request.turn.request_id,
                "branch_next_node_id": dev_b_output.branch.next_node_id,
                "npc_audio_url": dev_a_output.audio_url,
                "transition": _transition_summary(transition),
            },
            output_summary=_response_summary(response),
        )
        self.agent_run_middleware.record_data_flow(
            agent_run,
            from_node="response_builder",
            to_node="validator",
            payload_summary=_response_summary(response),
        )
        return {"response": response, "timing_ms": timing_ms}

    def validate_unreal_response_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        response = _require_state_value(state, "response", UnrealResponse)
        agent_run = _require_agent_run(state)
        timing_ms = _state_timing_ms(state)
        turn_started = _state_turn_started(state)

        stage_started = perf_counter()
        self.validator.validate_unreal_response(response)
        timing_ms["validation_ms"] += _elapsed_ms(stage_started)
        response.debug.timing_ms = _turn_timing_ms(timing_ms, turn_started)
        self.agent_run_middleware.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="validator.validate_unreal_response",
            input_summary=_response_summary(response),
            output_summary={"validated": True},
        )
        self.agent_run_middleware.record_data_flow(
            agent_run,
            from_node="validator",
            to_node="unreal_response",
            payload_summary=_response_summary(response),
        )
        return {"response": response, "timing_ms": timing_ms}

    def finish_agent_run_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        request = _require_state_value(state, "request", PrePrototypeRequest)
        response = _require_state_value(state, "response", UnrealResponse)
        agent_run = _require_agent_run(state)

        self.agent_run_middleware.record_event(
            agent_run,
            event="agent_end",
            status="completed",
            output_summary=_response_summary(response),
        )
        self.agent_run_middleware.complete_and_append(
            agent_run,
            status="completed",
            summary={
                "input": _request_input_summary(request),
                "output": _response_summary(response),
                "fallback_used": _understanding_fallback_used(self.understanding_agent.last_trace),
                "audio_url": response.npc.audio_url,
            },
            model_usage=_agent_run_model_usage(self.understanding_agent.last_trace),
        )
        self.active_agent_run = None
        return {"response": response}

    def _transition_for_branch(
        self,
        node_context: NodeContext,
        dev_b_output: DevBPolicyOutput,
    ) -> TransitionContext | None:
        if dev_b_output.branch.next_action != "COMPLETE_CHAPTER":
            return None

        transition_node = self.openkb_service.get_node_context(
            node_context.chapter_id,
            dev_b_output.branch.next_node_id,
        )
        return transition_node.transition

    def complete_failed_run(self, request: PrePrototypeRequest, exc: Exception) -> None:
        """Append a failed C AgentRun if a graph node raises.

        LangGraph correctly propagates the exception, but the compiled graph
        does not expose the latest state to the caller.  The active run is kept
        on this C-owned tool object so the slim orchestrator can preserve the
        old failure logging behavior without reintroducing procedural workflow
        code.
        """

        if self.active_agent_run is None:
            return

        agent_run = self.active_agent_run
        self.agent_run_middleware.record_event(
            agent_run,
            event="agent_end",
            status="failed",
            error=str(exc),
        )
        trace = getattr(self.understanding_agent, "last_trace", {})
        self.agent_run_middleware.complete_and_append(
            agent_run,
            status="failed",
            summary={
                "input": _request_input_summary(request),
                "output": {"error": str(exc), "error_type": exc.__class__.__name__},
                "fallback_used": _understanding_fallback_used(trace),
                "audio_url": None,
            },
            model_usage=_agent_run_model_usage(trace),
        )
        self.active_agent_run = None

    def build_dev_b_policy_input(
        self,
        request: PrePrototypeRequest,
        normalized_input: NormalizedInput,
        node_context: NodeContext,
        understanding: UnderstandingOutput,
    ) -> DevBPolicyInput:
        scenario_state = ScenarioState(
            patience=request.turn.scenario_state.patience,
            suspicion=request.turn.scenario_state.suspicion,
            retry_count=request.turn.scenario_state.retry_count,
            hint_count=request.turn.scenario_state.hint_count,
            previous_fail_count=request.turn.scenario_state.previous_fail_count,
            completed_intents=request.turn.game_state.completed_intents,
        )

        return DevBPolicyInput(
            contract_version="dev_b_policy.v1",
            request_id=request.turn.request_id,
            session_id=request.turn.session.session_id,
            player_id=request.turn.session.player_id,
            chapter_id=request.turn.session.chapter_id,
            scene_id=request.turn.session.scene_id,
            current_node_id=request.turn.session.current_node_id,
            turn_index=request.turn.session.turn_index,
            player_text=normalized_input.player_text,
            input_source=normalized_input.input_source,
            interaction=request.turn.interaction,
            player_profile=request.turn.player_profile,
            scenario_state=scenario_state,
            node_context=node_context,
            understanding=understanding,
            previous_node_results=request.turn.previous_node_results,
            client_allowed_next_nodes=request.turn.client_allowed_next_nodes,
        )


def _attach_langgraph_runtime_metadata(agent_run: dict[str, Any]) -> None:
    metadata = agent_run.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        agent_run["metadata"] = metadata

    metadata["runtime"] = {
        "orchestrator": "langgraph",
        "graph_name": DEVELOPER_C_GRAPH_NAME,
        "tool_style": DEVELOPER_C_GRAPH_TOOL_STYLE,
        "graph_nodes": list(DEVELOPER_C_GRAPH_NODE_NAMES),
        "structured_tool_names": list(DEVELOPER_C_STRUCTURED_TOOL_NAMES),
    }


def _structured_tool_description(node_name: str) -> str:
    """Return a beginner-readable description for one StructuredTool wrapper."""

    return (
        "Run the Developer C LangGraph step "
        f"`{node_name}` with the current backend turn state and return state updates."
    )


def _require_state_value(state: Mapping[str, Any], key: str, expected_type: type[Any]) -> Any:
    value = state.get(key)
    if not isinstance(value, expected_type):
        raise RuntimeError(f"Developer C graph state is missing required value: {key}")
    return value


def _require_agent_run(state: Mapping[str, Any]) -> dict[str, Any]:
    value = state.get("agent_run")
    if isinstance(value, dict):
        return value
    raise RuntimeError("Developer C graph state is missing required value: agent_run")


def _optional_state_value(state: Mapping[str, Any], key: str, expected_type: type[Any]) -> Any | None:
    value = state.get(key)
    if value is None:
        return None
    if isinstance(value, expected_type):
        return value
    raise RuntimeError(f"Developer C graph state has invalid value type: {key}")


def _state_timing_ms(state: Mapping[str, Any]) -> dict[str, int]:
    value = state.get("timing_ms")
    if isinstance(value, dict):
        return {key: int(raw_value) for key, raw_value in value.items()}
    return _empty_timing_ms()


def _state_turn_started(state: Mapping[str, Any]) -> float:
    value = state.get("turn_started")
    return value if isinstance(value, float) else perf_counter()


def _request_input_summary(request: PrePrototypeRequest) -> dict[str, Any]:
    session = request.turn.session
    return {
        "request_id": request.turn.request_id,
        "session_id": session.session_id,
        "turn_index": session.turn_index,
        "chapter_id": session.chapter_id,
        "scene_id": session.scene_id,
        "current_node_id": session.current_node_id,
        "audio_mime_type": request.turn.audio.mime_type,
        "has_audio_bytes": request.audio.audio_bytes is not None,
        "has_mock_transcript": request.audio.transcript is not None,
        "client_allowed_next_nodes": request.turn.client_allowed_next_nodes,
        "interaction": _interaction_summary(request.turn.interaction),
    }


def _audio_input_summary(request: PrePrototypeRequest) -> dict[str, Any]:
    return {
        "mime_type": request.turn.audio.mime_type,
        "sample_rate_hz": request.turn.audio.sample_rate_hz,
        "channels": request.turn.audio.channels,
        "duration_ms": request.turn.audio.duration_ms,
        "language_hint": request.turn.audio.language_hint,
        "file_name": request.audio.file_name,
        "content_type": request.audio.content_type,
        "mock_wav_path": request.audio.mock_wav_path,
        "transcript_preview": _preview(request.audio.transcript or ""),
    }


def _normalized_input_summary(normalized_input: NormalizedInput) -> dict[str, Any]:
    return {
        "player_text_preview": _preview(normalized_input.player_text),
        "stt_model": normalized_input.stt_model,
        "runtime_used": normalized_input.stt_runtime_used,
        "confidence": normalized_input.input_source.stt_confidence,
        "language_detected": normalized_input.input_source.language_detected,
        "needs_repeat": normalized_input.input_source.needs_repeat,
    }


def _node_context_summary(node_context: NodeContext) -> dict[str, Any]:
    return {
        "node_id": node_context.node_id,
        "scenario_id": node_context.scenario_id,
        "chapter_id": node_context.chapter_id,
        "node_type": node_context.node_type,
        "required_intents": node_context.required_intents,
        "required_slots": node_context.required_slots,
        "allowed_next_nodes": node_context.allowed_next_nodes,
        "success_next_node": node_context.success_next_node,
        "retry_next_node": node_context.retry_next_node,
    }


def _understanding_summary(understanding: UnderstandingOutput) -> dict[str, Any]:
    return {
        "intent": understanding.intent,
        "intent_success": understanding.intent_success,
        "confidence": understanding.confidence,
        "answer_relevance": understanding.answer_relevance,
        "risk_delta": understanding.risk_delta,
        "missing_slots": understanding.missing_slots,
        "needs_clarification": understanding.needs_clarification,
    }


def _dev_b_input_summary(dev_b_input: DevBPolicyInput) -> dict[str, Any]:
    return {
        "contract_version": dev_b_input.contract_version,
        "node_id": dev_b_input.current_node_id,
        "player_text_preview": _preview(dev_b_input.player_text),
        "turn_index": dev_b_input.turn_index,
        "interaction": _interaction_summary(dev_b_input.interaction),
        "patience": dev_b_input.scenario_state.patience,
        "suspicion": dev_b_input.scenario_state.suspicion,
        "retry_count": dev_b_input.scenario_state.retry_count,
    }


def _dev_b_output_summary(dev_b_output: DevBPolicyOutput) -> dict[str, Any]:
    return {
        "contract_version": dev_b_output.contract_version,
        "node_id": dev_b_output.node_id,
        "evaluation": {
            "verdict": dev_b_output.evaluation.verdict,
            "feedback_tags": dev_b_output.evaluation.feedback_tags,
        },
        "branch": dev_b_output.branch.model_dump(),
        "state_delta": dev_b_output.state_delta.model_dump(),
        "level_hint": {
            "needs_hint": dev_b_output.level_hint.needs_hint,
            "hint_level": dev_b_output.level_hint.hint_level,
            "hint_type": dev_b_output.level_hint.hint_type,
        },
        "error_capture": {
            "should_record": dev_b_output.error_capture.should_record,
            "error_count": len(dev_b_output.error_capture.error_items),
        },
        "feedback_generation": (
            dev_b_output.feedback_generation.model_dump()
            if dev_b_output.feedback_generation is not None
            else None
        ),
        "openkb_write": (
            dev_b_output.openkb_write.model_dump()
            if dev_b_output.openkb_write is not None
            else None
        ),
    }


def _dialogue_directive_summary(dev_b_output: DevBPolicyOutput) -> dict[str, Any] | None:
    if dev_b_output.dialogue_directive is None:
        return None
    return dev_b_output.dialogue_directive.model_dump()


def _dev_a_output_summary(dev_a_output: DevADialogueOutput) -> dict[str, Any]:
    return {
        "speaker": dev_a_output.speaker,
        "text_preview": _preview(dev_a_output.text),
        "tone": dev_a_output.tone,
        "animation": dev_a_output.animation,
        "has_feedback_kr": dev_a_output.feedback_kr is not None,
        "audio_url": dev_a_output.audio_url,
        "diagnostics": dev_a_output.diagnostics,
    }


def _transition_summary(transition: TransitionContext | None) -> dict[str, Any] | None:
    return transition.model_dump() if transition is not None else None


def _response_summary(response: UnrealResponse) -> dict[str, Any]:
    return {
        "contract_version": response.contract_version,
        "request_id": response.request_id,
        "current_node_id": response.current_node_id,
        "next_node_id": response.next_node_id,
        "next_action": response.next_action,
        "transition": _transition_summary(response.transition),
        "interaction": _interaction_summary(response.interaction),
        "npc_audio_url": response.npc.audio_url,
        "evaluation_verdict": response.evaluation.verdict,
        "recorded_error_count": response.report.recorded_error_count,
        "timing_ms": response.debug.timing_ms.model_dump(),
    }


def _understanding_fallback_used(trace: dict[str, Any]) -> bool:
    return bool(trace.get("fallback_used"))


def _agent_run_model_usage(trace: dict[str, Any]) -> dict[str, Any] | None:
    usage = trace.get("model_usage")
    return usage if isinstance(usage, dict) else None


def _interaction_summary(interaction: Any) -> dict[str, Any]:
    return {
        "initiator": interaction.initiator,
        "interaction_type": interaction.interaction_type,
        "quest_id": interaction.quest_id,
        "interaction_id": interaction.interaction_id,
        "time_limit_s": interaction.time_limit_s,
        "first_contact": interaction.first_contact,
    }


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


def _turn_timing_ms(timing_ms: dict[str, int], turn_started: float) -> TurnTimingMs:
    return TurnTimingMs(
        total_ms=_elapsed_ms(turn_started),
        stt_ms=timing_ms["stt_ms"],
        openkb_ms=timing_ms["openkb_ms"],
        understanding_ms=timing_ms["understanding_ms"],
        developer_b_ms=timing_ms["developer_b_ms"],
        logging_ms=timing_ms["logging_ms"],
        developer_a_ms=timing_ms["developer_a_ms"],
        response_build_ms=timing_ms["response_build_ms"],
        validation_ms=timing_ms["validation_ms"],
    )


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def _preview(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
