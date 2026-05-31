"""CSRF protection middleware (ISSUE-082, OWASP A01).

Strategy — **double-submit cookie**.

1. ``GET /api/v1/csrf`` mints a random URL-safe token, returns it in
   the JSON body **and** sets it as a cookie (``vs_csrf``,
   ``SameSite=Strict``, HttpOnly **False** so the SPA can read it).
2. The frontend reads ``vs_csrf`` once per session and echoes its
   value back on every mutating fetch via the ``X-VS-CSRF`` header.
3. The middleware (this module) compares the header value to the
   cookie value with ``hmac.compare_digest`` and rejects mismatches
   with 403.

Bearer bypass (architecture §11.1):
- Requests that carry ``Authorization: Bearer …`` are *not* subject to
  CSRF. The Bearer token itself is proof-of-possession and the
  ``vs_sess`` cookie is irrelevant for those callers (Toss WebView,
  native clients, integration tests). Skipping the gate here keeps the
  WebView bridge usable while still protecting cookie-authenticated
  browser sessions.

Architecture-Ref: §11.1 (auth strategy table — CSRF row).
PRD-Ref: OWASP A01.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Mapping

from fastapi import APIRouter, FastAPI, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.responses import Response as StarletteResponse

# Header + cookie names. The header name is the public contract documented
# in ``docs/architecture.md`` §11.1; do not rename without a frontend bump.
CSRF_HEADER_NAME = "X-VS-CSRF"
CSRF_COOKIE_NAME = "vs_csrf"

# Methods that *do not* require a CSRF check (RFC 7231 "safe" methods).
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Token entropy: 32 bytes → 43 URL-safe chars (~256 bits).
_TOKEN_BYTES = 32


# ---------------------------------------------------------------------------
# Token store (in-process for Phase-1; real Redis backend slots in later)
# ---------------------------------------------------------------------------


_csrf_tokens: dict[str, str] = {}


def csrf_store_for_tests() -> dict[str, str]:
    """Expose the in-process store so test fixtures can wipe it."""
    return _csrf_tokens


def generate_csrf_token() -> str:
    """Return a fresh URL-safe random token (>= 32 chars, ~256 bits)."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def _has_bearer_auth(headers: Mapping[str, str]) -> bool:
    """True iff the request carries ``Authorization: Bearer <token>``.

    Header lookup is case-insensitive (HTTP spec); Starlette's
    ``Headers`` already lowercases keys, but we re-check both casings
    for callers that pass raw dicts.
    """
    raw = headers.get("authorization") or headers.get("Authorization") or ""
    return raw.lower().startswith("bearer ")


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class CSRFMiddleware(BaseHTTPMiddleware):
    """Reject mutating requests whose CSRF header does not match the cookie.

    Bypass conditions (in order):
    - ``enabled=False`` → middleware short-circuits (staged rollout, tests).
    - Safe HTTP methods (GET/HEAD/OPTIONS) skip the check.
    - ``Authorization: Bearer …`` requests skip the check (Toss WebView,
      native clients use Bearer, not cookie).

    Failure modes:
    - Missing header → 403 ``csrf_missing``.
    - Header present but no matching cookie / store entry → 403
      ``csrf_mismatch``.
    - Header + cookie present but values differ → 403 ``csrf_mismatch``.
    """

    def __init__(self, app, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next
    ) -> StarletteResponse:
        if not self.enabled:
            return await call_next(request)

        if request.method.upper() in _SAFE_METHODS:
            return await call_next(request)

        if _has_bearer_auth(request.headers):
            return await call_next(request)

        header_token = request.headers.get(CSRF_HEADER_NAME) or request.headers.get(
            CSRF_HEADER_NAME.lower()
        )
        if not header_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": {
                        "error": {
                            "code": "csrf_missing",
                            "message": (
                                f"{CSRF_HEADER_NAME} header is required for "
                                "mutating requests"
                            ),
                        }
                    }
                },
            )

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        # Either the cookie is missing OR the value diverges → mismatch.
        # We deliberately collapse "missing cookie" and "wrong value" into
        # the same 403 code so we don't leak which leg failed.
        if not cookie_token or not hmac.compare_digest(header_token, cookie_token):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": {
                        "error": {
                            "code": "csrf_mismatch",
                            "message": (
                                f"{CSRF_HEADER_NAME} header does not match "
                                "session token"
                            ),
                        }
                    }
                },
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Token endpoint — `GET /api/v1/csrf`
# ---------------------------------------------------------------------------


csrf_router = APIRouter(tags=["security"])


@csrf_router.get("/api/v1/csrf")
async def get_csrf(request: Request, response: Response) -> dict[str, str]:
    """Return the caller's CSRF token, minting one if needed.

    Token semantics:
    - First call from a browser without a ``vs_csrf`` cookie → mint a
      fresh token, set the cookie, return the value.
    - Subsequent calls from the same browser → return the *same* token
      (the cookie is the source of truth). This lets the SPA cache the
      value across navigations without forcing a rotate per request.

    Cookie attributes:
    - ``HttpOnly=False`` — the SPA must be able to read it via
      ``document.cookie`` (or fetch and parse this response body).
    - ``SameSite=Strict`` — defence-in-depth: even if the attacker can
      coerce the browser into a cross-site request, the cookie is not
      sent, so the comparison fails by default.
    """
    existing = request.cookies.get(CSRF_COOKIE_NAME)
    token = existing or generate_csrf_token()
    if not existing:
        # Track the token server-side so future hardening (rotate on
        # session change, single-use tokens, ...) has a place to hook in.
        _csrf_tokens[token] = token
        # ``secure=True`` over HTTPS only — tests (and local dev) hit the
        # app over ``http://testserver`` / ``http://localhost``, so we
        # mirror the ``vs_sess`` cookie logic and gate on the request URL.
        is_secure = request.url.scheme == "https"
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            httponly=False,  # SPA needs to read it
            samesite="strict",
            secure=is_secure,
            max_age=60 * 60 * 24 * 30,  # mirror vs_sess lifetime
            path="/",
        )
    return {"csrfToken": token}


# ---------------------------------------------------------------------------
# Wiring helper
# ---------------------------------------------------------------------------


def install_csrf(app: FastAPI, *, enabled: bool = True) -> None:
    """Attach the CSRF middleware + ``/api/v1/csrf`` endpoint to ``app``.

    Use this from ``create_app`` to keep the wiring in one place:

        app.add_middleware(AuthMiddleware)
        install_csrf(app, enabled=settings.csrf_enabled)

    When ``enabled=False`` the middleware short-circuits to a no-op so
    existing endpoints continue to work during the staged rollout, but
    the ``GET /api/v1/csrf`` endpoint is always mounted so the frontend
    can fetch a token regardless of the gate state (idempotent + safe).
    """
    app.add_middleware(CSRFMiddleware, enabled=enabled)
    app.include_router(csrf_router)


__all__ = [
    "CSRF_COOKIE_NAME",
    "CSRF_HEADER_NAME",
    "CSRFMiddleware",
    "csrf_router",
    "csrf_store_for_tests",
    "generate_csrf_token",
    "install_csrf",
]
