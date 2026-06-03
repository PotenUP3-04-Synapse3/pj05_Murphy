from __future__ import annotations

from pathlib import Path
import tempfile
from importlib import import_module
from typing import Any, Literal, Protocol

import httpx

from backend.app.schemas.game_turn import AudioMetadata, InputSource, MockAudioInput, NormalizedInput
from backend.app.services.settings_service import AppSettings, get_settings

SttMode = Literal["local", "mock"]
SttRuntimeUsed = Literal["local", "api"]


class SttRuntimeError(RuntimeError):
    pass


class SttRuntime(Protocol):
    def transcribe_wav(self, audio: MockAudioInput, audio_metadata: AudioMetadata) -> str:
        ...


class LocalWhisperLargeV3TurboRuntime:
    def __init__(self, model_name: str | None = None, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.model_name = model_name or self.settings.murphy_stt_local_model
        self._model: Any | None = None

    def transcribe_wav(self, audio: MockAudioInput, audio_metadata: AudioMetadata) -> str:
        audio_bytes = _require_uploaded_wav(audio)
        suffix = _safe_audio_suffix(audio.file_name)
        temp_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_path = Path(temp_audio.name)

            transcribe_kwargs: dict[str, Any] = {"task": "transcribe", "fp16": False}
            language = _language_code(audio_metadata.language_hint)
            if language is not None:
                transcribe_kwargs["language"] = language

            result = self._load_model().transcribe(str(temp_path), **transcribe_kwargs)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

        if not isinstance(result, dict):
            raise SttRuntimeError("Local Whisper returned an unsupported transcription result.")

        text = result.get("text")
        if not isinstance(text, str) or not text.strip():
            raise SttRuntimeError("Local Whisper returned an empty transcript.")

        return text.strip()

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            whisper = import_module("whisper")
        except ImportError as exc:
            raise SttRuntimeError(
                "Local Whisper runtime requires the openai-whisper package. "
                "Install the local STT extra before running real local transcription."
            ) from exc

        try:
            self._model = whisper.load_model(self.model_name)
        except Exception as exc:
            raise SttRuntimeError(f"Failed to load local Whisper model: {self.model_name}") from exc

        return self._model


class OpenAITranscriptionApiFallbackRuntime:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        endpoint_url: str | None = None,
        timeout_s: float | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.openai_api_key
        self.model_name = model_name or self.settings.murphy_stt_api_model
        self.endpoint_url = endpoint_url or self.settings.murphy_stt_api_endpoint
        self.timeout_s = timeout_s or self.settings.murphy_stt_api_timeout_s

    def transcribe_wav(self, audio: MockAudioInput, audio_metadata: AudioMetadata) -> str:
        audio_bytes = _require_uploaded_wav(audio)
        if not self.api_key:
            raise SttRuntimeError("OPENAI_API_KEY is required for STT API fallback.")

        data = {"model": self.model_name}
        language = _language_code(audio_metadata.language_hint)
        if language is not None:
            data["language"] = language

        files = {
            "file": (
                audio.file_name or "player_input.wav",
                audio_bytes,
                audio.content_type or "audio/wav",
            )
        }

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                response = client.post(
                    self.endpoint_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=data,
                    files=files,
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise SttRuntimeError("STT API fallback request failed.") from exc
        except ValueError as exc:
            raise SttRuntimeError("STT API fallback returned non-JSON response.") from exc

        if not isinstance(payload, dict):
            raise SttRuntimeError("STT API fallback returned an unsupported response.")

        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise SttRuntimeError("STT API fallback returned an empty transcript.")

        return text.strip()


class WhisperLargeV3TurboSttService:
    model_name: Literal["whisper-large-v3-turbo"] = "whisper-large-v3-turbo"
    primary_runtime: Literal["local"] = "local"
    fallback_runtime: Literal["api"] = "api"

    def __init__(
        self,
        local_runtime: SttRuntime | None = None,
        api_fallback: SttRuntime | None = None,
        mode: SttMode | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.local_runtime = local_runtime or LocalWhisperLargeV3TurboRuntime(settings=self.settings)
        self.api_fallback = api_fallback or OpenAITranscriptionApiFallbackRuntime(settings=self.settings)
        self.mode = mode or self.settings.murphy_stt_mode

    def transcribe_wav(
        self,
        audio: MockAudioInput,
        audio_metadata: AudioMetadata,
    ) -> NormalizedInput:
        if audio_metadata.mime_type != "audio/wav":
            raise ValueError("Only audio/wav mock input is supported.")

        transcript = audio.transcript
        runtime_used: SttRuntimeUsed = self.primary_runtime
        stt_confidence: float | None = 0.87
        if transcript is None and audio.audio_bytes is not None:
            if self.mode == "mock":
                transcript = self._transcribe_uploaded_wav(audio)
            else:
                transcript, runtime_used = self._transcribe_with_local_then_api(audio, audio_metadata)
                stt_confidence = None

        return NormalizedInput(
            player_text=transcript or "I'm here for tourism.",
            input_source=InputSource(
                input_type="voice",
                stt_confidence=stt_confidence,
                language_detected=audio_metadata.language_hint or "en-US",
                needs_repeat=False,
            ),
            stt_model=self.model_name,
            stt_primary_runtime=self.primary_runtime,
            stt_fallback_runtime=self.fallback_runtime,
            stt_runtime_used=runtime_used,
        )

    def _transcribe_uploaded_wav(self, audio: MockAudioInput) -> str:
        _require_uploaded_wav(audio)
        return "I'm here for tourism."

    def _transcribe_with_local_then_api(
        self,
        audio: MockAudioInput,
        audio_metadata: AudioMetadata,
    ) -> tuple[str, SttRuntimeUsed]:
        _require_uploaded_wav(audio)
        try:
            return self.local_runtime.transcribe_wav(audio, audio_metadata), self.primary_runtime
        except Exception:
            return self.api_fallback.transcribe_wav(audio, audio_metadata), self.fallback_runtime


def _require_uploaded_wav(audio: MockAudioInput) -> bytes:
    if audio.content_type not in {None, "audio/wav", "audio/x-wav"}:
        raise ValueError("Only wav uploads can be transcribed by the STT boundary.")

    if not audio.audio_bytes or not audio.audio_bytes.startswith(b"RIFF"):
        raise ValueError("Uploaded audio must be a RIFF wav file.")

    return audio.audio_bytes


def _safe_audio_suffix(file_name: str | None) -> str:
    suffix = Path(file_name or "player_input.wav").suffix.lower()
    if suffix in {".wav", ".wave"}:
        return suffix

    return ".wav"


def _language_code(language_hint: str | None) -> str | None:
    if not language_hint:
        return None

    return language_hint.split("-", maxsplit=1)[0].lower()
