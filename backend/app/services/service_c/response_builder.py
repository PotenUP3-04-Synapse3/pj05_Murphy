"""Assemble the final Unreal-safe response payload.

Beginner guide:
Earlier services produce separate pieces: STT text, Understanding evidence,
Developer B policy, Developer A dialogue/TTS, and logging summaries.  This
builder copies only the fields Unreal is allowed to see into the
`UnrealResponse` schema.  It does not create branch decisions; it uses the
validated Developer B result.
"""

from backend.app.schemas.game_turn import (
    DebugInfo,
    DevADialogueOutput,
    DevBPolicyOutput,
    EvaluationResponse,
    FlowResponse,
    NormalizedInput,
    NpcResponse,
    PrePrototypeRequest,
    RecordedErrorSummary,
    ReportResponse,
    SttResponse,
    TransitionContext,
    TurnTimingMs,
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
        transition: TransitionContext | None = None,
        timing_ms: TurnTimingMs | None = None,
    ) -> UnrealResponse:
        """Assemble the final UnrealResponse object from turn components.

        Beginner guide:
        This builder functions as the response packaging layer. It takes the outputs
        from other team components (STT, Understanding, Dev B policy, Dev A dialogue)
        and structures them into the final UnrealResponse contract.

        It does not make any business decisions, score evaluations, or branch decisions
        on its own. It enforces the contract schemas and returns the mutated GameState
        back to Unreal so that location and item assignments persist across turns.
        """
        return UnrealResponse(
            contract_version="dev_c_unreal_response.v1",
            request_id=request.turn.request_id,
            session_id=request.turn.session.session_id,
            turn_index=request.turn.session.turn_index,
            current_node_id=request.turn.session.current_node_id,
            next_node_id=dev_b_output.branch.next_node_id,
            next_action=dev_b_output.branch.next_action,
            transition=transition,
            interaction=request.turn.interaction,
            game_state=request.turn.game_state,
            stt=SttResponse(
                model=normalized_input.stt_model,
                primary_runtime=normalized_input.stt_primary_runtime,
                fallback_runtime=normalized_input.stt_fallback_runtime,
                runtime_used=normalized_input.stt_runtime_used,
                player_text=normalized_input.player_text,
                confidence=normalized_input.input_source.stt_confidence,
                language_detected=normalized_input.input_source.language_detected,
                needs_repeat=normalized_input.input_source.needs_repeat,
            ),
            npc=NpcResponse(
                speaker=dev_a_output.speaker,
                text=dev_a_output.text,
                emotion=dev_b_output.npc_emotion,
                tone=dev_a_output.tone,
                animation=dev_a_output.animation,
                audio_url=dev_a_output.audio_url,
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
            flow=_build_flow_response(
                current_scene_id=request.turn.session.scene_id,
                current_node_id=request.turn.session.current_node_id,
                next_node_id=dev_b_output.branch.next_node_id,
                next_action=dev_b_output.branch.next_action,
                transition=transition,
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
                final_result=dev_b_output.final_result,
            ),
            debug=DebugInfo(
                stt_model=normalized_input.stt_model,
                stt_confidence=normalized_input.input_source.stt_confidence,
                understanding_confidence=understanding.confidence,
                contract_versions=[
                    request.turn.contract_version,
                    request.turn.interaction.contract_version,
                    "dev_c_unreal_flow.v1",
                    dev_b_output.contract_version,
                    dev_a_output.contract_version,
                    "dev_c_unreal_response.v1",
                ],
                timing_ms=timing_ms or TurnTimingMs(),
                diagnostics=dev_a_output.diagnostics,
            ),
        )


def _build_flow_response(
    *,
    current_scene_id: str,
    current_node_id: str,
    next_node_id: str,
    next_action: str,
    transition: TransitionContext | None,
) -> FlowResponse:
    if transition is not None and transition.unreal_event == "START_AIRPORT_ARRIVAL_TUTORIAL":
        return FlowResponse(
            transition_type="cutscene",
            transition_id="flight_to_arrival_tutorial",
            from_scene_id=current_scene_id,
            to_scene_id="ARRIVAL_TUTORIAL",
            cinematic_id="CIN_FLIGHT_ARRIVAL_JFK",
            skip_allowed=True,
        )

    if transition is not None and transition.unreal_event == "ENTER_BAGGAGE_CLAIM":
        return FlowResponse(
            transition_type="scene_transition",
            transition_id="immigration_to_baggage_claim",
            from_scene_id=current_scene_id,
            to_scene_id="BAGGAGE_MISSING",
        )

    if transition is not None and transition.unreal_event == "SHOW_ALPHA_SCOREBOARD":
        return FlowResponse(
            transition_type="scoreboard",
            transition_id="alpha_final_scoreboard",
            from_scene_id=current_scene_id,
            to_scene_id="ALPHA_SCOREBOARD",
            show_scoreboard=True,
        )

    # 비속어 배드 엔딩도 결과 UI를 열어야 하므로 Alpha scoreboard flow로 보냅니다.
    if transition is not None and transition.unreal_event == "SHOW_BAD_END_SCOREBOARD":
        return FlowResponse(
            transition_type="scoreboard",
            transition_id="bad_end_scoreboard",
            from_scene_id=current_scene_id,
            to_scene_id="ALPHA_SCOREBOARD",
            show_scoreboard=True,
        )

    if current_node_id == "FLIGHT_005_WRAP_UP" and next_node_id == "IMM_001_PASSPORT":
        return FlowResponse(
            transition_type="cutscene",
            transition_id="flight_to_immigration_arrival",
            from_scene_id=current_scene_id,
            to_scene_id="IMMIGRATION_ALPHA",
            cinematic_id="CIN_FLIGHT_ARRIVAL_JFK",
            skip_allowed=True,
        )

    if current_node_id == "IMM_007_FINAL_DECISION" and next_node_id == "BAG_001_NOTICE_BAG_MISSING":
        return FlowResponse(
            transition_type="scene_transition",
            transition_id="immigration_to_baggage_claim",
            from_scene_id=current_scene_id,
            to_scene_id="BAGGAGE_MISSING",
        )

    if current_node_id == "ALPHA_999_FINAL_SCOREBOARD" and next_action == "FINAL_DECISION":
        return FlowResponse(
            transition_type="scoreboard",
            transition_id="alpha_final_scoreboard",
            from_scene_id=current_scene_id,
            to_scene_id="ALPHA_SCOREBOARD",
            show_scoreboard=True,
        )

    return FlowResponse(from_scene_id=current_scene_id, to_scene_id=current_scene_id)
