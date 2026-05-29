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

    # Database (SQLAlchemy 2.0 async). Defaults match docker-compose.yml.
    # The asyncpg driver prefix is added automatically by `db.engine.build_async_url`.
    database_url: str = "postgresql://voicesaju:voicesaju@localhost:5432/voicesaju"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Adapter selection (Phase 1 PoC defaults to mock). Factories in
    # `voicesaju.adapters` read these at request time so test suites can
    # override via env without restarting the process.
    auth_provider: Literal["mock", "kakao", "apple", "toss_id"] = "mock"
    payment_provider: Literal["mock", "toss"] = "mock"

    # Mock-auth JWT signing secret. Dev default — fails in prod via validator.
    mock_auth_jwt_secret: str = "dev-mock-secret-do-not-use-in-prod"

    def model_post_init(self, __context: object) -> None:
        """Guardrail: mock auth must not run in production."""
        if self.environment == "prod" and self.auth_provider == "mock":
            raise ValueError(
                "AUTH_PROVIDER=mock is not allowed when ENVIRONMENT=prod. "
                "Configure a real provider before production deploy."
            )


def get_settings() -> Settings:
    """Return a Settings instance (factory for dependency injection / tests)."""
    return Settings()
