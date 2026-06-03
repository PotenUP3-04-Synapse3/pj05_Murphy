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

        transcript = audio.transcript
        if transcript is None and audio.audio_bytes is not None:
            transcript = self._transcribe_uploaded_wav(audio)

        return NormalizedInput(
            player_text=transcript or "I'm here for tourism.",
            input_source=InputSource(
                input_type="voice",
                stt_confidence=0.87,
                language_detected=audio_metadata.language_hint or "en-US",
                needs_repeat=False,
            ),
            stt_model=self.model_name,
        )

    def _transcribe_uploaded_wav(self, audio: MockAudioInput) -> str:
        if audio.content_type not in {None, "audio/wav", "audio/x-wav"}:
            raise ValueError("Only wav uploads can be transcribed by the demo STT boundary.")

        if not audio.audio_bytes or not audio.audio_bytes.startswith(b"RIFF"):
            raise ValueError("Uploaded demo audio must be a RIFF wav file.")

        return "I'm here for tourism."
