"""Authentication middleware.

Reads `Authorization: Bearer <token>` from the request and attaches the
resolved `UserContext` to `request.state.user`. Unauthenticated requests
proceed with `request.state.user = None` so endpoints can decide whether
to require auth.

PRD-Ref: FR-016, FR-017.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from voicesaju.adapters import UnknownProviderError, get_auth_adapter
from voicesaju.adapters.auth import AuthAdapter, UserContext


class AuthMiddleware(BaseHTTPMiddleware):
    """Extracts and verifies the bearer token on every request."""

    def __init__(self, app, adapter: AuthAdapter | None = None) -> None:
        super().__init__(app)
        # Resolve the adapter lazily so tests can override via app dependency.
        try:
            self._adapter = adapter or get_auth_adapter()
        except UnknownProviderError:
            self._adapter = None

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.user = self._resolve_user(request)
        return await call_next(request)

    def _resolve_user(self, request: Request) -> UserContext | None:
        header = request.headers.get("authorization") or request.headers.get(
            "Authorization"
        )
        if not header or not header.lower().startswith("bearer "):
            return None
        token = header.split(" ", 1)[1].strip()
        if not token or self._adapter is None:
            return None
        try:
            return self._adapter.verify_token(token)
        except Exception:  # noqa: BLE001 — middleware never raises on bad tokens
            return None


__all__ = ["AuthMiddleware"]
