from dataclasses import dataclass
from typing import Any, Literal, cast
import json

import httpx

from backend.app.agents.agent_a.npc_llm_client import (
    NPCDialogueLLMClient,
    NPCDialogueLLMUnavailable,
    build_npc_dialogue_llm_client_from_environment,
)
from backend.app.services.service_a.developer_a_fallback_service import build_text_fallback
from backend.app.services.service_a.developer_a_input_service import normalize_level_design_payload
from backend.app.services.service_a.dialogue_policy_service import build_dialogue_policy
from backend.app.services.service_a.npc_emotion_service import infer_npc_emotion_state
from backend.app.services.service_a.npc_roster_service import NPCProfile, resolve_npc_profile
from backend.app.services.service_a.player_language_profile_service import (
    build_player_language_profile,
)
from backend.app.services.service_a.tts_text_polisher_service import (
    build_tts_style_metadata,
    polish_tts_text,
)

# 분기 유형(Branch Type)을 나타내는 리터럴 타입(Literal Type)입니다.
BranchType = Literal["success", "retry", "fail", "neutral"]
# NPC의 대사 톤(Dialogue Tone)을 정의하는 리터럴 타입(Literal Type)입니다.
DialogueTone = Literal[
    "formal_neutral",
    "formal_firm",
    "formal_stern",
    "formal_warning",
    "formal_supportive",
]


# NPC 대사 생성을 위한 입력 데이터 구조(Data Structure)를 정의하는 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class NPCDialogueInput:
    # 개발자 C 어댑터(Developer C Adapter)가 넘겨주는 계약 페이로드(Payload)를 저장하는 플레이어의 텍스트 입력(Player Text)입니다.
    player_text: str
    # 현재 시나리오 노드(Scenario Node)의 컨텍스트 정보(Context Information)를 담고 있는 사전(Dictionary) 객체입니다.
    node_context: dict[str, Any]
    # 플레이어 발화의 언어적 이해 결과(Semantic Understanding)를 담고 있는 사전(Dictionary) 객체입니다.
    understanding: dict[str, Any]
    # 플레이어의 언어 레벨(Language Level)과 관련된 힌트 정보(Hint Information)를 담고 있는 사전(Dictionary) 객체입니다.
    level_hint: dict[str, Any]
    # 대화의 성공/실패/재시도 여부 등 분기(Branch) 판정 정보가 담긴 사전(Dictionary) 객체입니다.
    branch: dict[str, Any]


# NPC 대사 생성의 최종 결과(Result)를 나타내는 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class NPCDialogueResult:
    # 말하는 화자(Speaker)의 이름(예: Officer Miller)입니다.
    speaker: str
    # 플레이어에게 보여줄 영어 대사 텍스트(Dialogue Text)입니다.
    text: str
    # 대사를 발화할 때의 감정 톤(Dialogue Tone)입니다.
    tone: DialogueTone
    # Unreal 엔진에서 화자가 취할 기본 애니메이션(Animation) 이름입니다.
    animation: str
    # 플레이어를 위해 제공하는 한글 피드백(Korean Feedback) 메시지입니다.
    feedback_kr: str


def generate_npc_dialogue(payload: NPCDialogueInput) -> NPCDialogueResult:
    """개발자 C 어댑터(Developer C Adapter)에서 호출하는 결정적(Deterministic) NPC 대사 생성 함수(Function)입니다.
    
    개발자 A는 오직 NPC 대사 및 피드백 톤(Feedback Tone)만을 결정하고, 
    대화 분기(Branching) 자체는 개발자 B와 C의 판정 값에 의존합니다.
    """
    # 입력 데이터에서 현재 판정된 분기 유형(Branch Type)을 획득합니다.
    branch_type = _branch_type(payload)
    # 개발자 B로부터 플레이어가 사용해야 할 추천 표현(Recommended Expression)을 획득합니다.
    recommended_expression = str(payload.level_hint.get("recommended_expression", "")).strip()

    # 분기 결과가 성공(Success)인 경우의 처리 흐름입니다.
    if branch_type == "success":
        return NPCDialogueResult(
            speaker="Officer Miller",
            text=_success_text(payload),
            tone="formal_neutral",
            animation="move",
            feedback_kr=_success_feedback(recommended_expression),
        )

    # 분기 결과가 재시도(Retry)인 경우의 처리 흐름입니다.
    if branch_type == "retry":
        return NPCDialogueResult(
            speaker="Officer Miller",
            text=_retry_text(payload),
            tone="formal_firm",
            animation="move",
            feedback_kr=_retry_feedback(recommended_expression),
        )

    # 기본값 또는 중립(Neutral) 분기일 경우의 예외적(Fallback) 처리 흐름입니다.
    return NPCDialogueResult(
        speaker="Officer Miller",
        text="Please answer the question clearly.",
        tone="formal_supportive",
        animation="move",
        feedback_kr=_retry_feedback(recommended_expression),
    )


def _branch_type(payload: NPCDialogueInput) -> BranchType:
    """입력 데이터(Payload)로부터 안전하게 분기 유형(Branch Type)을 파싱하는 헬퍼 함수(Helper Function)입니다."""
    value = str(payload.branch.get("branch_type", "neutral")).lower()
    if value in {"success", "retry", "fail", "neutral"}:
        return cast(BranchType, value)
    # 규격에 맞지 않는 예외적인 분기 값이 인입된 경우 안전하게 기본값(Neutral)으로 보정합니다.
    return "neutral"


def _success_text(payload: NPCDialogueInput) -> str:
    """성공 분기(Success Branch) 진입 시 다음 시나리오 노드(Scenario Node)에 대응하는 NPC 대사를 생성합니다."""
    next_node_id = str(payload.branch.get("next_node_id", ""))
    if next_node_id == "IMM_003_DURATION":
        return "Travel. Okay. How long will you stay?"
    return "Okay. Let's continue."


def _retry_text(payload: NPCDialogueInput) -> str:
    """재시도 분기(Retry Branch) 진입 시 NPC가 질문을 다시 던지거나 재답변을 유도하는 대사를 생성합니다."""
    question = str(payload.node_context.get("npc_question", "")).strip()
    if question == "Where will you stay in the United States?":
        return "I need a clear answer. Where will you stay?"
    if question:
        return f"I need a clear answer. {question}"
    return "I need a clear answer."


def _success_feedback(recommended_expression: str) -> str:
    """성공 시 플레이어에게 전달할 격려 및 추천 표현 기반의 피드백 메시지를 빌드합니다."""
    if recommended_expression:
        return f"좋아요. 더 자연스럽게는: {recommended_expression}"
    return "좋아요. 짧고 분명하게 전달했어요."


def _retry_feedback(recommended_expression: str) -> str:
    """답변 재시도(Retry) 시 플레이어의 학습을 돕기 위한 힌트 피드백 메시지를 빌드합니다."""
    if recommended_expression:
        return f"괜찮아요. 짧게 이렇게 말해보세요: {recommended_expression}"
    return "괜찮아요. 짧고 분명한 문장으로 다시 말해보세요."


def generate_npc_dialogue_from_level_design(
    payload: dict[str, Any],
    use_llm: bool = False,
    llm_client: NPCDialogueLLMClient | None = None,
) -> dict[str, Any]:
    """레벨 디자인 에이전트(Level Design Agent) JSON 데이터를 기반으로 개발자 A의 대사 생성 결과를 도출하는 함수(Function)입니다.
    
    인자(Arguments):
        payload: 레벨 디자인 에이전트가 제공하는 원본 입력 사전(Dictionary) 객체입니다.
        use_llm: LLM을 사용하여 대사를 생성할지 여부를 결정하는 부울(Boolean) 값입니다.
        llm_client: 커스텀(Custom) LLM 클라이언트 인스턴스(Instance)입니다. 없으면 환경 변수에서 빌드합니다.
    """
    # 1. 원본 페이로드(Payload)를 개발자 A 내부 처리에 적합하게 정규화(Normalize)합니다.
    normalized = normalize_level_design_payload(payload)
    # 2. 페이로드 정보에 매칭되는 NPC의 프로필(Profile)을 조회합니다.
    npc_profile = resolve_npc_profile(_npc_id_from_payload(payload))
    # 3. 플레이어의 언어 실력 및 응답 통계를 바탕으로 플레이어 프로필을 빌드합니다.
    profile = build_player_language_profile(normalized)
    # 4. 플레이어의 성공/재시도 통계 등을 통해 NPC의 현재 감정 상태(Emotion State)를 추론합니다.
    emotion_state = infer_npc_emotion_state(normalized)
    # 5. 플레이어 프로필과 감정 상태를 연동하여 대사 생성 정책(Dialogue Policy)을 정의합니다.
    policy = build_dialogue_policy(normalized, profile, emotion_state)
    
    candidate_text = str(normalized.get("candidate_text", "")).strip()
    
    # 개발자 B로부터 전달받은 대사 후보군(Candidate Text)이 없거나 차단된 경우, 안전하게 폴백(Fallback) 대사를 생성합니다.
    if not candidate_text:
        result = _apply_npc_profile(build_text_fallback(normalized), npc_profile)
    else:
        # 추천 표현 및 피드백 정보를 추출하고 다듬습니다.
        recommended = str(normalized.get("recommended_expression", "")).strip()
        feedback_note = str(normalized.get("feedback_note", "")).strip()
        feedback_kr = _level_design_feedback(feedback_note, recommended)
        
        # 생성 정책(Policy)에 따라 대사의 아웃라인을 다듬고 조립합니다.
        npc_text = _compose_level_design_text(
            candidate_text=candidate_text,
            recommended_expression=recommended,
            policy=policy,
        )
        # TTS 음성 합성이 좀 더 자연스럽게 발화되도록 텍스트(Text)에 쉼표 및 끊어읽기를 적용합니다.
        tts_text = polish_tts_text(npc_text, profile, emotion_state, policy)

        result = {
            "speaker": npc_profile.display_name,
            "npc_text": npc_text,
            "text": npc_text,
            "tts_text": tts_text,
            "feedback_kr": feedback_kr,
            "tone": policy.tone,
            "animation": npc_profile.default_animation,
            "fallback": {"used": False, "reason": None},
        }
        
    # 생성 이력 추적용 메타데이터(Metadata)를 결과 사전(Dictionary)에 병합합니다.
    result = _with_generation_metadata(result, profile, emotion_state, policy)
    
    # LLM을 사용하지 않는 경우, 룰 기반(Rule-based)의 템플릿(Template) 결과를 그대로 반환합니다.
    if not use_llm:
        return result
        
    # LLM을 사용하는 경우, 생성된 룰 기반 텍스트를 기초로 LLM에 상세 튜닝을 요청합니다. 실패 시 폴백을 반환합니다.
    return _generate_with_llm_or_fallback(payload, normalized, result, llm_client, npc_profile)


def _level_design_feedback(feedback_note: str, recommended_expression: str) -> str:
    """피드백 노트와 추천 표현을 조합하여 플레이어 대상 한글 학습 가이드를 생성하는 헬퍼 함수(Helper Function)입니다."""
    if feedback_note and recommended_expression:
        return f"{feedback_note} 더 자연스럽게는: {recommended_expression}"
    if recommended_expression:
        return f"더 자연스럽게는: {recommended_expression}"
    if feedback_note:
        return feedback_note
    return "의미는 전달됐습니다. 짧고 분명하게 이어가면 됩니다."


def _map_level_design_tone(tone_hint: str) -> DialogueTone:
    """레벨 디자인의 톤 힌트 문자열을 개발자 A 내부에서 사용하는 대사 톤(Dialogue Tone)으로 매핑합니다."""
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
    """정책에 맞게 대사 후보군의 어순이나 응답 어구(Ack)를 추가 조립합니다."""
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
    """디버깅 및 비용 추적을 위해 플레이어 레벨, NPC 감정, 대화 정책의 메타데이터(Metadata)를 추가합니다."""
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


def _apply_npc_profile(result: dict[str, Any], npc_profile: NPCProfile) -> dict[str, Any]:
    """정의된 NPC 프로필의 기본 정보(화자 이름, 대기 애니메이션)를 결과 딕셔너리에 매핑합니다."""
    return {
        **result,
        "speaker": npc_profile.display_name,
        "animation": npc_profile.default_animation,
    }


def _npc_id_from_payload(payload: dict[str, Any]) -> str | None:
    """원본 페이로드 데이터에서 NPC ID를 식별하여 추출합니다."""
    npc = payload.get("npc")
    if not isinstance(npc, dict):
        return None
    value = npc.get("npc_id") or npc.get("id")
    return str(value) if value is not None else None


def _generate_with_llm_or_fallback(
    source_payload: dict[str, Any],
    normalized: dict[str, Any],
    fallback_result: dict[str, Any],
    llm_client: NPCDialogueLLMClient | None,
    npc_profile: NPCProfile,
) -> dict[str, Any]:
    """LLM 클라이언트를 이용하여 NPC 대사를 정교하게 생성하며, 오류 발생 시 룰 기반 결과를 안전 장치(Fallback)로 활용합니다."""
    try:
        client = llm_client or build_npc_dialogue_llm_client_from_environment()
        llm_result = client.generate(
            {
                "level_design_payload": source_payload,
                "normalized": normalized,
                "fallback_candidate": {
                    "speaker": fallback_result["speaker"],
                    "npc_text": fallback_result["npc_text"],
                    "tts_text": fallback_result["tts_text"],
                    "tone": fallback_result["tone"],
                    "feedback_kr": fallback_result["feedback_kr"],
                    "fallback": fallback_result.get("fallback"),
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

    llm_usage = llm_result.get("__llm_usage", {})
    npc_text = str(llm_result.get("npc_text") or "").strip()
    tts_text = str(llm_result.get("tts_text") or "").strip()
    
    # 생성된 대사가 안전한 영문 아스키(ASCII) 텍스트인지 검사합니다.
    if not _is_safe_english_dialogue_text(npc_text) or not _is_safe_english_dialogue_text(tts_text):
        fallback_result["llm"] = {
            "used": False,
            "fallback_used": True,
            "reason": "invalid_llm_dialogue_language",
            "model_name": str(llm_result.get("__fallback_model") or getattr(client, "model", "unknown")),
            "input_tokens": int(llm_usage.get("input_tokens", 0)),
            "output_tokens": int(llm_usage.get("output_tokens", 0)),
            "total_tokens": int(llm_usage.get("total_tokens", 0)),
        }
        return fallback_result

    seed_fallback = _dict_value(fallback_result.get("fallback"))
    merged = {
        **fallback_result,
        "speaker": npc_profile.display_name,
        "npc_text": npc_text,
        "text": npc_text,
        "tts_text": tts_text,
        "feedback_kr": str(llm_result.get("feedback_kr") or fallback_result["feedback_kr"]),
        "tone": str(llm_result.get("tone") or fallback_result["tone"]),
        "animation": npc_profile.default_animation,
        "fallback": {"used": False, "reason": None},
        "llm": {
            "used": True,
            "fallback_used": bool(llm_result.get("__fallback_model")),
            "seed_fallback_used": bool(seed_fallback.get("used")),
            "model_name": str(llm_result.get("__fallback_model") or getattr(client, "model", "unknown")),
            "input_tokens": int(llm_usage.get("input_tokens", 0)),
            "output_tokens": int(llm_usage.get("output_tokens", 0)),
            "total_tokens": int(llm_usage.get("total_tokens", 0)),
            "model_reason": str(llm_result.get("llm_reason", "")),
        },
    }
    return merged


def _dict_value(value: Any) -> dict[str, Any]:
    """전달받은 값이 사전(Dictionary) 타입인지 검사 후 안전한 기본값을 반환합니다."""
    return value if isinstance(value, dict) else {}


def _is_safe_english_dialogue_text(text: str) -> bool:
    """대화에 사용할 대사 텍스트가 영어 알파벳 및 아스키 문자만 포함하는지 검증합니다."""
    stripped = text.strip()
    if not stripped:
        return False
    if not stripped.isascii():
        return False
    letters = [character for character in stripped if character.isalpha()]
    if not letters:
        return False
    return True
