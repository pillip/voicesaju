"""FastAPI application factory and Uvicorn entrypoint."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.adapters import get_auth_adapter, get_payment_adapter
from voicesaju.adapters.auth import AuthSession
from voicesaju.adapters.payment import (
    CheckoutSession,
    MockPaymentAdapter,
    PaymentKind,
)
from voicesaju.config import Settings, get_settings
from voicesaju.db.engine import get_session
from voicesaju.middleware.auth import AuthMiddleware
from voicesaju.observability.logging import (  # noqa: F401 -- referenced below in create_app
    RequestIdMiddleware,
    configure_logging,
)
from voicesaju.observability.otel import (  # noqa: F401 -- used in create_app
    attach_metrics_route,
    configure_otel,
    instrument_app,
)
from voicesaju.payment.history import router as payment_history_router
from voicesaju.payment.routes import router as payment_router  # noqa: F401
from voicesaju.payment.subscription_routes import (  # noqa: F401
    router as subscription_router,
)
from voicesaju.payment.webhook import router as payment_webhook_router
from voicesaju.readings.routers.followups import router as reading_followups_router
from voicesaju.readings.routers.history import (  # noqa: F401
    router as reading_history_router,
)
from voicesaju.readings.routers.intro import router as reading_intro_router
from voicesaju.readings.routers.pipeline import router as reading_pipeline_router
from voicesaju.users.routers.account import router as account_router  # noqa: F401
from voicesaju.users.routers.auth import router as oauth_router
from voicesaju.users.routers.device import router as device_router
from voicesaju.users.routers.me import router as me_router
from voicesaju.users.routers.profile import router as profile_router
from voicesaju.users.routers.toss_bridge import bridge_router as toss_bridge_router
from voicesaju.users.routers.toss_bridge import paywall_router as toss_paywall_router

logger = logging.getLogger(__name__)


class CheckoutRequest(BaseModel):
    """Body for `POST /api/payments/checkout`."""

    user_id: str
    kind: PaymentKind
    amount_krw: int
    idempotency_key: str | None = None


class WebhookPayload(BaseModel):
    """Body for `POST /api/payments/webhook` (internal, fired by mock adapter)."""

    session_id: str
    status: Literal["succeeded", "failed", "cancelled"]
    paid_at: str | None = None
    amount_krw: int = 0


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    AC: App factory does not raise on import (smoke).
    AC: GET /healthz returns 200 {"status":"ok"}.
    AC: GET /healthz/db returns 200 {"status":"ok","db":"connected"} when DB is up,
        503 otherwise.
    """
    settings = settings or get_settings()

    # ISSUE-079: structured JSON logging — runs first so subsequent
    # subsystem startup logs are rendered as JSON with redaction.
    configure_logging(
        service_name=settings.app_name,
        log_level=settings.log_level,
    )

    # ISSUE-077: Configure OpenTelemetry. No-op when otel_enabled=False.
    configure_otel(
        enabled=settings.otel_enabled,
        endpoint=settings.otel_endpoint,
        service_name=settings.otel_service_name,
        environment=settings.environment,
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    # ISSUE-077: Auto-instrument FastAPI + httpx + Prometheus /metrics.
    if settings.otel_enabled:
        instrument_app(app)
    attach_metrics_route(app)

    # ISSUE-079: inject per-request `request_id` ContextVar. LIFO
    # ordering: registered AFTER AuthMiddleware so request_id is set
    # before the auth layer runs.
    app.add_middleware(RequestIdMiddleware)

    # Resolve user from Bearer token on every request → request.state.user.
    app.add_middleware(AuthMiddleware)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        """Liveness probe. Returns 200 once the process is serving requests."""
        return {"status": "ok"}

    @app.get("/healthz/db", tags=["meta"])
    async def healthz_db(
        response: Response,
        session: AsyncSession = Depends(get_session),  # noqa: B008
    ) -> dict[str, str]:
        """Readiness probe: executes `SELECT 1` against the configured DB.

        Returns 200 on success, 503 on any DB error.
        """
        try:
            await session.execute(text("SELECT 1"))
        except Exception as exc:  # pragma: no cover - exercised via tests
            logger.warning("healthz/db failed: %s", exc)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "error", "db": "disconnected"}
        return {"status": "ok", "db": "connected"}

    # ---- Payments (mock-backed Phase 1 endpoints) ---------------------
    # TODO(ISSUE-014): persist payments + entitlements rows here once the
    # payments table lands. For Phase 1 the mock adapter keeps state in
    # process and the webhook flips it to `succeeded` after ~3s.

    @app.post("/api/payments/checkout", tags=["payments"])
    async def payments_checkout(
        body: CheckoutRequest, background_tasks: BackgroundTasks
    ) -> CheckoutSession:
        adapter = get_payment_adapter()
        session_obj = await adapter.create_checkout_session(
            user_id=body.user_id,
            kind=body.kind,
            amount_krw=body.amount_krw,
            idempotency_key=body.idempotency_key,
        )
        if isinstance(adapter, MockPaymentAdapter):
            # Schedule the simulated webhook; real Toss client will
            # receive the equivalent callback from Toss itself.
            background_tasks.add_task(
                adapter.fire_webhook, session_obj.session_id, body.amount_krw
            )
        return session_obj

    @app.post("/api/payments/webhook", tags=["payments"])
    async def payments_webhook(payload: WebhookPayload) -> dict[str, str]:
        # Phase 1: no DB persistence yet — log and acknowledge.
        # The mock adapter already updated in-process state via fire_webhook;
        # this endpoint exists so the real Toss callback shape is wired.
        logger.info(
            "payments.webhook session_id=%s status=%s",
            payload.session_id,
            payload.status,
        )
        return {"status": "ok"}

    # ---- Auth (mock-backed Phase 1 endpoints) -------------------------
    @app.get("/api/auth/login", tags=["auth"])
    async def auth_login() -> AuthSession:
        """Issue an auth session.

        Mock provider returns a signed dev JWT immediately (no redirect).
        Real OAuth providers (Phase 2) will return a redirect URL instead.
        """
        adapter = get_auth_adapter()
        return AuthSession(access_token=adapter.start_login())

    # ---- Device (anonymous tracking) ---------------------------------
    # ISSUE-024 (FR-003, FR-013). Mounts `POST /api/v1/auth/device`.
    app.include_router(device_router)

    # ---- OAuth callbacks ---------------------------------------------
    # ISSUE-026 (FR-016, FR-017). Mounts Kakao + Apple start/callback
    # endpoints under `/api/v1/auth/{kakao,apple}/*`.
    app.include_router(oauth_router)

    # ---- Profile (onboarding + saju chart) ---------------------------
    # ISSUE-029 (FR-001, FR-002, FR-027, FR-030). Mounts
    # `POST /api/v1/profile`.
    app.include_router(profile_router)

    # ---- Account (logout + soft-delete) ------------------------------
    # ISSUE-072 (NFR-005). Mounts `POST /api/v1/users/me/delete`.
    app.include_router(account_router)

    # ---- Reading intro clip (persona audio lookup) -------------------
    # ISSUE-031 (FR-005). Mounts `GET /api/v1/reading/intro/{category}`.
    app.include_router(reading_intro_router)
    app.include_router(reading_pipeline_router)

    # ---- Reading follow-up suggestions + per-slot answer SSE ----------
    # ISSUE-041 (FR-009, FR-010, NFR-004). Mounts
    # `GET /api/v1/reading/{id}/followups` and
    # `POST /api/v1/reading/{id}/followups/{index}`.
    app.include_router(reading_followups_router)

    # ---- Reading history list + archived audio replay ----------------
    # ISSUE-066 (FR-028, US-16). Mounts
    # `GET /api/v1/me/readings` (paginated list) and
    # `GET /api/v1/reading/{id}/audio.mp3` (archived MP3 replay).
    app.include_router(reading_history_router)

    # ---- Me + entitlement summary ------------------------------------
    # ISSUE-040 (FR-006, FR-014, FR-022). Mounts `GET /api/v1/me`,
    # which returns the caller's entitlement summary (replaces the
    # M1 web stub `web/src/lib/api/me-stub.ts`).
    app.include_router(me_router)

    # ---- Payments (Toss) ---------------------------------------------
    # ISSUE-044 (FR-021). Mounts `POST /api/v1/payments/checkout` and
    # `POST /api/v1/payments/confirm`. Phase-1 delegates to
    # MockTossClient under PAYMENT_PROVIDER=mock.
    app.include_router(payment_router)

    # ---- Payments history (single-purchase list, paginated) ----------
    # ISSUE-073 (FR-026, US-12). Mounts `GET /api/v1/payments/history`.
    app.include_router(payment_history_router)

    # ---- Subscriptions (create + cancel) -----------------------------
    # ISSUE-068 (FR-022, US-12). Mounts `POST /api/v1/subscriptions`
    # and `POST /api/v1/subscriptions/cancel`. Cancel dispatches the
    # `subscription_cancel_retry` arq job for Toss-side retry.
    app.include_router(subscription_router)

    # ---- Payments webhook (Toss → us, HMAC-signed) -------------------
    # ISSUE-045 (FR-021, FR-022). Mounts `POST /api/v1/payments/webhook`.
    # Verifies HMAC-SHA256(body, TOSS_WEBHOOK_SECRET) before any DB write
    # and dispatches by `eventType` (PAYMENT_DONE / PAYMENT_FAILED /
    # SUBSCRIPTION_RENEWED / SUBSCRIPTION_CANCELED / BILLING_FAILED).
    app.include_router(payment_webhook_router)

    # ---- Toss WebView bridge + paywall -------------------------------
    # ISSUE-046 (FR-016, FR-024, US-14). Mounts
    # `POST /api/v1/auth/toss-bridge` (HS256 JWT verify + vs_sess
    # SameSite=None cookie) and `GET /api/v1/reading/paywall`
    # (channel-gated payment-method list).
    app.include_router(toss_bridge_router)
    app.include_router(toss_paywall_router)

    # ---- Daily tarot (GET today + POST flip with SSE) ----------------
    # ISSUE-049 (FR-012, FR-013, FR-014, FR-015, NFR-003). Mounts
    # `GET /api/v1/tarot/today` (card metadata + quota) and
    # `POST /api/v1/tarot/today/flip` (idempotent draw + SSE reading).
    # Import happens at function scope so autoflake doesn't strip it
    # when the router is added in a single PR before any other tarot
    # router consumer references it at module scope.
    from voicesaju.tarot.routers.today import (
        router as tarot_today_router,
    )

    app.include_router(tarot_today_router)

    # ---- Daily tarot card art (placeholder + R2-backed) --------------
    # ISSUE-055 (DEP-06). Mounts
    # `GET /api/v1/tarot/cards/{card_index}/art` so the placeholder
    # URL emitted by ISSUE-049's `_card_art_url` resolves to real PNG
    # bytes from the active storage adapter (MockStorageAdapter under
    # Phase-1, real R2 once ISSUE-005 lands).
    from voicesaju.tarot.routers.cards_art import (
        router as tarot_cards_art_router,
    )

    app.include_router(tarot_cards_art_router)

    # ---- Quote cards (share endpoint) --------------------------------
    # ISSUE-060 (FR-020). Mounts
    # `GET /api/v1/quote-cards/by-slug/{slug}` so the Next.js OG route
    # handler + SSR share landing page can resolve a public share_slug
    # to the row metadata needed for image render / redirect.
    from voicesaju.content.routers.quote_cards import (
        router as quote_cards_router,
    )

    app.include_router(quote_cards_router)

    return app


# Uvicorn entrypoint: `uv run uvicorn voicesaju.main:app`
app = create_app()
