from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os

from backend.app.agents.agent_a.npc_dialogue_agent import (
    NPCDialogueResult,
    generate_npc_dialogue_from_level_design,
)
from backend.app.agents.agent_a.npc_llm_client import NPCDialogueCallbackHandler
from backend.app.services.service_a.agent_run_recorder import (
    NPCDialogueAgentRunRecorder,
)
from backend.app.services.service_a.audio_quality_service import (
    analyze_wav_quality,
    build_postprocess_policy,
)
from backend.app.services.service_a.audio_storage_service import (
    audio_output_path,
    build_audio_cache_key,
)
from backend.app.services.service_a.developer_a_fallback_service import build_audio_fallback
from backend.app.services.service_a.developer_a_input_service import (
    normalize_level_design_payload,
)
from backend.app.services.service_a.npc_dialogue_agent_run_store import NPCDialogueAgentRunStore
from backend.app.services.service_a.npc_roster_service import resolve_npc_profile
from backend.app.services.service_a.tts_provider_service import (
    EdgeTTSProvider,
    ElevenLabsTTSProvider,
    FakeTTSProvider,
)
from backend.app.services.service_a.tts_service import (
    TTSAudio,
    TTSRequest,
    build_edge_provider_request,
    build_elevenlabs_provider_request,
    synthesize_speech,
)
from backend.app.services.service_a.voice_profile_service import resolve_voice_profile
from backend.app.tools.tool_a.npc_dialogue_artifact_tool import build_npc_dialogue_artifact
from backend.app.tools.tool_a.npc_dialogue_cost_tool import estimate_openai_cost_usd
from backend.app.tools.tool_a.npc_dialogue_evidence_tool import build_npc_dialogue_evidence_summary

PROMPT_VERSION = "npc_dialogue_prompt_v1"

# 13종 감정(Emotion)에 따른 ElevenLabs TTS의 기본 파라미터 매핑입니다.
# 형식: (stability, style, speed, similarity_boost)
EMOTION_TTS_PARAMETERS = {
    "joy": (0.65, 0.20, 0.95, 0.85),
    "panic": (0.30, 0.85, 1.10, 0.80),
    "sad": (0.60, 0.15, 0.75, 0.80),
    "suspicion": (0.55, 0.35, 0.85, 0.85),
    "disgust": (0.50, 0.40, 0.80, 0.80),
    "fear": (0.35, 0.80, 1.05, 0.80),
    "smirk": (0.60, 0.30, 0.90, 0.85),
    "normal": (0.72, 0.10, 0.86, 0.82),
    "anger": (0.40, 0.75, 1.00, 0.85),
    "surprise": (0.50, 0.50, 1.00, 0.80),
    "pain": (0.45, 0.60, 0.80, 0.80),
    "confusion": (0.55, 0.30, 0.85, 0.82),
    "boredom": (0.75, 0.05, 0.70, 0.80),
}



# NPC 대사 생성 결과(NPCDialogueResult)와 음성 파일(TTSAudio)을 하나의 객체로 묶어 제공하는 보관 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class VoiceOutput:
    dialogue: NPCDialogueResult
    audio: TTSAudio


def build_voice_output(dialogue: NPCDialogueResult) -> VoiceOutput:
    """NPC 대사와 가짜(Mock) 음성 데이터를 조립하여 단일 패키지로 반환합니다."""
    audio = synthesize_speech(
        TTSRequest(
            text=dialogue.text,
            speaker=dialogue.speaker,
            tone=dialogue.tone,
        )
    )
    return VoiceOutput(dialogue=dialogue, audio=audio)


def build_voice_output_from_level_design(
    payload: dict[str, Any],
    runtime_root: Path | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    use_real_tts: bool = False,
    use_llm_dialogue: bool = False,
    audio_url_base: str | None = None,
    agent_run_root: Path | None = None,
) -> dict[str, Any]:
    """레벨 디자인 에이전트 JSON을 수신하여 NPC 대사를 최종 튜닝하고 대응하는 TTS 음향 합성 자원을 결합해 조립합니다.
    
    이 함수는 개발자 A 컴포넌트의 통합 진입점(Entry Point) 역할을 수행합니다.
    """
    root = runtime_root or Path("backend/runtime")
    run_root = agent_run_root or root / "agent_runs"
    agent_run_middleware = NPCDialogueAgentRunRecorder()
    # 에이전트 실행 추적이 가능하도록 디버그 근거 요약을 빌드합니다.
    evidence_metadata = build_npc_dialogue_evidence_summary(payload)
    agent_run_middleware.record_event(
        evidence_metadata,
        event="agent_start",
        status="started",
        data_loaded={
            "request_id": request_id,
            "session_id": session_id,
            "payload_keys": sorted(payload.keys()),
        },
        input_summary={
            "node_id": payload.get("node_id"),
            "player_text": payload.get("player_text"),
        },
    )

    try:
        # 1. 원본 입력을 내부 처리 사양으로 정규화(Normalization)합니다.
        normalized = normalize_level_design_payload(payload)
        agent_run_middleware.record_event(
            evidence_metadata,
            event="tool_call",
            status="completed",
            tool_name="developer_a_input_service.normalize_level_design_payload",
            data_loaded={
                "node_id": normalized.get("node_id"),
                "english_level": normalized.get("english_level"),
                "branch_type": normalized.get("branch_type"),
                "target_slot": normalized.get("target_slot"),
            },
            output_summary={
                "candidate_text_available": bool(normalized.get("candidate_text")),
            },
        )
        # 2. 대화 생성 엔진을 구동하여 NPC 텍스트 대사를 생성합니다.
        # LangChain 콜백과 기존 미들웨어가 동시에 작동하도록 콜백 핸들러를 생성하여 주입합니다.
        callback_handler = NPCDialogueCallbackHandler(
            recorder=agent_run_middleware,
            metadata=evidence_metadata
        )
        dialogue = generate_npc_dialogue_from_level_design(
            payload,
            use_llm=use_llm_dialogue,
            callbacks=[callback_handler],
        )
        npc_profile = resolve_npc_profile(_npc_id(payload))
        agent_run_middleware.record_event(
            evidence_metadata,
            event="tool_call",
            status="completed",
            tool_name="agent_a.npc_dialogue_agent.generate_npc_dialogue_from_level_design",
            input_summary={
                "use_llm_dialogue": use_llm_dialogue,
                "prompt_version": PROMPT_VERSION,
            },
            output_summary={
                "npc_text": dialogue.get("npc_text") or dialogue.get("text"),
                "tone": dialogue.get("tone"),
                "fallback": dialogue.get("fallback"),
                "llm": dialogue.get("llm"),
            },
        )
        # 3. 사용자 및 NPC의 특성을 반영하여 일관된 목소리 프로필(Voice Profile)을 획득합니다.
        voice_profile = resolve_voice_profile(
            user_id=user_id or session_id or str(payload.get("user_id", "")),
            npc_id=npc_profile.npc_id,
        )
        agent_run_middleware.record_event(
            evidence_metadata,
            event="tool_call",
            status="completed",
            tool_name="voice_profile_service.resolve_voice_profile",
            data_loaded={
                "npc_id": npc_profile.npc_id,
                "voice_profile_id": voice_profile.voice_profile_id,
                "voice_id": voice_profile.voice_id,
            },
        )
        # 4. 사용될 TTS 엔진 종류를 판단하여 해당 엔진에 맞춘 데이터 구조를 인가합니다.
        tts_provider_name = _selected_tts_provider(use_real_tts=use_real_tts)
        tts_request = _build_provider_request(
            provider_name=tts_provider_name,
            text=str(dialogue.get("tts_text") or dialogue["npc_text"]),
            speaker_id=npc_profile.npc_id,
            voice_profile_id=voice_profile.voice_profile_id,
            voice_id=voice_profile.voice_id,
            tone=str(dialogue["tone"]),
            english_level=str(normalized["english_level"]),
            dialogue=dialogue,
            player_text=str(normalized.get("player_text", "")),
        )
        agent_run_middleware.record_event(
            evidence_metadata,
            event="tool_call",
            status="completed",
            tool_name=f"tts_service.build_{tts_provider_name}_provider_request",
            output_summary={
                "provider": tts_request.provider,
                "voice": tts_request.provider_options.get("voice"),
                "rate": tts_request.provider_options.get("rate"),
                "volume": tts_request.provider_options.get("volume"),
                "pitch": tts_request.provider_options.get("pitch"),
                "model_id": tts_request.provider_options.get("model_id"),
                "api_output_format": tts_request.provider_options.get("api_output_format"),
                "stability": tts_request.provider_options.get("stability"),
                "similarity_boost": tts_request.provider_options.get("similarity_boost"),
                "style": tts_request.provider_options.get("style"),
                "speed": tts_request.provider_options.get("speed"),
                "speaking_rate": tts_request.speaking_rate,
                "sample_rate": tts_request.sample_rate,
                "text_length": len(tts_request.text),
            },
        )
        # 5. 지정된 프로바이더(Provider)를 사용하여 음향 데이터 WAV 생성을 처리합니다.
        tts = _build_tts_audio(
            tts_request=tts_request,
            runtime_root=root,
            use_real_tts=use_real_tts,
            audio_url_base=audio_url_base,
            node_id=str(normalized.get("node_id", "")),
            target_slot=str(normalized.get("target_slot", "")),
            branch_type=str(normalized.get("branch_type", "")),
            provider_name=tts_provider_name,
        )
        agent_run_middleware.record_event(
            evidence_metadata,
            event="tool_call",
            status="completed",
            tool_name=_tts_provider_tool_name(tts_provider_name),
            output_summary={
                "provider": tts.get("provider"),
                "voice_id": tts.get("voice_id"),
                "audio_url": tts.get("audio_url"),
                "audio_path": tts.get("audio_path"),
                "status": tts.get("status"),
                "generation_speed": _tts_generation_speed(tts),
                "conversion_seconds": tts.get("conversion_seconds"),
            },
        )
        agent_run_middleware.record_event(
            evidence_metadata,
            event="agent_end",
            status="completed",
            output_summary={
                "npc_text": dialogue.get("npc_text") or dialogue.get("text"),
                "audio_url": tts.get("audio_url"),
                "fallback": dialogue.get("fallback"),
            },
        )
        # 6. 실행 상세 결과를 AgentRun 로그 DB에 파일로 기록 및 커밋합니다.
        (
            agent_run,
            unified_agent_run_path,
            readable_agent_run_path,
        ) = _record_agent_run(
            payload=payload,
            normalized=normalized,
            dialogue=dialogue,
            tts=tts,
            run_root=run_root,
            evidence_metadata=evidence_metadata,
            request_id=request_id,
            session_id=session_id,
        )
        output = {
            **dialogue,
            "tts": tts,
            "agent_run_id": agent_run["agent_run_id"],
            "unified_agent_run_path": str(unified_agent_run_path),
            "readable_agent_run_path": str(readable_agent_run_path),
            "agent_run": agent_run,
        }
        return output
    except Exception as exc:
        # 오류 발생 시 시스템 중단을 막기 위해 기본 텍스트 대사 및 오디오 폴백(Fallback) 개체를 신속히 구성해 제공합니다.
        fallback_tts = build_audio_fallback(
            provider="edge",
            voice_id="en-US-GuyNeural",
            reason=type(exc).__name__,
        )
        agent_run_middleware.record_event(
            evidence_metadata,
            event="agent_error",
            status="failed",
            error=type(exc).__name__,
        )
        (
            agent_run,
            unified_agent_run_path,
            readable_agent_run_path,
        ) = _record_failed_agent_run(
            payload=payload,
            fallback_tts=fallback_tts,
            run_root=run_root,
            error=exc,
            evidence_metadata=evidence_metadata,
            request_id=request_id,
            session_id=session_id,
        )
        return {
            "speaker": "Officer Miller",
            "npc_text": "Okay. Please continue.",
            "text": "Okay. Please continue.",
            "feedback_kr": "의미는 전달됐습니다. 조금 더 자연스럽게 말해 봅시다.",
            "tone": "formal_neutral",
            "animation": "move",
            "tts": fallback_tts,
            "fallback": {"used": True, "reason": "voice_output_error"},
            "agent_run_id": agent_run["agent_run_id"],
            "unified_agent_run_path": str(unified_agent_run_path),
            "readable_agent_run_path": str(readable_agent_run_path),
            "agent_run": agent_run,
        }


def _build_tts_audio(
    tts_request: Any,
    runtime_root: Path,
    use_real_tts: bool,
    audio_url_base: str | None,
    node_id: str | None = None,
    target_slot: str | None = None,
    branch_type: str | None = None,
    provider_name: str = "edge",
) -> dict[str, Any]:
    """선택된 TTS 엔진을 사용하여 실제로 오디오 음원 파일을 합성하고, 캐시 검사 및 품질 분석 메타데이터를 취합하여 반환합니다."""
    voice = str(tts_request.provider_options["voice"])
    model_version = _provider_cache_model_version(
        provider_name=provider_name,
        use_real_tts=use_real_tts,
        tts_request=tts_request,
    )
    # 캐싱(Caching) 파일 경로 식별을 위한 유일 해시 키를 획득합니다.
    cache_key = build_audio_cache_key(
        text=tts_request.text,
        voice=voice,
        speed=tts_request.speaking_rate,
        sample_rate=tts_request.sample_rate,
        output_format=tts_request.output_format,
        model_version=model_version,
        provider=provider_name,
    )
    # 음원 파일이 실제로 저장될 스토리지 절대 경로를 확보합니다.
    output_path = audio_output_path(
        root=runtime_root,
        cache_key=cache_key,
        output_format=tts_request.output_format,
        node_id=node_id,
        target_slot=target_slot,
        branch_type=branch_type,
        voice_id=voice,
        provider=provider_name,
    )
    # TTS 엔진 인터페이스를 동적 해독하여 음원 합성을 수행합니다.
    provider = _resolve_tts_provider(provider_name=provider_name, use_real_tts=use_real_tts)
    metadata = provider.synthesize(tts_request, output_path)
    # 윈도우 진폭 연산(RMS)을 이용해 침묵(Silence) 비율 등 파형 기본 정보를 획득합니다.
    quality_metadata = analyze_wav_quality(output_path)
    audio_url = _build_audio_url(audio_url_base, output_path, runtime_root)
    return {
        **metadata,
        "audio_url": audio_url,
        "speaker_id": tts_request.speaker_id,
        "voice_profile_id": tts_request.voice_profile_id,
        "cache_key": cache_key,
        "quality_metadata": quality_metadata,
        # 향후 2차 후처리를 위한 디렉티브 메타데이터를 추가합니다.
        "postprocess_policy": build_postprocess_policy(provider=str(metadata["provider"])),
    }


def _build_audio_url(audio_url_base: str | None, output_path: Path, runtime_root: Path) -> str | None:
    """웹 서버가 외부 클라이언트에 노출할 오디오 파일의 인터넷 주소(URL)를 조립합니다."""
    if not audio_url_base:
        return None
    relative_path = output_path.relative_to(runtime_root / "audio").as_posix()
    return f"{audio_url_base.rstrip('/')}/{relative_path}"


def _build_provider_request(
    *,
    provider_name: str,
    text: str,
    speaker_id: str,
    voice_profile_id: str,
    voice_id: str,
    tone: str,
    english_level: str,
    dialogue: dict[str, Any],
    player_text: str = "",
) -> Any:
    """설정된 TTS 엔진 명세에 대응되는 개별 파라미터 구조체(Request Object)를 분기 빌드합니다."""
    if provider_name == "elevenlabs":
        # dialogue에 들어있거나, fallback으로 지정될 npc_emotion을 획득합니다.
        emotion = dialogue.get("npc_emotion")
        if not emotion:
            generation_profile = dialogue.get("generation_profile") or {}
            emotion = (generation_profile.get("npc_emotion") or {}).get("emotion")
            
        emotion_params = EMOTION_TTS_PARAMETERS.get(emotion) if emotion else None

        stability_val = dialogue.get("stability")
        if stability_val is None:
            default_stability = emotion_params[0] if emotion_params else _elevenlabs_stability_for_tone(tone)
            stability_val = _env_float("MURPHY_ELEVENLABS_STABILITY", default_stability)

        similarity_boost_val = dialogue.get("similarity_boost")
        if similarity_boost_val is None:
            default_similarity = emotion_params[3] if emotion_params else 0.82
            similarity_boost_val = _env_float("MURPHY_ELEVENLABS_SIMILARITY_BOOST", default_similarity)

        style_val = dialogue.get("style")
        if style_val is None:
            default_style = emotion_params[1] if emotion_params else _elevenlabs_style_for_tone(tone)
            style_val = _env_float("MURPHY_ELEVENLABS_STYLE", default_style)

        speed_val = dialogue.get("speed")
        if speed_val is None:
            default_speed = emotion_params[2] if emotion_params else _elevenlabs_speed_for_tone(tone)
            speed_val = _env_float("MURPHY_ELEVENLABS_SPEED", default_speed)

        return build_elevenlabs_provider_request(
            text=text,
            speaker_id=speaker_id,
            voice_profile_id=voice_profile_id,
            voice_id=_env_value("MURPHY_ELEVENLABS_VOICE_ID", voice_id or "CwhRBWXzGAHq8TQ4Fs17"),
            tone=tone,
            english_level=english_level,
            api_key=_env_value("MURPHY_ELEVENLABS_API_KEY", _env_value("ELEVENLABS_API_KEY", "")),
            model_id=_env_value("MURPHY_ELEVENLABS_MODEL_ID", "eleven_flash_v2_5"),
            stability=stability_val,
            similarity_boost=similarity_boost_val,
            style=style_val,
            speed=speed_val,
            api_output_format=_env_value("MURPHY_ELEVENLABS_API_OUTPUT_FORMAT", "mp3_44100_128"),
            output_format=_env_value("MURPHY_ELEVENLABS_OUTPUT_FORMAT", "wav"),
            base_url=_env_value("MURPHY_ELEVENLABS_BASE_URL", "https://api.elevenlabs.io/v1"),
            timeout_seconds=_env_float("MURPHY_ELEVENLABS_TIMEOUT_SECONDS", 60.0),
            use_speaker_boost=_env_bool("MURPHY_ELEVENLABS_USE_SPEAKER_BOOST", True),
            previous_text=player_text if player_text.strip() else None,
        )

    # Edge TTS를 기본 및 명시 프로바이더로 구동합니다.
    return build_edge_provider_request(
        text=text,
        speaker_id=speaker_id,
        voice_profile_id=voice_profile_id,
        edge_voice=_env_value("MURPHY_EDGE_TTS_VOICE", voice_id or "en-US-GuyNeural"),
        tone=tone,
        english_level=english_level,
        rate=_env_value("MURPHY_EDGE_TTS_RATE", "-5%"),
        volume=_env_value("MURPHY_EDGE_TTS_VOLUME", "+0%"),
        pitch=_env_value("MURPHY_EDGE_TTS_PITCH", "-2Hz"),
        output_format=_env_value("MURPHY_EDGE_TTS_OUTPUT_FORMAT", "wav"),
    )


def _resolve_tts_provider(provider_name: str, use_real_tts: bool) -> Any:
    """합성 옵션을 분기 해석하여 실제 AI 인스턴스 또는 모의(Mock)용 프로바이더 인스턴스를 빌드해 제공합니다."""
    if not use_real_tts:
        return FakeTTSProvider()
    if provider_name == "elevenlabs":
        return ElevenLabsTTSProvider()
    return EdgeTTSProvider()


def _selected_tts_provider(*, use_real_tts: bool) -> str:
    """환경 변수 및 설정을 기반으로 활성화할 타겟 TTS 프로바이더 이름을 판별합니다."""
    if not use_real_tts:
        return "edge"
    provider = _env_value("MURPHY_TTS_PROVIDER", "edge").lower()
    return provider if provider in {"edge", "elevenlabs"} else "edge"


def _model_version(*, provider_name: str, use_real_tts: bool) -> str:
    """캐시 키 식별을 위한 타겟 TTS의 릴리즈 가중치 모델 및 라이브러리 버전을 문자열로 매핑합니다."""
    if not use_real_tts:
        return "fake-tts-v1"
    if provider_name == "elevenlabs":
        return f"elevenlabs-{_env_value('MURPHY_ELEVENLABS_MODEL_ID', 'eleven_flash_v2_5')}"
    return "edge-tts-7.2.8"


def _provider_cache_model_version(*, provider_name: str, use_real_tts: bool, tts_request: Any) -> str:
    """TTS 엔진별로 캐싱 타겟 여부를 조율하기 위해 추가 파라미터를 보정한 정밀 캐시 모델 버전을 조립합니다."""
    model_version = _model_version(provider_name=provider_name, use_real_tts=use_real_tts)
    if provider_name != "elevenlabs":
        return model_version
    options = tts_request.provider_options
    return "|".join(
        [
            model_version,
            f"stability={options.get('stability')}",
            f"similarity={options.get('similarity_boost')}",
            f"style={options.get('style')}",
            f"speed={options.get('speed')}",
            f"format={options.get('api_output_format')}",
        ]
    )


def _tts_provider_tool_name(provider_name: str) -> str:
    """AgentRun 로그 타임라인 기록 시 식별을 위한 하위 툴 클래스의 메서드 지표 이름을 문자열로 매핑합니다."""
    if provider_name == "elevenlabs":
        return "tts_provider_service.elevenlabs.synthesize"
    return "tts_provider_service.edge.synthesize"


def _env_value(key: str, default: str) -> str:
    """안전하게 OS 환경 변수 또는 로컬 .env 설정 파일에서 환경 설정을 우선순위대로 획득합니다."""
    return os.getenv(key) or _read_env_file(Path(".env")).get(key, default)


def _env_float(key: str, default: float) -> float:
    """환경 설정에 정의된 문자열 값을 파싱하여 소수점(Float) 수치로 가져옵니다."""
    raw_value = _env_value(key, str(default))
    try:
        return float(raw_value)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    """설정된 환경 매개변수 값(True/False, 1/0 등)을 부울(Boolean) 참/거짓 값으로 분석합니다."""
    raw_value = _env_value(key, str(default)).lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    return default


def _elevenlabs_stability_for_tone(tone: str) -> float:
    """ElevenLabs 성우의 감정 톤(Tone)에 가장 어울리는 기본 목소리 안정성(Stability) 지표를 매핑합니다."""
    if tone == "formal_warning":
        return 0.38
    if tone == "formal_stern":
        return 0.52
    if tone == "formal_firm":
        return 0.62
    if tone == "formal_supportive":
        return 0.68
    return 0.72


def _elevenlabs_style_for_tone(tone: str) -> float:
    """ElevenLabs 성우의 감정에 어울리는 어조 과장 수준(Style) 지표를 조율합니다."""
    if tone == "formal_warning":
        return 0.78
    if tone == "formal_stern":
        return 0.42
    if tone == "formal_firm":
        return 0.28
    if tone == "formal_supportive":
        return 0.18
    return 0.1


def _elevenlabs_speed_for_tone(tone: str) -> float:
    """ElevenLabs 발화 어조 속도를 매핑합니다."""
    if tone == "formal_warning":
        return 0.76
    if tone == "formal_stern":
        return 0.8
    if tone == "formal_firm":
        return 0.84
    return 0.86


def _read_env_file(path: Path) -> dict[str, str]:
    """로컬 .env 파일을 키-값 매핑 구조로 해독합니다."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _record_agent_run(
    *,
    payload: dict[str, Any],
    normalized: dict[str, Any],
    dialogue: dict[str, Any],
    tts: dict[str, Any],
    run_root: Path,
    evidence_metadata: dict[str, Any],
    request_id: str | None,
    session_id: str | None,
) -> tuple[dict[str, Any], Path, Path]:
    """에이전트 구동에 따른 성공 실행 상태 기록을 수집하고 로그(AgentRun) 파일로 구조화해 씁니다."""
    llm_metadata = _as_dict(dialogue.get("llm"))
    model_name = str(
        llm_metadata.get("model_name")
        or ("gpt-4o-mini" if llm_metadata.get("used") else "rule_based")
    )
    input_tokens = _int_from_metadata(llm_metadata.get("input_tokens"))
    output_tokens = _int_from_metadata(llm_metadata.get("output_tokens"))
    fallback = _as_dict(dialogue.get("fallback"))

    # 실행 근거 메타데이터를 강화해 줍니다.
    evidence_metadata["npc_context"] = {
        "npc_id": _npc_id(payload),
        "npc_emotion": _npc_emotion(payload, dialogue),
        "tone": dialogue.get("tone"),
    }
    evidence_metadata["tts_summary"] = _tts_summary(tts)
    evidence_metadata["dialogue_source_trace"] = _dialogue_source_trace(
        payload=payload,
        normalized=normalized,
        dialogue=dialogue,
        tts=tts,
    )
    evidence_metadata["fallback"] = {
        "used": bool(fallback.get("used", False)),
        "reason": fallback.get("reason"),
    }

    # 미들웨어를 사용하여 레코드 조립을 실행합니다.
    middleware = NPCDialogueAgentRunRecorder()
    agent_run = middleware.start_run(
        prompt_version=PROMPT_VERSION,
        source_window=_source_window(payload, normalized),
        cache_key=f"sha256:{tts.get('cache_key', 'no_cache_key')}",
        model_name=model_name,
        permission_level="runtime_user_session",
        metadata=evidence_metadata,
    )
    agent_run = middleware.complete_run(
        agent_run,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_openai_cost_usd(
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    )

    # 영구 저장소에 최종 레코드를 보관 조치합니다.
    store = NPCDialogueAgentRunStore(run_root)
    unified_path, readable_path = store.append_unified_agent_run(
        agent_run,
        owner="developer_a",
        request_id=request_id or _optional_str(payload.get("request_id")),
        session_id=session_id or _optional_str(payload.get("session_id")),
        turn_index=_optional_int(payload.get("turn_index")),
        summary={
            "input": payload.get("player_text") or _as_dict(payload.get("player")).get("utterance"),
            "output": dialogue.get("npc_text") or dialogue.get("text"),
            "fallback_used": evidence_metadata["fallback"]["used"],
            "audio_url": tts.get("audio_url"),
        },
        artifact_path=None,
    )
    return agent_run, unified_path, readable_path


def _record_failed_agent_run(
    *,
    payload: dict[str, Any],
    fallback_tts: dict[str, Any],
    run_root: Path,
    error: Exception,
    evidence_metadata: dict[str, Any],
    request_id: str | None,
    session_id: str | None,
) -> tuple[dict[str, Any], Path, Path]:
    """예외 처리 발생 시 실패 상태 레코드(AgentRun Failed)를 조립하여 기록합니다."""
    evidence_metadata["fallback"] = {"used": True, "reason": type(error).__name__}
    evidence_metadata["tts_summary"] = _tts_summary(fallback_tts)
    evidence_metadata["dialogue_source_trace"] = _failed_dialogue_source_trace(
        payload=payload,
        fallback_tts=fallback_tts,
        error=error,
    )
    middleware = NPCDialogueAgentRunRecorder()
    agent_run = middleware.start_run(
        prompt_version=PROMPT_VERSION,
        source_window=_source_window(payload, {}),
        cache_key="sha256:fallback",
        model_name="fallback",
        permission_level="runtime_user_session",
        metadata=evidence_metadata,
    )
    agent_run = middleware.fail_run(agent_run, error=type(error).__name__)
    evidence = evidence_metadata["evidence_summary"][0]
    # 디버깅 편의를 위해 아티팩트도 함께 조립합니다.
    _artifact = build_npc_dialogue_artifact(
        agent_run_id=str(agent_run["agent_run_id"]),
        npc_id=_npc_id(payload),
        npc_text="Okay. Please continue.",
        tts_text="Okay. Please continue.",
        feedback_kr="응답을 이어갈 수 있도록 기본 대사를 반환했습니다.",
        audio_url=_optional_str(fallback_tts.get("audio_url")),
        audio_path=_optional_str(fallback_tts.get("audio_path")),
        source_id=str(evidence["source_id"]),
        source_snippet=str(evidence["snippet"]),
    )
    store = NPCDialogueAgentRunStore(run_root)
    unified_path, readable_path = store.append_unified_agent_run(
        agent_run,
        owner="developer_a",
        request_id=request_id or _optional_str(payload.get("request_id")),
        session_id=session_id or _optional_str(payload.get("session_id")),
        turn_index=_optional_int(payload.get("turn_index")),
        summary={
            "input": payload.get("player_text") or _as_dict(payload.get("player")).get("utterance"),
            "output": "Okay. Please continue.",
            "fallback_used": True,
            "audio_url": fallback_tts.get("audio_url"),
        },
        artifact_path=None,
    )
    return agent_run, unified_path, readable_path


def _source_window(payload: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    """게임 클라이언트 시나리오 윈도우(Scenario Window)의 생명 주기 데이터를 파싱합니다."""
    return {
        "source_type": "level_design_json",
        "node_id": normalized.get("node_id") or payload.get("node_id"),
        "turn_id": payload.get("turn_id"),
        "chapter_id": payload.get("chapter_id"),
    }


def _tts_summary(tts: dict[str, Any]) -> dict[str, Any]:
    """합성 완료된 음원 정보의 핵심 요약 정보를 빌드합니다."""
    return {
        "provider": tts.get("provider"),
        "voice_id": tts.get("voice_id"),
        "sample_rate": tts.get("sample_rate"),
        "audio_url": tts.get("audio_url"),
        "audio_path": tts.get("audio_path"),
        "status": tts.get("status"),
        "generation_speed": _tts_generation_speed(tts),
    }


def _tts_generation_speed(tts: dict[str, Any]) -> dict[str, Any]:
    """합성 속도 및 실시간 계수(Real-time Factor) 연산 통계를 조립합니다."""
    return {
        "generation_seconds": _optional_float(tts.get("generation_seconds")),
        "audio_seconds": _optional_float(tts.get("audio_seconds")),
        "real_time_factor": _optional_float(tts.get("real_time_factor")),
    }


def _dialogue_source_trace(
    *,
    payload: dict[str, Any],
    normalized: dict[str, Any],
    dialogue: dict[str, Any],
    tts: dict[str, Any],
) -> dict[str, Any]:
    """에이전트 실행에 직접 인가된 모든 변수와 인자 상태를 역추적(Trace)하기 위한 상세 지도를 그립니다."""
    npc_profile = resolve_npc_profile(_npc_id(payload))
    node_context = _as_dict(payload.get("node_context"))
    evaluation_summary = _as_dict(payload.get("evaluation_summary") or payload.get("evaluation"))
    level_hint = _as_dict(payload.get("level_hint"))
    in_game_feedback = _as_dict(payload.get("in_game_feedback"))
    branch = _as_dict(payload.get("branch"))
    candidate_text = str(normalized.get("candidate_text") or "").strip()
    llm = _as_dict(dialogue.get("llm"))
    llm_used = bool(llm.get("used"))
    seed_fallback_used = bool(llm.get("seed_fallback_used"))

    return {
        "npc_profile": {
            "npc_id": npc_profile.npc_id,
            "display_name": npc_profile.display_name,
            "role": npc_profile.role,
        },
        "used_inputs": {
            "node_context": {
                "used_for": "next_question_and_goal",
                "node_id": normalized.get("node_id") or payload.get("node_id"),
                "npc_question_goal": node_context.get("npc_question_goal"),
            },
            "player_text": {
                "used_for": "dialogue_evidence_preview",
                "value_preview": _preview_text(
                    payload.get("player_text") or _as_dict(payload.get("player")).get("utterance")
                ),
            },
            "developer_b_evaluation": {
                "used_for": "tone_and_progression_context",
                "branch_type": normalized.get("branch_type"),
                "task_success": evaluation_summary.get("task_success"),
                "clarity": evaluation_summary.get("clarity"),
                "feedback_note": evaluation_summary.get("feedback_note"),
            },
            "developer_b_feedback": {
                "used_for": "recast_candidate_and_feedback_note",
                "npc_recast_line_candidate": in_game_feedback.get("npc_recast_line_candidate"),
                "feedback_strategy": in_game_feedback.get("feedback_strategy"),
                "recommended_expression": level_hint.get("recommended_expression"),
                "needs_hint": level_hint.get("needs_hint"),
            },
            "branch": {
                "used_for": "next_node_continuity",
                "branch_type": branch.get("branch_type") or normalized.get("branch_type"),
                "next_node_id": branch.get("next_node_id"),
            },
            "voice_profile": {
                "used_for": "tts_voice_selection",
                "voice_profile_id": tts.get("voice_profile_id"),
                "voice_id": tts.get("voice_id"),
                "speaker_id": tts.get("speaker_id"),
                "provider": tts.get("provider"),
            },
        },
        "voice_profile": {
            "voice_profile_id": tts.get("voice_profile_id"),
            "voice_id": tts.get("voice_id"),
            "speaker_id": tts.get("speaker_id"),
            "provider": tts.get("provider"),
        },
        "output_decision": {
            "npc_text_source": _npc_text_source(
                llm_used=llm_used,
                seed_fallback_used=seed_fallback_used,
                candidate_text=candidate_text,
            ),
            "tts_text_source": "llm_dialogue" if llm_used else "tts_text_polisher_service",
            "npc_text_preview": _preview_text(dialogue.get("npc_text") or dialogue.get("text")),
            "tts_text_preview": _preview_text(dialogue.get("tts_text")),
            "audio_url": tts.get("audio_url"),
        },
    }


def _npc_text_source(*, llm_used: bool, seed_fallback_used: bool, candidate_text: str) -> str:
    """대화 텍스트가 최종적으로 파싱/생성된 출처를 식별합니다."""
    if llm_used and seed_fallback_used:
        return "llm_dialogue_from_fallback_seed"
    if llm_used:
        return "llm_dialogue"
    return "developer_b_recast_candidate" if candidate_text else "developer_a_fallback"


def _failed_dialogue_source_trace(
    *,
    payload: dict[str, Any],
    fallback_tts: dict[str, Any],
    error: Exception,
) -> dict[str, Any]:
    """오류 폴백 상태에서의 획득 출처 지도를 조립합니다."""
    npc_profile = resolve_npc_profile(_npc_id(payload))
    return {
        "npc_profile": {
            "npc_id": npc_profile.npc_id,
            "display_name": npc_profile.display_name,
            "role": npc_profile.role,
        },
        "used_inputs": {
            "payload_keys": sorted(payload.keys()),
        },
        "voice_profile": {
            "voice_id": fallback_tts.get("voice_id"),
            "provider": fallback_tts.get("provider"),
        },
        "output_decision": {
            "npc_text_source": "developer_a_error_fallback",
            "tts_text_source": "developer_a_error_fallback",
            "error": type(error).__name__,
        },
    }


def _npc_id(payload: dict[str, Any]) -> str:
    """입력 데이터 구조에서 매핑되는 NPC 고유 코드를 찾아 안전 반환합니다."""
    npc = _as_dict(payload.get("npc"))
    return resolve_npc_profile(_optional_str(npc.get("npc_id") or npc.get("id"))).npc_id


def _npc_emotion(payload: dict[str, Any], dialogue: dict[str, Any]) -> str:
    """NPC의 감정 상태 텍스트를 추출합니다."""
    npc = _as_dict(payload.get("npc"))
    generation_profile = _as_dict(dialogue.get("generation_profile"))
    emotion = _as_dict(generation_profile.get("npc_emotion"))
    return str(npc.get("emotion") or emotion.get("emotion") or "unknown")


def _as_dict(value: Any) -> dict[str, Any]:
    """Null 또는 기타 자료형을 안전하게 사전(Dictionary)으로 치환합니다."""
    return value if isinstance(value, dict) else {}


def _int_from_metadata(value: Any) -> int:
    """안전 정수 변환 유틸리티 함수입니다."""
    return value if isinstance(value, int) else 0


def _optional_str(value: Any) -> str | None:
    """안전 문자열 캐스팅 함수입니다."""
    return str(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    """안전 정수 또는 Null 반환 함수입니다."""
    return value if isinstance(value, int) else None


def _optional_float(value: Any) -> float | None:
    """안전 실수 또는 Null 반환 함수입니다."""
    return float(value) if isinstance(value, int | float) else None


def _preview_text(value: Any, limit: int = 120) -> str | None:
    """긴 대사 텍스트를 로그에서 보기 편하게 특정 임계치 길이로 슬라이싱해 주는 요약용 유틸리티 함수입니다."""
    if value is None:
        return None
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
