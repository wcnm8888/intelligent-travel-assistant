"""Typed local settings for the backend service."""

from functools import lru_cache
from ipaddress import IPv4Address
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Settings that are safe to load before any external service is configured."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    app_env: Literal["local", "test"] = "local"
    api_host: IPv4Address = IPv4Address("127.0.0.1")
    api_port: int = Field(default=8000, ge=1, le=65535)


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the process."""

    return Settings()
