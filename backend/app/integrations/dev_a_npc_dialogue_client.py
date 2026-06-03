from backend.app.schemas.game_turn import DevADialogueInput, DevADialogueOutput


class DevANpcDialogueClient:
    def generate_dialogue(self, payload: DevADialogueInput) -> DevADialogueOutput:
        recast_candidate = payload.developer_b_policy.in_game_feedback.npc_recast_line_candidate
        text = recast_candidate or "Please answer the question again."

        return DevADialogueOutput(
            contract_version="dev_a_dialogue.v1",
            speaker="Officer Miller",
            text=text,
            tone="formal_neutral",
            animation="officer_check_passport",
            feedback_kr=f"Natural expression: {payload.node_context.recommended_expression}",
        )
