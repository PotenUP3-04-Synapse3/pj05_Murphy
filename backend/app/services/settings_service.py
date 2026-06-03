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
    murphy_stt_mode: Literal["local", "mock"] = "local"
    murphy_stt_local_model: str = "turbo"
    murphy_stt_api_model: str = "whisper-1"
    murphy_stt_api_endpoint: str = "https://api.openai.com/v1/audio/transcriptions"
    murphy_stt_api_timeout_s: float = 60.0

    @classmethod
    def from_env_file(cls, env_file: str | Path) -> "AppSettings":
        return cls(_env_file=env_file)  # type: ignore[call-arg]


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
