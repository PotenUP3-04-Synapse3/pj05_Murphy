"""Turn player text into Developer C semantic understanding.

Beginner guide:
This is not the scenario branch decider.  It reads the player's transcript and
the current scenario node, then returns semantic evidence such as intent,
filled slots, missing slots, risk tags, and confidence.  Developer B still owns
the actual pass/fail/next-node policy.  When LLM mode is enabled, this agent
tries the LLM first, filters unsafe fields, repairs obvious slots with rules,
and falls back to deterministic rules when the LLM is unavailable.
"""

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
from backend.app.schemas.game_turn import NodeContext, SlotEvidence, UnderstandingOutput
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

ALPHA_SLOT_VALUE_KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "polite_response": {
        "offered_help": ("of course", "sure", "here you are", "take it", "use this pen"),
        "declined_politely": ("sorry", "i need it", "after me"),
        "short_acknowledgement": ("okay", "yes", "no problem"),
    },
    "travel_purpose": {
        "tourism": ("tourism", "vacation", "holiday", "travel", "trip", "sightseeing"),
        "business": ("business", "work", "conference", "meeting"),
        "family_visit": ("family", "uncle", "aunt", "parents", "cousin"),
        "friend_visit": ("friend", "friends"),
        "study": ("study", "school", "university", "academy"),
        "transit": ("transit", "transfer", "layover"),
    },
    "stay_plan": {
        "five_days": ("five days", "5 days"),
        "one_week": ("one week", "1 week"),
        "two_weeks": ("two weeks", "2 weeks"),
        "short_trip": ("short trip", "few days", "several days"),
        "until_date": ("until monday", "until tuesday", "until wednesday", "until thursday", "until friday"),
    },
    "interaction_repair": {
        "confirmed": ("yes", "that's right", "correct", "first time"),
        "asked_clarification": ("sorry", "what do you mean", "can you repeat"),
        "asked_back": ("how about you", "what about you"),
        "rephrased_answer": ("i mean", "let me say"),
    },
    "smalltalk_closing": {
        "polite_closing": ("nice talking", "good talking", "see you"),
        "thanks": ("thank", "thanks"),
        "ready": ("ready", "i'm ready"),
        "nervous_but_ready": ("nervous", "worried", "but ready"),
    },
    "missing_bag_statement": {
        "bag_not_arrived": ("bag didn't arrive", "bag did not arrive", "didn't come out", "not come out"),
        "suitcase_missing": ("missing suitcase", "lost suitcase", "can't find my suitcase", "cannot find my suitcase"),
        "need_staff_help": ("need help", "help me", "can you help"),
    },
    "claim_tag_status": {
        "has_claim_tag": ("claim tag", "bag tag", "baggage tag", "tag right here", "have the tag"),
        "has_ticket": ("ticket", "baggage ticket"),
        "has_boarding_pass": ("boarding pass",),
    },
    "carousel_search_confirmation": {
        "searched_carefully": ("checked carefully", "searched carefully", "looked carefully"),
        "waited_until_stopped": ("waited", "until it stopped", "carousel stopped"),
        "checked_twice": ("checked twice", "looked twice"),
    },
    "customs_hold_redirect_acknowledgement": {
        "will_go_to_customs_hold": ("i'll go", "i will go", "go back", "go there"),
        "understands_redirect": ("okay", "i understand", "got it"),
        "asks_where_to_go": ("where", "which way", "where should i go"),
    },
    "customs_hold_acknowledgement": {
        "will_unlock_and_check": ("open it", "unlock", "check the contents", "check inside"),
        "understands_inspection": ("inspection", "i understand", "okay"),
        "confirms_owner": ("my bag", "my suitcase", "it is mine", "it's mine"),
    },
    "customs_item_explanation": {
        "personal_item": ("personal item", "for me", "my item", "for myself"),
        "souvenir": ("souvenir", "memory", "keepsake"),
        "gift": ("gift", "present"),
        "medicine": ("medicine", "medication", "health", "red ginseng", "pill", "vitamin"),
        "food_for_personal_use": ("food", "snack", "personal use", "eat"),
    },
    "customs_clearance_acknowledgement": {
        "acknowledged_clearance": ("thank", "thanks", "okay", "i understand"),
        "will_exit_airport": ("exit", "leave the airport", "go out"),
        "will_take_suitcase": ("take my suitcase", "take it", "take my bag"),
    },
}

ALPHA_SLOT_OFF_TOPIC_PHRASES: dict[str, tuple[str, ...]] = {
    "polite_response": (
        "you're on",
        "you are on",
        "challenge accepted",
        "it's a bet",
        "deal with it",
    ),
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

            output, slot_evidence_postprocessing = _apply_generic_slot_evidence(
                output,
                player_text,
                node_context,
            )
            output, slot_repair_postprocessing = _repair_missing_allowed_slots(
                output,
                player_text,
                node_context,
            )
            postprocessing = _merge_postprocessing(
                slot_evidence_postprocessing,
                slot_repair_postprocessing,
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

        if _has_required_intent_mismatch(player_text, node_context):
            return _off_topic_required_slot_output(player_text, node_context)

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

        generic_slot = _extract_generic_required_slot(player_text, node_context)
        if generic_slot is not None:
            slot_name, slot_value = generic_slot
            return UnderstandingOutput(
                intent=_required_intent_for_slot(node_context, slot_name),
                intent_success=True,
                confidence=0.86,
                meaning_summary_kr=f"The player clearly answered the required slot: {slot_name}.",
                emotion="calm",
                answer_relevance="on_topic",
                ambiguity_type="none",
                risk_delta=0,
                risk_reason="The required slot is clear and no risk expression was found.",
                risk_tags=[],
                slot_evidence=[
                    SlotEvidence(
                        slot=slot_name,
                        value=slot_value,
                        confidence=0.86,
                        evidence_text=_matched_generic_evidence_text(player_text, node_context) or slot_value,
                    )
                ],
                extracted_slots={slot_name: slot_value},
                missing_slots=[],
                needs_clarification=False,
            )

        return UnderstandingOutput(
            intent=_required_intent_for_slot(node_context, primary_required_slot or "unknown"),
            intent_success=False,
            confidence=0.55,
            meaning_summary_kr="The player answer did not clearly fill the required slot.",
            emotion="nervous",
            answer_relevance="partially_related",
            ambiguity_type="unclear_required_slot",
            risk_delta=0,
            risk_reason="No risk expression was found.",
            risk_tags=[],
            extracted_slots={},
            missing_slots=node_context.required_slots,
            needs_clarification=True,
        )


def _reject_forbidden_llm_keys(result: dict[str, object]) -> None:
    forbidden_keys = FORBIDDEN_UNDERSTANDING_LLM_KEYS.intersection(result)
    if forbidden_keys:
        joined_keys = ", ".join(sorted(forbidden_keys))
        raise UnderstandingLLMUnavailable(f"Understanding LLM returned forbidden keys: {joined_keys}")


def _extract_generic_required_slot(
    player_text: str,
    node_context: NodeContext,
) -> tuple[str, str] | None:
    if not node_context.required_slots:
        return None

    slot_name = node_context.required_slots[0]
    allowed_values = node_context.allowed_slot_values.get(slot_name, [])
    if not allowed_values:
        return None

    matched_allowed_value = _match_alpha_allowed_slot_value(player_text, slot_name, allowed_values)
    if matched_allowed_value is not None:
        return slot_name, matched_allowed_value

    matched_evidence = _matched_generic_evidence_text(player_text, node_context)
    if matched_evidence is None:
        return None

    normalized_text = _normalize_for_keyword_match(player_text)
    for allowed_value in allowed_values:
        if _normalize_for_keyword_match(allowed_value).replace("_", " ") in normalized_text:
            return slot_name, allowed_value

    return slot_name, allowed_values[0]


def _match_alpha_allowed_slot_value(
    player_text: str,
    slot_name: str,
    allowed_values: list[str],
) -> str | None:
    """Match common Alpha fallback phrases to allowed slot values.

    Beginner guide:
    The LLM path can fill any current-node slot through `slot_evidence`, but
    local rule/mock mode still needs a small deterministic safety net.  This
    helper is keyed by slot name and allowed value, not by scenario node id, so
    adding another node that reuses the same slot can reuse the same fallback.
    """

    if _has_slot_intent_mismatch(player_text, slot_name):
        return None

    normalized_text = _normalize_for_keyword_match(player_text)
    slot_value_keywords = ALPHA_SLOT_VALUE_KEYWORDS.get(slot_name, {})
    for allowed_value in allowed_values:
        for keyword in slot_value_keywords.get(allowed_value, ()):
            if _normalize_for_keyword_match(keyword) in normalized_text:
                return allowed_value

    return None


def _matched_generic_evidence_text(
    player_text: str,
    node_context: NodeContext,
) -> str | None:
    normalized_text = _normalize_for_keyword_match(player_text)
    candidates = [
        *node_context.hint_policy.keyword,
        node_context.hint_policy.sentence_pattern,
        node_context.recommended_expression,
    ]
    for candidate in candidates:
        normalized_candidate = _normalize_for_keyword_match(candidate)
        if normalized_candidate and normalized_candidate in normalized_text:
            return candidate
    return None


def _normalize_for_keyword_match(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


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
    slot_evidence = [
        *output.slot_evidence,
        *[
            SlotEvidence(
                slot=repair["slot"],
                value=repair["value"],
                confidence=0.94 if repair["slot"] == "visit_purpose" else 0.92,
                evidence_text=repair["value"],
            )
            for repair in repairs
        ],
    ]
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
            "slot_evidence": slot_evidence,
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


def _apply_generic_slot_evidence(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> tuple[UnderstandingOutput, dict[str, Any]]:
    allowed_slots = _allowed_slot_names(node_context)
    accepted_evidence: list[SlotEvidence] = []
    dropped_slots: list[str] = []

    for evidence in output.slot_evidence:
        if evidence.slot in allowed_slots and _is_supported_slot_evidence(
            evidence,
            player_text,
            node_context,
        ):
            accepted_evidence.append(evidence)
        else:
            dropped_slots.append(evidence.slot)

    extracted_slots = {
        slot: value
        for slot, value in output.extracted_slots.items()
        if slot in allowed_slots
        and value
        and _is_supported_extracted_slot_value(
            slot_name=slot,
            slot_value=value,
            player_text=player_text,
            node_context=node_context,
        )
    }
    for evidence in accepted_evidence:
        extracted_slots.setdefault(evidence.slot, evidence.value)

    intent_mismatch = _has_required_intent_mismatch(player_text, node_context)
    if intent_mismatch:
        accepted_evidence = []
        extracted_slots = {
            slot: value
            for slot, value in extracted_slots.items()
            if slot not in node_context.required_slots
        }

    missing_slots = [
        slot for slot in node_context.required_slots if slot not in extracted_slots
    ]
    weak_required_slot_evidence = _has_weak_required_slot_evidence(
        accepted_evidence,
        extracted_slots,
        node_context,
    )
    answer_relevance = "off_topic" if intent_mismatch else output.answer_relevance
    confidence = _guard_confidence_for_evidence(
        output.confidence,
        intent_mismatch=intent_mismatch,
        weak_required_slot_evidence=weak_required_slot_evidence,
    )
    confidence_guard_applied = confidence != output.confidence
    applied = bool(accepted_evidence) and (
        any(evidence.slot not in output.extracted_slots for evidence in accepted_evidence)
        or missing_slots != output.missing_slots
    )
    filtered = len(accepted_evidence) != len(output.slot_evidence)
    if (
        not applied
        and not filtered
        and missing_slots == output.missing_slots
        and not intent_mismatch
        and not confidence_guard_applied
    ):
        return output, {
            "generic_slot_evidence_applied": False,
            "accepted_slot_evidence": [],
            "dropped_slot_evidence": [],
        }

    has_clear_required_slots = len(missing_slots) == 0
    normalized = output.model_copy(
        update={
            "intent_success": (
                has_clear_required_slots
                and answer_relevance != "off_topic"
                and output.risk_delta <= 0
                and output.intent_success
            )
            or (
                bool(accepted_evidence)
                and has_clear_required_slots
                and answer_relevance != "off_topic"
                and output.risk_delta <= 0
            ),
            "confidence": confidence,
            "answer_relevance": answer_relevance,
            "ambiguity_type": "off_topic_response" if intent_mismatch else output.ambiguity_type,
            "slot_evidence": accepted_evidence,
            "extracted_slots": extracted_slots,
            "missing_slots": missing_slots,
            "needs_clarification": len(missing_slots) > 0,
        }
    )
    return normalized, {
        "generic_slot_evidence_applied": applied,
        "intent_relevance_guard_applied": intent_mismatch,
        "confidence_evidence_guard_applied": confidence_guard_applied,
        "weak_required_slot_evidence": weak_required_slot_evidence,
        "accepted_slot_evidence": [evidence.slot for evidence in accepted_evidence],
        "dropped_slot_evidence": dropped_slots,
    }


def _allowed_slot_names(node_context: NodeContext) -> set[str]:
    return {
        *node_context.required_slots,
        *node_context.optional_slots,
        *node_context.critical_slots,
    }


def _has_weak_required_slot_evidence(
    accepted_evidence: list[SlotEvidence],
    extracted_slots: dict[str, str],
    node_context: NodeContext,
) -> bool:
    """Return whether a filled required slot lacks strong text evidence.

    Beginner guide:
    A high confidence score should mean "we have strong evidence."  If the LLM
    fills a required slot but does not provide matching `slot_evidence`, C keeps
    the slot value for compatibility but lowers the confidence below 0.9.
    """

    if not node_context.required_slots:
        return False

    evidence_by_slot = {evidence.slot: evidence for evidence in accepted_evidence}
    for slot in node_context.required_slots:
        if slot not in extracted_slots:
            continue
        evidence = evidence_by_slot.get(slot)
        if evidence is None:
            return True
        if evidence.confidence < 0.85 or not evidence.evidence_text.strip():
            return True
    return False


def _guard_confidence_for_evidence(
    confidence: float,
    *,
    intent_mismatch: bool,
    weak_required_slot_evidence: bool,
) -> float:
    """Lower overconfident Understanding scores when evidence is weak.

    Beginner guide:
    Developer B consumes C's confidence as a signal.  This helper keeps obvious
    off-topic phrases lower, and also prevents a 0.9+ score when a required slot
    was filled without strong evidence.
    """

    if intent_mismatch:
        return min(confidence, 0.72)
    if weak_required_slot_evidence:
        return min(confidence, 0.89)
    return confidence


def _has_required_intent_mismatch(player_text: str, node_context: NodeContext) -> bool:
    """Return whether the transcript clearly does not answer the required slot.

    Beginner guide:
    This is a small deterministic guard that runs after the LLM.  It does not
    try to understand every possible sentence.  It only catches known phrases
    that are dangerous because they look like a valid short answer, but mean
    something unrelated to the current scenario task.
    """

    return any(_has_slot_intent_mismatch(player_text, slot) for slot in node_context.required_slots)


def _has_slot_intent_mismatch(player_text: str, slot_name: str) -> bool:
    """Return whether a phrase is a known mismatch for one slot.

    Beginner guide:
    For the seatmate pen request, "Okay" can be a valid short acknowledgement.
    "Okay, you're on" is different: it is an idiom for accepting a challenge or
    bet.  This helper blocks that kind of phrase before it becomes a valid slot
    value.
    """

    normalized_text = _normalize_for_keyword_match(player_text)
    return any(
        _normalize_for_keyword_match(phrase) in normalized_text
        for phrase in ALPHA_SLOT_OFF_TOPIC_PHRASES.get(slot_name, ())
    )


def _off_topic_required_slot_output(player_text: str, node_context: NodeContext) -> UnderstandingOutput:
    """Build a safe Understanding output for a known off-topic phrase.

    Beginner guide:
    Developer B decides the branch later, but it relies on C's Understanding
    result.  When C knows the player did not answer the required intent, C must
    return missing slots and a lower confidence instead of a confident success.
    """

    primary_required_slot = node_context.required_slots[0] if node_context.required_slots else "unknown"
    return UnderstandingOutput(
        intent=_required_intent_for_slot(node_context, primary_required_slot),
        intent_success=False,
        confidence=0.72,
        meaning_summary_kr="The player used an off-topic idiom instead of answering the current request.",
        emotion="confused",
        answer_relevance="off_topic",
        ambiguity_type="off_topic_response",
        risk_delta=0,
        risk_reason="No immigration risk expression was found.",
        risk_tags=[],
        extracted_slots={},
        missing_slots=node_context.required_slots,
        needs_clarification=True,
    )


def _is_supported_slot_evidence(
    evidence: SlotEvidence,
    player_text: str,
    node_context: NodeContext,
) -> bool:
    """Return whether one LLM slot evidence item is allowed and grounded.

    Beginner guide:
    The LLM can propose a slot name and value.  C accepts it only when the slot
    belongs to the current node and, for enum-like slots, the value has clear
    support in the player text.  This prevents a valid-looking enum value from
    passing through when the sentence means something else.
    """

    if not _is_supported_extracted_slot_value(
        slot_name=evidence.slot,
        slot_value=evidence.value,
        player_text=player_text,
        node_context=node_context,
    ):
        return False

    allowed_values = node_context.allowed_slot_values.get(evidence.slot, [])
    if not allowed_values:
        return True
    if _match_alpha_allowed_slot_value(player_text, evidence.slot, [evidence.value]) == evidence.value:
        return True

    normalized_value = _normalize_for_keyword_match(evidence.value)
    normalized_text = _normalize_for_keyword_match(player_text)
    return bool(normalized_value and normalized_value in normalized_text)


def _is_supported_extracted_slot_value(
    *,
    slot_name: str,
    slot_value: str,
    player_text: str,
    node_context: NodeContext,
) -> bool:
    """Return whether an extracted slot value is valid for the current text.

    Beginner guide:
    Some slots are free text, such as a hotel name.  Some slots have allowed
    enum values, such as `polite_response` or `visit_purpose`.  For extracted
    slots, C keeps valid enum values because the LLM may do legitimate semantic
    normalization such as "museums" -> "tourism".  Known mismatch phrases are
    still blocked before they can become a success.
    """

    allowed_values = node_context.allowed_slot_values.get(slot_name, [])
    if not allowed_values:
        return True
    if slot_value not in allowed_values:
        return False
    if _has_slot_intent_mismatch(player_text, slot_name):
        return False
    return True


def _merge_postprocessing(
    slot_evidence_postprocessing: dict[str, Any],
    slot_repair_postprocessing: dict[str, Any],
) -> dict[str, Any]:
    slot_evidence_changed = bool(
        slot_evidence_postprocessing.get("generic_slot_evidence_applied")
        or slot_evidence_postprocessing.get("dropped_slot_evidence")
        or slot_evidence_postprocessing.get("intent_relevance_guard_applied")
        or slot_evidence_postprocessing.get("confidence_evidence_guard_applied")
    )
    slot_repair_changed = bool(slot_repair_postprocessing.get("slot_repair_applied"))
    if slot_evidence_changed and slot_repair_changed:
        return {
            **slot_evidence_postprocessing,
            **slot_repair_postprocessing,
        }
    if slot_evidence_changed:
        return {
            **slot_evidence_postprocessing,
            "slot_repair_applied": False,
        }
    return slot_repair_postprocessing


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
        "extracted_slots": output.extracted_slots,
        "slot_evidence_slots": [evidence.slot for evidence in output.slot_evidence],
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
