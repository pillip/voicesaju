"""FastAPI application factory and Uvicorn entrypoint."""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.config import Settings, get_settings
from voicesaju.db.engine import get_session

logger = logging.getLogger(__name__)


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

    return app


# Uvicorn entrypoint: `uv run uvicorn voicesaju.main:app`
app = create_app()
