from pydantic import ValidationError as PydanticValidationError

from backend.app.agents.agent_c.understanding_llm_client import (
    OpenAIUnderstandingLLMClient,
    UnderstandingLLMClient,
    UnderstandingLLMUnavailable,
)
from backend.app.schemas.game_turn import NodeContext, UnderstandingOutput
from backend.app.services.service_c.settings_service import AppSettings, get_settings


FORBIDDEN_UNDERSTANDING_LLM_KEYS = {
    "branch",
    "next_node_id",
    "next_action",
    "state_delta",
    "verdict",
    "score",
    "scores",
    "evaluation",
    "hint",
    "hint_kr",
    "level_hint",
    "npc_text",
    "tts_text",
    "commands",
    "unreal_commands",
}


class UnderstandingAgent:
    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        llm_client: UnderstandingLLMClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm_client = llm_client

    def analyze_player_text(
        self,
        player_text: str,
        node_context: NodeContext,
    ) -> UnderstandingOutput:
        if self.settings.murphy_understanding_mode == "llm":
            try:
                return self._analyze_with_llm(player_text, node_context)
            except (UnderstandingLLMUnavailable, PydanticValidationError, TypeError, ValueError):
                return self._analyze_with_rules(player_text, node_context)

        return self._analyze_with_rules(player_text, node_context)

    def _analyze_with_llm(
        self,
        player_text: str,
        node_context: NodeContext,
    ) -> UnderstandingOutput:
        result = self._get_llm_client().analyze(
            {
                "player_text": player_text,
                "node_context": node_context.model_dump(),
                "output_contract": {
                    "allowed_output": "UnderstandingOutput only",
                    "forbidden_authority": [
                        "branch",
                        "next_node_id",
                        "next_action",
                        "state_delta",
                        "scores",
                        "hints",
                        "npc_dialogue",
                        "unreal_commands",
                    ],
                },
            }
        )
        _reject_forbidden_llm_keys(result)
        return UnderstandingOutput.model_validate(result)

    def _get_llm_client(self) -> UnderstandingLLMClient:
        if self.llm_client is not None:
            return self.llm_client
        return OpenAIUnderstandingLLMClient.from_settings(self.settings)

    def _analyze_with_rules(
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


def _reject_forbidden_llm_keys(result: dict[str, object]) -> None:
    forbidden_keys = FORBIDDEN_UNDERSTANDING_LLM_KEYS.intersection(result)
    if forbidden_keys:
        joined_keys = ", ".join(sorted(forbidden_keys))
        raise UnderstandingLLMUnavailable(f"Understanding LLM returned forbidden keys: {joined_keys}")
