from dataclasses import dataclass
from typing import Any, Literal, cast, TypedDict, NotRequired
import json

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
    # 개발자 B로부터 플레이어가 사용해야 할 추천 표현(Recommended Expression)을 획득합니다.
    recommended_expression = str(payload.level_hint.get("recommended_expression", "")).strip()

    # 분기 결과가 성공(Success)인 경우의 처리 흐름입니다.
    if branch_type == "success":
        return NPCDialogueResult(
            speaker="Hale",
            text=_success_text(payload),
            tone="formal_neutral",
            animation="move",
            feedback_kr=_success_feedback(recommended_expression),
        )

    # 분기 결과가 재시도(Retry)인 경우의 처리 흐름입니다.
    if branch_type == "retry":
        return NPCDialogueResult(
            speaker="Hale",
            text=_retry_text(payload),
            tone="formal_firm",
            animation="move",
            feedback_kr=_retry_feedback(recommended_expression),
        )

    # 기본값 또는 중립(Neutral) 분기일 경우의 예외적(Fallback) 처리 흐름입니다.
    return NPCDialogueResult(
        speaker="Hale",
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


def node_initialize_state(state: NPCDialogueState) -> dict[str, Any]:
    """입력 데이터 파싱, 프로필 로드, 감정 추론 및 기본 룰 기반 결과를 빌드하여 상태를 초기화하는 노드입니다."""
    # [1단계] 공유 상태(State)에서 원본 페이로드 데이터를 추출합니다.
    payload = state["payload"]
    # [2단계] 원본 페이로드(Payload)를 정규화(Normalize)합니다.
    normalized = normalize_level_design_payload(payload)
    # [3단계] 페이로드 정보에 매칭되는 NPC의 프로필(Profile)을 조회합니다.
    npc_profile = resolve_npc_profile(_npc_id_from_payload(payload))
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
        
    use_llm = state.get("use_llm", False)
    surface_goal = normalized.get("dialogue_seed", {}).get("surface_goal") or ""
    transition_status = normalized.get("transition", {}).get("status") or ""
    next_action = normalized.get("next_action") or ""
    is_complete_chapter = (transition_status == "complete_chapter" or next_action == "COMPLETE_CHAPTER")
    
    # profanity_res가 없을 때만 surface_goal 질문을 합성합니다.
    if use_llm and surface_goal and not is_complete_chapter and not profanity_res:
        original_text = fallback_res.get("npc_text") or fallback_res.get("text") or ""
        synthesized_text = synthesize_fallback_next_question(original_text, surface_goal)
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
        "result": result
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
    llm_client = state.get("llm_client")
    npc_profile = state["npc_profile"]
    callbacks = state.get("callbacks")

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
        # 에러 발생 시 상태 전이를 예외 처리 폴백 노드로 분기하기 위해 error를 세팅하여 반환합니다.
        return {"error": type(exc).__name__}


    # [5단계] 출력 토큰 사용량 정보 및 원본 영어 텍스트를 확보합니다.
    llm_usage = llm_result.get("__llm_usage", {})
    npc_text = str(llm_result.get("npc_text") or "").strip()
    tts_text = str(llm_result.get("tts_text") or "").strip()
    
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

    # [6단계] 생성된 대사가 안전한 영문 아스키(ASCII) 텍스트인지 검사합니다.
    if not _is_safe_english_dialogue_text(npc_text) or not _is_safe_english_dialogue_text(tts_text):
        return {"error": "invalid_llm_dialogue_language"}

    # 추천 표현(Recommended Expression)이 NPC 대사에 그대로 에코되는지 검사합니다.
    rec_exp = normalized.get("recommended_expression", "").strip()
    if rec_exp and rec_exp in npc_text:
        return {"error": "recommended_expression_echo"}

    # surface_goal이 존재할 때 물음표 질문이 누락되었는지 검사합니다.
    surface_goal = (payload.get("dialogue_seed") or {}).get("surface_goal")
    if surface_goal:
        import re
        sentences = [s.strip() for s in re.split(r'[.!?]', npc_text) if s.strip()]
        if len(sentences) <= 1 and "?" not in npc_text:
            return {"error": "missing_followup_question"}

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


def build_npc_dialogue_graph() -> Any:
    """NPCDialogue 에이전트의 내부 LangGraph 상태 기계를 조립하여 컴파일합니다."""
    workflow = StateGraph(NPCDialogueState)
    
    workflow.add_node("initialize_state", node_initialize_state)
    workflow.add_node("generate_dialogue_llm", node_generate_dialogue_llm)
    workflow.add_node("apply_fallback", node_apply_fallback)
    
    workflow.add_edge(START, "initialize_state")
    
    workflow.add_conditional_edges(
        "initialize_state",
        route_after_init,
        {
            "generate_dialogue_llm": "generate_dialogue_llm",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "generate_dialogue_llm",
        route_after_llm,
        {
            "apply_fallback": "apply_fallback",
            END: END
        }
    )
    workflow.add_edge("apply_fallback", END)
    
    return workflow.compile()


def generate_npc_dialogue_from_level_design(
    payload: dict[str, Any],
    use_llm: bool = False,
    llm_client: Any = None,
    callbacks: list[Any] | None = None,
) -> dict[str, Any]:
    """레벨 디자인 에이전트(Level Design Agent) JSON 데이터를 기반으로 컴파일된 LangGraph를 동작시켜 최종 대사 및 오디오 설정 사전을 도출합니다."""
    graph = build_npc_dialogue_graph()
    initial_state = {
        "payload": payload,
        "use_llm": use_llm,
        "llm_client": llm_client,
    }
    config = {}
    if callbacks:
        config["callbacks"] = callbacks
    final_state = graph.invoke(initial_state, config=config)
    return final_state["result"]


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
