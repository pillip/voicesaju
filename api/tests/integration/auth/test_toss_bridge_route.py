"""Integration tests for the Toss bridge auth route (ISSUE-046).

Covers the full bridge flow end-to-end via FastAPI ``TestClient``:

- AC1: valid token + allowlisted Origin → user upserted by ``toss_id`` +
  ``vs_sess`` cookie set with ``SameSite=None; Secure`` attributes.
- AC2: invalid signature → 401.
- AC3: Origin not in allowlist → 403 (no cookie set).
- AC4: Channel=``toss_webview`` + ``GET /api/v1/reading/paywall`` →
  only ``method=tosspay`` listed in the response.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models.users import User
from voicesaju.main import create_app

SECRET = "test-toss-bridge-secret-do-not-use-in-prod"
AUDIENCE = "voicesaju"
ALLOWED_ORIGIN = "https://m.tosspayments.com"


@pytest.fixture(autouse=True)
def _env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")
    monkeypatch.setenv("PAYMENT_PROVIDER", "mock")
    monkeypatch.setenv("TOSS_BRIDGE_SECRET", SECRET)
    monkeypatch.setenv("TOSS_BRIDGE_AUDIENCE", AUDIENCE)
    # JSON-array form so Pydantic v2 settings can parse a list[str] from env.
    monkeypatch.setenv("TOSS_WEBVIEW_ORIGIN_ALLOWLIST", f'["{ALLOWED_ORIGIN}"]')


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def client(engine: AsyncEngine) -> Iterator[TestClient]:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_token(
    *,
    sub: str = "toss-user-1",
    aud: str = AUDIENCE,
    exp_delta_seconds: int = 300,
    secret: str = SECRET,
) -> str:
    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "iss": "tosspayments",
            "sub": sub,
            "aud": aud,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=exp_delta_seconds)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )


# ---------------------------------------------------------------------------
# AC1 — valid token + allowlisted origin → User upsert + cookie set
# ---------------------------------------------------------------------------


def test_valid_token_creates_user_and_sets_cookie(
    client: TestClient, engine: AsyncEngine
) -> None:
    token = _make_token(sub="toss-user-1")

    resp = client.post(
        "/api/v1/auth/toss-bridge",
        json={"token": token},
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == "created"
    assert body["toss_id"] == "toss-user-1"
    assert body["user_id"]

    # Cookie was set on the response.
    set_cookie = resp.headers.get("set-cookie", "")
    assert "vs_sess=" in set_cookie
    # SameSite=None Secure cookie required for cross-site WebView use.
    assert "samesite=none" in set_cookie.lower()
    assert "secure" in set_cookie.lower()

    # User row landed.
    import asyncio

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> User:
        async with maker() as s:
            return (
                await s.execute(select(User).where(User.toss_id == "toss-user-1"))
            ).scalar_one()

    user = asyncio.run(_read())
    assert user.toss_id == "toss-user-1"


def test_valid_token_links_existing_user(
    client: TestClient, engine: AsyncEngine
) -> None:
    """Re-POSTing with the same Toss subject returns ``found_by_toss_id``."""
    import asyncio

    maker = async_sessionmaker(engine, expire_on_commit=False)

    # Seed an existing user with toss_id.
    async def _seed() -> str:
        async with maker() as s:
            u = User(toss_id="existing-toss-1")
            s.add(u)
            await s.commit()
            await s.refresh(u)
            return str(u.id)

    user_id = asyncio.run(_seed())

    token = _make_token(sub="existing-toss-1")
    resp = client.post(
        "/api/v1/auth/toss-bridge",
        json={"token": token},
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == "found"
    assert body["user_id"] == user_id


# ---------------------------------------------------------------------------
# AC2 — bad signature → 401
# ---------------------------------------------------------------------------


def test_invalid_signature_returns_401(client: TestClient) -> None:
    bogus = _make_token(secret="some-other-secret")
    resp = client.post(
        "/api/v1/auth/toss-bridge",
        json={"token": bogus},
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert resp.status_code == 401, resp.text
    # No cookie set on rejection.
    assert "vs_sess=" not in resp.headers.get("set-cookie", "")


def test_expired_token_returns_401(client: TestClient) -> None:
    expired = _make_token(exp_delta_seconds=-60)
    resp = client.post(
        "/api/v1/auth/toss-bridge",
        json={"token": expired},
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC3 — Origin not in allowlist → 403
# ---------------------------------------------------------------------------


def test_disallowed_origin_returns_403(client: TestClient) -> None:
    token = _make_token()
    resp = client.post(
        "/api/v1/auth/toss-bridge",
        json={"token": token},
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 403, resp.text
    # No cookie set.
    assert "vs_sess=" not in resp.headers.get("set-cookie", "")


def test_missing_origin_returns_403(client: TestClient) -> None:
    """A request without an Origin header cannot be a legitimate Toss WebView."""
    token = _make_token()
    resp = client.post(
        "/api/v1/auth/toss-bridge",
        json={"token": token},
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# AC4 — paywall returns only tosspay when channel=toss_webview
# ---------------------------------------------------------------------------


def test_paywall_toss_webview_channel_returns_only_tosspay(
    client: TestClient,
) -> None:
    resp = client.get("/api/v1/reading/paywall?channel=toss_webview")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    methods = body.get("methods")
    assert methods is not None
    # Only one option, and it's tosspay.
    assert {m["method"] for m in methods} == {"tosspay"}


def test_paywall_default_channel_returns_all_methods(
    client: TestClient,
) -> None:
    resp = client.get("/api/v1/reading/paywall")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    methods = body.get("methods")
    assert methods is not None
    method_set = {m["method"] for m in methods}
    # The default web channel exposes both Toss-acquired methods.
    assert "tosspay" in method_set
    assert "kakaopay" in method_set


def test_paywall_web_channel_returns_all_methods(
    client: TestClient,
) -> None:
    resp = client.get("/api/v1/reading/paywall?channel=web")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    methods = body.get("methods")
    method_set = {m["method"] for m in methods}
    assert "tosspay" in method_set
    assert "kakaopay" in method_set
