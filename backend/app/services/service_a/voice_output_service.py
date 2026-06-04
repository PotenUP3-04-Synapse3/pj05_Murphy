from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from backend.app.services.service_a.developer_a_runtime_log_service import (
    write_developer_a_event,
)
from backend.app.services.service_a.npc_dialogue_agent_run_store import NPCDialogueAgentRunStore
from backend.app.services.service_a.tts_provider_service import FakeKokoroProvider
from backend.app.services.service_a.tts_provider_service import RealKokoroProvider
from backend.app.services.service_a.tts_service import (
    TTSAudio,
    TTSRequest,
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
    log_path = root / "logs" / "developer_a_events.jsonl"
    write_developer_a_event(
        log_path=log_path,
        component_name="VoiceOutputService",
        event="start",
        status="running",
        request_id=request_id,
        session_id=session_id,
    )

    try:
        normalized = normalize_level_design_payload(payload)
        dialogue = generate_npc_dialogue_from_level_design(payload, use_llm=use_llm_dialogue)
        voice_profile = resolve_voice_profile(
            user_id=user_id or str(payload.get("user_id", "")),
            npc_id="officer_miller",
        )
        tts_request = build_kokoro_provider_request(
            text=str(dialogue.get("tts_text") or dialogue["npc_text"]),
            speaker_id="officer_miller",
            voice_profile_id=voice_profile.voice_profile_id,
            kokoro_voice=voice_profile.voice_id,
            tone=str(dialogue["tone"]),
            english_level=str(normalized["english_level"]),
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
        tts = _build_kokoro_audio(
            tts_request=tts_request,
            runtime_root=root,
            use_real_tts=use_real_tts,
            audio_url_base=audio_url_base,
            node_id=str(normalized.get("node_id", "")),
            target_slot=str(normalized.get("target_slot", "")),
            branch_type=str(normalized.get("branch_type", "")),
        )
        agent_run, artifact, agent_run_path, artifact_path = _record_agent_run(
            payload=payload,
            normalized=normalized,
            dialogue=dialogue,
            tts=tts,
            run_root=run_root,
        )
        output = {
            **dialogue,
            "tts": tts,
            "agent_run_id": agent_run["agent_run_id"],
            "agent_run_path": str(agent_run_path),
            "artifact_path": str(artifact_path),
            "agent_run": agent_run,
            "agent_run_artifact": artifact,
        }
        write_developer_a_event(
            log_path=log_path,
            component_name="VoiceOutputService",
            event="end",
            status="ok",
            request_id=request_id,
            session_id=session_id,
            metadata={"provider": tts["provider"], "voice_id": tts["voice_id"]},
        )
        return output
    except Exception as exc:
        # Developer A는 branch를 바꾸지 않고 음성 실패 metadata만 반환한다.
        fallback_tts = build_audio_fallback(
            provider="kokoro",
            voice_id="am_michael",
            reason=type(exc).__name__,
        )
        write_developer_a_event(
            log_path=log_path,
            component_name="VoiceOutputService",
            event="error",
            status="failed",
            request_id=request_id,
            session_id=session_id,
            metadata={"error_type": type(exc).__name__},
        )
        agent_run, artifact, agent_run_path, artifact_path = _record_failed_agent_run(
            payload=payload,
            fallback_tts=fallback_tts,
            run_root=run_root,
            error=exc,
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
            "agent_run_path": str(agent_run_path),
            "artifact_path": str(artifact_path),
            "agent_run": agent_run,
            "agent_run_artifact": artifact,
        }


def _build_kokoro_audio(
    tts_request: Any,
    runtime_root: Path,
    use_real_tts: bool,
    audio_url_base: str | None,
    node_id: str | None = None,
    target_slot: str | None = None,
    branch_type: str | None = None,
) -> dict[str, Any]:
    voice = str(tts_request.provider_options["voice"])
    model_version = "kokoro-0.9.4" if use_real_tts else "fake-kokoro-v1"
    cache_key = build_audio_cache_key(
        text=tts_request.text,
        voice=voice,
        speed=tts_request.speaking_rate,
        sample_rate=tts_request.sample_rate,
        output_format=tts_request.output_format,
        model_version=model_version,
    )
    output_path = audio_output_path(
        root=runtime_root,
        cache_key=cache_key,
        output_format=tts_request.output_format,
        node_id=node_id,
        target_slot=target_slot,
        branch_type=branch_type,
        voice_id=voice,
    )
    provider = RealKokoroProvider() if use_real_tts else FakeKokoroProvider()
    metadata = provider.synthesize(tts_request, output_path)
    quality_metadata = analyze_wav_quality(output_path)
    audio_url = _build_audio_url(audio_url_base, output_path, runtime_root)
    return {
        **metadata,
        "audio_url": audio_url,
        "cache_key": cache_key,
        "quality_metadata": quality_metadata,
        "postprocess_policy": build_postprocess_policy(provider=str(metadata["provider"])),
    }


def _build_audio_url(audio_url_base: str | None, output_path: Path, runtime_root: Path) -> str | None:
    if not audio_url_base:
        return None
    relative_path = output_path.relative_to(runtime_root / "audio").as_posix()
    return f"{audio_url_base.rstrip('/')}/{relative_path}"


def _record_agent_run(
    *,
    payload: dict[str, Any],
    normalized: dict[str, Any],
    dialogue: dict[str, Any],
    tts: dict[str, Any],
    run_root: Path,
) -> tuple[dict[str, Any], dict[str, object], Path, Path]:
    evidence_metadata = build_npc_dialogue_evidence_summary(payload)
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

    evidence = evidence_metadata["evidence_summary"][0]
    artifact = build_npc_dialogue_artifact(
        agent_run_id=str(agent_run["agent_run_id"]),
        npc_id=_npc_id(payload),
        npc_text=str(dialogue.get("npc_text") or dialogue.get("text") or ""),
        tts_text=str(dialogue.get("tts_text") or dialogue.get("npc_text") or ""),
        feedback_kr=str(dialogue.get("feedback_kr", "")),
        audio_url=_optional_str(tts.get("audio_url")),
        audio_path=_optional_str(tts.get("audio_path")),
        source_id=str(evidence["source_id"]),
        source_snippet=str(evidence["snippet"]),
    )
    store = NPCDialogueAgentRunStore(run_root)
    return agent_run, artifact, store.append_agent_run(agent_run), store.append_artifact(artifact)


def _record_failed_agent_run(
    *,
    payload: dict[str, Any],
    fallback_tts: dict[str, Any],
    run_root: Path,
    error: Exception,
) -> tuple[dict[str, Any], dict[str, object], Path, Path]:
    evidence_metadata = build_npc_dialogue_evidence_summary(payload)
    evidence_metadata["fallback"] = {"used": True, "reason": type(error).__name__}
    evidence_metadata["tts_summary"] = _tts_summary(fallback_tts)
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
    artifact = build_npc_dialogue_artifact(
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
    return agent_run, artifact, store.append_agent_run(agent_run), store.append_artifact(artifact)


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
    }


def _npc_id(payload: dict[str, Any]) -> str:
    npc = _as_dict(payload.get("npc"))
    return str(npc.get("npc_id") or npc.get("id") or "officer_miller")


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
