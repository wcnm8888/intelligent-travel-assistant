"""Typed local settings for the backend service."""

import os
from functools import lru_cache
from ipaddress import IPv4Address
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from intelligent_travel_assistant.adapters.providers import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_ENV_FILE = None if os.environ.get("APP_ENV") == "test" else PROJECT_ROOT / ".env.local"


def default_local_sqlite_database_path() -> Path:
    """Return a source-tree-independent local application data path."""

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data)
        if candidate.is_absolute():
            return candidate / "IntelligentTravelAssistant" / "travel-plans.sqlite3"
    return Path.home() / ".local" / "share" / "IntelligentTravelAssistant" / "travel-plans.sqlite3"


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
    sqlite_database_path: Path | None = Field(default=None, repr=False)

    deepseek_api_key: SecretStr | None = Field(default=None, repr=False)
    deepseek_model: Literal["deepseek-v4-flash"] = DEEPSEEK_MODEL
    deepseek_base_url: Literal["https://api.deepseek.com"] = DEEPSEEK_BASE_URL

    amap_api_key: SecretStr | None = Field(default=None, repr=False)

    qweather_api_host: str | None = Field(default=None, repr=False)
    qweather_project_id: str | None = Field(default=None, repr=False)
    qweather_credential_id: str | None = Field(default=None, repr=False)
    qweather_private_key_path: Path | None = Field(default=None, repr=False)

    @field_validator("sqlite_database_path")
    @classmethod
    def require_absolute_sqlite_path(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("sqlite database path must be absolute")
        if value is not None and value.resolve().is_relative_to(PROJECT_ROOT.resolve()):
            raise ValueError("sqlite database path must be outside the project tree")
        return value


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the process."""

    return Settings()
