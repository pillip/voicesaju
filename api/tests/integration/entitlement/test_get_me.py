"""Integration tests for ``GET /api/v1/me`` (ISSUE-040).

Verifies the real entitlement endpoint that replaces the M1 stub at
``web/src/lib/api/me-stub.ts`` (added in ISSUE-030).

Architecture-Ref: §6.1 (``GET /api/v1/me`` shape).
data_model-Ref: AP-16 / AP-17 / AP-21.
PRD-Ref: FR-006, FR-014, FR-022.

Conventions follow ``tests/integration/profile/test_create_profile.py``:
in-memory SQLite engine, real ORM models, ``_get_current_user_id``
dependency override so we don't need to actually sign a JWT.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models import (  # noqa: F401 - register metadata
    FreeToken,
    Subscription,
    User,
)
from voicesaju.main import create_app


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_user(engine: AsyncEngine, kakao_sub: str = "kakao-me-1") -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


def _make_client(engine: AsyncEngine, user_id: str | None) -> TestClient:
    """Build a TestClient with DB + auth overrides bound to ``user_id``.

    Passing ``user_id=None`` simulates an anonymous request — the route
    handler returns the non-member shape rather than 401, matching the
    architecture §6.1 contract for ``GET /api/v1/me``.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    from voicesaju.users.routers.me import _get_optional_user_id

    app.dependency_overrides[_get_optional_user_id] = lambda: user_id

    return TestClient(app)


# ---------------------------------------------------------------------------
# Authenticated user with active signup_grant.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_returns_token_for_signed_in_user_with_signup_grant(
    engine: AsyncEngine,
) -> None:
    """Signed-in user with a signup_grant → ``entitlement.kind='free_token'``."""
    user_id = await _seed_user(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(FreeToken(user_id=user_id, kind="signup_grant"))
        await s.commit()

    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"] == user_id
    ent = body["entitlement"]
    assert ent["kind"] == "free_token"
    assert ent["has_anything"] is True
    assert ent["requires_payment"] is False
    assert ent["token_id"] is not None
    client.close()


# ---------------------------------------------------------------------------
# Authenticated user with active subscription credit.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_returns_subscription_for_active_subscriber(
    engine: AsyncEngine,
) -> None:
    """Signed-in subscriber with quota=1 → ``entitlement.kind='subscription'``."""
    user_id = await _seed_user(engine, kakao_sub="kakao-sub-1")

    now = datetime.now(UTC)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(
            Subscription(
                user_id=user_id,
                status="active",
                monthly_saju_remaining=1,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        await s.commit()

    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ent = body["entitlement"]
    assert ent["kind"] == "subscription"
    assert ent["has_anything"] is True
    assert ent["subscription_id"] is not None
    client.close()


# ---------------------------------------------------------------------------
# Authenticated user with no entitlement.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_returns_none_for_user_with_no_entitlement(
    engine: AsyncEngine,
) -> None:
    """Signed-in user, no token + no subscription → ``entitlement.kind='none'``."""
    user_id = await _seed_user(engine, kakao_sub="kakao-empty-1")
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ent = body["entitlement"]
    assert ent["kind"] == "none"
    assert ent["has_anything"] is False
    assert ent["requires_payment"] is True
    client.close()


# ---------------------------------------------------------------------------
# Anonymous caller (no session) — Architecture §6.1 returns a sensible shape.
# ---------------------------------------------------------------------------


def test_get_me_anonymous_returns_none_entitlement(engine: AsyncEngine) -> None:
    """Anonymous caller → ``user_id=None``, ``entitlement.kind='none'``.

    Architecture §6.1 documents ``GET /api/v1/me`` as a safe-to-call probe
    that returns the caller's identity + entitlement summary. Anonymous
    callers receive ``user_id=null`` so the frontend can branch on it.
    """
    client = _make_client(engine, None)
    resp = client.get("/api/v1/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"] is None
    ent = body["entitlement"]
    assert ent["kind"] == "none"
    assert ent["has_anything"] is False
    assert ent["requires_payment"] is True
    client.close()
