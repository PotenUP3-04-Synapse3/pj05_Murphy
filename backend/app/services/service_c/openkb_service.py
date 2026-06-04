from backend.app.schemas.game_turn import HintPolicy, NodeContext


class OpenKBService:
    def get_node_context(self, chapter_id: str, current_node_id: str) -> NodeContext:
        if chapter_id != "CH0_IMMIGRATION" or current_node_id != "IMM_002_PURPOSE":
            raise ValueError(f"Unsupported mock node: {chapter_id}/{current_node_id}")

        return NodeContext(
            node_id="IMM_002_PURPOSE",
            chapter_id="CH0_IMMIGRATION",
            npc_question="What is the purpose of your visit?",
            npc_question_goal="ask_visit_purpose",
            required_intents=["state_visit_purpose"],
            required_slots=["visit_purpose"],
            optional_slots=["destination", "activity", "duration"],
            critical_slots=["illegal_work_intent", "unclear_purpose", "suspicious_purpose"],
            allowed_slot_values={
                "visit_purpose": [
                    "tourism",
                    "business",
                    "family_visit",
                    "friend_visit",
                    "study",
                    "transit",
                ]
            },
            risk_keywords=["illegal", "forever", "secret", "disappear", "no return ticket"],
            recommended_expression="I'm here for tourism.",
            base_hint_kr="Tell the purpose of your visit.",
            hint_policy=HintPolicy(
                keyword=["tourism", "business", "vacation"],
                sentence_pattern="I'm here for ___.",
                situation_hint="Say why you are visiting.",
                action_hint="Say the purpose first, then add a short reason if needed.",
            ),
            success_next_node="IMM_003_DURATION",
            retry_next_node="IMM_002_RETRY_PURPOSE",
            clarify_next_node="IMM_EXTRA_001_CLARIFY_PURPOSE",
            hint_next_node="IMM_002_RETRY_PURPOSE",
            warning_next_node="END_SECONDARY_INSPECTION",
            allowed_next_nodes=[
                "IMM_003_DURATION",
                "IMM_002_RETRY_PURPOSE",
                "IMM_EXTRA_001_CLARIFY_PURPOSE",
                "END_SECONDARY_INSPECTION",
            ],
        )
