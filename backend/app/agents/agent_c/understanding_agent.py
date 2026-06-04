from backend.app.schemas.game_turn import NodeContext, UnderstandingOutput


class UnderstandingAgent:
    def analyze_player_text(
        self,
        player_text: str,
        node_context: NodeContext,
    ) -> UnderstandingOutput:
        normalized = player_text.lower()
        matched_tourism = "tourism" in normalized or "travel" in normalized
        risky = any(keyword in normalized for keyword in node_context.risk_keywords)

        if risky:
            return UnderstandingOutput(
                intent="state_visit_purpose",
                intent_success=False,
                confidence=0.9,
                meaning_summary_kr="The player used a risky immigration expression.",
                emotion="nervous",
                answer_relevance="on_topic",
                ambiguity_type="risk_expression",
                risk_delta=30,
                risk_reason="Risk keyword found in player answer.",
                risk_tags=["risk_expression"],
                extracted_slots={},
                missing_slots=["visit_purpose"],
                needs_clarification=False,
            )

        if matched_tourism:
            return UnderstandingOutput(
                intent="state_visit_purpose",
                intent_success=True,
                confidence=0.94,
                meaning_summary_kr="The player said they are visiting for tourism.",
                emotion="nervous_humor",
                answer_relevance="on_topic",
                ambiguity_type="none",
                risk_delta=0,
                risk_reason="The purpose is clear and no risk expression was found.",
                risk_tags=[],
                extracted_slots={"visit_purpose": "tourism"},
                missing_slots=[],
                needs_clarification=False,
            )

        return UnderstandingOutput(
            intent="unknown",
            intent_success=False,
            confidence=0.55,
            meaning_summary_kr="The player answer did not clearly state a visit purpose.",
            emotion="nervous",
            answer_relevance="partially_related",
            ambiguity_type="unclear_purpose",
            risk_delta=0,
            risk_reason="No risk expression was found.",
            risk_tags=[],
            extracted_slots={},
            missing_slots=["visit_purpose"],
            needs_clarification=True,
        )
