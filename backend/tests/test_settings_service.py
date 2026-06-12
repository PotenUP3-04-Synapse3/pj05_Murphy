from backend.app.services.service_c.settings_service import AppSettings
from backend.app.services.service_c.stt_service import (
    LocalWhisperLargeV3TurboRuntime,
    OpenAITranscriptionApiFallbackRuntime,
    WhisperLargeV3TurboSttService,
)


def _clear_runtime_env(monkeypatch) -> None:
    for key in [
        "OPENAI_API_KEY",
        "GEMMA4_VLLM_BASE_URL",
        "GEMMA4_VLLM_MODEL",
        "GEMMA4_VLLM_API_KEY",
        "MURPHY_STT_MODE",
        "MURPHY_STT_LOCAL_MODEL",
        "MURPHY_STT_API_MODEL",
        "MURPHY_STT_API_ENDPOINT",
        "MURPHY_STT_API_TIMEOUT_S",
        "MURPHY_TTS_MODE",
        "MURPHY_NPC_DIALOGUE_MODE",
        "MURPHY_UNDERSTANDING_MODE",
        "MURPHY_UNDERSTANDING_LLM_PROVIDER",
        "MURPHY_UNDERSTANDING_LLM_FALLBACK",
        "MURPHY_UNDERSTANDING_LLM_MODEL",
        "MURPHY_UNDERSTANDING_LLM_TIMEOUT_SECONDS",
        "MURPHY_UNREAL_REQUEST_CAPTURE_MODE",
        "MURPHY_UNREAL_REQUEST_CAPTURE_ROOT",
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_REALTIME_STT_ENDPOINT",
        "ELEVENLABS_REALTIME_STT_MODEL",
        "ELEVENLABS_REALTIME_AUDIO_FORMAT",
        "ELEVENLABS_REALTIME_COMMIT_STRATEGY",
        "ELEVENLABS_REALTIME_RECEIVE_TIMEOUT_S",
        "ELEVENLABS_REALTIME_ESTIMATED_COST_PER_MINUTE_USD",
        "MURPHY_STT_DEBUG_LOG_MODE",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_app_settings_reads_values_from_env_file(tmp_path, monkeypatch) -> None:
    _clear_runtime_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-test-env-file",
                "GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1",
                "GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it",
                "GEMMA4_VLLM_API_KEY=dummy",
                "MURPHY_STT_MODE=mock",
                "MURPHY_STT_LOCAL_MODEL=turbo",
                "MURPHY_STT_API_MODEL=gpt-4o-mini-transcribe",
                "MURPHY_STT_API_ENDPOINT=https://example.test/v1/audio/transcriptions",
                "MURPHY_STT_API_TIMEOUT_S=12.5",
                "MURPHY_TTS_MODE=real",
                "MURPHY_NPC_DIALOGUE_MODE=llm",
                "MURPHY_UNDERSTANDING_MODE=llm",
                "MURPHY_UNDERSTANDING_LLM_PROVIDER=openai",
                "MURPHY_UNDERSTANDING_LLM_FALLBACK=gemma4_vllm",
                "MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini",
                "MURPHY_UNDERSTANDING_LLM_TIMEOUT_SECONDS=10.5",
                "MURPHY_UNREAL_REQUEST_CAPTURE_MODE=debug",
                f"MURPHY_UNREAL_REQUEST_CAPTURE_ROOT={tmp_path / 'captures'}",
                "ELEVENLABS_API_KEY=xi-test-env-file",
                "ELEVENLABS_REALTIME_STT_ENDPOINT=wss://example.test/v1/speech-to-text/realtime",
                "ELEVENLABS_REALTIME_STT_MODEL=scribe_v2_realtime",
                "ELEVENLABS_REALTIME_AUDIO_FORMAT=pcm_16000",
                "ELEVENLABS_REALTIME_COMMIT_STRATEGY=manual",
                "ELEVENLABS_REALTIME_RECEIVE_TIMEOUT_S=0.25",
                "ELEVENLABS_REALTIME_ESTIMATED_COST_PER_MINUTE_USD=0.004",
                "MURPHY_STT_DEBUG_LOG_MODE=debug",
            ]
        ),
        encoding="utf-8",
    )

    settings = AppSettings.from_env_file(env_file)

    assert settings.openai_api_key == "sk-test-env-file"
    assert settings.gemma4_vllm_base_url == "http://100.95.34.69:8001/v1"
    assert settings.gemma4_vllm_model == "google/gemma-4-26B-A4B-it"
    assert settings.gemma4_vllm_api_key == "dummy"
    assert settings.murphy_stt_mode == "mock"
    assert settings.murphy_stt_local_model == "turbo"
    assert settings.murphy_stt_api_model == "gpt-4o-mini-transcribe"
    assert settings.murphy_stt_api_endpoint == "https://example.test/v1/audio/transcriptions"
    assert settings.murphy_stt_api_timeout_s == 12.5
    assert settings.murphy_tts_mode == "real"
    assert settings.murphy_npc_dialogue_mode == "llm"
    assert settings.murphy_understanding_mode == "llm"
    assert settings.murphy_understanding_llm_provider == "openai"
    assert settings.murphy_understanding_llm_fallback == "gemma4_vllm"
    assert settings.murphy_understanding_llm_model == "gpt-4o-mini"
    assert settings.murphy_understanding_llm_timeout_seconds == 10.5
    assert settings.murphy_unreal_request_capture_mode == "debug"
    assert settings.murphy_unreal_request_capture_root == tmp_path / "captures"
    assert settings.elevenlabs_api_key == "xi-test-env-file"
    assert settings.elevenlabs_realtime_stt_endpoint == "wss://example.test/v1/speech-to-text/realtime"
    assert settings.elevenlabs_realtime_stt_model == "scribe_v2_realtime"
    assert settings.elevenlabs_realtime_audio_format == "pcm_16000"
    assert settings.elevenlabs_realtime_commit_strategy == "manual"
    assert settings.elevenlabs_realtime_receive_timeout_s == 0.25
    assert settings.elevenlabs_realtime_estimated_cost_per_minute_usd == 0.004
    assert settings.murphy_stt_debug_log_mode == "debug"


def test_stt_runtimes_use_settings_loaded_from_env_file(tmp_path, monkeypatch) -> None:
    _clear_runtime_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-runtime-env-file",
                "MURPHY_STT_MODE=mock",
                "MURPHY_STT_LOCAL_MODEL=turbo",
                "MURPHY_STT_API_MODEL=gpt-4o-mini-transcribe",
                "MURPHY_STT_API_ENDPOINT=https://example.test/v1/audio/transcriptions",
                "MURPHY_STT_API_TIMEOUT_S=12.5",
            ]
        ),
        encoding="utf-8",
    )
    settings = AppSettings.from_env_file(env_file)

    local_runtime = LocalWhisperLargeV3TurboRuntime(settings=settings)
    api_fallback = OpenAITranscriptionApiFallbackRuntime(settings=settings)
    service = WhisperLargeV3TurboSttService(settings=settings)

    assert local_runtime.model_name == "turbo"
    assert api_fallback.api_key == "sk-runtime-env-file"
    assert api_fallback.model_name == "gpt-4o-mini-transcribe"
    assert api_fallback.endpoint_url == "https://example.test/v1/audio/transcriptions"
    assert api_fallback.timeout_s == 12.5
    assert service.mode == "mock"
