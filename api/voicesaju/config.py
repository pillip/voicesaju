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
    # LLM adapter selection. ISSUE-101 ships the mock implementation
    # which streams fixture text from `tests/fixtures/llm/{category}/`.
    # `claude` reserves the env slot for ISSUE-035 (real Anthropic SSE).
    llm_provider: Literal["mock", "claude"] = "mock"
    # TTS adapter selection. ISSUE-102 ships the mock implementation
    # which streams 10 pre-baked silent MP3 chunks at 200ms pacing.
    # `supertone` reserves the env slot for ISSUE-036 (real Supertone SSE).
    tts_provider: Literal["mock", "supertone"] = "mock"
    # Storage adapter selection (ISSUE-038). ``mock`` writes audio +
    # OG assets to ``./.local_storage/`` (gitignored, local-fs); ``r2``
    # reserves the env slot for ISSUE-005 (real Cloudflare R2). Real
    # provisioning is Phase-2 deferred — the Phase-2 stub still
    # instantiates so the app boots under ``STORAGE_PROVIDER=r2``.
    storage_provider: Literal["mock", "r2"] = "mock"

    # Mock-auth JWT signing secret. Dev default — fails in prod via validator.
    mock_auth_jwt_secret: str = "dev-mock-secret-do-not-use-in-prod"

    # --- Toss Payments (ISSUE-044) ---
    # Price catalogue per A-01. Override via env (PRICE_SINGLE_KRW=…)
    # once the OQ-04 single/subscription pricing decision is finalised.
    price_single_krw: int = 4_900
    price_subscription_krw: int = 9_900
    # Toss redirect targets. The routes fall back to
    # ``Request.base_url + /payment/{success,fail}`` if these are unset
    # so local-dev works without env vars.
    toss_success_url: str | None = None
    toss_fail_url: str | None = None
    # Real-Toss client config (Phase-2 — ISSUE-043). The Phase-1 wiring
    # leaves these unset; switching to ``PAYMENT_PROVIDER=toss`` without
    # populating them surfaces a clear NotImplementedError on first call.
    toss_secret_key: str | None = None
    toss_api_base: str = "https://api.tosspayments.com"
    # Webhook signing secret (ISSUE-045). Toss signs each webhook body
    # with ``HMAC-SHA256(body, TOSS_WEBHOOK_SECRET)`` and ships the hex
    # digest in ``X-Toss-Signature``. ``verify_signature`` in
    # ``voicesaju.payment.webhook_signature`` rejects an empty secret
    # outright so a half-configured deploy cannot accept arbitrary
    # webhooks. Env: ``TOSS_WEBHOOK_SECRET``.
    toss_webhook_secret: str | None = None
    # Toss WebView bridge (ISSUE-046). Symmetric secret used to verify
    # HS256 JWTs issued by the Toss bridge; ``TOSS_BRIDGE_AUDIENCE``
    # is the ``aud`` claim Toss embeds. The origin allowlist gates
    # SameSite=None cookie issuance to documented WebView origins.
    toss_bridge_secret: str | None = None
    toss_bridge_audience: str = "voicesaju"
    toss_webview_origin_allowlist: list[str] = ["https://m.tosspayments.com"]

    # --- Anthropic LLM client (ISSUE-034) ---
    # API key for the real ``ClaudeAdapter`` path. Optional in non-prod
    # since the default ``LLM_PROVIDER=mock`` never touches Anthropic.
    # Real provisioning lives behind ISSUE-035 (Phase 2 manual setup).
    anthropic_api_key: str | None = None
    # KRW per million tokens — conservative estimates per PRD §11 OQ-01.
    # Override via env (`ANTHROPIC_SONNET_INPUT_KRW_PER_MTOK=…`) once the
    # exact billed price is known. The cost-tracker dashboard alerts on
    # >18% / >20% of single price so we want these numbers stable per
    # deploy, not hardcoded in the SDK wrapper.
    anthropic_sonnet_input_krw_per_mtok: float = 4_000.0
    anthropic_sonnet_output_krw_per_mtok: float = 20_000.0
    anthropic_haiku_input_krw_per_mtok: float = 1_000.0
    anthropic_haiku_output_krw_per_mtok: float = 5_000.0

    # --- Sentry (ISSUE-078) ---
    # DSN is the single switch. When unset, the SDK is never initialised
    # so import-time overhead stays zero in tests / local dev.
    # The `before_send` hook strips PII (birth_dt, payment keys, Toss
    # order IDs, JWTs) before any event reaches the wire.
    sentry_dsn: str | None = None
    sentry_environment: str | None = None
    sentry_release: str | None = None

    def model_post_init(self, __context: object) -> None:
        """Guardrail: mock-* adapters must not run in production."""
        if self.environment == "prod" and self.auth_provider == "mock":
            raise ValueError(
                "AUTH_PROVIDER=mock is not allowed when ENVIRONMENT=prod. "
                "Configure a real provider before production deploy."
            )
        if self.environment == "prod" and self.llm_provider == "mock":
            raise ValueError(
                "LLM_PROVIDER=mock is not allowed when ENVIRONMENT=prod. "
                "Configure a real provider before production deploy."
            )


def get_settings() -> Settings:
    """Return a Settings instance (factory for dependency injection / tests)."""
    return Settings()
