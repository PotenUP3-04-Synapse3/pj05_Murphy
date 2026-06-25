"""Load Developer C runtime settings from environment variables.

Beginner guide:
`AppSettings` is the central place for local `.env` and process environment
configuration.  Services receive this object instead of reading environment
variables directly, which makes tests easier and keeps secrets such as API keys
out of logs and public payloads.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: str | None = None
    gemma4_vllm_base_url: str = "http://100.95.34.69:8001/v1"
    gemma4_vllm_model: str = "google/gemma-4-26B-A4B-it"
    gemma4_vllm_api_key: str = "dummy"
    murphy_stt_mode: Literal["local", "mock"] = "local"
    murphy_stt_local_model: str = "turbo"
    murphy_stt_api_model: str = "whisper-1"
    murphy_stt_api_endpoint: str = "https://api.openai.com/v1/audio/transcriptions"
    murphy_stt_api_timeout_s: float = 60.0
    murphy_tts_mode: Literal["fake", "real"] = "fake"
    murphy_npc_dialogue_mode: Literal["rule", "llm"] = "rule"
    murphy_understanding_mode: Literal["rule", "llm"] = "rule"
    murphy_understanding_llm_provider: Literal["openai"] = "openai"
    murphy_understanding_llm_fallback: Literal["none", "gemma4_vllm"] = "none"
    murphy_understanding_llm_model: str = "gpt-4o-mini"
    murphy_understanding_llm_timeout_seconds: float = 10.0
    murphy_incivility_classifier_mode: Literal["rule"] = "rule"
    murphy_unreal_request_capture_mode: Literal["off", "debug"] = "off"
    murphy_unreal_request_capture_root: Path = Path("backend/runtime/generated/unreal_requests")
    elevenlabs_api_key: str | None = None
    elevenlabs_realtime_stt_endpoint: str = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
    elevenlabs_realtime_stt_model: str = "scribe_v2_realtime"
    elevenlabs_realtime_audio_format: str = "pcm_16000"
    elevenlabs_realtime_commit_strategy: Literal["manual", "vad"] = "manual"
    elevenlabs_realtime_receive_timeout_s: float = 0.2
    elevenlabs_realtime_commit_timeout_s: float = 3.0
    elevenlabs_realtime_estimated_cost_per_minute_usd: float = 0.0
    murphy_stt_debug_log_mode: Literal["off", "debug"] = "off"
    murphy_c_legacy_history: bool = False
    murphy_turn_authority: Literal["legacy", "unified"] = "legacy"


    @classmethod
    def from_env_file(cls, env_file: str | Path) -> "AppSettings":
        return cls(_env_file=env_file)  # type: ignore[call-arg]


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
