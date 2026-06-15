from backend.app.schemas.game_turn import AudioMetadata, MockAudioInput
from backend.app.services.service_c.stt_service import WhisperLargeV3TurboSttService


class FakeSttRuntime:
    def __init__(self, transcript: str | None = None, error: Exception | None = None) -> None:
        self.transcript = transcript
        self.error = error
        self.calls = 0

    def transcribe_wav(self, audio: MockAudioInput, audio_metadata: AudioMetadata) -> str:
        self.calls += 1
        if self.error is not None:
            raise self.error

        return self.transcript or "I'm here for tourism."


def _audio_metadata() -> AudioMetadata:
    return AudioMetadata(
        mime_type="audio/wav",
        sample_rate_hz=16000,
        channels=1,
        duration_ms=2800,
        language_hint="en-US",
    )


def _uploaded_wav() -> MockAudioInput:
    return MockAudioInput(
        file_name="purpose.wav",
        content_type="audio/wav",
        audio_bytes=b"RIFF....WAVEfmt ",
    )


def test_stt_service_uses_local_whisper_runtime_for_uploaded_wav() -> None:
    local_runtime = FakeSttRuntime("Local transcript says tourism.")
    api_fallback = FakeSttRuntime("API transcript should not be used.")
    service = WhisperLargeV3TurboSttService(
        local_runtime=local_runtime,
        api_fallback=api_fallback,
        mode="local",
    )

    normalized_input = service.transcribe_wav(_uploaded_wav(), _audio_metadata())

    assert normalized_input.player_text == "Local transcript says tourism."
    assert normalized_input.stt_primary_runtime == "local"
    assert normalized_input.stt_fallback_runtime == "api"
    assert normalized_input.stt_runtime_used == "local"
    assert local_runtime.calls == 1
    assert api_fallback.calls == 0


def test_stt_service_falls_back_to_api_when_local_runtime_fails() -> None:
    local_runtime = FakeSttRuntime(error=RuntimeError("local model unavailable"))
    api_fallback = FakeSttRuntime("API fallback transcript says tourism.")
    service = WhisperLargeV3TurboSttService(
        local_runtime=local_runtime,
        api_fallback=api_fallback,
        mode="local",
    )

    normalized_input = service.transcribe_wav(_uploaded_wav(), _audio_metadata())

    assert normalized_input.player_text == "API fallback transcript says tourism."
    assert normalized_input.stt_runtime_used == "api"
    assert local_runtime.calls == 1
    assert api_fallback.calls == 1


def test_stt_service_reports_realtime_transcript_provider_without_batch_stt() -> None:
    local_runtime = FakeSttRuntime("Local transcript should not be used.")
    api_fallback = FakeSttRuntime("API transcript should not be used.")
    service = WhisperLargeV3TurboSttService(
        local_runtime=local_runtime,
        api_fallback=api_fallback,
        mode="local",
    )

    normalized_input = service.transcribe_wav(
        MockAudioInput(
            transcript="Realtime final transcript.",
            transcript_provider="elevenlabs_relay",
            file_name="realtime-final-transcript.txt",
            content_type="text/plain",
        ),
        _audio_metadata(),
    )

    assert normalized_input.player_text == "Realtime final transcript."
    assert normalized_input.stt_runtime_used == "elevenlabs_relay"
    assert local_runtime.calls == 0
    assert api_fallback.calls == 0
