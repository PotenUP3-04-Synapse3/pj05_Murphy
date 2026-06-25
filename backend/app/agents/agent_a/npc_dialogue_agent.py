from dataclasses import dataclass
from typing import Any, Literal, cast, TypedDict, NotRequired
import json
import re

import httpx

from langgraph.graph import StateGraph, START, END

from langchain_core.runnables import RunnableConfig
from backend.app.agents.agent_a.npc_llm_client import (
    NPCDialogueLLMUnavailable,
    build_npc_dialogue_llm_client_from_environment,
)
from backend.app.services.service_a.developer_a_fallback_service import build_text_fallback
from backend.app.services.service_a.developer_a_input_service import normalize_level_design_payload
from backend.app.services.service_a.dialogue_policy_service import (
    build_dialogue_policy,
    synthesize_fallback_next_question,
)
from backend.app.services.service_a.npc_emotion_service import infer_npc_emotion_state
from backend.app.services.service_a.npc_roster_service import NPCProfile, resolve_npc_profile
from backend.app.services.service_a.player_language_profile_service import (
    build_player_language_profile,
)
from backend.app.services.service_a.tts_text_polisher_service import (
    build_tts_style_metadata,
    polish_tts_text,
    validate_and_clamp_ssml,
)
from backend.app.services.service_a.profanity_response_policy import (
    get_profanity_fallback_response,
)
from backend.app.services.service_a.profanity_lexicon import (
    contains_blocked,
    allowed_for,
    MIRROR_ALLOWED_STRONG,
)
import os

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
    # 말하는 화자(Speaker)의 이름(예: Hale)입니다.
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

    # 분기 결과가 성공(Success)인 경우의 처리 흐름입니다.
    if branch_type == "success":
        return NPCDialogueResult(
            speaker="Hale",
            text=_success_text(payload),
            tone="formal_neutral",
            animation="move",
            feedback_kr=_success_feedback(),
        )

    # 분기 결과가 재시도(Retry)인 경우의 처리 흐름입니다.
    if branch_type == "retry":
        return NPCDialogueResult(
            speaker="Hale",
            text=_retry_text(payload),
            tone="formal_firm",
            animation="move",
            feedback_kr=_retry_feedback(),
        )

    # 기본값 또는 중립(Neutral) 분기일 경우의 예외적(Fallback) 처리 흐름입니다.
    return NPCDialogueResult(
        speaker="Hale",
        text="Please answer the question clearly.",
        tone="formal_supportive",
        animation="move",
        feedback_kr=_retry_feedback(),
    )


def _branch_type(payload: NPCDialogueInput) -> BranchType:
    """입력 데이터(Payload)로부터 안전하게 분기 유형(Branch Type)을 파싱하는 헬퍼 함수(Helper Function)입니다."""
    value = str(payload.branch.get("branch_type", "neutral")).lower()
    if value in {"success", "retry", "fail", "neutral"}:
        return cast(BranchType, value)
    # 규격에 맞지 않는 예외적인 분기 값이 인입된 경우 안전하게 기본값(Neutral)으로 보정합니다.
    return "neutral"


def _is_complete_chapter_turn(normalized: dict[str, Any]) -> bool:
    """Return True when this turn should close the scene instead of asking more."""

    transition_status = str(normalized.get("transition", {}).get("status") or "").lower()
    next_action = str(normalized.get("next_action") or "").upper()
    next_node_id = str(normalized.get("next_node_id") or "").upper()
    return (
        transition_status in {"complete_chapter", "chapter_complete"}
        or next_action == "COMPLETE_CHAPTER"
        or next_node_id.endswith("_999_COMPLETE")
    )


def _global_dialogue_violation(
    npc_text: str,
    tts_text: str,
    normalized: dict[str, Any],
    payload: dict[str, Any],
) -> str | None:
    """Return a fallback reason when any LLM text violates global node policy."""

    if _has_retry_hook_leak(npc_text, tts_text, normalized):
        return "immigration_retry_hook_violation"

    if _has_positive_reaction_on_failure(npc_text, tts_text, normalized):
        return "positive_reaction_violation"

    if _is_immigration_turn(normalized):
        if _contradicts_current_immigration_slot(npc_text, tts_text, payload):
            return "current_slot_contradiction"
        if _has_immigration_surface_goal_mismatch(npc_text, tts_text, normalized):
            return "immigration_surface_goal_mismatch"

    return None


def _has_positive_reaction_on_failure(
    npc_text: str,
    tts_text: str,
    normalized: dict[str, Any],
) -> bool:
    branch_type = str(normalized.get("branch_type") or "").lower()
    next_action = str(normalized.get("next_action") or "").upper()
    if branch_type not in {"retry", "clarify", "warning"} and next_action not in {"REASK", "GIVE_HINT", "WARNING"}:
        return False

    combined = (npc_text + " " + tts_text).lower()
    normalized_combined = _normalize_for_echo_match(combined)
    words = normalized_combined.split()
    if not words:
        return False

    positive_words = {
        "good", "great", "nice", "excellent", "perfect", "wonderful", "awesome",
        "yes", "okay", "ok", "sure", "alright"
    }
    if words[0] in positive_words:
        return True
    if len(words) >= 2 and words[0] == "thank" and words[1] == "you":
        return True
    if len(words) >= 2 and words[0] == "all" and words[1] == "right":
        return True

    return False


def _is_immigration_turn(normalized: dict[str, Any]) -> bool:
    node_id = str(normalized.get("node_id") or "")
    npc_role = str(normalized.get("npc_role") or "")
    return npc_role == "immigration_officer" or node_id.startswith("IMM_")


def _has_immigration_retry_hook_leak(
    npc_text: str,
    tts_text: str,
    normalized: dict[str, Any],
) -> bool:
    return _has_retry_hook_leak(npc_text, tts_text, normalized)


def _has_retry_hook_leak(
    npc_text: str,
    tts_text: str,
    normalized: dict[str, Any],
) -> bool:
    branch_type = str(normalized.get("branch_type") or "").lower()
    next_action = str(normalized.get("next_action") or "").upper()
    if branch_type not in {"retry", "clarify"} and next_action not in {"REASK", "GIVE_HINT"}:
        return False
    combined = _normalize_for_echo_match(f"{npc_text} {tts_text}")
    return "you mentioned" in combined or "mentioned mentioned" in combined


def _has_immigration_surface_goal_mismatch(
    npc_text: str,
    tts_text: str,
    normalized: dict[str, Any],
) -> bool:
    purpose = str(normalized.get("dialogue_purpose") or "")
    branch_type = str(normalized.get("branch_type") or "").lower()
    next_action = str(normalized.get("next_action") or "").upper()
    if purpose != "continue_to_next_question":
        return False
    if branch_type not in {"success", "neutral"} or next_action == "COMPLETE_CHAPTER":
        return False

    surface_goal = str((normalized.get("dialogue_seed") or {}).get("surface_goal") or "")
    if surface_goal not in _IMMIGRATION_SURFACE_GOAL_CHECKS:
        return False
    if surface_goal == "confirm_immigration_clearance_transition" and (
        "?" in npc_text or "?" in tts_text
    ):
        return True
    combined = _normalize_for_echo_match(f"{npc_text} {tts_text}")
    return not _IMMIGRATION_SURFACE_GOAL_CHECKS[surface_goal](combined)


def _contradicts_current_immigration_slot(
    npc_text: str,
    tts_text: str,
    payload: dict[str, Any],
) -> bool:
    understanding = payload.get("understanding") or {}
    extracted_slots = understanding.get("extracted_slots") or {}
    occupation = str(extracted_slots.get("occupation") or "").strip().lower()
    if not occupation:
        return False
    combined = _normalize_for_echo_match(f"{npc_text} {tts_text}")
    if occupation not in {"unemployed", "no_job", "no job"}:
        stale_unemployed_terms = ("unemployed", "no job", "jobless", "looking for a job")
        if any(term in combined for term in stale_unemployed_terms):
            return True
    return False


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _open_hooks_for_fallback_synthesis(
    normalized: dict[str, Any],
    session_context_card: dict[str, Any],
) -> list[str] | None:
    """Disable casual hook prefixes in formal immigration turns."""

    if _is_immigration_turn(normalized):
        return []
    return session_context_card.get("open_hooks")


def _is_passport_submission_refusal_branch(normalized: dict[str, Any]) -> bool:
    return "passport_submission_refused" in str(normalized.get("branch_reason") or "")


_IMMIGRATION_SURFACE_GOAL_CHECKS = {
    "request_passport_submission": lambda text: "passport" in text.split(),
    "ask_visit_purpose": lambda text: _contains_any(
        text,
        ("purpose", "why are you here", "what brings"),
    ),
    "ask_stay_duration": lambda text: _contains_any(
        text,
        ("how long", "how many days", "stay for", "planning to stay"),
    ),
    "ask_stay_location": lambda text: _contains_any(
        text,
        ("where will you stay", "where are you staying", "where will you be staying", "address"),
    ),
    "ask_return_ticket": lambda text: "return ticket" in text or "return flight" in text,
    "ask_first_visit": lambda text: _contains_any(
        text,
        ("first visit", "first time", "visited before"),
    ),
    "ask_occupation": lambda text: _contains_any(
        text,
        ("occupation", "job", "do for a living", "work do you do"),
    ),
    "confirm_immigration_clearance_transition": lambda text: _contains_any(
        text,
        ("cleared", "enjoy your stay", "here is your passport", "baggage claim"),
    ),
}


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


def _success_feedback() -> str:
    """성공 시 플레이어에게 전달할 격려 및 피드백 메시지를 빌드합니다."""
    return "좋아요. 짧고 분명하게 전달했어요."


def _retry_feedback() -> str:
    """답변 재시도(Retry) 시 플레이어의 학습을 돕기 위한 힌트 피드백 메시지를 빌드합니다."""
    return "괜찮아요. 짧고 분명한 문장으로 다시 말해보세요."


def _normalize_for_echo_match(value: str) -> str:
    """추천 표현 누출(Echo) 비교를 위해 텍스트를 정규화합니다.

    초보자용 설명:
    "Thank you, officer."처럼 플레이어용 모범 답안(recommended_expression)이
    NPC 대사에 그대로 새는지 검사할 때, 대소문자/구두점/공백/SSML 차이 때문에
    놓치는 일이 없도록 비교 직전에 한 번 정규화합니다. 즉 단순 substring 매칭이
    아니라 "의미상 같은 문장"인지 보기 위한 사전 처리입니다.
    """

    # tts_text에는 <break time="0.4s"/> 같은 SSML 태그가 섞일 수 있으므로 먼저 제거합니다.
    without_ssml = re.sub(r"<[^>]+>", " ", value)
    lowered = without_ssml.lower()
    # 영문/숫자/공백만 남겨서 구두점 차이를 흡수합니다.
    stripped = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return " ".join(stripped.split())


def _is_recommended_expression_echoed(recommended_expression: str, *texts: str) -> bool:
    """추천 표현이 NPC 대사(또는 TTS)에 verbatim에 가깝게 새어 들어갔는지 판정합니다.

    초보자용 설명:
    recommended_expression은 플레이어가 배워야 할 모범 답안이라 NPC가 자기
    입으로 말하면 안 됩니다. npc_text뿐 아니라 tts_text도 함께 검사하고,
    구두점/대소문자/공백 차이를 무시한 정규화 후 substring으로 비교합니다.
    너무 짧은 추천 표현(예: "Yes.")은 일반 대사와 우연히 겹쳐 오탐을 낼 수
    있으므로 2단어 이상일 때만 검사합니다.
    """

    normalized_expression = _normalize_for_echo_match(recommended_expression)
    # 1단어짜리 추천 표현은 정상 NPC 리액션과 겹칠 수 있어 검사 대상에서 제외합니다.
    if len(normalized_expression.split()) < 2:
        return False
    return any(
        normalized_expression in _normalize_for_echo_match(text)
        for text in texts
        if text
    )


def _is_repeated_smalltalk_object_request(
    npc_text: str,
    tts_text: str,
    normalized: dict[str, Any],
    turn_buffer: list[dict[str, Any]] | None = None,
) -> bool:
    """Return True when Flight smalltalk is drifting back into an answered favor."""

    if not _mentions_pen_request(npc_text) and not _mentions_pen_request(tts_text):
        return False

    player_text = str(normalized.get("player_text") or "")
    if _mentions_repeat_complaint(player_text):
        return True

    if turn_buffer:
        for turn in turn_buffer:
            previous_npc = str(turn.get("npc_text") or "")
            previous_player = str(turn.get("player_text") or "")
            if _mentions_pen_request(previous_npc) or _mentions_pen_resolution(previous_player):
                return True

    dialogue_history = normalized.get("dialogue_history") or []
    for turn in dialogue_history:
        if not isinstance(turn, dict):
            continue
        previous_npc = str(turn.get("npc_text_preview") or "")
        previous_player = str(turn.get("player_text_preview") or "")
        if _mentions_pen_request(previous_npc) or _mentions_pen_resolution(previous_player):
            return True
    return False


def _mentions_pen_request(text: str) -> bool:
    normalized = _normalize_for_echo_match(text)
    if "pen" not in normalized.split():
        return False
    request_markers = (
        "borrow your pen",
        "borrow the pen",
        "borrow a pen",
        "spare pen",
        "one more pen",
        "another pen",
        "still borrow",
        "could i borrow",
        "can i borrow",
        "do you have a pen",
        "do you have one more pen",
    )
    return any(marker in normalized for marker in request_markers)


def _mentions_pen_resolution(text: str) -> bool:
    normalized = _normalize_for_echo_match(text)
    if "pen" not in normalized.split():
        return False
    resolution_markers = (
        "here you go",
        "here you are",
        "you can have",
        "already gave",
        "gave it to you",
        "last one",
        "get yourself",
        "nope",
    )
    return any(marker in normalized for marker in resolution_markers)


def _mentions_repeat_complaint(text: str) -> bool:
    normalized = _normalize_for_echo_match(text)
    if "pen" not in normalized.split():
        return False
    complaint_markers = (
        "keep asking",
        "already gave",
        "gave it to you",
        "pen loop",
        "asking me about my pen",
        "why do you want more",
        "why you want more",
        "one more",
        "more pen",
    )
    return any(marker in normalized for marker in complaint_markers)


def _ignores_open_smalltalk_social_obligation(
    npc_text: str,
    tts_text: str,
    normalized: dict[str, Any],
) -> bool:
    """Return True when an LLM jumps topics before resolving an open request."""

    if str(normalized.get("dialogue_purpose") or "") != "smalltalk_diagnostic":
        return False
    social_context = normalized.get("social_context") or {}
    if not isinstance(social_context, dict):
        return False
    if str(social_context.get("pending_social_obligation") or "") != "seatmate_pen_request":
        return False
    if str(social_context.get("obligation_status") or "") not in {"open", "ignored", "unclear"}:
        return False
    if "social_obligation_dropped" in str(normalized.get("branch_reason") or ""):
        return False
    if "flight_smalltalk_engagement_" in str(normalized.get("branch_reason") or ""):
        return False

    combined = _normalize_for_echo_match(f"{npc_text} {tts_text}")
    request_repair_markers = (
        "pen",
        "borrow",
        "did you hear",
        "do you mean",
        "are you saying",
        "answer",
        "playing with me",
        "teasing me",
    )
    return not any(marker in combined for marker in request_repair_markers)


# LangGraph 에이전트의 내부 공유 상태(Shared State) 명세를 정의하는 TypedDict 클래스입니다.
class NPCDialogueState(TypedDict):
    # payload: 개발자 C의 어댑터로부터 넘겨받은 원본 입력 데이터(Raw Input Payload)입니다.
    payload: dict[str, Any]
    # normalized: 레벨 디자인 규격에 맞게 정규화(Normalization)를 마친 페이로드 데이터입니다.
    normalized: dict[str, Any]
    # npc_profile: 현재 매칭된 NPC의 인게임 설정 프로필(Roster Profile)입니다.
    npc_profile: NPCProfile
    # profile: 플레이어의 언어적 메타데이터(English Level, Clarity 등)를 취합한 프로필 객체입니다.
    profile: Any
    # emotion_state: 플레이어 통계를 바탕으로 추론된 NPC의 실시간 감정 상태(Emotion State)입니다.
    emotion_state: Any
    # policy: 대사 어조 및 추가 조립 규칙을 지시하는 대화 생성 정책(Dialogue Policy)입니다.
    policy: Any
    # result: 생성 완료된 최종 대사 및 부가 정보(TTS 파라미터를 포함한 결과)를 담은 딕셔너리입니다.
    result: NotRequired[dict[str, Any]]
    # use_llm: 대사 생성 시 LLM을 호출할지 여부를 나타내는 플래그(Flag)입니다.
    use_llm: bool
    # llm_client: 실제 API 호출을 수행하는 LLM 클라이언트 인스턴스(Client Instance)입니다.
    llm_client: Any
    # error: LLM 호출 등 처리 중 발생한 예외 상황의 에러 종류 문자열입니다.
    error: NotRequired[str]
    # session_context_card: NPC 세션 메모리 요약 카드를 저장하는 사전 객체입니다.
    session_context_card: NotRequired[dict[str, Any]]
    
    # 단기 메모리(Short-term Memory) 관련 변수
    turn_buffer: NotRequired[list[dict[str, Any]]]
    accumulated_slots: NotRequired[dict[str, str]]
    forbidden_questions: NotRequired[list[str]]
    last_npc_intent: NotRequired[str]
    _memory_cleanup_pending: NotRequired[bool]


def node_initialize_state(state: NPCDialogueState) -> dict[str, Any]:
    """입력 데이터 파싱, 프로필 로드, 감정 추론 및 기본 룰 기반 결과를 빌드하여 상태를 초기화하는 노드입니다."""
    # [1단계] 공유 상태(State)에서 원본 페이로드 데이터를 추출합니다.
    payload = state["payload"]
    # [2단계] 원본 페이로드(Payload)를 정규화(Normalize)합니다.
    normalized = normalize_level_design_payload(payload)
    # [3단계] 페이로드 정보에 매칭되는 NPC의 프로필(Profile)을 조회합니다.
    npc_profile = resolve_npc_profile(_npc_id_from_payload(payload))
    # 세션 메모리 요약 카드 빌드
    from backend.app.services.service_a.session_context_card_service import build_session_context_card
    npc_memory = {
        "turn_buffer": state.get("turn_buffer") or [],
        "accumulated_slots": state.get("accumulated_slots") or {},
        "forbidden_questions": state.get("forbidden_questions") or [],
        "last_npc_intent": state.get("last_npc_intent") or "",
    }
    session_context_card = build_session_context_card(
        normalized, npc_profile, payload, npc_memory=npc_memory
    )
    # [4단계] 플레이어의 언어 실력 및 응답 통계를 바탕으로 플레이어 프로필을 빌드합니다.
    profile = build_player_language_profile(normalized)
    # [5단계] 플레이어의 성공/재시도 통계 등을 통해 NPC의 현재 감정 상태(Emotion State)를 추론합니다.
    emotion_state = infer_npc_emotion_state(normalized)
    # [6단계] 플레이어 프로필과 감정 상태를 연동하여 대사 생성 정책(Dialogue Policy)을 정의합니다.
    policy = build_dialogue_policy(normalized, profile, emotion_state)
    
    candidate_text = str(normalized.get("candidate_text", "")).strip()
    
    # 2026-06-15 리팩토링: 이제 Candidate Text는 사용되지 않는 Deprecated 스펙입니다.
    # 만약 입력 페이로드에 이 값이 존재한다면 명시적인 오류를 발생시키고 에러 로그를 남깁니다.
    if candidate_text:
        import logging
        logger = logging.getLogger("backend.app.agents.agent_a")
        logger.error(f"Deprecated 'candidate_text' (npc_recast_line_candidate) detected in payload: {candidate_text}")
        raise ValueError(
            f"Error: 'candidate_text' field is deprecated and forbidden in Agent A inputs. "
            f"Detected value: '{candidate_text}'"
        )
    
    # [6.5단계] incivility_tier 및 profanity_mode 파싱
    incivility = payload.get("incivility") or {}
    incivility_tier = int(incivility.get("tier", 0))
    profanity_mode = os.getenv("MURPHY_NPC_PROFANITY_MIRROR_MODE", "off").strip().lower()
    
    # [7단계] 안전한 룰 기반 기본 응답(Fallback Result)을 1차적으로 빌드하고, use_llm이 True이면서 surface_goal이 있으면 룰베이스 다음 질문을 합성합니다.
    fallback_res = build_text_fallback(normalized)
    
    # Profanity Mirror / Firm 룰베이스 매트릭스 적용
    profanity_res = get_profanity_fallback_response(npc_profile.npc_id, incivility_tier, profanity_mode)
    if profanity_res:
        fallback_res.update({
            "npc_text": profanity_res["npc_text"],
            "text": profanity_res["npc_text"],
            "tts_text": profanity_res.get("tts_text") or profanity_res["npc_text"],
            "tone": profanity_res["tone"],
            "npc_emotion": profanity_res["npc_emotion"],
        })
    else:
        # retry/clarify 분기일 경우 룰베이스 대사 변주 적용
        branch_type = normalized.get("branch_type")
        dialogue_history = normalized.get("dialogue_history") or []
        turn_buffer = state.get("turn_buffer") or []
        surface_goal = normalized.get("dialogue_seed", {}).get("surface_goal") or ""
        
        last_npc_text = ""
        if turn_buffer:
            last_npc_text = turn_buffer[-1].get("npc_text") or ""
        elif dialogue_history:
            last_turn = dialogue_history[-1]
            last_npc_text = last_turn.get("npc_text_preview", "") if isinstance(last_turn, dict) else ""
            
        if branch_type in {"retry", "clarify"} and last_npc_text:
            current_text = fallback_res.get("npc_text") or fallback_res.get("text") or ""
            from backend.app.services.service_a.dialogue_policy_service import get_retry_variation
            varied_text = get_retry_variation(surface_goal, last_npc_text, current_text)
            fallback_res["npc_text"] = varied_text
            fallback_res["text"] = varied_text
            if "tts_text" in fallback_res:
                fallback_res["tts_text"] = varied_text
        
    use_llm = state.get("use_llm", False)
    surface_goal = normalized.get("dialogue_seed", {}).get("surface_goal") or ""
    is_complete_chapter = _is_complete_chapter_turn(normalized)
    
    purpose = normalized.get("dialogue_purpose") or ""
    # profanity_res가 없을 때만 surface_goal 질문을 합성합니다.
    if (
        use_llm
        and surface_goal
        and not is_complete_chapter
        and not profanity_res
        and purpose != "smalltalk_diagnostic"
        and not _is_passport_submission_refusal_branch(normalized)
    ):
        original_text = fallback_res.get("npc_text") or fallback_res.get("text") or ""
        synthesized_text = synthesize_fallback_next_question(
            original_text,
            surface_goal,
            _open_hooks_for_fallback_synthesis(normalized, session_context_card),
            branch_type=normalized.get("branch_type"),
        )
        fallback_res["npc_text"] = synthesized_text
        fallback_res["text"] = synthesized_text
        if "tts_text" in fallback_res:
            fallback_res["tts_text"] = synthesized_text
            
    # 룰베이스 경로(use_llm이 False일 때) 최종 tts_text 다듬기
    if not use_llm:
        raw_text = fallback_res.get("npc_text") or fallback_res.get("text") or ""
        polished_tts = polish_tts_text(
            raw_text,
            profile,
            emotion_state,
            policy,
            non_verbal_palette=npc_profile.non_verbal_palette,
        )
        fallback_res["tts_text"] = polished_tts
            
    resolved_emotion = fallback_res.get("npc_emotion") or emotion_state.emotion
    result = _apply_npc_profile(fallback_res, npc_profile, resolved_emotion)
        
    # [8단계] 생성 이력 추적용 메타데이터(Metadata)를 결과 사전(Dictionary)에 병합합니다.
    result = _with_generation_metadata(result, profile, emotion_state, policy, incivility_tier, profanity_mode)
    
    # [9단계] 갱신된 변수들을 가진 딕셔너리를 반환하여 상태를 업데이트합니다.
    return {
        "normalized": normalized,
        "npc_profile": npc_profile,
        "profile": profile,
        "emotion_state": emotion_state,
        "policy": policy,
        "result": result,
        "session_context_card": session_context_card,
    }


def route_after_init(state: NPCDialogueState) -> str:
    """초기화 노드 완료 후 LLM 대사 생성 흐름으로 분기할지 판단하는 라우팅 함수입니다."""
    use_llm = state.get("use_llm", False)
    if use_llm:
        return "generate_dialogue_llm"
    return END


def node_generate_dialogue_llm(state: NPCDialogueState, config: RunnableConfig | None = None) -> dict[str, Any]:
    """LangChain 및 LLM 클라이언트를 사용하여 감정 톤과 일레븐랩스 파라미터를 실시간으로 동적 튜닝하여 대사를 생성하는 노드입니다."""
    # [1단계] 상태(State)에서 필요한 캐싱 데이터와 클라이언트를 추출합니다.
    payload = state["payload"]
    normalized = state["normalized"]
    fallback_result = state["result"]
    
    # 직렬화 방지를 위해 config에서 llm_client를 우선적으로 추출합니다.
    llm_client = None
    if config and "configurable" in config:
        llm_client = config["configurable"].get("llm_client")
    if not llm_client:
        llm_client = state.get("llm_client")
        
    npc_profile = state["npc_profile"]
    callbacks = state.get("callbacks")
    session_context_card = state.get("session_context_card") or {}
    policy = state["policy"]

    # [2단계] 콜백 핸들러 구성 및 RunnableConfig 설정을 초기화합니다.
    run_config = config or RunnableConfig()
    if callbacks and not run_config.get("callbacks"):
        from langchain_core.callbacks import BaseCallbackHandler
        run_config = run_config.copy()
        run_config["callbacks"] = cast(list[BaseCallbackHandler], callbacks)

    try:
        # [3단계] 최종 LLM 클라이언트를 준비합니다.
        client: Any = llm_client or build_npc_dialogue_llm_client_from_environment()
        
        import logging
        logger = logging.getLogger("backend.app.agents.agent_a")
        dialogue_seed = payload.get("dialogue_seed")
        if not dialogue_seed:
            logger.warning("dialogue_seed is missing from payload in node_generate_dialogue_llm.")

        purpose = payload.get("dialogue_directive", {}).get("purpose", "")

        incivility = payload.get("incivility") or {}
        incivility_tier = int(incivility.get("tier", 0))
        profanity_mode = os.getenv("MURPHY_NPC_PROFANITY_MIRROR_MODE", "off").strip().lower()
        
        allowed_mild = sorted(list(allowed_for("mirror", "mild")))
        allowed_strong = sorted(list(allowed_for("mirror", "strong")))

        llm_payload = {
            "level_design_payload": payload,
            "normalized": normalized,
            "persona_instruction": npc_profile.persona_instruction, # Roster에서 매핑된 페르소나 탑재
            "fallback_candidate": {
                "speaker": fallback_result["speaker"],
                "npc_text": fallback_result["npc_text"],
                "tts_text": fallback_result["tts_text"],
                "tone": fallback_result["tone"],
                "feedback_kr": fallback_result["feedback_kr"],
                "fallback": fallback_result.get("fallback"),
            },
            "generation_profile": fallback_result["generation_profile"],
            "dialogue_seed": dialogue_seed or {},
            
            # Jinja 변수 바인딩
            "npc_role": npc_profile.role,
            "english_level": fallback_result["generation_profile"]["player_language"]["english_level"],
            "incivility_tier": incivility_tier,
            "profanity_mode": profanity_mode,
            "surface_goal": (dialogue_seed or {}).get("surface_goal") or "",
            "allowed_emotions": ["joy", "panic", "sad", "suspicion", "disgust", "fear", "smirk", "normal", "anger", "surprise", "pain", "confusion", "boredom"],
            "non_verbal_palette": npc_profile.non_verbal_palette,
            "allowed_mild": allowed_mild,
            "allowed_strong": allowed_strong,
            "room_id": payload.get("room_id"),
            "speaker_player_id": payload.get("speaker_player_id"),
            "bag_owner_player_id": payload.get("bag_owner_player_id"),
            "addressed_player_id": payload.get("addressed_player_id"),
            
            # smalltalk_diagnostic 변수들
            "purpose": purpose,
            "topic_switch": payload.get("dialogue_directive", {}).get("topic_switch", False),
            "length_target": payload.get("dialogue_directive", {}).get("length_target"),
            
            # Eokkka / Challenge 관련 변수들
            "suspicion_scope": normalized.get("suspicion_scope", "none"),
            "required_slots": payload.get("node_context", {}).get("required_slots", []),
            "dialogue_history": normalized.get("dialogue_history", []),
            "assigned_visit_location": normalized.get("assigned_visit_location", ""),
            "assigned_visit_location_ko": normalized.get("assigned_visit_location_ko", ""),
            "visit_location_difficulty": normalized.get("visit_location_difficulty", 0),
            "visit_location_suspicion_reason": normalized.get("visit_location_suspicion_reason", ""),
            "random_customs_item": normalized.get("random_customs_item", ""),
            "random_customs_item_difficulty": normalized.get("random_customs_item_difficulty", 0),
            "random_customs_item_suspicion_reason": normalized.get("random_customs_item_suspicion_reason", ""),
            
            # 세션 컨텍스트 카드 필드들
            "confirmed_facts": session_context_card.get("confirmed_facts", []),
            "forbidden_repeat_questions": session_context_card.get("forbidden_repeat_questions", []),
            "open_hooks": session_context_card.get("open_hooks", []),
            "closed_hooks": session_context_card.get("closed_hooks", []),
            "do_not_reopen": session_context_card.get("do_not_reopen", []),
            "social_obligation_lifecycle": session_context_card.get("social_obligation_lifecycle", "none"),
            "last_npc_intent": session_context_card.get("last_npc_intent", ""),
            "recent_turns_compact": session_context_card.get("recent_turns_compact", []),
            "topic_thread": session_context_card.get("topic_thread", []),
            "social_context": normalized.get("social_context", {}),
            "social_obligation_status": (normalized.get("social_context") or {}).get("obligation_status", ""),
            "social_pending_obligation": (normalized.get("social_context") or {}).get("pending_social_obligation", ""),
            "social_recommended_npc_move": (normalized.get("social_context") or {}).get("recommended_npc_move", ""),
            "branch_reason": normalized.get("branch_reason", ""),
            
            # 정책 관련 변수들
            "policy_action": policy.action,
            "policy_next_question_style": policy.next_question_style,
            "policy_max_sentence_count": policy.max_sentence_count,
        }

        # [4단계] 랭체인 1.0+ 규격에 부합하도록 invoke 또는 generate 호출을 수행합니다.
        if hasattr(client, "invoke"):
            llm_result = client.invoke(llm_payload, config=run_config)
        else:
            import inspect
            sig = inspect.signature(client.generate)
            if "callbacks" in sig.parameters:
                llm_result = client.generate(llm_payload, callbacks=run_config.get("callbacks"))
            else:
                llm_result = client.generate(llm_payload)
    except (NPCDialogueLLMUnavailable, httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
        import logging
        import traceback
        logging.getLogger("backend.app.agents.agent_a").error(
            "LLM ValueError type=%s msg=%s\n%s",
            type(exc).__name__, exc, traceback.format_exc(),
        )
        return {"error": type(exc).__name__}


    # [5단계] 출력 토큰 사용량 정보 및 원본 영어 텍스트를 확보합니다.
    llm_usage = llm_result.get("__llm_usage", {})
    npc_text = str(llm_result.get("npc_text") or "").strip()
    tts_text = str(llm_result.get("tts_text") or "").strip()

    if _has_retry_hook_leak(
        npc_text,
        tts_text,
        normalized,
    ):
        logger.error(
            "Retry LLM output leaked a callback hook. npc_text=%r",
            npc_text,
        )
        reason = (
            "immigration_retry_hook_violation"
            if _is_immigration_turn(normalized)
            else "retry_hook_violation"
        )
        return {"error": reason}
    
    # [5.2단계] retry/clarify 분기일 경우 긍정 리액션 차단, 톤 보정 및 피드백 보정 가드 적용
    branch_type = normalized.get("branch_type")
    next_action = normalized.get("next_action") or ""
    if branch_type in {"retry", "clarify", "warning"} or next_action in {"REASK", "GIVE_HINT", "WARNING"}:
        if llm_result.get("tone") not in {"formal_firm", "formal_stern", "formal_warning"}:
            llm_result["tone"] = "formal_firm"

        feedback_kr = str(llm_result.get("feedback_kr") or "").strip()
        if "좋아요" in feedback_kr or "잘했" in feedback_kr or "성공" in feedback_kr or "훌륭" in feedback_kr:
            llm_result["feedback_kr"] = "괜찮아요. 짧고 분명한 문장으로 다시 말해보세요."

        positive_patterns = [
            r"^good\b[.,!\s]*",
            r"^great\b[.,!\s]*",
            r"^nice\b[.,!\s]*",
            r"^thank\s+you\b[.,!\s]*",
            r"^thanks\b[.,!\s]*",
            r"^excellent\b[.,!\s]*",
            r"^perfect\b[.,!\s]*",
            r"^wonderful\b[.,!\s]*",
            r"^awesome\b[.,!\s]*",
        ]
        for pat in positive_patterns:
            if re.match(pat, npc_text, re.IGNORECASE):
                npc_text = re.sub(pat, "", npc_text, flags=re.IGNORECASE).strip()
                if npc_text:
                    npc_text = npc_text[0].upper() + npc_text[1:]
            if re.match(pat, tts_text, re.IGNORECASE):
                tts_text = re.sub(pat, "", tts_text, flags=re.IGNORECASE).strip()
                if tts_text:
                    tts_text = tts_text[0].upper() + tts_text[1:]
    
    # [5.3단계] 비-ADVANCE 분기 준수 가드 (대화 일관성 확보, CR-B-AB-DESYNC)
    next_action = normalized.get("next_action") or ""
    purpose = normalized.get("dialogue_purpose") or ""
    surface_goal = normalized.get("dialogue_seed", {}).get("surface_goal") or ""
    is_non_advance = (next_action in {"REASK", "GIVE_HINT", "WARNING"}) or (purpose in {"support_retry", "warn_and_control_risk"})
    
    if (
        is_non_advance
        and purpose != "smalltalk_diagnostic"
        and surface_goal
        and not _is_passport_submission_refusal_branch(normalized)
    ):
        def _extract_reaction_part(text: str) -> str:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
            reaction_sentences = []
            for s in sentences:
                if "?" in s:
                    break
                reaction_sentences.append(s)
            return " ".join(reaction_sentences)

        reaction_part = _extract_reaction_part(npc_text)
        if not reaction_part:
            reaction_part = "Pardon me?"

        synthesized = synthesize_fallback_next_question(
            reaction_part,
            surface_goal,
            branch_type=normalized.get("branch_type"),
        )
        turn_buffer = state.get("turn_buffer") or []
        dialogue_history = normalized.get("dialogue_history") or []
        last_npc_text = ""
        if turn_buffer:
            last_npc_text = turn_buffer[-1].get("npc_text") or ""
        elif dialogue_history:
            last_turn = dialogue_history[-1]
            last_npc_text = last_turn.get("npc_text_preview", "") if isinstance(last_turn, dict) else ""

        if last_npc_text:
            from backend.app.services.service_a.dialogue_policy_service import get_retry_variation
            npc_text = get_retry_variation(surface_goal, last_npc_text, synthesized)
        else:
            npc_text = synthesized

        # tts_text도 npc_text와 동일하게 맞춤
        tts_text = npc_text
    
    # [5.5단계] 비속어 및 욕설 후처리 검증 (ALWAYS_BLOCKED 및 허용되지 않은 비속어 감지 시 fallback 처리)
    # 1. ALWAYS_BLOCKED 감지 시 차단
    blocked_found = contains_blocked(npc_text) or contains_blocked(tts_text)
    if blocked_found:
        logger.error(f"Always-blocked profanity detected in LLM output. Detected: {blocked_found}")
        return {"error": "profanity_lexicon_violation"}
        
    # 2. mirror 모드 외에 비속어가 등장하거나 mirror 모드더라도 허용 범위 밖의 비속어가 쓰였는지 검증
    max_intensity = os.getenv("MURPHY_NPC_PROFANITY_MIRROR_MAX_INTENSITY", "mild").strip().lower()
    allowed_set = allowed_for(profanity_mode, max_intensity)
    
    words_npc = [w.strip(".,!?\"'();:") for w in npc_text.lower().split()]
    words_tts = [w.strip(".,!?\"'();:") for w in tts_text.lower().split()]
    
    for word in words_npc + words_tts:
        if word in MIRROR_ALLOWED_STRONG and word not in allowed_set:
            logger.error(f"Unallowed profanity word '{word}' detected under mode={profanity_mode}")
            return {"error": "profanity_lexicon_violation"}
            
    # tts_text에 대해 SSML break 태그 유효성 검증 및 시간 0.0s~3.0s 클램프 수행
    tts_text = validate_and_clamp_ssml(tts_text)

    if _is_complete_chapter_turn(normalized) and ("?" in npc_text or "?" in tts_text):
        logger.error(
            "Complete chapter LLM output asked a follow-up question. npc_text=%r",
            npc_text,
        )
        return {"error": "complete_chapter_question_violation"}

    global_violation = _global_dialogue_violation(
        npc_text,
        tts_text,
        normalized,
        payload,
    )
    if global_violation:
        logger.error(
            "Dialogue LLM output violated policy. reason=%s npc_text=%r",
            global_violation,
            npc_text,
        )
        return {"error": global_violation}

    # [6단계] 생성된 대사가 안전한 영문 아스키(ASCII) 텍스트인지 검사합니다.
    if not _is_safe_english_dialogue_text(npc_text) or not _is_safe_english_dialogue_text(tts_text):
        return {"error": "invalid_llm_dialogue_language"}

    # [신규 가드] duplicate_intent_question
    # 한 응답에 같은 의도의 질문이 두 번 나오면 차단
    # 문장 끝의 구두점을 유지하면서 문장을 분할합니다.
    sentences_for_dup = [s.strip() for s in re.split(r'(?<=[.!?])\s+', npc_text) if s.strip()]
    # 질문 의도 키워드 그룹
    INTENT_KEYWORDS_GROUPS = [
        {"purpose", "visit", "brings you"},
        {"how long", "stay", "duration", "days"},
        {"where", "stay", "staying", "address"},
        {"return ticket", "ticket"},
        {"job", "occupation", "do you do", "work"},
        {"first visit", "first time"},
    ]
    question_sentences = [s for s in sentences_for_dup if "?" in s or any(
        s.lower().startswith(w) for w in ("what", "where", "how", "do you",
                                           "could you", "may i", "is this", "are you")
    )]
    if len(question_sentences) >= 2:
        for group in INTENT_KEYWORDS_GROUPS:
            hit_count = sum(1 for sent in question_sentences
                            if any(kw in sent.lower() for kw in group))
            if hit_count >= 2:
                logger.error(
                    "Duplicate intent question detected: %r", npc_text[:120]
                )
                return {"error": "duplicate_intent_question"}

    # [신규 가드] clearance_failure_contradiction
    # success closing과 fail closing이 한 응답에 동시 출현하면 차단
    SUCCESS_CLOSING_MARKERS = (
        "enjoy your stay", "enjoy your trip", "go to baggage claim",
        "you are good to go", "you're good to go", "all set", "have a nice day",
        "all cleared", "you may proceed",
    )
    FAILURE_CLOSING_MARKERS = (
        "cannot complete", "secondary inspection", "interview is over",
        "denied", "must wait", "cannot proceed", "this is over",
    )
    npc_lower = npc_text.lower()
    has_success = any(m in npc_lower for m in SUCCESS_CLOSING_MARKERS)
    has_failure = any(m in npc_lower for m in FAILURE_CLOSING_MARKERS)
    if has_success and has_failure:
        logger.error(
            "Clearance/failure contradiction detected: %r", npc_text[:160]
        )
        return {"error": "clearance_failure_contradiction"}


    # 추천 표현(Recommended Expression)이 NPC 대사/TTS에 그대로 에코되는지 검사합니다.
    # 대소문자/구두점/공백/SSML 차이를 무시하고 npc_text와 tts_text를 함께 검사합니다.
    rec_exp = normalized.get("recommended_expression", "").strip()
    if rec_exp and _is_recommended_expression_echoed(rec_exp, npc_text, tts_text):
        logger.error(
            "Recommended expression echoed into NPC dialogue. rec_exp=%r npc_text=%r",
            rec_exp,
            npc_text,
        )
        return {"error": "recommended_expression_echo"}

    # surface_goal이 존재할 때 물음표 질문이 누락되었는지 검사합니다. (diagnostic 목적 하에서는 해제)
    surface_goal = (payload.get("dialogue_seed") or {}).get("surface_goal")
    purpose = payload.get("dialogue_directive", {}).get("purpose", "")
    if (
        surface_goal
        and purpose != "smalltalk_diagnostic"
        and not _is_passport_submission_refusal_branch(normalized)
    ):
        sentences = [s.strip() for s in re.split(r'[.!?]', npc_text) if s.strip()]
        if len(sentences) <= 1 and "?" not in npc_text:
            return {"error": "missing_followup_question"}

    # [신규 가드] 재질문 차단 가드 (repeats_confirmed_fact)
    forbidden_questions = session_context_card.get("forbidden_repeat_questions") or []
    npc_text_lower = npc_text.lower().strip()
    npc_text_clean = re.sub(r'[.!?,\'":;-]', '', npc_text_lower)
    for fq in forbidden_questions:
        fq_clean = re.sub(r'[.!?,\'":;-]', '', fq.lower())
        if fq_clean in npc_text_clean or npc_text_clean in fq_clean:
            logger.error(f"Post-processing violation: NPC dialogue repeats forbidden question: '{npc_text}' (matches: '{fq}')")
            return {"error": "repeats_confirmed_fact"}

    # [신규 가드] 꼬리물기 hook 가드 (weak_followup_no_hook)
    branch_type = normalized.get("branch_type", "neutral")
    open_hooks = session_context_card.get("open_hooks") or []
    if branch_type in {"success", "neutral"} and open_hooks and purpose != "smalltalk_diagnostic":
        sentences = [s.strip() for s in re.split(r'[.!?]', npc_text) if s.strip()]
        contains_hook = any(hook.lower() in npc_text_lower for hook in open_hooks)
        if not contains_hook and len(sentences) <= 1:
            logger.error(f"Post-processing violation: NPC dialogue lacks open_hooks {open_hooks} in a brief response: '{npc_text}'")
            return {"error": "weak_followup_no_hook"}

    # [신규 가드] speaker_role_confusion
    # NPC가 직전 턴에 요청/부탁을 했을 때, 이번 응답이 응답자(=player) 표현을
    # 포함하면 명시적으로 fallback 전환.
    LAST_TURN_REQUEST_MARKERS = (
        "could i borrow", "can i borrow", "may i borrow",
        "could you help", "can you help", "would you help",
        "could i have", "may i see", "can i get",
    )
    RESPONDER_PHRASE_MARKERS = (
        "here you are", "here you go", "here it is",
        "of course, take", "sure, take", "you can have it",
        "take it", "no problem, take",
    )

    last_npc_text = (state.get("last_npc_intent") or "").lower()
    # session_context_card의 recent_turns_compact 마지막 NPC 발화도 함께 확인
    card = state.get("session_context_card") or {}
    recent = card.get("recent_turns_compact") or []
    prev_npc_line = ""
    if recent:
        # 마지막 항목에서 NPC 부분만 추출 (포맷에 맞춰)
        prev_npc_line = str(recent[-1]).lower()

    was_request = any(m in last_npc_text or m in prev_npc_line
                      for m in LAST_TURN_REQUEST_MARKERS)
    is_responder = any(p in npc_text.lower() for p in RESPONDER_PHRASE_MARKERS)

    if was_request and is_responder:
        logger.error(
            "Speaker role confusion: NPC played responder role after own request. "
            "prev=%r curr=%r", prev_npc_line[:80], npc_text[:80]
        )
        return {"error": "speaker_role_confusion"}

    # [신규 가드] 비-ADVANCE 분기 준수 가드 (CR-B-AB-DESYNC)
    next_action = normalized.get("next_action") or ""
    is_non_advance = (next_action in {"REASK", "GIVE_HINT", "WARNING"})
    if (
        is_non_advance
        and purpose != "smalltalk_diagnostic"
        and not _is_passport_submission_refusal_branch(normalized)
    ):
        logger.info(f"Non-ADVANCE action '{next_action}' detected. Overriding LLM next question with current surface_goal '{surface_goal}'")
        sentences = [s.strip() for s in re.split(r'[.!?]', npc_text) if s.strip()]
        reaction_part = sentences[0] if sentences else ""
        overridden_text = synthesize_fallback_next_question(
            reaction_part,
            str(surface_goal),
            _open_hooks_for_fallback_synthesis(normalized, session_context_card),
            branch_type=normalized.get("branch_type"),
        )
        npc_text = overridden_text
        tts_text = overridden_text

    # coherence guard 신설 (smalltalk_diagnostic 전용)
    if purpose == "smalltalk_diagnostic":
        sentences = [s.strip() for s in re.split(r'[.!?]', npc_text) if s.strip()]
        
        # (a) 반응 없는 맨 질문 검사 (첫 문장이 질문이거나 전체 문장이 1개인데 질문인 경우)
        if sentences:
            first_sentence = sentences[0]
            first_idx = npc_text.find(first_sentence)
            if first_idx != -1:
                end_char = npc_text[first_idx + len(first_sentence):first_idx + len(first_sentence) + 1]
                if end_char == "?":
                    logger.error(f"Coherence violation: Naked question at the start of dialogue: {npc_text}")
                    return {"error": "coherence_violation_naked_question"}
            if len(sentences) == 1 and "?" in npc_text:
                logger.error(f"Coherence violation: Single question dialogue without reaction: {npc_text}")
                return {"error": "coherence_violation_naked_question"}
                
        # (b) 직전 발화와 비연결 턴 검사 (llm_reason에 [COHERENT] 누락 또는 [NON-SEQUITUR] 포함 검사)
        llm_reason_upper = llm_result.get("llm_reason", "").upper()
        if "NON-SEQUITUR" in llm_reason_upper or "COHERENT" not in llm_reason_upper:
            logger.error(f"Coherence violation: non-sequitur detected or coherent flag missing in llm_reason: {llm_result.get('llm_reason')}")
            return {"error": "coherence_violation_non_sequitur"}

        if _is_repeated_smalltalk_object_request(
            npc_text, tts_text, normalized, turn_buffer=state.get("turn_buffer")
        ):
            logger.error(
                "Smalltalk repeated object request detected after history/player correction: %r",
                npc_text,
            )
            return {"error": "smalltalk_repeated_object_request"}

        if _ignores_open_smalltalk_social_obligation(npc_text, tts_text, normalized):
            logger.error(
                "Smalltalk LLM output ignored an open social obligation: %r",
                npc_text,
            )
            return {"error": "smalltalk_social_obligation_ignored"}

    # topic_switch 전환구 강제 보정 (smalltalk_diagnostic 전용)
    topic_switch = payload.get("dialogue_directive", {}).get("topic_switch", False)
    if purpose == "smalltalk_diagnostic" and topic_switch:
        clean_text = npc_text.strip()
        starts_with_pivot = any(clean_text.startswith(p) for p in ["Anyway", "By the way", "Anyway,", "By the way,"])
        if not starts_with_pivot:
            npc_text = f"Anyway, {npc_text}"
            tts_clean = tts_text.strip()
            if tts_clean.startswith("<break"):
                break_end_idx = tts_clean.find("/>")
                if break_end_idx != -1:
                    tts_text = tts_clean[:break_end_idx+2] + " Anyway, " + tts_clean[break_end_idx+2:]
                else:
                    tts_text = f"Anyway, {tts_text}"
            else:
                tts_text = f"Anyway, {tts_text}"

    seed_fallback = _dict_value(fallback_result.get("fallback"))
    
    # [7단계] LLM이 직접 생성한 4대 파라미터와 최종 npc_emotion을 결과 딕셔너리에 바인딩합니다.
    npc_emotion = (
        normalized.get("npc_emotion")
        or llm_result.get("npc_emotion")
        or fallback_result["generation_profile"]["npc_emotion"]["emotion"]
    )
    from backend.app.services.service_a.animation_mapping_service import resolve_animation_by_emotion
    anim = resolve_animation_by_emotion(npc_profile.default_animation, npc_emotion)

    merged = {
        **fallback_result,
        "speaker": npc_profile.display_name,
        "npc_text": npc_text,
        "text": npc_text,
        "tts_text": tts_text,
        "feedback_kr": str(llm_result.get("feedback_kr") or fallback_result["feedback_kr"]),
        "tone": str(llm_result.get("tone") or fallback_result["tone"]),
        "animation": anim,
        "fallback": {"used": False, "reason": None},
        "npc_emotion": str(npc_emotion),
        "stability": llm_result.get("stability"),
        "style": llm_result.get("style"),
        "speed": llm_result.get("speed"),
        "similarity_boost": llm_result.get("similarity_boost"),
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
    
    # generation_profile 정보도 LLM이 결정한 동적 감정으로 동기화합니다.
    merged["generation_profile"]["npc_emotion"]["emotion"] = merged["npc_emotion"]
    
    return {"result": merged}


def route_after_llm(state: NPCDialogueState) -> str:
    """LLM 대사 생성 수행 후 에러 발생 시 fallback 노드로 흐름을 분기하기 위한 라우팅 함수입니다."""
    if "error" in state:
        return "apply_fallback"
    return END


def node_apply_fallback(state: NPCDialogueState) -> dict[str, Any]:
    """LLM 호출 오류 시 안전한 룰 기반 결과를 fallback으로 매핑하여 반환하는 노드입니다."""
    fallback_result = state["result"]
    error_reason = state.get("error", "UnknownError")
    
    fallback_result["llm"] = {
        "used": False,
        "fallback_used": True,
        "reason": error_reason,
    }
    return {"result": fallback_result}


def node_load_memory(state: NPCDialogueState) -> dict[str, Any]:
    """체크포인터 복원 결과가 처음이거나 비어있을 때 단기 메모리를 기본값으로 채우고 정리를 보조합니다."""
    from backend.app.services.service_a.npc_short_term_memory_service import clear_memory_state
    
    updates: dict[str, Any] = {}
    
    turn_buffer = state.get("turn_buffer")
    accumulated_slots = state.get("accumulated_slots")
    forbidden_questions = state.get("forbidden_questions")
    last_npc_intent = state.get("last_npc_intent")
    
    if turn_buffer is None:
        updates["turn_buffer"] = []
    if accumulated_slots is None:
        updates["accumulated_slots"] = {}
    if forbidden_questions is None:
        updates["forbidden_questions"] = []
    if last_npc_intent is None:
        updates["last_npc_intent"] = ""
        
    # 챕터 정리 펜딩 검사 및 비우기
    if state.get("_memory_cleanup_pending", False):
        base_state = {
            "turn_buffer": state.get("turn_buffer") or [],
            "accumulated_slots": state.get("accumulated_slots") or {},
            "forbidden_questions": state.get("forbidden_questions") or [],
            "last_npc_intent": state.get("last_npc_intent") or "",
        }
        cleared = clear_memory_state(base_state)
        updates.update(cleared)
        updates["_memory_cleanup_pending"] = False
        
    return updates


def node_persist_memory(state: NPCDialogueState) -> dict[str, Any]:
    """이번 턴의 대화 결과와 슬롯 획득 정보를 단기 메모리에 저장 및 업데이트합니다.
    
    Fail-fast 규칙에 따라 필수 키 누락 시 KeyError를 던집니다.
    """
    from backend.app.services.service_a.npc_short_term_memory_service import (
        append_turn,
        merge_slots,
        derive_forbidden_questions
    )
    
    result = state.get("result")
    payload = state.get("payload")
    normalized = state.get("normalized")
    
    if not result:
        raise KeyError("result is missing in state")
    if not payload:
        raise KeyError("payload is missing in state")
    if not normalized:
        raise KeyError("normalized is missing in state")
        
    npc_text = result.get("npc_text") or result.get("text")
    npc_id = normalized.get("npc_id")
    
    # Fail-fast 검사
    if npc_text is None:
        raise KeyError("npc_text is required in result")
    if npc_id is None:
        raise KeyError("npc_id is required in normalized payload")
        
    # 현재 턴에서 새로 채워진 슬롯들을 추출
    understanding = payload.get("understanding") or {}
    incoming_slots = understanding.get("extracted_slots") or {}
    
    # dialogue_seed의 filled_slots도 보조적으로 머지
    dialogue_seed = payload.get("dialogue_seed") or {}
    seed_slots = dialogue_seed.get("filled_slots") or {}
    incoming_slots = merge_slots(incoming_slots, seed_slots)
    
    # accumulated_slots 갱신
    current_slots = state.get("accumulated_slots") or {}
    new_accumulated_slots = merge_slots(current_slots, incoming_slots)
    
    # forbidden_questions 갱신
    new_forbidden = derive_forbidden_questions(new_accumulated_slots)
    
    # turn_buffer 갱신
    node_id = normalized.get("node_id") or ""
    surface_goal = dialogue_seed.get("surface_goal") or ""
    branch_type = normalized.get("branch_type") or "neutral"
    player_text = normalized.get("player_text") or ""
    npc_emotion = result.get("npc_emotion") or ""
    
    speaker_player_id = (
        payload.get("speaker_player_id")
        or payload.get("turn", {}).get("speaker_player_id")
    )

    base_memory = {
        "turn_buffer": state.get("turn_buffer") or [],
    }

    updated_memory = append_turn(
        base_memory,
        node_id=node_id,
        surface_goal=surface_goal,
        branch_type=branch_type,
        player_text=player_text,
        npc_text=npc_text,
        filled_slots=incoming_slots,
        npc_emotion=npc_emotion,
        speaker_player_id=speaker_player_id,
    )
    
    # last_npc_intent 갱신
    new_last_npc_intent = surface_goal
    
    # 챕터 완료 검사
    is_complete_chapter = _is_complete_chapter_turn(normalized)
    
    updates: dict[str, Any] = {
        "turn_buffer": updated_memory["turn_buffer"],
        "accumulated_slots": new_accumulated_slots,
        "forbidden_questions": new_forbidden,
        "last_npc_intent": new_last_npc_intent,
    }
    
    if is_complete_chapter:
        updates["_memory_cleanup_pending"] = True
        
    return updates


# 글로벌 싱글톤 캐시
_GRAPH_SINGLETON: Any | None = None

def _get_compiled_graph() -> Any:
    """NPCDialogue 에이전트 그래프의 컴파일본을 반환하는 내부 헬퍼 함수입니다.
    
    싱글톤 패턴으로 컴파일하며, InMemorySaver checkpointer를 부착합니다.
    """
    global _GRAPH_SINGLETON
    if _GRAPH_SINGLETON is None:
        try:
            from langgraph.checkpoint.memory import InMemorySaver
            checkpointer = InMemorySaver()
        except ImportError:
            try:
                from langgraph.checkpoint import MemorySaver  # type: ignore
                checkpointer = MemorySaver()
            except ImportError:
                raise RuntimeError("langgraph checkpointer unavailable; required for NPC memory")
                
        workflow = StateGraph(NPCDialogueState)
        
        workflow.add_node("load_memory", node_load_memory)
        workflow.add_node("initialize_state", node_initialize_state)
        workflow.add_node("generate_dialogue_llm", node_generate_dialogue_llm)
        workflow.add_node("apply_fallback", node_apply_fallback)
        workflow.add_node("persist_memory", node_persist_memory)
        
        workflow.add_edge(START, "load_memory")
        workflow.add_edge("load_memory", "initialize_state")
        
        workflow.add_conditional_edges(
            "initialize_state",
            route_after_init,
            {
                "generate_dialogue_llm": "generate_dialogue_llm",
                END: "persist_memory"
            }
        )
        workflow.add_conditional_edges(
            "generate_dialogue_llm",
            route_after_llm,
            {
                "apply_fallback": "apply_fallback",
                END: "persist_memory"
            }
        )
        workflow.add_edge("apply_fallback", "persist_memory")
        workflow.add_edge("persist_memory", END)
        
        _GRAPH_SINGLETON = workflow.compile(checkpointer=checkpointer)
        
    return _GRAPH_SINGLETON


def reset_graph_singleton_for_testing() -> None:
    """테스트 진행 시 메모리를 깨끗하게 비운 싱글톤으로 초기화하기 위한 헬퍼 함수입니다."""
    global _GRAPH_SINGLETON
    _GRAPH_SINGLETON = None


def build_npc_dialogue_graph() -> Any:
    """NPCDialogue 에이전트의 내부 LangGraph 상태 기계를 조립하여 컴파일합니다."""
    return _get_compiled_graph()


def generate_npc_dialogue_from_level_design(
    payload: dict[str, Any],
    use_llm: bool = False,
    llm_client: Any = None,
    callbacks: list[Any] | None = None,
) -> dict[str, Any]:
    """레벨 디자인 에이전트(Level Design Agent) JSON 데이터를 기반으로 컴파일된 LangGraph를 동작시켜 최종 대사 및 오디오 설정 사전을 도출합니다."""
    from backend.app.services.service_a.npc_short_term_memory_service import build_thread_id
    
    graph = _get_compiled_graph()
    
    # session_id, room_id, player_id, scope 추출
    session_id = (
        payload.get("session_id")
        or payload.get("turn", {}).get("session", {}).get("session_id")
        or ""
    )
    room_id = (
        payload.get("room_id")
        or payload.get("turn", {}).get("session", {}).get("room_id")
        or session_id
    )
    player_id = (
        payload.get("player_id")
        or payload.get("turn", {}).get("session", {}).get("player_id")
    )
    scope = payload.get("scope", "player")

    # npc_id 추출 및 정규화
    npc_id = _npc_id_from_payload(payload) or ""

    # thread_id 빌드 (fail-fast: 누락 시 ValueError)
    thread_id = build_thread_id(room_id, npc_id, player_id=player_id, scope=scope)
    
    config = {
        "configurable": {
            "thread_id": thread_id,
            "llm_client": llm_client,
        }
    }
    if callbacks:
        config["callbacks"] = callbacks  # type: ignore
        
    initial_state = {
        "payload": payload,
        "use_llm": use_llm,
        "llm_client": None,  # 직렬화 에러 방지를 위해 상태에는 None 전달
    }
    
    final_state = graph.invoke(initial_state, config=config)
    return final_state["result"]


def _level_design_feedback(feedback_note: str) -> str:
    """피드백 노트와 추천 표현을 조합하여 플레이어 대상 한글 학습 가이드를 생성하는 헬퍼 함수(Helper Function)입니다."""
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
    incivility_tier: int = 0,
    profanity_mode: str = "off",
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
        "incivility": {
            "tier": incivility_tier,
            "profanity_mode": profanity_mode,
        },
        "tts_style": build_tts_style_metadata(profile, emotion_state, policy),
    }
    return result


def _apply_npc_profile(result: dict[str, Any], npc_profile: NPCProfile, emotion: str) -> dict[str, Any]:
    """정의된 NPC 프로필의 기본 정보(화자 이름, 대기 애니메이션)를 결과 딕셔너리에 매핑합니다. 
    또한 감정에 따라 최종 애니메이션을 동적으로 결정합니다."""
    from backend.app.services.service_a.animation_mapping_service import resolve_animation_by_emotion
    anim = resolve_animation_by_emotion(npc_profile.default_animation, emotion)
    return {
        **result,
        "speaker": npc_profile.display_name,
        "animation": anim,
    }


def _npc_id_from_payload(payload: dict[str, Any]) -> str | None:
    """원본 페이로드 데이터에서 NPC ID를 식별하여 추출합니다."""
    npc = payload.get("npc")
    if not isinstance(npc, dict):
        return None
    value = npc.get("npc_id") or npc.get("id")
    return str(value) if value is not None else None


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
