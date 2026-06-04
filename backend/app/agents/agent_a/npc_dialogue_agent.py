from dataclasses import dataclass
from typing import Any, Literal, cast
import json

import httpx

from backend.app.agents.agent_a.npc_llm_client import (
    NPCDialogueLLMClient,
    NPCDialogueLLMUnavailable,
    OpenAINPCDialogueLLMClient,
)
from backend.app.services.service_a.developer_a_fallback_service import build_text_fallback
from backend.app.services.service_a.developer_a_input_service import normalize_level_design_payload
from backend.app.services.service_a.dialogue_policy_service import build_dialogue_policy
from backend.app.services.service_a.npc_emotion_service import infer_npc_emotion_state
from backend.app.services.service_a.player_language_profile_service import (
    build_player_language_profile,
)
from backend.app.services.service_a.tts_text_polisher_service import (
    build_tts_style_metadata,
    polish_tts_text,
)

BranchType = Literal["success", "retry", "fail", "neutral"]
DialogueTone = Literal["formal_neutral", "formal_firm", "formal_supportive"]


@dataclass(frozen=True)
class NPCDialogueInput:
    # Developer C adapter가 넘겨주는 계약 payload를 그대로 받는다.
    player_text: str
    node_context: dict[str, Any]
    understanding: dict[str, Any]
    level_hint: dict[str, Any]
    branch: dict[str, Any]


@dataclass(frozen=True)
class NPCDialogueResult:
    speaker: str
    text: str
    tone: DialogueTone
    animation: str
    feedback_kr: str


def generate_npc_dialogue(payload: NPCDialogueInput) -> NPCDialogueResult:
    """Developer C adapter용 결정적 Officer Miller 대사를 만든다."""
    # Developer A는 대사와 feedback tone만 결정하고, 분기 자체는 Developer B/C 입력을 따른다.
    branch_type = _branch_type(payload)
    recommended_expression = str(payload.level_hint.get("recommended_expression", "")).strip()

    if branch_type == "success":
        return NPCDialogueResult(
            speaker="Officer Miller",
            text=_success_text(payload),
            tone="formal_neutral",
            animation="officer_check_passport",
            feedback_kr=_success_feedback(recommended_expression),
        )

    if branch_type == "retry":
        return NPCDialogueResult(
            speaker="Officer Miller",
            text=_retry_text(payload),
            tone="formal_firm",
            animation="officer_waiting",
            feedback_kr=_retry_feedback(recommended_expression),
        )

    return NPCDialogueResult(
        speaker="Officer Miller",
        text="Please answer the question clearly.",
        tone="formal_supportive",
        animation="officer_waiting",
        feedback_kr=_retry_feedback(recommended_expression),
    )


def _branch_type(payload: NPCDialogueInput) -> BranchType:
    value = str(payload.branch.get("branch_type", "neutral")).lower()
    if value in {"success", "retry", "fail", "neutral"}:
        return cast(BranchType, value)
    # 알 수 없는 branch 값은 adapter 교체 중에도 안전하게 기본 응답으로 떨어뜨린다.
    return "neutral"


def _success_text(payload: NPCDialogueInput) -> str:
    next_node_id = str(payload.branch.get("next_node_id", ""))
    if next_node_id == "IMM_003_DURATION":
        return "Travel. Okay. How long will you stay?"
    return "Okay. Let's continue."


def _retry_text(payload: NPCDialogueInput) -> str:
    question = str(payload.node_context.get("npc_question", "")).strip()
    if question == "Where will you stay in the United States?":
        return "I need a clear answer. Where will you stay?"
    if question:
        return f"I need a clear answer. {question}"
    return "I need a clear answer."


def _success_feedback(recommended_expression: str) -> str:
    if recommended_expression:
        return f"좋아요. 더 자연스럽게는: {recommended_expression}"
    return "좋아요. 짧고 분명하게 전달했어요."


def _retry_feedback(recommended_expression: str) -> str:
    if recommended_expression:
        return f"괜찮아요. 짧게 이렇게 말해보세요: {recommended_expression}"
    return "괜찮아요. 짧고 분명한 문장으로 다시 말해보세요."


def generate_npc_dialogue_from_level_design(
    payload: dict[str, Any],
    use_llm: bool = False,
    llm_client: NPCDialogueLLMClient | None = None,
) -> dict[str, Any]:
    """Level Design Agent JSON을 기반으로 Developer A 대사 결과를 만든다."""
    normalized = normalize_level_design_payload(payload)
    profile = build_player_language_profile(normalized)
    emotion_state = infer_npc_emotion_state(normalized)
    policy = build_dialogue_policy(normalized, profile, emotion_state)
    if normalized["do_not_generate_npc_text"] or normalized["blocks_progression"]:
        return _with_generation_metadata(build_text_fallback(normalized), profile, emotion_state, policy)

    candidate_text = str(normalized.get("candidate_text", "")).strip()
    if not candidate_text:
        return _with_generation_metadata(build_text_fallback(normalized), profile, emotion_state, policy)

    recommended = str(normalized.get("recommended_expression", "")).strip()
    feedback_note = str(normalized.get("feedback_note", "")).strip()
    feedback_kr = _level_design_feedback(feedback_note, recommended)
    npc_text = _compose_level_design_text(
        candidate_text=candidate_text,
        recommended_expression=recommended,
        policy=policy,
    )
    tts_text = polish_tts_text(npc_text, profile, emotion_state, policy)

    result = {
        "speaker": "Officer Miller",
        "npc_text": npc_text,
        "text": npc_text,
        "tts_text": tts_text,
        "feedback_kr": feedback_kr,
        "tone": policy.tone,
        "animation": "officer_check_passport",
        "fallback": {"used": False, "reason": None},
    }
    result = _with_generation_metadata(result, profile, emotion_state, policy)
    if not use_llm:
        return result
    return _generate_with_llm_or_fallback(payload, normalized, result, llm_client)


def _level_design_feedback(feedback_note: str, recommended_expression: str) -> str:
    if feedback_note and recommended_expression:
        return f"{feedback_note} 더 자연스럽게는: {recommended_expression}"
    if recommended_expression:
        return f"더 자연스럽게는: {recommended_expression}"
    if feedback_note:
        return feedback_note
    return "의미는 전달됐습니다. 짧고 분명하게 이어가면 됩니다."


def _map_level_design_tone(tone_hint: str) -> DialogueTone:
    if tone_hint == "firm":
        return "formal_firm"
    if tone_hint in {"supportive", "encouraging"}:
        return "formal_supportive"
    return "formal_neutral"


def _compose_level_design_text(
    candidate_text: str,
    recommended_expression: str,
    policy: Any,
) -> str:
    if not policy.add_officer_ack:
        return candidate_text
    if not policy.use_recast or not recommended_expression:
        return candidate_text
    if candidate_text.startswith(("Alright.", "Okay.")):
        return candidate_text
    return f"Alright. {candidate_text}"


def _with_generation_metadata(
    result: dict[str, Any],
    profile: Any,
    emotion_state: Any,
    policy: Any,
) -> dict[str, Any]:
    tts_text = str(result.get("tts_text") or result.get("npc_text") or result.get("text") or "")
    result["tts_text"] = tts_text
    result["generation_profile"] = {
        "player_language": {
            "english_level": profile.english_level,
            "task_success": profile.task_success,
            "clarity": profile.clarity,
            "needs_hint": profile.needs_hint,
            "complexity": profile.complexity,
            "feedback_depth": profile.feedback_depth,
        },
        "npc_emotion": {
            "emotion": emotion_state.emotion,
            "intensity": emotion_state.intensity,
            "reason": emotion_state.reason,
        },
        "dialogue_policy": {
            "action": policy.action,
            "tone": policy.tone,
            "max_sentence_count": policy.max_sentence_count,
            "use_recast": policy.use_recast,
            "add_officer_ack": policy.add_officer_ack,
            "next_question_style": policy.next_question_style,
        },
        "tts_style": build_tts_style_metadata(profile, emotion_state, policy),
    }
    return result


def _generate_with_llm_or_fallback(
    source_payload: dict[str, Any],
    normalized: dict[str, Any],
    fallback_result: dict[str, Any],
    llm_client: NPCDialogueLLMClient | None,
) -> dict[str, Any]:
    try:
        client = llm_client or OpenAINPCDialogueLLMClient.from_environment()
        llm_result = client.generate(
            {
                "level_design_payload": source_payload,
                "normalized": normalized,
                "fallback_candidate": {
                    "npc_text": fallback_result["npc_text"],
                    "tts_text": fallback_result["tts_text"],
                    "tone": fallback_result["tone"],
                    "feedback_kr": fallback_result["feedback_kr"],
                },
                "generation_profile": fallback_result["generation_profile"],
            }
        )
    except (NPCDialogueLLMUnavailable, httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
        fallback_result["llm"] = {
            "used": False,
            "fallback_used": True,
            "reason": type(exc).__name__,
        }
        return fallback_result

    merged = {
        **fallback_result,
        "speaker": str(llm_result["speaker"]),
        "npc_text": str(llm_result["npc_text"]),
        "text": str(llm_result["npc_text"]),
        "tts_text": str(llm_result["tts_text"]),
        "feedback_kr": str(llm_result["feedback_kr"]),
        "tone": str(llm_result["tone"]),
        "animation": str(llm_result["animation"]),
        "llm": {
            "used": True,
            "fallback_used": False,
            "model_reason": str(llm_result.get("llm_reason", "")),
        },
    }
    return merged
