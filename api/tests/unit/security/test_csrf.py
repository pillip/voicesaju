"""Unit tests for CSRF protection (ISSUE-082).

PRD-Ref: OWASP A01.
Architecture-Ref: §11.1 — ``X-VS-CSRF`` header carries a per-session
secret bound to the ``vs_sess`` cookie. The middleware rejects mutating
requests when the header is missing or does not match the stored secret.
Toss WebView requests authenticate via ``Authorization: Bearer …`` and
bypass CSRF entirely (per architecture §11.1).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voicesaju.security.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CSRFMiddleware,
    csrf_store_for_tests,
    generate_csrf_token,
    install_csrf,
)

# ---------------------------------------------------------------------------
# Helpers — minimal app factory exercises the middleware in isolation.
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    app = FastAPI()
    install_csrf(app)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/mutate")
    async def mutate() -> dict[str, str]:
        return {"status": "mutated"}

    @app.put("/mutate-put")
    async def mutate_put() -> dict[str, str]:
        return {"status": "mutated"}

    return app


@pytest.fixture(autouse=True)
def _reset_csrf_store() -> None:
    csrf_store_for_tests().clear()


# ---------------------------------------------------------------------------
# Token generator
# ---------------------------------------------------------------------------


def test_generate_csrf_token_is_url_safe_and_long() -> None:
    """Tokens are URL-safe base64, at least 32 chars (>= 192 bits entropy)."""
    tok = generate_csrf_token()
    assert isinstance(tok, str)
    assert len(tok) >= 32
    # URL-safe charset only (alphanumeric, `-`, `_`).
    assert all(c.isalnum() or c in {"-", "_"} for c in tok)


def test_generate_csrf_token_is_unique_per_call() -> None:
    """Tokens must not repeat across calls — collisions would defeat CSRF."""
    tokens = {generate_csrf_token() for _ in range(50)}
    assert len(tokens) == 50


# ---------------------------------------------------------------------------
# Middleware — happy paths
# ---------------------------------------------------------------------------


def test_get_request_skips_csrf_check() -> None:
    """GETs are never gated — only mutating methods enforce CSRF."""
    client = TestClient(_make_app())
    resp = client.get("/ping")
    assert resp.status_code == 200


def test_csrf_endpoint_returns_token_and_sets_cookie() -> None:
    """``GET /api/v1/csrf`` issues a token and persists it via cookie."""
    client = TestClient(_make_app())
    resp = client.get("/api/v1/csrf")
    assert resp.status_code == 200
    payload = resp.json()
    assert "csrfToken" in payload
    assert isinstance(payload["csrfToken"], str)
    assert len(payload["csrfToken"]) >= 32
    # Cookie is set on the response so subsequent requests carry it.
    assert CSRF_COOKIE_NAME in resp.cookies


def test_post_with_valid_csrf_header_proceeds() -> None:
    """AC2: matching header value → handler runs."""
    client = TestClient(_make_app())
    token_resp = client.get("/api/v1/csrf")
    token = token_resp.json()["csrfToken"]

    resp = client.post("/mutate", headers={CSRF_HEADER_NAME: token})
    assert resp.status_code == 200
    assert resp.json() == {"status": "mutated"}


def test_put_with_valid_csrf_header_proceeds() -> None:
    """All mutating verbs (POST/PUT/PATCH/DELETE) accept a matching token."""
    client = TestClient(_make_app())
    token = client.get("/api/v1/csrf").json()["csrfToken"]

    resp = client.put("/mutate-put", headers={CSRF_HEADER_NAME: token})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Middleware — rejection
# ---------------------------------------------------------------------------


def test_post_without_csrf_header_is_rejected() -> None:
    """AC1: missing header → 403."""
    client = TestClient(_make_app())
    # Mint a session so the request carries a cookie but no header.
    client.get("/api/v1/csrf")
    resp = client.post("/mutate")
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["error"]["code"] == "csrf_missing"


def test_post_with_wrong_csrf_header_is_rejected() -> None:
    """Mismatched header → 403 (cookie token != header token)."""
    client = TestClient(_make_app())
    client.get("/api/v1/csrf")  # establishes the cookie
    resp = client.post(
        "/mutate",
        headers={CSRF_HEADER_NAME: "totally-wrong-token-value"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["error"]["code"] == "csrf_mismatch"


def test_post_without_cookie_is_rejected() -> None:
    """Header without a backing cookie → 403 (no session secret to match)."""
    client = TestClient(_make_app())
    # Use a fabricated header but no prior /csrf to set the cookie.
    resp = client.post(
        "/mutate",
        headers={CSRF_HEADER_NAME: "anything-anything-anything"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Toss WebView bypass — AC3
# ---------------------------------------------------------------------------


def test_authorization_bearer_bypasses_csrf() -> None:
    """AC3: requests with ``Authorization: Bearer …`` skip CSRF entirely.

    Toss WebView posts back to us using a Bearer token (its own session
    is opaque to the cookie store), so CSRF would be moot — Bearer is
    already proof-of-possession.
    """
    client = TestClient(_make_app())
    resp = client.post(
        "/mutate",
        headers={"Authorization": "Bearer fake.jwt.value"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "mutated"}


def test_authorization_case_insensitive_bypass() -> None:
    """HTTP header names are case-insensitive — lowercase also bypasses."""
    client = TestClient(_make_app())
    resp = client.post(
        "/mutate",
        headers={"authorization": "Bearer x"},
    )
    assert resp.status_code == 200


def test_non_bearer_authorization_does_not_bypass() -> None:
    """Only ``Bearer`` qualifies — ``Basic`` etc. still need a CSRF token."""
    client = TestClient(_make_app())
    resp = client.post(
        "/mutate",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Token rotation / reuse
# ---------------------------------------------------------------------------


def test_csrf_endpoint_reuses_cookie_token() -> None:
    """Second call to ``/csrf`` returns the SAME token already bound to cookie.

    Rotating per-request would force the frontend to call ``/csrf``
    before every mutation; instead we mint once per session and let the
    frontend cache it.
    """
    client = TestClient(_make_app())
    t1 = client.get("/api/v1/csrf").json()["csrfToken"]
    t2 = client.get("/api/v1/csrf").json()["csrfToken"]
    assert t1 == t2


# ---------------------------------------------------------------------------
# Constant-time comparison
# ---------------------------------------------------------------------------


def test_middleware_uses_constant_time_compare(monkeypatch: pytest.MonkeyPatch) -> None:
    """Internal compare uses ``hmac.compare_digest`` to avoid timing leaks."""
    import hmac

    calls: list[tuple[str, str]] = []

    original = hmac.compare_digest

    def spy(a, b):  # type: ignore[no-untyped-def]
        calls.append((str(a), str(b)))
        return original(a, b)

    monkeypatch.setattr("voicesaju.security.csrf.hmac.compare_digest", spy)

    client = TestClient(_make_app())
    token = client.get("/api/v1/csrf").json()["csrfToken"]
    client.post("/mutate", headers={CSRF_HEADER_NAME: token})

    assert calls, "compare_digest must be invoked on the verification path"


# ---------------------------------------------------------------------------
# Middleware wiring — direct class usage
# ---------------------------------------------------------------------------


def test_middleware_can_be_added_directly() -> None:
    """``app.add_middleware(CSRFMiddleware)`` is the supported install path.

    ``install_csrf`` is the convenience wrapper that also mounts
    ``GET /api/v1/csrf``; consumers that only want the gate (e.g. tests
    of other middlewares) can add the class directly.
    """
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.post("/x")
    async def x() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    resp = client.post("/x")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Staged-rollout flag
# ---------------------------------------------------------------------------


def test_install_csrf_disabled_short_circuits() -> None:
    """``install_csrf(app, enabled=False)`` lets POSTs through unconditionally.

    The Phase-1 default for ``Settings.csrf_enabled`` is False so
    existing endpoints keep working while the frontend wires up the
    header on every mutating fetch. The gate flips on per environment.
    """
    app = FastAPI()
    install_csrf(app, enabled=False)

    @app.post("/mutate")
    async def mutate() -> dict[str, str]:
        return {"status": "mutated"}

    client = TestClient(app)
    resp = client.post("/mutate")
    assert resp.status_code == 200
    # /csrf endpoint stays mounted so the frontend can still mint a token.
    csrf_resp = client.get("/api/v1/csrf")
    assert csrf_resp.status_code == 200
    assert "csrfToken" in csrf_resp.json()
