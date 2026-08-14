"""Typed local settings for the backend service."""

import os
from functools import lru_cache
from ipaddress import IPv4Address
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from intelligent_travel_assistant.adapters.providers import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_ENV_FILE = None if os.environ.get("APP_ENV") == "test" else PROJECT_ROOT / ".env.local"


class Settings(BaseSettings):
    """Settings that are safe to load before any external service is configured."""

    model_config = SettingsConfigDict(
        env_file=SETTINGS_ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    app_env: Literal["local", "test"] = "local"
    api_host: IPv4Address = IPv4Address("127.0.0.1")
    api_port: int = Field(default=8000, ge=1, le=65535)

    deepseek_api_key: SecretStr | None = Field(default=None, repr=False)
    deepseek_model: Literal["deepseek-v4-flash"] = DEEPSEEK_MODEL
    deepseek_base_url: Literal["https://api.deepseek.com"] = DEEPSEEK_BASE_URL

    amap_api_key: SecretStr | None = Field(default=None, repr=False)

    qweather_api_host: str | None = Field(default=None, repr=False)
    qweather_project_id: str | None = Field(default=None, repr=False)
    qweather_credential_id: str | None = Field(default=None, repr=False)
    qweather_private_key_path: Path | None = Field(default=None, repr=False)


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the process."""

    return Settings()
