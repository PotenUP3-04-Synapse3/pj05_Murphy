from backend.app.schemas.game_turn import DevBPolicyOutput, UnrealResponse


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

        if not -100 <= policy_output.state_delta.patience_delta <= 100:
            raise ValidationError("state_delta.patience_delta is out of range")

        if not -100 <= policy_output.state_delta.suspicion_delta <= 100:
            raise ValidationError("state_delta.suspicion_delta is out of range")

        if not policy_output.error_capture.should_record and policy_output.error_capture.markdown_entry is not None:
            raise ValidationError("error_capture.markdown_entry must be null when should_record is false")

    def validate_unreal_response(self, response: UnrealResponse) -> None:
        if response.contract_version != "dev_c_unreal_response.v1":
            raise ValidationError("Unreal response contract_version must be dev_c_unreal_response.v1")

        if not response.npc.text:
            raise ValidationError("Unreal response npc.text must not be empty")
