from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.graphs.graph import build_developer_c_graph, build_initial_developer_c_state
from backend.app.integrations.dev_a_npc_dialogue_client import DevANpcDialogueClient
from backend.app.integrations.dev_b_level_hint_client import DevBPolicyClient
from backend.app.middleware.middleware_c.developer_c_agent_run_middleware import DeveloperCAgentRunMiddleware
from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    NodeContext,
    NormalizedInput,
    PrePrototypeRequest,
    UnderstandingOutput,
    UnrealResponse,
)
from backend.app.services.service_c.logging_service import LoggingService
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.services.service_c.response_builder import ResponseBuilder
from backend.app.services.service_c.stt_service import WhisperLargeV3TurboSttService
from backend.app.services.service_c.validator import Validator
from backend.app.tools.tool_c.developer_c_graph_tools import DeveloperCGraphTools


class Orchestrator:
    """Public Developer C turn orchestrator backed by LangGraph.

    The old version of this class contained the whole step-by-step workflow in
    one large method.  This refactor keeps the same public API but moves the
    actual order into `backend.app.graphs.graph` and the concrete C-owned tool
    calls into `backend.app.tools.tool_c.developer_c_graph_tools`.
    """

    def __init__(
        self,
        *,
        agent_run_root: Path | None = None,
        agent_run_middleware: DeveloperCAgentRunMiddleware | None = None,
    ) -> None:
        self.stt_service = WhisperLargeV3TurboSttService()
        self.openkb_service = OpenKBService()
        self.understanding_agent = UnderstandingAgent()
        self.dev_b_client = DevBPolicyClient(agent_run_root=agent_run_root)
        self.dev_a_client = DevANpcDialogueClient()
        self.logging_service = LoggingService()
        self.response_builder = ResponseBuilder()
        self.validator = Validator()
        self.agent_run_middleware = agent_run_middleware or DeveloperCAgentRunMiddleware(agent_run_root)
        self.graph_app = build_developer_c_graph()
        self.graph_tools = self._build_graph_tools()

    def run_turn(self, request: PrePrototypeRequest) -> UnrealResponse:
        """Run one Unreal turn through the compiled Developer C LangGraph."""

        self.graph_tools = self._build_graph_tools()
        state = build_initial_developer_c_state(
            request=request,
            tools=self.graph_tools,
        )

        try:
            final_state: dict[str, Any] = self.graph_app.invoke(state)
        except Exception as exc:
            self.graph_tools.complete_failed_run(request, exc)
            raise

        response = final_state.get("response")
        if not isinstance(response, UnrealResponse):
            raise RuntimeError("Developer C LangGraph completed without an UnrealResponse.")
        return response

    def build_dev_b_policy_input(
        self,
        request: PrePrototypeRequest,
        normalized_input: NormalizedInput,
        node_context: NodeContext,
        understanding: UnderstandingOutput,
    ) -> DevBPolicyInput:
        """Compatibility helper for tests and C-owned diagnostics."""

        self.graph_tools = self._build_graph_tools()
        return self.graph_tools.build_dev_b_policy_input(
            request,
            normalized_input,
            node_context,
            understanding,
        )

    def _build_graph_tools(self) -> DeveloperCGraphTools:
        """Bind the current Orchestrator dependencies into LangGraph tools.

        Existing tests and local debugging sometimes replace attributes such as
        `understanding_agent` after constructing the orchestrator.  Rebuilding
        the C tool object before each run preserves that useful behavior while
        still keeping execution inside the graph.
        """

        return DeveloperCGraphTools(
            stt_service=self.stt_service,
            openkb_service=self.openkb_service,
            understanding_agent=self.understanding_agent,
            dev_b_client=self.dev_b_client,
            dev_a_client=self.dev_a_client,
            logging_service=self.logging_service,
            response_builder=self.response_builder,
            validator=self.validator,
            agent_run_middleware=self.agent_run_middleware,
        )
