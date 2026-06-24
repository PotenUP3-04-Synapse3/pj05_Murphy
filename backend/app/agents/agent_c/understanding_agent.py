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
from typing import Any, Literal

from backend.app.agents.agent_c.llm_cost_estimator import build_model_usage_summary
from backend.app.agents.agent_c.understanding_llm_client import (
    UnderstandingLLMClient,
    UnderstandingLLMUnavailable,
    build_understanding_llm_client_from_settings,
    normalize_understanding_llm_result,
)
from backend.app.agents.agent_c.visit_purpose_classifier import classify_visit_purpose
from backend.app.schemas.game_turn import NodeContext, SlotEvidence, SocialContextCard, UnderstandingOutput
from backend.app.schemas.slot_policy import get_slot_policy
from backend.app.services.service_c.incivility_classifier import classify_incivility_rule
from backend.app.services.service_c.settings_service import AppSettings, get_settings

_LOGGER = logging.getLogger(__name__)

SceneNorm = Literal["general", "peer_smalltalk", "institutional_check", "service_recovery"]
RecommendedNPCMove = Literal[
    "continue",
    "acknowledge_then_progress",
    "acknowledge_and_retry_request",
    "playful_boundary",
    "firm_redirect",
    "service_repair",
    "clarify",
]


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
    "stay_location": {
        "hotel": (
            "hotel", "motel", "inn", "resort",
            "hyatt", "hilton", "marriott", "sheraton", "holiday inn", "westin",
            "wyndham", "ramada", "ritz", "four seasons", "plaza", "palace", "hostel"
        ),
        "friend_house": ("friend's house", "friend house", "with my friend", "my friend's place"),
        "family_house": ("family house", "with my family", "my uncle", "my aunt", "parents house"),
        "airbnb": ("airbnb", "rental apartment", "rental house"),
        "address": ("street", "st.", "avenue", "ave", "road", "rd.", "boulevard", "blvd", "drive", "lane"),
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
    "item_purpose": {
        "personal_recreation": ("personal use", "for myself", "for me", "recreation", "vacation", "enjoy"),
        "gift": ("gift", "present", "for my friend", "for my family"),
        "repair_part": ("repair", "fix", "replacement part", "spare part", "part for my"),
        "hobby_use": ("hobby", "collection", "collect", "craft", "fishing", "camera"),
        "sports_activity": ("sports", "sport", "golf", "tennis", "exercise", "activity"),
    },
    # B가 추가한 입국심사 압박 질문도 로컬 룰 모드에서 멈추지 않도록 대표 표현을 연결합니다.
    "long_stay_reason": {
        "tourism": ("tourism", "travel", "sightseeing", "visit places", "see new york"),
        "study": ("study", "school", "class", "course", "academy", "university"),
        "family_visit": ("family", "parents", "uncle", "aunt", "cousin", "relative"),
        "remote_work": ("remote work", "work remotely", "online work", "work online"),
        "long_vacation": ("long vacation", "long holiday", "take a break", "rest", "vacation"),
    },
    "hotel_reservation_status": {
        "has_reservation": ("yes", "reservation", "booked", "booking", "reserved", "i have a reservation"),
        "has_digital_confirmation": ("digital confirmation", "confirmation email", "booking app", "on my phone"),
        "has_address": ("hotel address", "address", "street", "avenue", "road"),
    },
    "hotel_choice_reason": {
        "location": ("location", "near", "close to", "convenient", "good area"),
        "price": ("price", "cheap", "affordable", "budget", "not expensive"),
        "reviews": ("reviews", "rating", "good review", "high rated", "stars"),
        "recommended": ("recommended", "recommendation", "friend told me", "family recommended"),
        "near_tourist_spots": ("near tourist", "near attractions", "near museum", "near times square", "sightseeing"),
    },
    "itinerary_status": {
        "has_itinerary": ("yes", "itinerary", "travel itinerary", "schedule", "planned itinerary"),
        "has_plans": ("plans", "i have plans", "planned", "plan to visit"),
        "has_list": ("list", "a list", "places list", "list of places"),
    },
    "first_visit_status": {
        "yes_first_time": ("yes", "first time", "my first visit", "first visit", "never been"),
        "no_visited_before": ("no", "visited before", "been here before", "second time", "third time", "not my first"),
    },
    "occupation": {
        "student": ("student", "university student", "college student", "school student"),
        "office_worker": ("office worker", "company employee", "employee", "work at a company"),
        "engineer": ("engineer", "developer", "programmer", "software engineer"),
        "designer": ("designer", "graphic designer", "product designer", "ui designer"),
        "teacher": ("teacher", "instructor", "professor", "teach"),
        "business_owner": ("business owner", "own a business", "self employed", "run a business"),
        "unemployed": ("unemployed", "no job", "between jobs", "not working"),
    },
    "cash_amount": {
        "under_10k": ("under 10000", "under 10,000", "under $10,000", "less than 10000", "less than 10,000"),
        "over_10k": ("over 10000", "over 10,000", "over $10,000", "more than 10000", "more than 10,000"),
        "zero": ("no cash", "zero cash", "i don't have cash", "only card", "none"),
        "specific_amount": ("dollars", "usd", "$", "cash", "hundred", "thousand"),
    },
    "payment_source": {
        "myself": ("myself", "by myself", "i paid", "my money", "from my savings"),
        "parents": ("parents", "my parents", "mother", "father", "mom", "dad"),
        "company": ("company", "my company", "employer", "work paid", "business trip"),
        "sponsor": ("sponsor", "sponsored", "scholarship", "host paid"),
        "family": ("family", "my family", "relative", "uncle", "aunt"),
    },
    "denied_entry_status": {
        "never_denied": ("no", "never", "never denied", "never been denied", "no denial", "no, never", "not denied"),
        "has_denial_history": ("denied before", "was denied", "entry denied", "refused entry", "once denied"),
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
    "stay_location": (
        "i said",
        "i told you",
        "already told",
        "already said",
        "as i said",
    ),
}

FLIGHT_SMALLTALK_MIN_FREE_RESPONSE_CONFIDENCE = 0.72
FLIGHT_SMALLTALK_FILLER_ONLY_PHRASES = {
    "uh",
    "um",
    "uhm",
    "hmm",
    "hm",
    "er",
    "ah",
    "what",
    "pardon",
    "sorry",
}
FLIGHT_SMALLTALK_LOW_CONTENT_NON_ANSWER_PHRASES = {
    "fine",
    "fine fine",
    "fine fine fine",
    "whatever",
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
                output = _attach_incivility_classification(output, player_text)
                output = _attach_social_context(output, player_text, node_context)
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
            passport_refusal = _repair_passport_submission_refusal_output(
                output,
                player_text,
                node_context,
            )
            passport_refusal_postprocessing: dict[str, Any] = {}
            if passport_refusal is not None:
                output, passport_refusal_postprocessing = passport_refusal
            output, slot_repair_postprocessing = _repair_missing_allowed_slots(
                output,
                player_text,
                node_context,
            )
            # If any required slot is open, align intent_success with intent_satisfied
            has_open_required = any(get_slot_policy(slot) == "open" for slot in node_context.required_slots)
            if has_open_required:
                output = output.model_copy(update={"intent_success": output.intent_satisfied})

            output = _attach_incivility_classification(output, player_text)
            output = _attach_social_context(output, player_text, node_context)
            postprocessing = _merge_postprocessing(
                slot_evidence_postprocessing,
                slot_repair_postprocessing,
                passport_refusal_postprocessing,
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
        output = _attach_incivility_classification(output, player_text)
        output = _attach_social_context(output, player_text, node_context)
        self.last_trace = _build_rule_trace(output)
        return output

    def _analyze_with_llm(
        self,
        player_text: str,
        node_context: NodeContext,
    ) -> tuple[UnderstandingOutput, dict[str, Any]]:
        result = normalize_understanding_llm_result(
            self._get_llm_client().analyze(
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
            passport_refusal = _passport_submission_refusal_output(player_text, node_context)
            if passport_refusal is not None:
                return passport_refusal
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
                intent_satisfied=False,
                judgment_reason="Risk keyword found in player answer.",
            )

        if _is_flight_smalltalk_diagnostic_node(node_context):
            return _flight_smalltalk_diagnostic_output(player_text, node_context)

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
                    intent_satisfied=True,
                    judgment_reason="The stay duration is clear.",
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
                intent_satisfied=False,
                judgment_reason="The player answer did not clearly state a stay duration.",
            )

        # 방문 목적 분류기는 해당 노드가 visit_purpose 슬롯을 요구할 때만 성공으로 사용합니다.
        if "visit_purpose" in node_context.required_slots and visit_purpose is not None:
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
                intent_satisfied=True,
                judgment_reason="The purpose is clear.",
            )

        if _is_low_content_non_answer(player_text) and node_context.required_slots:
            return UnderstandingOutput(
                intent=_required_intent_for_slot(node_context, primary_required_slot or "unknown"),
                intent_success=False,
                confidence=0.34,
                meaning_summary_kr="The player gave a thin everyday response that did not answer the required slot.",
                emotion="nervous",
                answer_relevance=_missing_required_slot_answer_relevance(player_text, node_context),
                ambiguity_type="low_content_non_answer",
                risk_delta=0,
                risk_reason="No risk expression was found.",
                risk_tags=[],
                extracted_slots={},
                missing_slots=node_context.required_slots,
                needs_clarification=True,
                intent_satisfied=False,
                judgment_reason="The player gave a low-content social response instead of the required answer.",
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
                intent_satisfied=True,
                judgment_reason=f"The required slot {slot_name} is clear.",
            )

        return UnderstandingOutput(
            intent=_required_intent_for_slot(node_context, primary_required_slot or "unknown"),
            intent_success=False,
            confidence=0.55,
            meaning_summary_kr="The player answer did not clearly fill the required slot.",
            emotion="nervous",
            answer_relevance=_missing_required_slot_answer_relevance(player_text, node_context),
            ambiguity_type="unclear_required_slot",
            risk_delta=0,
            risk_reason="No risk expression was found.",
            risk_tags=[],
            extracted_slots={},
            missing_slots=node_context.required_slots,
            needs_clarification=True,
            intent_satisfied=False,
            judgment_reason="The player answer did not clearly fill the required slot.",
        )


def _reject_forbidden_llm_keys(result: dict[str, object]) -> None:
    forbidden_keys = FORBIDDEN_UNDERSTANDING_LLM_KEYS.intersection(result)
    if forbidden_keys:
        joined_keys = ", ".join(sorted(forbidden_keys))
        raise UnderstandingLLMUnavailable(f"Understanding LLM returned forbidden keys: {joined_keys}")


def _attach_incivility_classification(
    output: UnderstandingOutput,
    player_text: str,
) -> UnderstandingOutput:
    """Attach deterministic incivility evidence to an Understanding result.

    초보자용 설명:
    LLM mode에서도 욕설 신호는 마지막에 규칙 기반으로 다시 붙입니다. 이렇게 하면
    LLM이 `incivility`를 빼먹거나 낮게 판단해도, 강한 욕설/모욕 신호가 A와 B로
    전달되는 길이 끊기지 않습니다.
    """

    rule_incivility = classify_incivility_rule(player_text)
    if output.incivility is not None and output.incivility.tier > rule_incivility.tier:
        return output

    return output.model_copy(update={"incivility": rule_incivility})


def _attach_social_context(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> UnderstandingOutput:
    """Attach a soft social-pragmatics card without changing branch authority."""

    return output.model_copy(
        update={
            "social_context": _build_social_context_card(
                output,
                player_text,
                node_context,
            )
        }
    )


def _build_social_context_card(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> SocialContextCard:
    scene_norm = _scene_norm_for_node(node_context.node_id)
    pending_obligation = _pending_social_obligation(node_context)

    if _is_passport_submission_node(node_context) and (
        output.extracted_slots.get("refuse_submission") == "true"
        or _looks_like_passport_submission_refusal(player_text)
    ):
        return SocialContextCard(
            scene_norm=scene_norm,
            conversation_move="refusal",
            prior_turn_relation="answered",
            social_pattern="none",
            pending_social_obligation=pending_obligation,
            obligation_status="addressed",
            engagement_quality="useful",
            recommended_npc_move="firm_redirect",
            pragmatics_confidence=0.93,
            reason="The player clearly refused the institutional passport-submission request.",
        )

    if _is_flight_smalltalk_diagnostic_node(node_context) and _flight_pen_obligation_addressed(player_text):
        return SocialContextCard(
            scene_norm=scene_norm,
            conversation_move="refusal" if _looks_like_refusal(player_text) else "meaningful_answer",
            prior_turn_relation="answered",
            social_pattern="none",
            pending_social_obligation="seatmate_pen_request",
            obligation_status="addressed",
            engagement_quality="useful",
            recommended_npc_move="acknowledge_then_progress",
            pragmatics_confidence=0.9,
            reason="The player addressed the seatmate's pen request.",
        )

    if _is_greeting_only(player_text):
        return SocialContextCard(
            scene_norm=scene_norm,
            conversation_move="greeting_only",
            prior_turn_relation="non_answer",
            social_pattern="greeting",
            pending_social_obligation=pending_obligation,
            obligation_status="open" if pending_obligation else "none",
            engagement_quality="thin",
            recommended_npc_move=_repair_move_for_scene(scene_norm),
            pragmatics_confidence=0.86,
            reason="The player greeted but did not answer the active request.",
        )

    if _is_clarification_request_only(player_text):
        return SocialContextCard(
            scene_norm=scene_norm,
            conversation_move="clarification_request",
            prior_turn_relation="asked_to_clarify",
            social_pattern="clarification_request",
            pending_social_obligation=pending_obligation,
            obligation_status="unclear" if pending_obligation else "none",
            engagement_quality="thin",
            recommended_npc_move="clarify",
            pragmatics_confidence=0.84,
            reason="The player asked for clarification instead of answering the active request.",
        )

    if _is_low_content_non_answer(player_text):
        return SocialContextCard(
            scene_norm=scene_norm,
            conversation_move="low_content_non_answer",
            prior_turn_relation="non_answer",
            social_pattern="low_content_non_answer",
            pending_social_obligation=pending_obligation,
            obligation_status="ignored" if pending_obligation else "none",
            engagement_quality="thin",
            recommended_npc_move=_repair_move_for_scene(scene_norm),
            pragmatics_confidence=0.78,
            reason="The player gave a thin everyday response that did not answer the active request.",
        )

    if _is_filler_only(player_text):
        return SocialContextCard(
            scene_norm=scene_norm,
            conversation_move="filler",
            prior_turn_relation="non_answer",
            social_pattern="filler",
            pending_social_obligation=pending_obligation,
            obligation_status="unclear" if pending_obligation else "none",
            engagement_quality="thin",
            recommended_npc_move="clarify",
            pragmatics_confidence=0.74,
            reason="The player gave only filler or hesitation.",
        )

    if output.answer_relevance == "off_topic":
        return SocialContextCard(
            scene_norm=scene_norm,
            conversation_move="off_topic",
            prior_turn_relation="ignored",
            social_pattern="off_topic",
            pending_social_obligation=pending_obligation,
            obligation_status="ignored" if pending_obligation else "none",
            engagement_quality="stalled",
            recommended_npc_move=_repair_move_for_scene(scene_norm),
            pragmatics_confidence=0.76,
            reason="The player did not address the active conversational obligation.",
        )

    if output.intent_success or output.intent_satisfied:
        return SocialContextCard(
            scene_norm=scene_norm,
            conversation_move="meaningful_answer",
            prior_turn_relation="answered",
            social_pattern="none",
            pending_social_obligation=pending_obligation,
            obligation_status="addressed" if pending_obligation else "none",
            engagement_quality="useful",
            recommended_npc_move="continue",
            pragmatics_confidence=0.82,
            reason="The player gave usable conversational content.",
        )

    return SocialContextCard(
        scene_norm=scene_norm,
        conversation_move="unknown",
        prior_turn_relation="unknown",
        social_pattern="none",
        pending_social_obligation=pending_obligation,
        obligation_status="unclear" if pending_obligation else "none",
        engagement_quality="unclear",
        recommended_npc_move="clarify",
        pragmatics_confidence=0.35,
        reason="The player's social move was unclear.",
    )


def _scene_norm_for_node(node_id: str) -> SceneNorm:
    if node_id.startswith("FLIGHT_"):
        return "peer_smalltalk"
    if node_id.startswith("IMM_"):
        return "institutional_check"
    if node_id.startswith("BAG_"):
        return "service_recovery"
    return "general"


def _pending_social_obligation(node_context: NodeContext) -> str | None:
    if _is_flight_smalltalk_diagnostic_node(node_context):
        return "seatmate_pen_request"
    if _has_customs_hold_contents_obligation(node_context):
        return "check_suitcase_contents"
    if node_context.npc_question_goal:
        return f"answer_{node_context.npc_question_goal}"
    return None


def _has_customs_hold_contents_obligation(node_context: NodeContext) -> bool:
    return (
        node_context.node_id.startswith("BAG_005")
        or node_context.npc_question_goal == "customs_hold_explanation_before_unlock"
        or "customs_hold_acknowledgement" in node_context.required_slots
    )


def _missing_required_slot_answer_relevance(
    player_text: str,
    node_context: NodeContext,
) -> Literal["partially_related", "off_topic"]:
    if _scene_norm_for_node(node_context.node_id) == "service_recovery" and node_context.required_slots:
        return "off_topic"
    _ = player_text
    return "partially_related"


def _repair_move_for_scene(scene_norm: SceneNorm) -> RecommendedNPCMove:
    if scene_norm == "peer_smalltalk":
        return "acknowledge_and_retry_request"
    if scene_norm == "institutional_check":
        return "firm_redirect"
    if scene_norm == "service_recovery":
        return "service_repair"
    return "clarify"


def _is_greeting_only(player_text: str) -> bool:
    normalized = _normalize_for_keyword_match(player_text)
    words = re.findall(r"[a-z0-9']+", normalized)
    if not words:
        return False
    greeting_words = {"hello", "hi", "hey", "hiya"}
    soft_fillers = {"there", "again", "um", "uh", "uhm", "ah"}
    return any(word in greeting_words for word in words) and all(
        word in greeting_words or word in soft_fillers for word in words
    )


def _is_filler_only(player_text: str) -> bool:
    normalized = _normalize_for_keyword_match(player_text)
    words = re.findall(r"[a-z0-9']+", normalized)
    return not words or " ".join(words) in FLIGHT_SMALLTALK_FILLER_ONLY_PHRASES


def _is_clarification_request_only(player_text: str) -> bool:
    normalized = _normalize_for_keyword_match(player_text)
    words = re.findall(r"[a-z0-9']+", normalized)
    if not words:
        return False
    clarification_words = {"what", "pardon", "sorry", "huh"}
    soft_words = {"again", "please", "me"}
    return any(word in clarification_words for word in words) and all(
        word in clarification_words or word in soft_words for word in words
    )


def _is_low_content_non_answer(player_text: str) -> bool:
    normalized = _normalize_for_keyword_match(player_text)
    words = re.findall(r"[a-z0-9']+", normalized)
    if not words:
        return False
    joined = " ".join(words)
    if joined in FLIGHT_SMALLTALK_LOW_CONTENT_NON_ANSWER_PHRASES:
        return True
    if len(words) <= 4:
        everyday_words = {
            "okay",
            "ok",
            "alright",
            "hello",
            "hi",
            "hey",
            "fine",
            "yeah",
            "yes",
            "no",
            "um",
            "uh",
            "uhm",
            "ah",
        }
        has_greeting = any(word in {"hello", "hi", "hey"} for word in words)
        return has_greeting and all(word in everyday_words for word in words)
    return False


def _flight_pen_obligation_addressed(player_text: str) -> bool:
    normalized = _normalize_for_keyword_match(player_text)
    if not normalized:
        return False
    tokens = set(normalized.split())
    if tokens.intersection({"sure", "no", "nope", "cant", "can't"}):
        return True
    addressed_markers = (
        "of course",
        "here you go",
        "here you are",
        "take it",
        "use this",
        "you can use",
        "no problem",
        "sorry no",
        "sorry i need",
        "i need it",
    )
    return any(marker in normalized for marker in addressed_markers)


def _looks_like_refusal(player_text: str) -> bool:
    normalized = _normalize_for_keyword_match(player_text)
    tokens = set(normalized.split())
    if tokens.intersection({"no", "nope", "cant", "can't"}):
        return True
    refusal_markers = ("sorry no", "i need it")
    return any(marker in normalized for marker in refusal_markers)


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

    # 자유형 주소는 "address"라는 단어가 없어도 번지+도로명 패턴이면 주소 답변으로 봅니다.
    if slot_name == "stay_location" and "address" in allowed_values and _looks_like_freeform_address(player_text):
        return "address"

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
    ]
    for candidate in candidates:
        normalized_candidate = _normalize_for_keyword_match(candidate)
        if normalized_candidate and normalized_candidate in normalized_text:
            return candidate
    return None


def _normalize_for_keyword_match(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _looks_like_freeform_address(player_text: str) -> bool:
    """번지와 도로명이 같이 나온 자유형 주소 발화를 감지합니다.

    초보자용 설명:
    플레이어가 "address"라고 직접 말하지 않아도 "123 Main Street"처럼 숫자와
    도로명 단어가 함께 있으면 입국심사관 질문의 `stay_location=address`로
    처리해야 합니다. 이 함수는 그 최소 패턴만 안전하게 확인합니다.
    """

    normalized = _normalize_for_keyword_match(player_text)
    street_words = (
        "street",
        "st",
        "avenue",
        "ave",
        "road",
        "rd",
        "boulevard",
        "blvd",
        "drive",
        "dr",
        "lane",
        "ln",
        "way",
        "place",
        "pl",
    )
    has_number = re.search(r"\b\d{1,6}[a-z]?\b", normalized) is not None
    has_street_word = any(re.search(rf"\b{re.escape(word)}\b", normalized) for word in street_words)
    return has_number and has_street_word


def _visit_purpose_summary(visit_purpose: str) -> str:
    if visit_purpose == "tourism":
        return "The player said they are visiting for tourism."
    return f"The player clearly stated a visit purpose: {visit_purpose}."


def _stay_duration_summary(stay_duration: str) -> str:
    return f"The player clearly stated a stay duration: {stay_duration}."


def _repair_confidence(slot_name: str) -> float:
    """규칙 기반 slot repair가 부여할 confidence를 슬롯별로 정합니다."""

    if slot_name == "visit_purpose":
        return 0.94
    if slot_name == "stay_duration":
        return 0.92
    return 0.91


def _repair_missing_allowed_slots(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> tuple[UnderstandingOutput, dict[str, Any]]:
    no_repair = {"slot_repair_applied": False}
    if _is_flight_smalltalk_diagnostic_node(node_context):
        return output, no_repair

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

    generic_slot = _extract_generic_required_slot(player_text, node_context)
    if generic_slot is not None:
        slot_name, slot_value = generic_slot
        if extracted_slots.get(slot_name) is None:
            extracted_slots[slot_name] = slot_value
            repairs.append(
                {
                    "source": "rule_generic_slot_classifier",
                    "slot": slot_name,
                    "value": slot_value,
                    "summary": f"The player clearly answered the required slot: {slot_name}.",
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
                confidence=_repair_confidence(repair["slot"]),
                evidence_text=repair["value"],
            )
            for repair in repairs
        ],
    ]
    repaired = output.model_copy(
        update={
            "intent": _required_intent_for_slot(node_context, primary_repair["slot"]),
            "intent_success": len(missing_slots) == 0,
            "intent_satisfied": len(missing_slots) == 0,
            "confidence": max(
                output.confidence,
                _repair_confidence(primary_repair["slot"]),
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
    if _is_flight_smalltalk_diagnostic_node(node_context):
        return _normalize_flight_smalltalk_diagnostic_output(output, player_text, node_context)

    passport_handover = _repair_passport_handover_output(
        output,
        player_text,
        node_context,
    )
    if passport_handover is not None:
        return passport_handover

    first_visit = _repair_first_visit_output(
        output,
        player_text,
        node_context,
    )
    if first_visit is not None:
        return first_visit

    final_clearance_ack = _repair_final_clearance_acknowledgement_output(
        output,
        player_text,
        node_context,
    )
    if final_clearance_ack is not None:
        return final_clearance_ack

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

    # slot-evidence-first: LLM이 직접 준 extracted_slots는 신뢰하지 않고,
    # 현재 노드에 맞게 검증된 evidence만 최종 슬롯으로 승격합니다.
    extracted_slots: dict[str, str] = {}
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
    missing_required_slot_evidence = bool(missing_slots and output.intent_success)
    answer_relevance = "off_topic" if intent_mismatch else output.answer_relevance
    confidence = _guard_confidence_for_evidence(
        output.confidence,
        intent_mismatch=intent_mismatch,
        weak_required_slot_evidence=weak_required_slot_evidence or missing_required_slot_evidence,
    )
    confidence_guard_applied = confidence != output.confidence
    applied = bool(accepted_evidence)
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


def _repair_passport_handover_output(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> tuple[UnderstandingOutput, dict[str, Any]] | None:
    """Treat deictic handover phrases as passport submission in passport context."""

    slot_name = "passport_submission_status"
    if slot_name not in node_context.required_slots:
        return None
    if _has_risk_expression(player_text, node_context):
        return None
    if not _looks_like_passport_handover(player_text):
        return None

    evidence = SlotEvidence(
        slot=slot_name,
        value="submitted",
        confidence=0.96,
        evidence_text=player_text.strip() or "Here you go.",
    )
    normalized = output.model_copy(
        update={
            "intent": _required_intent_for_slot(node_context, slot_name),
            "intent_success": True,
            "intent_satisfied": True,
            "confidence": max(output.confidence, 0.94),
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "slot_evidence": [evidence],
            "extracted_slots": {slot_name: "submitted"},
            "missing_slots": [],
            "needs_clarification": False,
            "risk_delta": 0,
            "risk_reason": "Passport handover phrase recognized in passport-submission context.",
            "risk_tags": [],
            "judgment_reason": "The player handed over the passport with a short deictic phrase.",
        }
    )
    return normalized, {
        "generic_slot_evidence_applied": True,
        "passport_handover_repair_applied": True,
        "intent_relevance_guard_applied": False,
        "confidence_evidence_guard_applied": normalized.confidence != output.confidence,
        "weak_required_slot_evidence": False,
        "accepted_slot_evidence": [slot_name],
        "dropped_slot_evidence": [],
    }


def _repair_passport_submission_refusal_output(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> tuple[UnderstandingOutput, dict[str, Any]] | None:
    """Promote explicit passport-submission refusal into critical evidence."""

    normalized = _passport_submission_refusal_output(player_text, node_context, base_output=output)
    if normalized is None:
        return None
    return normalized, {
        "generic_slot_evidence_applied": True,
        "passport_refusal_repair_applied": True,
        "intent_relevance_guard_applied": False,
        "confidence_evidence_guard_applied": normalized.confidence != output.confidence,
        "weak_required_slot_evidence": False,
        "accepted_slot_evidence": ["refuse_submission"],
        "dropped_slot_evidence": [],
    }


def _passport_submission_refusal_output(
    player_text: str,
    node_context: NodeContext,
    *,
    base_output: UnderstandingOutput | None = None,
) -> UnderstandingOutput | None:
    if not _is_passport_submission_node(node_context):
        return None
    if not _looks_like_passport_submission_refusal(player_text):
        return None

    base_confidence = base_output.confidence if base_output is not None else 0.0
    base_risk_delta = base_output.risk_delta if base_output is not None else 0
    base_risk_tags = list(base_output.risk_tags) if base_output is not None else []
    if "refuse_submission" not in base_risk_tags:
        base_risk_tags.append("refuse_submission")

    return UnderstandingOutput(
        intent=_required_intent_for_slot(node_context, "passport_submission_status"),
        intent_success=False,
        confidence=max(base_confidence, 0.9),
        meaning_summary_kr="The player explicitly refused to present the passport.",
        emotion=base_output.emotion if base_output is not None else "calm",
        answer_relevance="on_topic",
        ambiguity_type="explicit_refusal",
        risk_delta=max(base_risk_delta, 20),
        risk_reason="The player refused a required passport submission request.",
        risk_tags=base_risk_tags,
        slot_evidence=[
            SlotEvidence(
                slot="refuse_submission",
                value="true",
                confidence=0.95,
                evidence_text=player_text.strip() or "no",
            )
        ],
        extracted_slots={"refuse_submission": "true"},
        missing_slots=[],
        needs_clarification=False,
        intent_satisfied=False,
        judgment_reason="The player gave a clear refusal, not an unclear answer.",
        incivility=base_output.incivility if base_output is not None else None,
    )


def _is_passport_submission_node(node_context: NodeContext) -> bool:
    return (
        "passport_submission_status" in node_context.required_slots
        and "refuse_submission" in node_context.critical_slots
    )


def _looks_like_passport_submission_refusal(player_text: str) -> bool:
    normalized = _normalize_for_keyword_match(player_text)
    tokens = set(normalized.split())
    if tokens.intersection({"no", "nope"}):
        return True
    refusal_markers = (
        "answer is no",
        "the answer is no",
        "i said no",
        "i already said no",
        "i refuse",
        "refuse to",
        "will not",
        "wont",
        "won't",
        "do not want to",
        "dont want to",
        "don't want to",
        "not giving",
        "not show",
        "not presenting",
        "not present",
    )
    return any(marker in normalized for marker in refusal_markers)


def _looks_like_passport_handover(player_text: str) -> bool:
    normalized = _normalize_for_keyword_match(player_text)
    handover_markers = (
        "here you go",
        "here you are",
        "here it is",
        "there you go",
        "take it",
        "my passport",
        "here is my passport",
        "heres my passport",
    )
    if any(marker in normalized for marker in handover_markers):
        return True
    return "passport" in normalized.split() and "here" in normalized.split()


def _repair_first_visit_output(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> tuple[UnderstandingOutput, dict[str, Any]] | None:
    """Recover first-visit answers when the LLM misses the enum slot."""

    slot_name = "first_visit_status"
    if slot_name not in node_context.required_slots:
        return None
    if _has_risk_expression(player_text, node_context):
        return None

    slot_value = _classify_first_visit_status(player_text)
    if slot_value is None:
        return None

    evidence = SlotEvidence(
        slot=slot_name,
        value=slot_value,
        confidence=0.93,
        evidence_text=player_text.strip(),
    )
    normalized = output.model_copy(
        update={
            "intent": _required_intent_for_slot(node_context, slot_name),
            "intent_success": True,
            "intent_satisfied": True,
            "confidence": max(output.confidence, 0.91),
            "meaning_summary_kr": "The player answered whether this is their first U.S. visit.",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "slot_evidence": [evidence],
            "extracted_slots": {slot_name: slot_value},
            "missing_slots": [],
            "needs_clarification": False,
            "risk_delta": 0,
            "risk_reason": "First-visit answer recognized with deterministic slot repair.",
            "risk_tags": [],
            "judgment_reason": "The player gave a yes/no first-visit answer with prior-visit wording.",
        }
    )
    return normalized, {
        "generic_slot_evidence_applied": True,
        "first_visit_repair_applied": True,
        "intent_relevance_guard_applied": False,
        "confidence_evidence_guard_applied": normalized.confidence != output.confidence,
        "weak_required_slot_evidence": False,
        "accepted_slot_evidence": [slot_name],
        "dropped_slot_evidence": [],
    }


def _classify_first_visit_status(player_text: str) -> str | None:
    normalized = _normalize_for_keyword_match(player_text)
    tokens = set(normalized.split())
    prior_visit_markers = (
        "visited before",
        "been here before",
        "i have been here",
        "ive been here",
        "i ve been here",
        "been here quite",
        "been here a lot",
        "been here quite a lot",
        "quite a lot",
        "quite often",
        "visit united states quite often",
        "visited united states",
        "came here before",
        "been to the united states",
        "been to america",
        "not my first",
        "not first",
        "second time",
        "third time",
    )
    first_time_markers = (
        "yes",
        "first time",
        "first visit",
        "my first",
        "never been",
        "never visited",
    )
    if any(marker in normalized for marker in prior_visit_markers):
        return "no_visited_before"
    if "no" in tokens or "nope" in tokens:
        return "no_visited_before"
    if any(marker in normalized for marker in first_time_markers):
        return "yes_first_time"
    return None


def _repair_final_clearance_acknowledgement_output(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> tuple[UnderstandingOutput, dict[str, Any]] | None:
    """Accept short acknowledgements and "good to go" checks at clearance."""

    slot_name = "immigration_transition_acknowledgement"
    if slot_name not in node_context.required_slots:
        return None
    if _has_risk_expression(player_text, node_context):
        return None

    slot_value = _classify_final_clearance_acknowledgement(player_text)
    if slot_value is None:
        return None

    evidence = SlotEvidence(
        slot=slot_name,
        value=slot_value,
        confidence=0.93,
        evidence_text=player_text.strip(),
    )
    normalized = output.model_copy(
        update={
            "intent": _required_intent_for_slot(node_context, slot_name),
            "intent_success": True,
            "intent_satisfied": True,
            "confidence": max(output.confidence, 0.91),
            "meaning_summary_kr": "The player acknowledged the immigration clearance.",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "slot_evidence": [evidence],
            "extracted_slots": {slot_name: slot_value},
            "missing_slots": [],
            "needs_clarification": False,
            "risk_delta": 0,
            "risk_reason": "Clearance acknowledgement recognized with deterministic slot repair.",
            "risk_tags": [],
            "judgment_reason": "The player acknowledged or confirmed they can proceed after clearance.",
        }
    )
    return normalized, {
        "generic_slot_evidence_applied": True,
        "final_clearance_ack_repair_applied": True,
        "intent_relevance_guard_applied": False,
        "confidence_evidence_guard_applied": normalized.confidence != output.confidence,
        "weak_required_slot_evidence": False,
        "accepted_slot_evidence": [slot_name],
        "dropped_slot_evidence": [],
    }


def _classify_final_clearance_acknowledgement(player_text: str) -> str | None:
    normalized = _normalize_for_keyword_match(player_text)
    tokens = set(normalized.split())
    if _contains_any(normalized, ("thank", "thanks", "thank you")):
        return "thanked_officer"
    if _contains_any(
        normalized,
        (
            "good to go",
            "go right now",
            "go now",
            "can i go",
            "may i go",
            "am i cleared",
            "baggage claim",
        ),
    ):
        return "ready_for_baggage_claim"
    if tokens.intersection({"okay", "ok", "good", "alright", "understood"}):
        return "acknowledged"
    if _contains_any(normalized, ("all right", "i understand", "got it", "you are cleared")):
        return "acknowledged"
    return None


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


def _is_flight_smalltalk_diagnostic_node(node_context: NodeContext) -> bool:
    """기내 스몰토크 단일 진단 노드인지 확인합니다.

    초보자용 설명:
    이 노드는 과거 펜 요청 시나리오에서 쓰던 `polite_response` 슬롯이 아직
    데이터에 남아 있지만, Alpha 진단 플로우에서는 그 슬롯을 진행 조건으로
    쓰지 않습니다. 그래서 C는 이 노드를 슬롯 채점 노드가 아니라 자유 발화
    진단 노드로 다룹니다.
    """

    return (
        node_context.node_id == "FLIGHT_A_001_SEATMATE_SMALLTALK"
        and node_context.npc_question_goal == "estimate_user_travel_speaking_level"
    )


def _flight_smalltalk_diagnostic_output(
    player_text: str,
    node_context: NodeContext,
) -> UnderstandingOutput:
    """rule 모드에서 기내 스몰토크 진단용 Understanding 결과를 만듭니다."""

    free_response = _flight_smalltalk_free_response(player_text, node_context)
    return UnderstandingOutput(
        intent=node_context.npc_question_goal,
        intent_success=free_response["intent_success"],
        confidence=free_response["confidence"],
        meaning_summary_kr="The player gave a free-form answer for the flight speaking diagnostic.",
        emotion="calm",
        answer_relevance=free_response["answer_relevance"],
        ambiguity_type=free_response["ambiguity_type"],
        risk_delta=0,
        risk_reason="No immigration risk expression was found.",
        risk_tags=[],
        extracted_slots={},
        missing_slots=[],
        needs_clarification=free_response["needs_clarification"],
        intent_satisfied=free_response["intent_success"],
        judgment_reason=free_response["judgment_reason"],
    )


def _normalize_flight_smalltalk_diagnostic_output(
    output: UnderstandingOutput,
    player_text: str,
    node_context: NodeContext,
) -> tuple[UnderstandingOutput, dict[str, Any]]:
    """LLM 결과에서 진단 노드의 레거시 슬롯 흔적을 제거합니다.

    초보자용 설명:
    LLM이 `polite_response`처럼 유효해 보이는 슬롯 값을 반환해도, 현재 노드는
    레벨 진단용 self-loop입니다. C는 B/A가 그 값을 진행 조건이나 고정 대사
    근거로 오해하지 않도록 slot evidence와 extracted slot을 비워서 넘깁니다.
    """

    free_response = _flight_smalltalk_free_response(player_text, node_context)
    intent_mismatch = _has_required_intent_mismatch(player_text, node_context)
    answer_relevance = free_response["answer_relevance"]
    confidence = (
        max(output.confidence, free_response["confidence"])
        if free_response["intent_success"]
        else min(output.confidence, free_response["confidence"])
    )
    normalized = output.model_copy(
        update={
            "intent": node_context.npc_question_goal,
            "intent_success": free_response["intent_success"],
            "confidence": confidence,
            "answer_relevance": answer_relevance,
            "ambiguity_type": free_response["ambiguity_type"],
            "slot_evidence": [],
            "extracted_slots": {},
            "missing_slots": [],
            "needs_clarification": free_response["needs_clarification"],
            "intent_satisfied": free_response["intent_success"],
            "judgment_reason": free_response["judgment_reason"],
        }
    )
    return normalized, {
        "generic_slot_evidence_applied": False,
        "flight_smalltalk_diagnostic_slot_neutralized": True,
        "flight_smalltalk_free_response_applied": free_response["intent_success"],
        "intent_relevance_guard_applied": intent_mismatch,
        "confidence_evidence_guard_applied": confidence != output.confidence,
        "weak_required_slot_evidence": False,
        "accepted_slot_evidence": [],
        "dropped_slot_evidence": [evidence.slot for evidence in output.slot_evidence],
    }


def _flight_smalltalk_free_response(player_text: str, node_context: NodeContext) -> dict[str, Any]:
    """Return C's single-node free smalltalk understanding signal.

    Flight smalltalk is a diagnostic self-loop, not a slot gate.  The old node
    data still mentions `polite_response`, but after the first NPC line Arabella
    can ask natural follow-ups.  C therefore judges whether the player produced
    a meaningful conversational response and leaves politeness/branch policy to
    Developer B.
    """

    normalized_text = _normalize_for_keyword_match(player_text)
    words = re.findall(r"[a-z0-9']+", normalized_text)
    if _is_greeting_only(player_text):
        return {
            "intent_success": False,
            "confidence": 0.48,
            "answer_relevance": "partially_related",
            "ambiguity_type": "social_obligation_unanswered",
            "needs_clarification": True,
            "judgment_reason": "The player only greeted and did not answer the seatmate's pending request.",
        }

    if _is_clarification_request_only(player_text):
        return {
            "intent_success": False,
            "confidence": 0.36,
            "answer_relevance": "partially_related",
            "ambiguity_type": "clarification_request",
            "needs_clarification": True,
            "judgment_reason": "The player asked for clarification instead of answering the seatmate's pending request.",
        }

    if _is_low_content_non_answer(player_text):
        return {
            "intent_success": False,
            "confidence": 0.34,
            "answer_relevance": "partially_related",
            "ambiguity_type": "low_content_non_answer",
            "needs_clarification": True,
            "judgment_reason": "The player gave a thin everyday response instead of answering the seatmate's pending request.",
        }

    if not words or " ".join(words) in FLIGHT_SMALLTALK_FILLER_ONLY_PHRASES:
        return {
            "intent_success": False,
            "confidence": 0.22,
            "answer_relevance": "partially_related",
            "ambiguity_type": "too_short_for_diagnostic",
            "needs_clarification": True,
            "judgment_reason": "The flight smalltalk response was too short to evaluate.",
        }

    if _has_required_intent_mismatch(player_text, node_context):
        return {
            "intent_success": False,
            "confidence": 0.22,
            "answer_relevance": "off_topic",
            "ambiguity_type": "off_topic_response",
            "needs_clarification": False,
            "judgment_reason": "The response matched a known off-topic idiom for the flight prompt.",
        }

    confidence = 0.78 if len(words) >= 3 else FLIGHT_SMALLTALK_MIN_FREE_RESPONSE_CONFIDENCE
    return {
        "intent_success": True,
        "confidence": confidence,
        "answer_relevance": "on_topic",
        "ambiguity_type": "diagnostic_free_speech",
        "needs_clarification": False,
        "judgment_reason": "The player gave a meaningful free smalltalk response.",
    }


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
        intent_satisfied=False,
        judgment_reason="The player used an off-topic idiom instead of answering the current request.",
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

    if get_slot_policy(evidence.slot) == "open":
        return True

    allowed_values = node_context.allowed_slot_values.get(evidence.slot, [])
    if not allowed_values:
        return True
    if _match_alpha_allowed_slot_value(player_text, evidence.slot, [evidence.value]) == evidence.value:
        return True

    if evidence.confidence >= 0.85 and _is_evidence_text_grounded(player_text, evidence.evidence_text):
        return True

    normalized_value = _normalize_for_keyword_match(evidence.value)
    normalized_text = _normalize_for_keyword_match(player_text)
    return bool(normalized_value and normalized_value in normalized_text)


def _is_evidence_text_grounded(player_text: str, evidence_text: str) -> bool:
    """LLM이 제시한 evidence_text가 실제 사용자 발화에 있는지 확인합니다.

    Beginner guide:
    slot-evidence-first 구조에서는 LLM의 정규화 값보다 "무슨 말을 근거로
    그렇게 봤는가"가 더 중요합니다.  예를 들어 사용자가 "museums"라고 말했고
    LLM이 `visit_purpose=tourism`으로 정규화했다면, 값 `tourism`은 원문에 없을 수
    있습니다.  대신 evidence_text가 원문에 정확히 있으면 C가 현재 노드의
    allowed value 검증과 함께 받아들입니다.
    """

    normalized_evidence = _normalize_for_keyword_match(evidence_text)
    normalized_text = _normalize_for_keyword_match(player_text)
    return bool(normalized_evidence and normalized_evidence in normalized_text)


def _is_supported_extracted_slot_value(
    *,
    slot_name: str,
    slot_value: str,
    player_text: str,
    node_context: NodeContext,
) -> bool:
    """slot_evidence.value가 현재 노드의 허용 범위 안에 있는지 확인합니다.

    Beginner guide:
    이제 LLM이 직접 준 `extracted_slots`는 쓰지 않습니다.  하지만
    `slot_evidence.value`도 B가 정의한 enum 값과 맞아야 합니다.  이 함수는
    evidence가 현재 노드의 allowed value 안에 있는지 확인하고, 알려진 off-topic
    표현이 enum success로 승격되지 않게 막습니다.
    """

    if get_slot_policy(slot_name) == "open":
        if _has_slot_intent_mismatch(player_text, slot_name):
            return False
        return True

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
    extra_postprocessing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extra_postprocessing = extra_postprocessing or {}
    slot_evidence_changed = bool(
        slot_evidence_postprocessing.get("generic_slot_evidence_applied")
        or slot_evidence_postprocessing.get("flight_smalltalk_diagnostic_slot_neutralized")
        or slot_evidence_postprocessing.get("dropped_slot_evidence")
        or slot_evidence_postprocessing.get("intent_relevance_guard_applied")
        or slot_evidence_postprocessing.get("confidence_evidence_guard_applied")
    )
    slot_repair_changed = bool(slot_repair_postprocessing.get("slot_repair_applied"))
    extra_changed = bool(extra_postprocessing)
    if slot_evidence_changed and slot_repair_changed:
        return {
            **slot_evidence_postprocessing,
            **slot_repair_postprocessing,
            **extra_postprocessing,
        }
    if slot_evidence_changed:
        return {
            **slot_evidence_postprocessing,
            "slot_repair_applied": False,
            **extra_postprocessing,
        }
    if extra_changed:
        return {
            **slot_repair_postprocessing,
            **extra_postprocessing,
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
        "output_summary": _understanding_output_summary(output),
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
    error_details = _exception_details(
        error,
        phase="understanding_llm",
        tool_name="understanding_llm_client.analyze",
    )
    return {
        "mode": "fallback",
        "model_name": model_name,
        "output_summary": _understanding_output_summary(fallback_output),
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
                "error_details": error_details,
                "output_summary": _understanding_output_summary(fallback_output),
            }
        ],
    }


def _exception_details(error: Exception, *, phase: str, tool_name: str) -> dict[str, str]:
    """예외를 C Understanding 로그에서 재사용할 수 있는 구조로 정리합니다.

    초보자용 설명:
    로그에 `ValueError` 같은 타입만 남으면 다음 사람이 원인을 다시 재현해야
    합니다. 여기서는 실패 타입, 실제 메시지, 실패 단계, 도구 이름을 한 묶음으로
    남겨서 LLM 스키마 문제인지, 네트워크 문제인지, 후처리 문제인지 빠르게
    구분할 수 있게 합니다.
    """

    return {
        "error_type": error.__class__.__name__,
        "error_message": str(error),
        "phase": phase,
        "tool_name": tool_name,
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
        "incivility": _incivility_summary(output),
    }


def _incivility_summary(output: UnderstandingOutput) -> dict[str, Any]:
    """Return a compact QA-safe incivility summary for logs."""

    if output.incivility is None:
        return {"tier": 0, "category": "none", "source": "none"}
    return {
        "tier": output.incivility.tier,
        "category": output.incivility.category,
        "source": output.incivility.source,
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
