from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.agents.agent_a.npc_dialogue_agent import (
    NPCDialogueResult,
    generate_npc_dialogue_from_level_design,
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
from backend.app.services.service_a.tts_provider_service import FakeKokoroProvider
from backend.app.services.service_a.tts_provider_service import RealKokoroProvider
from backend.app.services.service_a.tts_service import (
    TTSAudio,
    TTSRequest,
    build_kokoro_provider_request,
    synthesize_speech,
)
from backend.app.services.service_a.voice_profile_service import resolve_voice_profile


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
) -> dict[str, Any]:
    """Level Design JSON에서 NPC 대사와 fake Kokoro 음성 metadata를 함께 만든다."""
    root = runtime_root or Path("backend/runtime")
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
        output = {**dialogue, "tts": tts}
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
        return {
            "speaker": "Officer Miller",
            "npc_text": "Okay. Please continue.",
            "text": "Okay. Please continue.",
            "feedback_kr": "의미는 전달됐습니다. 조금 더 자연스럽게 말해 봅시다.",
            "tone": "formal_neutral",
            "animation": "officer_check_passport",
            "tts": fallback_tts,
            "fallback": {"used": True, "reason": "voice_output_error"},
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
