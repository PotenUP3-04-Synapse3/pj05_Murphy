from backend.app.schemas.game_turn import DevBPolicyOutput, FinalResult, UnrealResponse, UnrealResultResponse

ALLOWED_FINAL_RESULT_SCORING_POLICIES = {
    "simple_average",
    "scene_normalized_dimension_average",
}


class ValidationError(ValueError):
    pass


class Validator:
    def validate_dev_b_policy_output(
        self,
        policy_output: DevBPolicyOutput,
        current_node_id: str,
        allowed_next_nodes: list[str],
        client_allowed_next_nodes: list[str],
    ) -> None:
        if policy_output.contract_version != "dev_b_policy.v1":
            raise ValidationError("Developer B contract_version must be dev_b_policy.v1")

        if policy_output.node_id != current_node_id:
            raise ValidationError("Developer B node_id must match current_node_id")

        if policy_output.branch.next_node_id not in allowed_next_nodes:
            raise ValidationError("Developer B branch.next_node_id is not in node_context.allowed_next_nodes")

        if client_allowed_next_nodes and policy_output.branch.next_node_id not in client_allowed_next_nodes:
            raise ValidationError("Developer B branch.next_node_id is not in client_allowed_next_nodes")

        if not policy_output.branch.allowed_next_node_checked:
            raise ValidationError("Developer B branch.allowed_next_node_checked must be true")

        if not -100 <= policy_output.state_delta.patience_delta <= 100:
            raise ValidationError("state_delta.patience_delta is out of range")

        if not -100 <= policy_output.state_delta.suspicion_delta <= 100:
            raise ValidationError("state_delta.suspicion_delta is out of range")

        if not policy_output.level_hint.needs_hint:
            if policy_output.level_hint.hint_type is not None:
                raise ValidationError("level_hint.hint_type must be null when needs_hint is false")

            if policy_output.level_hint.hint_kr is not None:
                raise ValidationError("level_hint.hint_kr must be null when needs_hint is false")

        if policy_output.in_game_feedback.feedback_strategy == "recast":
            if not policy_output.in_game_feedback.npc_recast_line_candidate:
                raise ValidationError("recast feedback requires npc_recast_line_candidate")

        if policy_output.in_game_feedback.feedback_strategy == "clarification_request":
            if not policy_output.in_game_feedback.clarification_prompt_candidate:
                raise ValidationError("clarification feedback requires clarification_prompt_candidate")

        if policy_output.in_game_feedback.feedback_strategy == "scaffolding_hint":
            if not policy_output.in_game_feedback.scaffolding_hint:
                raise ValidationError("scaffolding_hint feedback requires scaffolding_hint")

        if not policy_output.error_capture.should_record and policy_output.error_capture.markdown_entry is not None:
            raise ValidationError("error_capture.markdown_entry must be null when should_record is false")

        if not policy_output.error_capture.should_record and policy_output.error_capture.error_items:
            raise ValidationError("error_capture.error_items must be empty when should_record is false")

        if policy_output.out_game_feedback_seed.include_in_final_report:
            if not policy_output.out_game_feedback_seed.focus_on_form_targets:
                raise ValidationError("out_game_feedback_seed.focus_on_form_targets must not be empty")

        if policy_output.final_result is not None:
            if policy_output.branch.branch_type != "final":
                raise ValidationError("final_result is only allowed on final branch outputs")
            self.validate_final_result(policy_output.final_result)

    def validate_unreal_response(self, response: UnrealResponse) -> None:
        if response.contract_version != "dev_c_unreal_response.v1":
            raise ValidationError("Unreal response contract_version must be dev_c_unreal_response.v1")

        if not response.npc.text:
            raise ValidationError("Unreal response npc.text must not be empty")

        if not response.npc.audio_url:
            raise ValidationError("Unreal response npc.audio_url must not be empty")

        if not response.npc.audio_url.startswith("/runtime/audio/"):
            raise ValidationError("Unreal response npc.audio_url must point to /runtime/audio/")

        if response.flow.contract_version != "dev_c_unreal_flow.v1":
            raise ValidationError("Unreal flow contract_version must be dev_c_unreal_flow.v1")

        if response.flow.transition_type == "scoreboard" and not response.flow.show_scoreboard:
            raise ValidationError("scoreboard flow must set show_scoreboard")

        if response.flow.transition_type != "scoreboard" and response.flow.show_scoreboard:
            raise ValidationError("show_scoreboard is only allowed for scoreboard flow")

        if response.report.final_result is not None:
            self.validate_final_result(response.report.final_result)

    def validate_unreal_result_response(self, response: UnrealResultResponse) -> None:
        if response.contract_version != "dev_c_unreal_result.v1":
            raise ValidationError("Unreal result contract_version must be dev_c_unreal_result.v1")

        self.validate_final_result(response.final_result)

    def validate_final_result(self, final_result: FinalResult) -> None:
        if not 0 <= final_result.final_score_100 <= 100:
            raise ValidationError("final_result.final_score_100 is out of range")

        scores = final_result.quantitative_scores
        score_values = [
            scores.overall,
            scores.comprehension,
            scores.fluency,
            scores.grammar_accuracy,
            scores.vocabulary_range,
            scores.clarity,
            scores.interaction_problem_solving,
        ]
        if any(not 0 <= value <= 100 for value in score_values):
            raise ValidationError("final_result.quantitative_scores contains an out-of-range score")

        if scores.overall != final_result.final_score_100:
            raise ValidationError("final_result.final_score_100 must match quantitative_scores.overall")

        if scores.scoring_policy not in ALLOWED_FINAL_RESULT_SCORING_POLICIES:
            raise ValidationError("final_result.quantitative_scores.scoring_policy is not allowed")

        if final_result.report_summary.included_node_count < 0:
            raise ValidationError("final_result.report_summary.included_node_count is out of range")

        if final_result.final_recommendation == "UNRANKED" and final_result.final_score_100 != 0:
            raise ValidationError("UNRANKED final_result.final_score_100 must be 0")
