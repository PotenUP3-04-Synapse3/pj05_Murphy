"""Call LLM providers for the Developer C Understanding Agent.

Beginner guide:
The rest of the backend should not know provider-specific HTTP details.  This
file hides those details behind a small `UnderstandingLLMClient` protocol.
There is a primary OpenAI Responses client, an OpenAI-compatible chat client for
the academy fallback server, and a wrapper that tries primary first and fallback
second.  All clients return plain dictionaries that are later validated by the
Understanding Agent schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
import json

import httpx

from backend.app.services.service_c.settings_service import AppSettings, get_settings


class UnderstandingLLMClient(Protocol):
    @property
    def model(self) -> str:
        ...

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class UnderstandingLLMUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAIUnderstandingLLMClient:
    api_key: str
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 10.0
    endpoint: str = "https://api.openai.com/v1/responses"

    @classmethod
    def from_settings(cls, settings: AppSettings | None = None) -> "OpenAIUnderstandingLLMClient":
        resolved_settings = settings or get_settings()
        if not resolved_settings.openai_api_key:
            raise UnderstandingLLMUnavailable("OPENAI_API_KEY is not configured.")
        return cls(
            api_key=resolved_settings.openai_api_key,
            model=resolved_settings.murphy_understanding_llm_model,
            timeout_seconds=resolved_settings.murphy_understanding_llm_timeout_seconds,
        )

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": _developer_instructions(),
                    "input": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": json.dumps(payload, ensure_ascii=False),
                                }
                            ],
                        }
                    ],
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "developer_c_understanding_result",
                            "strict": True,
                            "schema": _understanding_schema(),
                        }
                    },
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise UnderstandingLLMUnavailable(
                f"Understanding LLM request failed: {_http_status_error_detail(exc)}"
            ) from exc
        except httpx.HTTPError as exc:
            raise UnderstandingLLMUnavailable(f"Understanding LLM request failed: {exc}") from exc
        except ValueError as exc:
            raise UnderstandingLLMUnavailable("Understanding LLM returned non-JSON response.") from exc

        return _extract_structured_json(data)


@dataclass(frozen=True)
class OpenAICompatibleUnderstandingLLMClient:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 10.0

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _developer_instructions()},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 600,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise UnderstandingLLMUnavailable(
                "OpenAI-compatible Understanding LLM request failed: "
                f"{_http_status_error_detail(exc)}"
            ) from exc
        except httpx.HTTPError as exc:
            raise UnderstandingLLMUnavailable(
                f"OpenAI-compatible Understanding LLM request failed: {exc}"
            ) from exc
        except ValueError as exc:
            raise UnderstandingLLMUnavailable(
                "OpenAI-compatible Understanding LLM returned non-JSON response."
            ) from exc

        return _extract_chat_completion_structured_json(data)


@dataclass(frozen=True)
class FallbackUnderstandingLLMClient:
    primary: UnderstandingLLMClient
    fallback: UnderstandingLLMClient

    @property
    def model(self) -> str:
        return self.primary.model

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.primary.analyze(payload)
        except UnderstandingLLMUnavailable:
            result = self.fallback.analyze(payload)
            result["__fallback_model"] = self.fallback.model
            return result


def build_understanding_llm_client_from_settings(
    settings: AppSettings | None = None,
) -> UnderstandingLLMClient:
    resolved_settings = settings or get_settings()
    fallback = None
    if resolved_settings.murphy_understanding_llm_fallback == "gemma4_vllm":
        fallback = OpenAICompatibleUnderstandingLLMClient(
            api_key=resolved_settings.gemma4_vllm_api_key,
            model=resolved_settings.gemma4_vllm_model,
            base_url=resolved_settings.gemma4_vllm_base_url,
            timeout_seconds=resolved_settings.murphy_understanding_llm_timeout_seconds,
        )

    try:
        primary = OpenAIUnderstandingLLMClient.from_settings(resolved_settings)
    except UnderstandingLLMUnavailable:
        if fallback is not None:
            return fallback
        raise

    if fallback is not None:
        return FallbackUnderstandingLLMClient(primary=primary, fallback=fallback)
    return primary


def _developer_instructions() -> str:
    return (
        "You are Developer C's Understanding Agent for Murphy's Trippin. "
        "Return only JSON matching the schema. Produce semantic evidence from "
        "the player_text and node_context for Developer B to evaluate. Do not "
        "generate branch, next_node_id, next_action, verdict, scores, hints, "
        "NPC dialogue, TTS text, Unreal commands, or state_delta. Treat "
        "immigration risk expressions seriously and keep the Korean meaning "
        "summary concise."
        " Do not decide bad endings or profanity mirror responses; Developer C "
        "attaches deterministic incivility evidence after this LLM result, and "
        "Developer B owns branch policy."
        " First decide whether player_text actually satisfies one of the "
        "current node_context.required_intents. If it does not, return "
        "intent_success=false, answer_relevance=off_topic or partially_related, "
        "keep required slots missing, and do not normalize a loose phrase into "
        "an allowed slot value."
        " You must also set intent_satisfied=true if the player text satisfies the "
        "immigration officer's question intent, or false otherwise. Provide a short "
        "description of the judgment in judgment_reason."
        " Set satisfied=true if player satisfies the current node's goal, or false otherwise. "
        " Set branch_hint to 'success' if satisfied is true; 'clarify' if the answer is vague, "
        "ambiguous, or partially related; 'retry' if the answer is off-topic or fails to answer; "
        "and 'warning' or 'bad_end' if the traveler refuses cooperation or presents safety risk. "
        " Populate risk_evidence with the list of risk tags (in tags) and the risk delta severity score "
        "(in delta) representing any immigration or customs risk."
        " If player_text satisfies one of the allowed_slot_values of the required slots, "
        "do not set intent_satisfied=false or omit the slot value just because the player "
        "provided additional details or multiple valid travel purposes (e.g., visiting a friend "
        "AND sightseeing). Do not treat rich or multi-purpose answers as unsatisfied intent."
        " For confirmation required intents (starting with confirm_*), if player provides "
        "an affirmation/confirmation (like 'yes', 'yeah', 'only my bag didn't come'), canonicalize "
        "this to the most appropriate allowed slot value (such as 'searched_carefully') even if "
        "the exact manner/allowed value name isn't explicitly mentioned, and do not mark it "
        "as missing slot."
        " For provide_* required intents (e.g. provide_claim_tag), if the player uses a "
        "physical-handover expression ('here it is', 'here you go', 'take it', 'there you go', "
        "'this one', 'here') combined with the context of presenting an item, canonicalize to "
        "the most appropriate allowed_slot_value (e.g. has_claim_tag) and set intent_success=true. "
        "Do not require an explicit verbal 'yes I have it' when the phrasing clearly indicates "
        "a physical act of submission."
        " For acknowledge_* required intents (e.g. acknowledge_customs_hold_explanation), if the "
        "player uses a past-tense compliance expression confirming they have already performed the "
        "requested action ('I did', 'I checked', 'yeah I did', 'I already did it', 'done', "
        "'I looked', 'yeah I checked now'), canonicalize to the most appropriate allowed_slot_value "
        "(e.g. already_checked) and set intent_success=true. Past-tense compliance is as valid as "
        "future-tense agreement — do not mark it as unclear or missing intent."
        " Put every understood slot in slot_evidence using the slot names from "
        "node_context.required_slots, node_context.optional_slots, or "
        "node_context.critical_slots. Each evidence item must include the slot "
        "name, concise value, confidence, and the exact player-text phrase that "
        "supports it."
        " Do not assign confidence 0.9 or higher when slot_evidence is weak, "
        "idiomatic, inferred, or only loosely related to the required intent."
        " Do not return extracted_slots. Developer C derives final "
        "extracted_slots from accepted slot_evidence and the current "
        "node_context after this LLM call. For enum-like slots, put the "
        "canonical allowed value from node_context.allowed_slot_values in "
        "slot_evidence.value, and put the exact supporting player phrase in "
        "slot_evidence.evidence_text."
        " If node_context has customs_item_context, check the difficulty value first — "
        "it is the SOLE authoritative indicator of required explanation depth, NOT the "
        "content of suspicion_reason. "
        "If difficulty is 7 or higher, the player explanation MUST reasonably address "
        "the specific suspicion_reason associated with the item (e.g. quantity/resale "
        "intent for valuable/luxury items, quarantine/compliance for agricultural/food items). "
        "If the explanation is generic (e.g., 'it's a gift', 'it's a personal item', "
        "'it's a souvenir') and does NOT address the suspicion reason, you MUST return "
        "intent_success=false, intent_satisfied=false, and list required slots in missing_slots. "
        "If difficulty is LESS than 7, you MUST treat generic explanations as fully acceptable "
        "and return intent_success=true regardless of how serious the suspicion_reason may "
        "sound (e.g., cash structuring, money laundering). Do NOT apply the specificity "
        "requirement to items with difficulty < 7."
        " Also fill pragmatic_context as a compact situation-level judgment. "
        "Use it for real-world speech acts such as refusal, off-topic evasion, "
        "violent threats, coercive exit requests, or normal meaningful answers. "
        "For threats or unsafe intent, set player_move=violent_threat, choose "
        "the target, raise risk_level, and recommend warning or secondary_inspection. "
        "This card is evidence for Developer B and A; it still must not decide "
        "branch, next node, NPC dialogue, hints, or Unreal commands."
    )


def _understanding_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "intent",
            "intent_success",
            "confidence",
            "meaning_summary_kr",
            "emotion",
            "answer_relevance",
            "ambiguity_type",
            "risk_delta",
            "risk_reason",
            "risk_tags",
            "slot_evidence",
            "missing_slots",
            "needs_clarification",
            "intent_satisfied",
            "judgment_reason",
            "satisfied",
            "branch_hint",
            "risk_evidence",
            "pragmatic_context",
        ],
        "properties": {
            "intent": {"type": "string"},
            "intent_success": {"type": "boolean"},
            "confidence": {"type": "number"},
            "meaning_summary_kr": {"type": "string"},
            "emotion": {"type": "string"},
            "answer_relevance": {
                "type": "string",
                "enum": ["on_topic", "partially_related", "off_topic"],
            },
            "ambiguity_type": {"type": "string"},
            "risk_delta": {"type": "integer"},
            "risk_reason": {"type": "string"},
            "risk_tags": {"type": "array", "items": {"type": "string"}},
            "slot_evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["slot", "value", "confidence", "evidence_text"],
                    "properties": {
                        "slot": {"type": "string"},
                        "value": {"type": "string"},
                        "confidence": {"type": "number"},
                        "evidence_text": {"type": "string"},
                    },
                },
            },
            "missing_slots": {"type": "array", "items": {"type": "string"}},
            "needs_clarification": {"type": "boolean"},
            "intent_satisfied": {"type": "boolean"},
            "judgment_reason": {"type": "string"},
            "satisfied": {"type": "boolean"},
            "branch_hint": {
                "type": "string",
                "enum": ["success", "retry", "clarify", "hint", "warning", "bad_end"],
            },
            "risk_evidence": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tags", "delta"],
                "properties": {
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "delta": {"type": "integer"},
                },
            },
            "pragmatic_context": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "player_move",
                    "target",
                    "threat_directness",
                    "risk_level",
                    "procedural_posture",
                    "recommended_b_move",
                    "recommended_a_move",
                    "confidence",
                    "evidence",
                    "reason",
                ],
                "properties": {
                    "player_move": {
                        "type": "string",
                        "enum": [
                            "unknown",
                            "meaningful_answer",
                            "social_non_answer",
                            "off_topic",
                            "refusal",
                            "violent_threat",
                            "coercive_exit_request",
                        ],
                    },
                    "target": {
                        "type": "string",
                        "enum": ["none", "officer", "public_figure", "other_person", "self", "unknown"],
                    },
                    "threat_directness": {
                        "type": "string",
                        "enum": ["none", "implied", "explicit_intent", "direct_threat"],
                    },
                    "risk_level": {
                        "type": "string",
                        "enum": ["none", "low", "medium", "high", "critical"],
                    },
                    "procedural_posture": {
                        "type": "string",
                        "enum": [
                            "continue",
                            "clarify",
                            "warn",
                            "stop_normal_interview",
                            "secondary_inspection",
                            "end_interview",
                        ],
                    },
                    "recommended_b_move": {
                        "type": "string",
                        "enum": ["continue", "reask", "clarify", "warning", "secondary_inspection"],
                    },
                    "recommended_a_move": {
                        "type": "string",
                        "enum": ["continue", "repair", "formal_boundary", "stern_boundary"],
                    },
                    "confidence": {"type": "number"},
                    "evidence": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
    }


def _extract_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("output_text"), str):
        result = _normalize_structured_result(json.loads(data["output_text"]))
        result["__llm_usage"] = _extract_usage(data)
        return result
    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                result = _normalize_structured_result(json.loads(str(content_item.get("text", ""))))
                result["__llm_usage"] = _extract_usage(data)
                return result
    raise UnderstandingLLMUnavailable("OpenAI response did not include output_text.")


def _extract_chat_completion_structured_json(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices")
    if not isinstance(choices, list):
        raise UnderstandingLLMUnavailable("OpenAI-compatible response did not include choices.")
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        text = str(message.get("content") or "").strip()
        if text:
            result = _normalize_structured_result(json.loads(_strip_json_fence(text)))
            result["__llm_usage"] = _extract_chat_completion_usage(data)
            return result
    raise UnderstandingLLMUnavailable(
        "OpenAI-compatible response did not include message content."
    )


def _strip_json_fence(text: str) -> str:
    if text.startswith("```json"):
        return text.removeprefix("```json").removesuffix("```").strip()
    if text.startswith("```"):
        return text.removeprefix("```").removesuffix("```").strip()
    return text


def normalize_understanding_llm_result(result: dict[str, Any]) -> dict[str, Any]:
    """LLM 원문을 slot_evidence-first 내부 결과로 정리합니다.

    Beginner guide:
    LLM은 슬롯 최종값을 직접 확정하지 않습니다.  여기서는 LLM이 준
    `slot_evidence`만 정리하고, `extracted_slots`는 그 evidence에서 만든 임시
    값으로 채웁니다.  이후 `UnderstandingAgent`가 현재 노드의
    `required_slots`와 `allowed_slot_values`로 다시 필터링합니다.  구버전 LLM이나
    fallback 서버가 `extracted_slots`를 보내더라도 신뢰하지 않고 무시합니다.
    """

    slot_evidence = _normalize_slot_evidence(result.get("slot_evidence"))
    result["slot_evidence"] = slot_evidence
    result["extracted_slots"] = {}
    for evidence in slot_evidence:
        result["extracted_slots"].setdefault(evidence["slot"], evidence["value"])
    return result


def _normalize_structured_result(result: dict[str, Any]) -> dict[str, Any]:
    return normalize_understanding_llm_result(result)


def _normalize_slot_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot") or "").strip()
        slot_value = str(item.get("value") or "").strip()
        if not slot or not slot_value:
            continue
        normalized.append(
            {
                "slot": slot,
                "value": slot_value,
                "confidence": _normalize_confidence(item.get("confidence")),
                "evidence_text": str(item.get("evidence_text") or slot_value).strip() or slot_value,
            }
        )
    return normalized


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, confidence))


def _http_status_error_detail(exc: httpx.HTTPStatusError) -> str:
    response = exc.response
    try:
        payload = response.json()
    except ValueError:
        return f"status={response.status_code} body={response.text[:500]}"

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        code = error.get("code") or error.get("type") or "unknown"
        message = error.get("message") or response.text[:500]
        return f"status={response.status_code} code={code} message={message}"
    return f"status={response.status_code} body={response.text[:500]}"


def _extract_usage(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    input_tokens = _int_or_zero(usage.get("input_tokens"))
    output_tokens = _int_or_zero(usage.get("output_tokens"))
    total_tokens = _int_or_zero(usage.get("total_tokens")) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _extract_chat_completion_usage(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    input_tokens = _int_or_zero(usage.get("prompt_tokens"))
    output_tokens = _int_or_zero(usage.get("completion_tokens"))
    total_tokens = _int_or_zero(usage.get("total_tokens")) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _int_or_zero(value: Any) -> int:
    return value if isinstance(value, int) else 0
