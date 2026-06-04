import logging
from pydantic import ValidationError as PydanticValidationError
from time import perf_counter
from typing import Any

from backend.app.agents.agent_c.understanding_llm_client import (
    OpenAIUnderstandingLLMClient,
    UnderstandingLLMClient,
    UnderstandingLLMUnavailable,
)
from backend.app.agents.agent_c.visit_purpose_classifier import classify_visit_purpose
from backend.app.schemas.game_turn import NodeContext, UnderstandingOutput
from backend.app.services.service_c.settings_service import AppSettings, get_settings

_LOGGER = logging.getLogger(__name__)


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
        self.last_trace: dict[str, Any] = _build_rule_trace()

    def analyze_player_text(
        self,
        player_text: str,
        node_context: NodeContext,
    ) -> UnderstandingOutput:
        if self.settings.murphy_understanding_mode == "llm":
            started = perf_counter()
            model_name = self._llm_model_name()
            try:
                output = self._analyze_with_llm(player_text, node_context)
            except (UnderstandingLLMUnavailable, PydanticValidationError, TypeError, ValueError) as exc:
                _LOGGER.warning(
                    "Understanding Agent LLM failed; using rule fallback. error_type=%s error=%s",
                    exc.__class__.__name__,
                    exc,
                )
                output = self._analyze_with_rules(player_text, node_context)
                self.last_trace = _build_fallback_trace(
                    player_text=player_text,
                    node_context=node_context,
                    model_name=model_name,
                    duration_ms=_duration_ms(started),
                    error=exc,
                    fallback_output=output,
                )
                return output

            self.last_trace = _build_llm_trace(
                player_text=player_text,
                node_context=node_context,
                model_name=model_name,
                duration_ms=_duration_ms(started),
                output=output,
            )
            return output

        output = self._analyze_with_rules(player_text, node_context)
        self.last_trace = _build_rule_trace(output)
        return output

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

    def _llm_model_name(self) -> str:
        if self.llm_client is not None:
            return self.llm_client.model
        return self.settings.murphy_understanding_llm_model

    def _analyze_with_rules(
        self,
        player_text: str,
        node_context: NodeContext,
    ) -> UnderstandingOutput:
        normalized = player_text.lower()
        visit_purpose = classify_visit_purpose(
            player_text,
            node_context.allowed_slot_values.get("visit_purpose"),
        )
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

        if visit_purpose is not None:
            return UnderstandingOutput(
                intent="state_visit_purpose",
                intent_success=True,
                confidence=0.94,
                meaning_summary_kr=_visit_purpose_summary(visit_purpose),
                emotion="nervous_humor",
                answer_relevance="on_topic",
                ambiguity_type="none",
                risk_delta=0,
                risk_reason="The purpose is clear and no risk expression was found.",
                risk_tags=[],
                extracted_slots={"visit_purpose": visit_purpose},
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


def _visit_purpose_summary(visit_purpose: str) -> str:
    if visit_purpose == "tourism":
        return "The player said they are visiting for tourism."
    return f"The player clearly stated a visit purpose: {visit_purpose}."


def _build_rule_trace(output: UnderstandingOutput | None = None) -> dict[str, Any]:
    trace: dict[str, Any] = {
        "mode": "rule",
        "model_name": "rule_based",
        "fallback_used": False,
        "fallback_reason": None,
        "tool_calls": [],
    }
    if output is not None:
        trace["output_summary"] = _understanding_output_summary(output)
    return trace


def _build_llm_trace(
    *,
    player_text: str,
    node_context: NodeContext,
    model_name: str,
    duration_ms: int,
    output: UnderstandingOutput,
) -> dict[str, Any]:
    return {
        "mode": "llm",
        "model_name": model_name,
        "fallback_used": False,
        "fallback_reason": None,
        "tool_calls": [
            {
                "event": "tool_call",
                "status": "completed",
                "tool_name": "understanding_llm_client.analyze",
                "model_name": model_name,
                "duration_ms": duration_ms,
                "input_summary": _understanding_input_summary(player_text, node_context),
                "output_summary": _understanding_output_summary(output),
            }
        ],
    }


def _build_fallback_trace(
    *,
    player_text: str,
    node_context: NodeContext,
    model_name: str,
    duration_ms: int,
    error: Exception,
    fallback_output: UnderstandingOutput,
) -> dict[str, Any]:
    error_type = error.__class__.__name__
    return {
        "mode": "fallback",
        "model_name": model_name,
        "fallback_used": True,
        "fallback_reason": error_type,
        "tool_calls": [
            {
                "event": "tool_call",
                "status": "failed",
                "tool_name": "understanding_llm_client.analyze",
                "model_name": model_name,
                "duration_ms": duration_ms,
                "input_summary": _understanding_input_summary(player_text, node_context),
                "error": str(error),
                "error_type": error_type,
                "output_summary": _understanding_output_summary(fallback_output),
            }
        ],
    }


def _understanding_input_summary(player_text: str, node_context: NodeContext) -> dict[str, Any]:
    return {
        "player_text_preview": _preview(player_text),
        "node_id": node_context.node_id,
        "required_intents": node_context.required_intents,
        "required_slots": node_context.required_slots,
        "risk_keyword_count": len(node_context.risk_keywords),
    }


def _understanding_output_summary(output: UnderstandingOutput) -> dict[str, Any]:
    return {
        "intent": output.intent,
        "intent_success": output.intent_success,
        "confidence": output.confidence,
        "answer_relevance": output.answer_relevance,
        "risk_delta": output.risk_delta,
        "missing_slots": output.missing_slots,
        "needs_clarification": output.needs_clarification,
    }


def _duration_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _preview(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
