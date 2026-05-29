"""Application settings loaded from environment / .env.local."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic v2 BaseSettings reading from environment and .env.local."""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "voicesaju"
    environment: Literal["local", "dev", "staging", "prod"] = "local"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


def get_settings() -> Settings:
    """Return a Settings instance (factory for dependency injection / tests)."""
    return Settings()
