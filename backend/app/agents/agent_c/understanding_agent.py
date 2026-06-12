import logging
from pydantic import ValidationError as PydanticValidationError
import re
from time import perf_counter
from typing import Any

from backend.app.agents.agent_c.llm_cost_estimator import build_model_usage_summary
from backend.app.agents.agent_c.understanding_llm_client import (
    UnderstandingLLMClient,
    UnderstandingLLMUnavailable,
    build_understanding_llm_client_from_settings,
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
                output, model_usage = self._analyze_with_llm(player_text, node_context)
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

            output, postprocessing = _repair_missing_allowed_slots(
                output,
                player_text,
                node_context,
            )
            self.last_trace = _build_llm_trace(
                player_text=player_text,
                node_context=node_context,
                model_name=model_name,
                duration_ms=_duration_ms(started),
                output=output,
                model_usage=model_usage,
                postprocessing=postprocessing,
            )
            return output

        output = self._analyze_with_rules(player_text, node_context)
        self.last_trace = _build_rule_trace(output)
        return output

    def _analyze_with_llm(
        self,
        player_text: str,
        node_context: NodeContext,
    ) -> tuple[UnderstandingOutput, dict[str, Any]]:
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
        model_usage = build_model_usage_summary(
            model_name=self._llm_model_name(),
            usage=_dict_or_none(result.get("__llm_usage")),
        )
        _reject_forbidden_llm_keys(result)
        return UnderstandingOutput.model_validate(result), model_usage

    def _get_llm_client(self) -> UnderstandingLLMClient:
        if self.llm_client is not None:
            return self.llm_client
        return build_understanding_llm_client_from_settings(self.settings)

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
        stay_duration = _extract_stay_duration(player_text)
        risky = any(keyword in normalized for keyword in node_context.risk_keywords)
        primary_required_slot = node_context.required_slots[0] if node_context.required_slots else None

        if risky:
            return UnderstandingOutput(
                intent=_required_intent_for_slot(node_context, primary_required_slot or "unknown"),
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
                missing_slots=node_context.required_slots,
                needs_clarification=False,
            )

        if "stay_duration" in node_context.required_slots:
            if stay_duration is not None:
                return UnderstandingOutput(
                    intent=_required_intent_for_slot(node_context, "stay_duration"),
                    intent_success=True,
                    confidence=0.92,
                    meaning_summary_kr=_stay_duration_summary(stay_duration),
                    emotion="calm",
                    answer_relevance="on_topic",
                    ambiguity_type="none",
                    risk_delta=0,
                    risk_reason="The stay duration is clear and no risk expression was found.",
                    risk_tags=[],
                    extracted_slots={"stay_duration": stay_duration},
                    missing_slots=[],
                    needs_clarification=False,
                )

            return UnderstandingOutput(
                intent=_required_intent_for_slot(node_context, "stay_duration"),
                intent_success=False,
                confidence=0.55,
                meaning_summary_kr="The player answer did not clearly state a stay duration.",
                emotion="nervous",
                answer_relevance="partially_related",
                ambiguity_type="unclear_duration",
                risk_delta=0,
                risk_reason="No risk expression was found.",
                risk_tags=[],
                extracted_slots={},
                missing_slots=["stay_duration"],
                needs_clarification=True,
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


def _stay_duration_summary(stay_duration: str) -> str:
    return f"The player clearly stated a stay duration: {stay_duration}."


def _repair_missing_allowed_slots(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> tuple[UnderstandingOutput, dict[str, Any]]:
    no_repair = {"slot_repair_applied": False}
    if _has_risk_expression(player_text, node_context):
        return output, no_repair

    repairs: list[dict[str, str]] = []
    extracted_slots = dict(output.extracted_slots)

    if "visit_purpose" in node_context.required_slots and extracted_slots.get("visit_purpose") is None:
        visit_purpose = classify_visit_purpose(
            player_text,
            node_context.allowed_slot_values.get("visit_purpose"),
        )
        if visit_purpose is not None:
            extracted_slots["visit_purpose"] = visit_purpose
            repairs.append(
                {
                    "source": "rule_visit_purpose_classifier",
                    "slot": "visit_purpose",
                    "value": visit_purpose,
                    "summary": _visit_purpose_summary(visit_purpose),
                }
            )

    if "stay_duration" in node_context.required_slots and extracted_slots.get("stay_duration") is None:
        stay_duration = _extract_stay_duration(player_text)
        if stay_duration is not None:
            extracted_slots["stay_duration"] = stay_duration
            repairs.append(
                {
                    "source": "rule_stay_duration_classifier",
                    "slot": "stay_duration",
                    "value": stay_duration,
                    "summary": _stay_duration_summary(stay_duration),
                }
            )

    if not repairs:
        return output, no_repair

    repaired_slot_names = {repair["slot"] for repair in repairs}
    missing_slots = [slot for slot in output.missing_slots if slot not in repaired_slot_names]
    primary_repair = repairs[0]
    repaired = output.model_copy(
        update={
            "intent": _required_intent_for_slot(node_context, primary_repair["slot"]),
            "intent_success": len(missing_slots) == 0,
            "confidence": max(
                output.confidence,
                0.94 if primary_repair["slot"] == "visit_purpose" else 0.92,
            ),
            "meaning_summary_kr": primary_repair["summary"],
            "answer_relevance": "on_topic",
            "ambiguity_type": "none" if len(missing_slots) == 0 else output.ambiguity_type,
            "risk_delta": 0,
            "risk_reason": "The required slot is clear and no risk expression was found.",
            "risk_tags": [],
            "extracted_slots": extracted_slots,
            "missing_slots": missing_slots,
            "needs_clarification": len(missing_slots) > 0,
        }
    )
    if len(repairs) > 1:
        return repaired, {
            "slot_repair_applied": True,
            "repairs": [
                {
                    "source": repair["source"],
                    "slot": repair["slot"],
                    "value": repair["value"],
                    "reason": "llm_missing_allowed_slot",
                }
                for repair in repairs
            ],
        }

    return repaired, {
        "slot_repair_applied": True,
        "source": primary_repair["source"],
        "slot": primary_repair["slot"],
        "value": primary_repair["value"],
        "reason": "llm_missing_allowed_slot",
    }


def _required_intent_for_slot(node_context: NodeContext, slot_name: str) -> str:
    if slot_name == "visit_purpose" and "state_visit_purpose" in node_context.required_intents:
        return "state_visit_purpose"
    if slot_name == "stay_duration" and "state_stay_duration" in node_context.required_intents:
        return "state_stay_duration"
    return node_context.required_intents[0] if node_context.required_intents else "unknown"


def _has_risk_expression(player_text: str, node_context: NodeContext) -> bool:
    normalized = player_text.lower()
    return any(keyword in normalized for keyword in node_context.risk_keywords)


def _extract_stay_duration(player_text: str) -> str | None:
    normalized = " ".join(player_text.lower().replace("-", " ").split())
    quantity = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an)"
    duration_match = re.search(rf"\b({quantity}\s+(?:day|days|week|weeks|month|months))\b", normalized)
    if duration_match:
        value = duration_match.group(1)
        if value.startswith("a "):
            return f"one {value[2:]}"
        if value.startswith("an "):
            return f"one {value[3:]}"
        return value

    until_match = re.search(
        r"\b(until\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|next\s+\w+|\w+\s+\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?))\b",
        normalized,
    )
    if until_match:
        return until_match.group(1)

    return None


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
    model_usage: dict[str, Any],
    postprocessing: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "llm",
        "model_name": model_name,
        "model_usage": model_usage,
        "postprocessing": postprocessing,
        "fallback_used": False,
        "fallback_reason": None,
        "tool_calls": [
            {
                "event": "tool_call",
                "status": "completed",
                "tool_name": "understanding_llm_client.analyze",
                "model_name": model_name,
                "model_usage": model_usage,
                "duration_ms": duration_ms,
                "input_summary": _understanding_input_summary(player_text, node_context),
                "output_summary": {
                    **_understanding_output_summary(output),
                    "estimated_cost_usd": model_usage["estimated_cost_usd"],
                },
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


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _preview(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
