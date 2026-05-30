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
from voicesaju.readings.routers.intro import router as reading_intro_router
from voicesaju.readings.routers.pipeline import router as reading_pipeline_router
from voicesaju.users.routers.auth import router as oauth_router
from voicesaju.users.routers.device import router as device_router
from voicesaju.users.routers.me import router as me_router
from voicesaju.users.routers.profile import router as profile_router

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

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

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

    # ---- Reading intro clip (persona audio lookup) -------------------
    # ISSUE-031 (FR-005). Mounts `GET /api/v1/reading/intro/{category}`.
    app.include_router(reading_intro_router)
    app.include_router(reading_pipeline_router)

    # ---- Me + entitlement summary ------------------------------------
    # ISSUE-040 (FR-006, FR-014, FR-022). Mounts `GET /api/v1/me`,
    # which returns the caller's entitlement summary (replaces the
    # M1 web stub `web/src/lib/api/me-stub.ts`).
    app.include_router(me_router)

    return app


# Uvicorn entrypoint: `uv run uvicorn voicesaju.main:app`
app = create_app()
