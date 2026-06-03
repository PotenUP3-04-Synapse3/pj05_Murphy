from backend.app.schemas.game_turn import (
    DebugInfo,
    DevADialogueOutput,
    DevBPolicyOutput,
    EvaluationResponse,
    NormalizedInput,
    NpcResponse,
    PrePrototypeRequest,
    RecordedErrorSummary,
    ReportResponse,
    UiFeedback,
    UiResponse,
    UnderstandingOutput,
    UnrealResponse,
)


class ResponseBuilder:
    def build_unreal_response(
        self,
        request: PrePrototypeRequest,
        normalized_input: NormalizedInput,
        understanding: UnderstandingOutput,
        dev_b_output: DevBPolicyOutput,
        dev_a_output: DevADialogueOutput,
        logging_summary: RecordedErrorSummary,
    ) -> UnrealResponse:
        return UnrealResponse(
            contract_version="dev_c_unreal_response.v1",
            request_id=request.turn.request_id,
            session_id=request.turn.session.session_id,
            turn_index=request.turn.session.turn_index,
            current_node_id=request.turn.session.current_node_id,
            next_node_id=dev_b_output.branch.next_node_id,
            next_action=dev_b_output.branch.next_action,
            npc=NpcResponse(
                speaker=dev_a_output.speaker,
                text=dev_a_output.text,
                tone=dev_a_output.tone,
                animation=dev_a_output.animation,
            ),
            ui=UiResponse(
                show_hint=dev_b_output.level_hint.needs_hint,
                hint_kr=dev_b_output.level_hint.hint_kr,
                recommended_expression=dev_b_output.level_hint.recommended_expression,
                in_game_feedback=UiFeedback(
                    show=dev_b_output.in_game_feedback.show,
                    feedback_strategy=dev_b_output.in_game_feedback.feedback_strategy,
                    priority=dev_b_output.in_game_feedback.priority,
                ),
            ),
            state_delta=dev_b_output.state_delta,
            evaluation=EvaluationResponse(
                verdict=dev_b_output.evaluation.verdict,
                scores=dev_b_output.evaluation.scores,
                feedback_tags=dev_b_output.evaluation.feedback_tags,
            ),
            report=ReportResponse(
                recorded_error_count=logging_summary.recorded_error_count,
                report_item=dev_b_output.report_item,
            ),
            debug=DebugInfo(
                stt_model=normalized_input.stt_model,
                stt_confidence=normalized_input.input_source.stt_confidence,
                understanding_confidence=understanding.confidence,
                contract_versions=[
                    request.turn.contract_version,
                    dev_b_output.contract_version,
                    dev_a_output.contract_version,
                    "dev_c_unreal_response.v1",
                ],
            ),
        )
