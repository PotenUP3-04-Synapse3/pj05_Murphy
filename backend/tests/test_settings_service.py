from backend.app.services.service_c.settings_service import AppSettings
from backend.app.services.service_c.stt_service import (
    LocalWhisperLargeV3TurboRuntime,
    OpenAITranscriptionApiFallbackRuntime,
    WhisperLargeV3TurboSttService,
)


def _clear_runtime_env(monkeypatch) -> None:
    for key in [
        "OPENAI_API_KEY",
        "MURPHY_STT_MODE",
        "MURPHY_STT_LOCAL_MODEL",
        "MURPHY_STT_API_MODEL",
        "MURPHY_STT_API_ENDPOINT",
        "MURPHY_STT_API_TIMEOUT_S",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_app_settings_reads_values_from_env_file(tmp_path, monkeypatch) -> None:
    _clear_runtime_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-test-env-file",
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

    assert settings.openai_api_key == "sk-test-env-file"
    assert settings.murphy_stt_mode == "mock"
    assert settings.murphy_stt_local_model == "turbo"
    assert settings.murphy_stt_api_model == "gpt-4o-mini-transcribe"
    assert settings.murphy_stt_api_endpoint == "https://example.test/v1/audio/transcriptions"
    assert settings.murphy_stt_api_timeout_s == 12.5


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
