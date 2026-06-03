from typing import Literal

from backend.app.schemas.game_turn import AudioMetadata, InputSource, MockAudioInput, NormalizedInput


class WhisperLargeV3TurboSttService:
    model_name: Literal["whisper-large-v3-turbo"] = "whisper-large-v3-turbo"

    def transcribe_wav(
        self,
        audio: MockAudioInput,
        audio_metadata: AudioMetadata,
    ) -> NormalizedInput:
        if audio_metadata.mime_type != "audio/wav":
            raise ValueError("Only audio/wav mock input is supported.")

        return NormalizedInput(
            player_text=audio.transcript or "I'm here for tourism.",
            input_source=InputSource(
                input_type="voice",
                stt_confidence=0.87,
                language_detected=audio_metadata.language_hint or "en-US",
                needs_repeat=False,
            ),
            stt_model=self.model_name,
        )
