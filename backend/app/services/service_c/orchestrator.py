from pathlib import Path
from typing import Any

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.integrations.dev_a_npc_dialogue_client import DevANpcDialogueClient
from backend.app.integrations.dev_b_level_hint_client import DevBPolicyClient
from backend.app.middleware.middleware_c.developer_c_agent_run_middleware import (
    DeveloperCAgentRunMiddleware,
)
from backend.app.schemas.game_turn import (
    DevADialogueOutput,
    DevADialogueInput,
    DevBPolicyOutput,
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
    def __init__(
        self,
        *,
        agent_run_root: Path | None = None,
        agent_run_middleware: DeveloperCAgentRunMiddleware | None = None,
    ) -> None:
        self.stt_service = WhisperLargeV3TurboSttService()
        self.openkb_service = OpenKBService()
        self.understanding_agent = UnderstandingAgent()
        self.dev_b_client = DevBPolicyClient()
        self.dev_a_client = DevANpcDialogueClient()
        self.logging_service = LoggingService()
        self.response_builder = ResponseBuilder()
        self.validator = Validator()
        self.agent_run_middleware = agent_run_middleware or DeveloperCAgentRunMiddleware(agent_run_root)

    def run_turn(self, request: PrePrototypeRequest) -> UnrealResponse:
        agent_run = self.agent_run_middleware.start_run(request)
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

        try:
            normalized_input = self.stt_service.transcribe_wav(request.audio, request.turn.audio)
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

            node_context = self.openkb_service.get_node_context(
                request.turn.session.chapter_id,
                request.turn.session.current_node_id,
            )
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

            understanding = self.understanding_agent.analyze_player_text(
                normalized_input.player_text,
                node_context,
            )
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

            dev_b_input = self.build_dev_b_policy_input(
                request,
                normalized_input,
                node_context,
                understanding,
            )
            dev_b_output = self.dev_b_client.evaluate_turn(dev_b_input)
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

            self.validator.validate_dev_b_policy_output(
                dev_b_output,
                current_node_id=request.turn.session.current_node_id,
                allowed_next_nodes=node_context.allowed_next_nodes,
                client_allowed_next_nodes=request.turn.client_allowed_next_nodes,
            )
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

            logging_summary = self.logging_service.record_error_capture(
                request.turn.session.session_id,
                dev_b_output.error_capture,
            )
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

            response = self.response_builder.build_unreal_response(
                request=request,
                normalized_input=normalized_input,
                understanding=understanding,
                dev_b_output=dev_b_output,
                dev_a_output=dev_a_output,
                logging_summary=logging_summary,
            )
            self.agent_run_middleware.record_event(
                agent_run,
                event="tool_call",
                status="completed",
                tool_name="response_builder.build_unreal_response",
                input_summary={
                    "request_id": request.turn.request_id,
                    "branch_next_node_id": dev_b_output.branch.next_node_id,
                    "npc_audio_url": dev_a_output.audio_url,
                },
                output_summary=_response_summary(response),
            )
            self.agent_run_middleware.record_data_flow(
                agent_run,
                from_node="response_builder",
                to_node="validator",
                payload_summary=_response_summary(response),
            )

            self.validator.validate_unreal_response(response)
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
            return response
        except Exception as exc:
            self.agent_run_middleware.record_event(
                agent_run,
                event="agent_end",
                status="failed",
                error=str(exc),
            )
            self.agent_run_middleware.complete_and_append(
                agent_run,
                status="failed",
                summary={
                    "input": _request_input_summary(request),
                    "output": {"error": str(exc), "error_type": exc.__class__.__name__},
                    "fallback_used": _understanding_fallback_used(self.understanding_agent.last_trace),
                    "audio_url": None,
                },
                model_usage=_agent_run_model_usage(self.understanding_agent.last_trace),
            )
            raise

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
        "chapter_id": node_context.chapter_id,
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
    }


def _response_summary(response: UnrealResponse) -> dict[str, Any]:
    return {
        "contract_version": response.contract_version,
        "request_id": response.request_id,
        "current_node_id": response.current_node_id,
        "next_node_id": response.next_node_id,
        "next_action": response.next_action,
        "npc_audio_url": response.npc.audio_url,
        "evaluation_verdict": response.evaluation.verdict,
        "recorded_error_count": response.report.recorded_error_count,
    }


def _understanding_fallback_used(trace: dict[str, Any]) -> bool:
    return bool(trace.get("fallback_used"))


def _agent_run_model_usage(trace: dict[str, Any]) -> dict[str, Any] | None:
    usage = trace.get("model_usage")
    return usage if isinstance(usage, dict) else None


def _preview(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
