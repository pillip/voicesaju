"""Integration tests for POST /api/v1/auth/logout (ISSUE-072)."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from voicesaju.main import create_app


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_KEK_BASE64", base64.b64encode(b"\x00" * 32).decode())
    monkeypatch.setenv("KMS_PROVIDER", "local")


def test_logout_clears_session_cookie_idempotent() -> None:
    """Logout returns 200 and emits an expired vs_sess Set-Cookie header.

    Idempotent: the route accepts callers without a session cookie so
    the frontend can fire-and-forget. The cookie is always cleared on
    the response.
    """
    app = create_app()
    client = TestClient(app)

    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200, resp.text
    # Starlette delete_cookie emits an expired Set-Cookie.
    set_cookie = resp.headers.get("set-cookie", "")
    assert "vs_sess=" in set_cookie


def test_logout_with_stale_cookie_still_200() -> None:
    """A caller sending a vs_sess cookie that maps to no session is OK."""
    app = create_app()
    client = TestClient(app)
    client.cookies.set("vs_sess", "stale-session-id-not-in-store")

    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
