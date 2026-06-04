from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.integrations.dev_a_npc_dialogue_client import DevANpcDialogueClient
from backend.app.integrations.dev_b_level_hint_client import DevBPolicyClient
from backend.app.schemas.game_turn import (
    DevADialogueInput,
    DevBPolicyInput,
    NodeContext,
    NormalizedInput,
    PrePrototypeRequest,
    ScenarioState,
    UnderstandingOutput,
    UnrealResponse,
)
from backend.app.services.service_c.logging_service import LoggingService
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.services.service_c.response_builder import ResponseBuilder
from backend.app.services.service_c.stt_service import WhisperLargeV3TurboSttService
from backend.app.services.service_c.validator import Validator


class Orchestrator:
    def __init__(self) -> None:
        self.stt_service = WhisperLargeV3TurboSttService()
        self.openkb_service = OpenKBService()
        self.understanding_agent = UnderstandingAgent()
        self.dev_b_client = DevBPolicyClient()
        self.dev_a_client = DevANpcDialogueClient()
        self.logging_service = LoggingService()
        self.response_builder = ResponseBuilder()
        self.validator = Validator()

    def run_turn(self, request: PrePrototypeRequest) -> UnrealResponse:
        normalized_input = self.stt_service.transcribe_wav(request.audio, request.turn.audio)
        node_context = self.openkb_service.get_node_context(
            request.turn.session.chapter_id,
            request.turn.session.current_node_id,
        )
        understanding = self.understanding_agent.analyze_player_text(
            normalized_input.player_text,
            node_context,
        )
        dev_b_input = self.build_dev_b_policy_input(
            request,
            normalized_input,
            node_context,
            understanding,
        )
        dev_b_output = self.dev_b_client.evaluate_turn(dev_b_input)
        self.validator.validate_dev_b_policy_output(
            dev_b_output,
            current_node_id=request.turn.session.current_node_id,
            allowed_next_nodes=node_context.allowed_next_nodes,
            client_allowed_next_nodes=request.turn.client_allowed_next_nodes,
        )

        logging_summary = self.logging_service.record_error_capture(
            request.turn.session.session_id,
            dev_b_output.error_capture,
        )
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
            )
        )
        response = self.response_builder.build_unreal_response(
            request=request,
            normalized_input=normalized_input,
            understanding=understanding,
            dev_b_output=dev_b_output,
            dev_a_output=dev_a_output,
            logging_summary=logging_summary,
        )
        self.validator.validate_unreal_response(response)
        return response

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
            player_profile=request.turn.player_profile,
            scenario_state=scenario_state,
            node_context=node_context,
            understanding=understanding,
            previous_node_results=request.turn.previous_node_results,
            client_allowed_next_nodes=request.turn.client_allowed_next_nodes,
        )
