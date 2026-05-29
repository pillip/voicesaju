"""FastAPI application factory and Uvicorn entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from voicesaju.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    AC: App factory does not raise on import (smoke).
    AC: GET /healthz returns 200 {"status":"ok"}.
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

    return app


# Uvicorn entrypoint: `uv run uvicorn voicesaju.main:app`
app = create_app()
