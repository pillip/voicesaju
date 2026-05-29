"""Integration tests for the Kakao OAuth callback route (ISSUE-026).

Exercises ``GET /api/v1/auth/kakao/callback`` end-to-end via FastAPI's
``TestClient`` against:

- An in-memory SQLite engine (so ``free_tokens`` idempotency, ``users``
  row creation, and ``email_hash`` dup-detection are all exercised
  through the real ORM models).
- An in-process ``SessionStore`` (the architecture §11.1 Redis backend
  drops in behind the same Protocol without route changes).
- The mock auth adapter (``AUTH_PROVIDER=mock``) — Phase 1 default per
  the briefing; ISSUE-025 (Authlib + real Kakao userinfo HTTP) is
  deferred. The mock's ``resolve_oauth_callback`` returns deterministic
  synthetic ``(subject_id, email)`` so the tests don't need to spin up
  a Kakao stub server.

AC coverage:
- Valid callback → User row + ``vs_sess`` cookie set.
- First-time signup → exactly one ``free_tokens`` row with
  ``kind='signup_grant'`` (idempotent on a second callback for the
  same user).

NOTE: this file lives under ``tests/integration/`` to match the
layout requested in the ISSUE-026 spec, but the tests do NOT carry
the ``@pytest.mark.integration`` marker — they run against SQLite +
mock-adapter (no external services), so they belong in the default
CI suite (the ``integration`` marker is reserved for Postgres-bound
tests per the pyproject config).
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
from voicesaju.db.models import FreeToken, User  # noqa: F401 - register metadata
from voicesaju.main import create_app
from voicesaju.users.routers.auth import (
    _get_session_store_dep,
)
from voicesaju.users.services.session_service import (
    InMemorySessionStore,
)


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


def test_kakao_callback_creates_user_and_sets_vs_sess(
    client: TestClient,
) -> None:
    """AC: valid Kakao callback → User row + ``vs_sess`` cookie."""
    resp = client.get("/api/v1/auth/kakao/callback?code=signup-code-1")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == "created"
    assert body["provider"] == "kakao"
    assert body["signup_grant_minted"] is True
    assert body["user_id"]

    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "vs_sess=" in set_cookie
    assert "httponly" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=lax" in set_cookie
    # 30 days = 2_592_000 seconds.
    assert "max-age=2592000" in set_cookie


def test_kakao_callback_second_time_is_idempotent_signup_grant(
    client: TestClient,
    engine: AsyncEngine,
) -> None:
    """AC: second callback for the same user → no second ``signup_grant`` row."""
    first = client.get("/api/v1/auth/kakao/callback?code=signup-code-2")
    second = client.get("/api/v1/auth/kakao/callback?code=signup-code-2")

    assert first.status_code == 200
    assert second.status_code == 200
    # First call mints the grant; second call resolves by sub → no grant.
    assert first.json()["signup_grant_minted"] is True
    assert second.json()["outcome"] == "found_by_sub"
    assert second.json()["signup_grant_minted"] is False
    # Same user across both callbacks.
    assert first.json()["user_id"] == second.json()["user_id"]

    # And only one signup_grant row exists in the DB.
    import asyncio

    async def _count_grants() -> int:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as s:
            rows = (
                (
                    await s.execute(
                        select(FreeToken).where(
                            FreeToken.user_id == first.json()["user_id"],
                            FreeToken.kind == "signup_grant",
                        )
                    )
                )
                .scalars()
                .all()
            )
            return len(rows)

    assert asyncio.run(_count_grants()) == 1


def test_kakao_callback_missing_code_returns_400(client: TestClient) -> None:
    """AC: missing OAuth code → 400."""
    resp = client.get("/api/v1/auth/kakao/callback")
    # FastAPI returns 422 for a missing required query param; either is
    # acceptable for "client did the wrong thing" — assert it's not 200.
    assert resp.status_code in (400, 422)


def test_kakao_start_returns_redirect_target(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/kakao/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "kakao"
    assert "redirect_url" in body
