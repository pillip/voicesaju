"""Integration tests for ``GET /api/v1/profile/me`` (ISSUE-064).

Exercises the read-back endpoint that drives the ``/me/saju`` page
(Screen 17). Mirrors the layout used by ``test_create_profile.py``:
in-memory SQLite + ``TestClient`` + dependency overrides for both
``get_session`` and ``_get_current_user_id``.

AC coverage (ISSUE-064):
- Logged-in user with a profile → 200 with persisted chart + birth_time_known.
- ``birth_time_known=false`` round-trips so the page can render "모름".
- Logged-in user without a profile → 404 (onboarding-incomplete state).
- Anonymous caller → 401.
- Soft-deleted profile (``deleted_at IS NOT NULL``) → 404 (treated as absent).
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from datetime import UTC, datetime

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
from voicesaju.db.models import Profile, SajuChart, User  # noqa: F401
from voicesaju.main import create_app


@pytest.fixture(autouse=True)
def _local_kek_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a deterministic ``LocalKMS`` for envelope encryption."""
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_user(engine: AsyncEngine, **overrides: str) -> str:
    """Insert a ``users`` row and return its stringified UUID."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=overrides.get("kakao_sub", "kakao-seed-1"))
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


def _make_client(engine: AsyncEngine, user_id: str | None) -> TestClient:
    """TestClient with DB + (optional) auth overrides.

    ``user_id=None`` simulates an anonymous caller — ``_get_current_user_id``
    is left unpatched so the production guard fires a 401.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    if user_id is not None:
        from voicesaju.users.routers.profile import _get_current_user_id

        app.dependency_overrides[_get_current_user_id] = lambda: user_id

    return TestClient(app)


@pytest.fixture
def user_a(engine: AsyncEngine) -> str:
    return asyncio.run(_seed_user(engine, kakao_sub="kakao-a"))


def _seed_profile(
    engine: AsyncEngine,
    user_id: str,
    *,
    birth_date: str = "1988-12-12",
    birth_time: str | None = "07:30",
    is_lunar: bool = False,
    gender: str = "F",
) -> str:
    """POST /api/v1/profile to create a profile + chart; return profile_id."""
    client = _make_client(engine, user_id)
    resp = client.post(
        "/api/v1/profile",
        json={
            "birth_date": birth_date,
            "birth_time": birth_time,
            "is_lunar": is_lunar,
            "gender": gender,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["profile_id"]


# ---------------------------------------------------------------------------
# AC 1 — happy path: logged-in user with profile → chart payload
# ---------------------------------------------------------------------------


def test_get_profile_me_returns_persisted_chart(
    engine: AsyncEngine,
    user_a: str,
) -> None:
    """Logged-in user with a profile → 200 with chart + birth_time_known."""
    profile_id = _seed_profile(engine, user_a, birth_time="07:30")

    client = _make_client(engine, user_a)
    resp = client.get("/api/v1/profile/me")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["profile_id"] == profile_id
    assert body["chart_id"]
    assert body["birth_time_known"] is True

    chart = body["chart"]
    # Year/month/day pillars always present.
    assert chart["year"]["stem"] and chart["year"]["branch"]
    assert chart["month"]["stem"] and chart["month"]["branch"]
    assert chart["day"]["stem"] and chart["day"]["branch"]
    # Hour pillar present because birth_time was provided.
    assert chart["hour"] is not None
    assert chart["hour"]["stem"] and chart["hour"]["branch"]
    assert chart["engine_version"].startswith("saju.v1")


# ---------------------------------------------------------------------------
# AC 2 — time unknown → birth_time_known=false + chart.hour is None
# ---------------------------------------------------------------------------


def test_get_profile_me_with_unknown_birth_time(
    engine: AsyncEngine,
    user_a: str,
) -> None:
    """birth_time=null at create → GET round-trips birth_time_known=false."""
    _seed_profile(engine, user_a, birth_time=None)

    client = _make_client(engine, user_a)
    resp = client.get("/api/v1/profile/me")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["birth_time_known"] is False
    assert body["chart"]["hour"] is None


# ---------------------------------------------------------------------------
# AC 3 — anonymous → 401
# ---------------------------------------------------------------------------


def test_get_profile_me_requires_auth(engine: AsyncEngine) -> None:
    """Anonymous caller → 401 (consistent with POST /api/v1/profile)."""
    client = _make_client(engine, user_id=None)
    resp = client.get("/api/v1/profile/me")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# AC 4 — logged in but no profile → 404
# ---------------------------------------------------------------------------


def test_get_profile_me_without_profile_returns_404(
    engine: AsyncEngine,
    user_a: str,
) -> None:
    """User exists but no profile row → 404 (onboarding incomplete)."""
    # Note: we deliberately do NOT seed a profile here.
    client = _make_client(engine, user_a)
    resp = client.get("/api/v1/profile/me")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# AC 5 — soft-deleted profile is treated as absent
# ---------------------------------------------------------------------------


def test_get_profile_me_skips_soft_deleted_profile(
    engine: AsyncEngine,
    user_a: str,
) -> None:
    """A profile with ``deleted_at IS NOT NULL`` is invisible to GET /me."""
    _seed_profile(engine, user_a)

    # Stamp ``deleted_at`` directly on the row so we don't depend on the
    # ISSUE-072 soft-delete route (which lives on a sibling branch).
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _soft_delete() -> None:
        async with maker() as s:
            row = (
                await s.execute(select(Profile).where(Profile.user_id == user_a))
            ).scalar_one()
            row.deleted_at = datetime.now(UTC)
            await s.commit()

    asyncio.run(_soft_delete())

    client = _make_client(engine, user_a)
    resp = client.get("/api/v1/profile/me")
    assert resp.status_code == 404, resp.text
