"""Integration tests for the Apple OAuth callback route (ISSUE-026).

Exercises ``POST /api/v1/auth/apple/callback`` (Apple's mandatory
``response_mode=form_post`` shape) against:

- In-memory SQLite engine (same fixture pattern as the Kakao tests).
- In-process ``SessionStore``.
- Mock auth adapter — ISSUE-025 (real Apple JWT/JWKS) is deferred.

AC coverage:
- Apple ``form_post`` callback → session created identically to Kakao
  (per ISSUE-026 AC verbatim).
- Cross-provider dup-detection: a Kakao callback + an Apple callback
  with matching email_hash collapse to a single User row (architecture
  §11). Verified by inspecting the DB row count post-callback.

NOTE: lives under ``tests/integration/`` to mirror the issue spec
layout; unmarked because it runs on SQLite + mock (no external
services).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

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
from voicesaju.db.models import User  # noqa: F401 - register metadata
from voicesaju.main import create_app
from voicesaju.users.routers.auth import _get_session_store_dep
from voicesaju.users.services.session_service import InMemorySessionStore


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def store() -> InMemorySessionStore:
    return InMemorySessionStore()


@pytest.fixture
def client(engine: AsyncEngine, store: InMemorySessionStore) -> Iterator[TestClient]:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[_get_session_store_dep] = lambda: store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_apple_callback_creates_user_and_sets_vs_sess(
    client: TestClient,
) -> None:
    """AC: Apple ``form_post`` callback → session created same as Kakao."""
    resp = client.post(
        "/api/v1/auth/apple/callback",
        data={"code": "apple-signup-1"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == "created"
    assert body["provider"] == "apple"
    assert body["signup_grant_minted"] is True

    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "vs_sess=" in set_cookie
    assert "httponly" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=lax" in set_cookie


def test_apple_callback_then_kakao_callback_link_by_email(
    client: TestClient,
    engine: AsyncEngine,
) -> None:
    """AC: two providers, same email_hash → single User row (architecture §11)."""
    apple_resp = client.post(
        "/api/v1/auth/apple/callback",
        data={"code": "dup-email-test"},
    )
    kakao_resp = client.get(
        "/api/v1/auth/kakao/callback?code=dup-email-test",
    )

    assert apple_resp.status_code == 200
    assert kakao_resp.status_code == 200
    assert apple_resp.json()["outcome"] == "created"
    assert kakao_resp.json()["outcome"] == "linked_by_email"
    # Both providers resolve to the same User row.
    assert apple_resp.json()["user_id"] == kakao_resp.json()["user_id"]

    # Confirm DB only carries one User row even though two providers signed in.
    import asyncio

    async def _user_count() -> int:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as s:
            rows = (await s.execute(select(User))).scalars().all()
            return len(rows)

    assert asyncio.run(_user_count()) == 1


def test_apple_callback_missing_code_returns_4xx(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/apple/callback", data={})
    assert resp.status_code in (400, 422)


def test_apple_start_returns_redirect_target(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/apple/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "apple"
    assert "redirect_url" in body
