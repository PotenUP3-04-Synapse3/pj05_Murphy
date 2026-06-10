from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os

from backend.app.agents.agent_a.npc_dialogue_agent import (
    NPCDialogueResult,
    generate_npc_dialogue_from_level_design,
)
from backend.app.middleware.middleware_a.npc_dialogue_agent_run_middleware import (
    NPCDialogueAgentRunMiddleware,
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
from backend.app.services.service_a.tts_provider_service import ChatterboxTTSProvider
from backend.app.services.service_a.tts_provider_service import EdgeTTSProvider
from backend.app.services.service_a.tts_provider_service import ElevenLabsTTSProvider
from backend.app.services.service_a.tts_provider_service import FakeKokoroProvider
from backend.app.services.service_a.tts_provider_service import RealKokoroProvider
from backend.app.services.service_a.tts_service import (
    TTSAudio,
    TTSRequest,
    build_chatterbox_provider_request,
    build_edge_provider_request,
    build_elevenlabs_provider_request,
    build_kokoro_provider_request,
    synthesize_speech,
)
from backend.app.services.service_a.voice_profile_service import resolve_voice_profile
from backend.app.tools.tool_a.npc_dialogue_artifact_tool import build_npc_dialogue_artifact
from backend.app.tools.tool_a.npc_dialogue_cost_tool import estimate_openai_cost_usd
from backend.app.tools.tool_a.npc_dialogue_evidence_tool import build_npc_dialogue_evidence_summary

PROMPT_VERSION = "npc_dialogue_prompt_v1"


@dataclass(frozen=True)
class VoiceOutput:
    dialogue: NPCDialogueResult
    audio: TTSAudio


def build_voice_output(dialogue: NPCDialogueResult) -> VoiceOutput:
    # Unreal 응답 조립은 Developer C 책임이므로 여기서는 voice payload만 묶는다.
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
    """Level Design JSON에서 NPC 대사와 fake Kokoro 음성 metadata를 함께 만든다."""
    root = runtime_root or Path("backend/runtime")
    run_root = agent_run_root or root / "agent_runs"
    agent_run_middleware = NPCDialogueAgentRunMiddleware()
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
        dialogue = generate_npc_dialogue_from_level_design(payload, use_llm=use_llm_dialogue)
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
        tts_provider_name = _selected_tts_provider(use_real_tts=use_real_tts)
        tts_request = _build_provider_request(
            provider_name=tts_provider_name,
            text=str(dialogue.get("tts_text") or dialogue["npc_text"]),
            speaker_id=npc_profile.npc_id,
            voice_profile_id=voice_profile.voice_profile_id,
            kokoro_voice=voice_profile.voice_id,
            tone=str(dialogue["tone"]),
            english_level=str(normalized["english_level"]),
            dialogue=dialogue,
        )
        agent_run_middleware.record_event(
            evidence_metadata,
            event="tool_call",
            status="completed",
            tool_name=f"tts_service.build_{tts_provider_name}_provider_request",
            output_summary={
                "provider": tts_request.provider,
                "voice": tts_request.provider_options.get("voice"),
                "lang_code": tts_request.provider_options.get("lang_code"),
                "rate": tts_request.provider_options.get("rate"),
                "volume": tts_request.provider_options.get("volume"),
                "pitch": tts_request.provider_options.get("pitch"),
                "audio_prompt_path": tts_request.provider_options.get("audio_prompt_path"),
                "exaggeration": tts_request.provider_options.get("exaggeration"),
                "cfg_weight": tts_request.provider_options.get("cfg_weight"),
                "temperature": tts_request.provider_options.get("temperature"),
                "device": tts_request.provider_options.get("device"),
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
        tts = _build_kokoro_audio(
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
        # Developer A는 branch를 바꾸지 않고 음성 실패 metadata만 반환한다.
        fallback_tts = build_audio_fallback(
            provider="kokoro",
            voice_id="am_michael",
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
            "animation": "officer_check_passport",
            "tts": fallback_tts,
            "fallback": {"used": True, "reason": "voice_output_error"},
            "agent_run_id": agent_run["agent_run_id"],
            "unified_agent_run_path": str(unified_agent_run_path),
            "readable_agent_run_path": str(readable_agent_run_path),
            "agent_run": agent_run,
        }


def _build_kokoro_audio(
    tts_request: Any,
    runtime_root: Path,
    use_real_tts: bool,
    audio_url_base: str | None,
    node_id: str | None = None,
    target_slot: str | None = None,
    branch_type: str | None = None,
    provider_name: str = "kokoro",
) -> dict[str, Any]:
    voice = str(tts_request.provider_options["voice"])
    model_version = _provider_cache_model_version(
        provider_name=provider_name,
        use_real_tts=use_real_tts,
        tts_request=tts_request,
    )
    cache_key = build_audio_cache_key(
        text=tts_request.text,
        voice=voice,
        speed=tts_request.speaking_rate,
        sample_rate=tts_request.sample_rate,
        output_format=tts_request.output_format,
        model_version=model_version,
        provider=provider_name,
    )
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
    provider = _resolve_tts_provider(provider_name=provider_name, use_real_tts=use_real_tts)
    metadata = provider.synthesize(tts_request, output_path)
    quality_metadata = analyze_wav_quality(output_path)
    audio_url = _build_audio_url(audio_url_base, output_path, runtime_root)
    return {
        **metadata,
        "audio_url": audio_url,
        "speaker_id": tts_request.speaker_id,
        "voice_profile_id": tts_request.voice_profile_id,
        "cache_key": cache_key,
        "quality_metadata": quality_metadata,
        "postprocess_policy": build_postprocess_policy(provider=str(metadata["provider"])),
    }


def _build_audio_url(audio_url_base: str | None, output_path: Path, runtime_root: Path) -> str | None:
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
    kokoro_voice: str,
    tone: str,
    english_level: str,
    dialogue: dict[str, Any],
) -> Any:
    if provider_name == "elevenlabs":
        return build_elevenlabs_provider_request(
            text=text,
            speaker_id=speaker_id,
            voice_profile_id=voice_profile_id,
            voice_id=_env_value("MURPHY_ELEVENLABS_VOICE_ID", "CwhRBWXzGAHq8TQ4Fs17"),
            tone=tone,
            english_level=english_level,
            api_key=_env_value("MURPHY_ELEVENLABS_API_KEY", _env_value("ELEVENLABS_API_KEY", "")),
            model_id=_env_value("MURPHY_ELEVENLABS_MODEL_ID", "eleven_flash_v2_5"),
            stability=_env_float("MURPHY_ELEVENLABS_STABILITY", _elevenlabs_stability_for_tone(tone)),
            similarity_boost=_env_float("MURPHY_ELEVENLABS_SIMILARITY_BOOST", 0.82),
            style=_env_float("MURPHY_ELEVENLABS_STYLE", _elevenlabs_style_for_tone(tone)),
            speed=_env_float("MURPHY_ELEVENLABS_SPEED", _elevenlabs_speed_for_tone(tone)),
            api_output_format=_env_value("MURPHY_ELEVENLABS_API_OUTPUT_FORMAT", "mp3_44100_128"),
            output_format=_env_value("MURPHY_ELEVENLABS_OUTPUT_FORMAT", "wav"),
            base_url=_env_value("MURPHY_ELEVENLABS_BASE_URL", "https://api.elevenlabs.io/v1"),
            timeout_seconds=_env_float("MURPHY_ELEVENLABS_TIMEOUT_SECONDS", 60.0),
            use_speaker_boost=_env_bool("MURPHY_ELEVENLABS_USE_SPEAKER_BOOST", True),
        )

    if provider_name == "chatterbox":
        return build_chatterbox_provider_request(
            text=text,
            speaker_id=speaker_id,
            voice_profile_id=voice_profile_id,
            voice_id=_env_value("MURPHY_CHATTERBOX_VOICE_ID", "officer_miller_ref"),
            tone=tone,
            english_level=english_level,
            audio_prompt_path=_env_value(
                "MURPHY_CHATTERBOX_REFERENCE_AUDIO",
                "backend/app/assets/voices/officer_miller_ref.wav",
            ),
            exaggeration=_env_float(
                "MURPHY_CHATTERBOX_EXAGGERATION",
                _chatterbox_exaggeration_for_tone(tone),
            ),
            cfg_weight=_env_float("MURPHY_CHATTERBOX_CFG_WEIGHT", _chatterbox_cfg_weight_for_tone(tone)),
            temperature=_env_float("MURPHY_CHATTERBOX_TEMPERATURE", 0.6),
            device=_env_value("MURPHY_CHATTERBOX_DEVICE", "auto"),
            language_id=_env_value("MURPHY_CHATTERBOX_LANGUAGE_ID", "en"),
            output_format=_env_value("MURPHY_CHATTERBOX_OUTPUT_FORMAT", "wav"),
        )

    if provider_name == "edge":
        return build_edge_provider_request(
            text=text,
            speaker_id=speaker_id,
            voice_profile_id=voice_profile_id,
            edge_voice=_env_value("MURPHY_EDGE_TTS_VOICE", "en-US-GuyNeural"),
            tone=tone,
            english_level=english_level,
            rate=_env_value("MURPHY_EDGE_TTS_RATE", "-5%"),
            volume=_env_value("MURPHY_EDGE_TTS_VOLUME", "+0%"),
            pitch=_env_value("MURPHY_EDGE_TTS_PITCH", "-2Hz"),
            output_format=_env_value("MURPHY_EDGE_TTS_OUTPUT_FORMAT", "wav"),
        )

    return build_kokoro_provider_request(
        text=text,
        speaker_id=speaker_id,
        voice_profile_id=voice_profile_id,
        kokoro_voice=kokoro_voice,
        tone=tone,
        english_level=english_level,
        emotion=str(
            dialogue.get("generation_profile", {})
            .get("npc_emotion", {})
            .get("emotion", "calm_official")
        ),
        emotion_intensity=float(
            dialogue.get("generation_profile", {})
            .get("npc_emotion", {})
            .get("intensity", 0.35)
        ),
    )


def _resolve_tts_provider(provider_name: str, use_real_tts: bool) -> Any:
    if not use_real_tts:
        return FakeKokoroProvider()
    if provider_name == "elevenlabs":
        return ElevenLabsTTSProvider()
    if provider_name == "chatterbox":
        return ChatterboxTTSProvider()
    if provider_name == "edge":
        return EdgeTTSProvider()
    return RealKokoroProvider()


def _selected_tts_provider(*, use_real_tts: bool) -> str:
    if not use_real_tts:
        return "kokoro"
    provider = _env_value("MURPHY_TTS_PROVIDER", "kokoro").lower()
    return provider if provider in {"kokoro", "edge", "chatterbox", "elevenlabs"} else "kokoro"


def _model_version(*, provider_name: str, use_real_tts: bool) -> str:
    if not use_real_tts:
        return "fake-kokoro-v1"
    if provider_name == "elevenlabs":
        return f"elevenlabs-{_env_value('MURPHY_ELEVENLABS_MODEL_ID', 'eleven_flash_v2_5')}"
    if provider_name == "chatterbox":
        return "chatterbox-tts"
    if provider_name == "edge":
        return "edge-tts-7.2.8"
    return "kokoro-0.9.4"


def _provider_cache_model_version(*, provider_name: str, use_real_tts: bool, tts_request: Any) -> str:
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
    if provider_name == "elevenlabs":
        return "tts_provider_service.elevenlabs.synthesize"
    if provider_name == "chatterbox":
        return "tts_provider_service.chatterbox.synthesize"
    if provider_name == "edge":
        return "tts_provider_service.edge.synthesize"
    return "tts_provider_service.KokoroProvider.synthesize"


def _env_value(key: str, default: str) -> str:
    return os.getenv(key) or _read_env_file(Path(".env")).get(key, default)


def _env_float(key: str, default: float) -> float:
    raw_value = _env_value(key, str(default))
    try:
        return float(raw_value)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw_value = _env_value(key, str(default)).lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    return default


def _elevenlabs_stability_for_tone(tone: str) -> float:
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
    if tone == "formal_warning":
        return 0.76
    if tone == "formal_stern":
        return 0.8
    if tone == "formal_firm":
        return 0.84
    return 0.86


def _chatterbox_exaggeration_for_tone(tone: str) -> float:
    if tone == "formal_warning":
        return 0.9
    if tone == "formal_stern":
        return 0.8
    if tone == "formal_firm":
        return 0.7
    if tone == "formal_supportive":
        return 0.5
    return 0.45


def _chatterbox_cfg_weight_for_tone(tone: str) -> float:
    if tone == "formal_warning":
        return 0.25
    if tone == "formal_stern":
        return 0.3
    if tone == "formal_firm":
        return 0.35
    return 0.45


def _read_env_file(path: Path) -> dict[str, str]:
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
    llm_metadata = _as_dict(dialogue.get("llm"))
    model_name = str(
        llm_metadata.get("model_name")
        or ("gpt-4o-mini" if llm_metadata.get("used") else "rule_based")
    )
    input_tokens = _int_from_metadata(llm_metadata.get("input_tokens"))
    output_tokens = _int_from_metadata(llm_metadata.get("output_tokens"))
    fallback = _as_dict(dialogue.get("fallback"))

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

    middleware = NPCDialogueAgentRunMiddleware()
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
    evidence_metadata["fallback"] = {"used": True, "reason": type(error).__name__}
    evidence_metadata["tts_summary"] = _tts_summary(fallback_tts)
    evidence_metadata["dialogue_source_trace"] = _failed_dialogue_source_trace(
        payload=payload,
        fallback_tts=fallback_tts,
        error=error,
    )
    middleware = NPCDialogueAgentRunMiddleware()
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
    return {
        "source_type": "level_design_json",
        "node_id": normalized.get("node_id") or payload.get("node_id"),
        "turn_id": payload.get("turn_id"),
        "chapter_id": payload.get("chapter_id"),
    }


def _tts_summary(tts: dict[str, Any]) -> dict[str, Any]:
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
    npc = _as_dict(payload.get("npc"))
    return resolve_npc_profile(_optional_str(npc.get("npc_id") or npc.get("id"))).npc_id


def _npc_emotion(payload: dict[str, Any], dialogue: dict[str, Any]) -> str:
    npc = _as_dict(payload.get("npc"))
    generation_profile = _as_dict(dialogue.get("generation_profile"))
    emotion = _as_dict(generation_profile.get("npc_emotion"))
    return str(npc.get("emotion") or emotion.get("emotion") or "unknown")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_from_metadata(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _optional_float(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _preview_text(value: Any, limit: int = 120) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
