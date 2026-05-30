"""Integration tests for ``POST /api/v1/profile`` (ISSUE-029).

Exercises the profile-creation endpoint end-to-end via FastAPI's
``TestClient`` against an in-memory SQLite engine — the same convention
used by the ISSUE-026 OAuth callback tests so the `users`, `profiles`,
and `saju_charts` tables all participate via the real ORM models.

The route requires an authenticated user (per architecture §6.2). We
seed a ``User`` row before each request and inject a ``UserContext``
into ``request.state.user`` by overriding the auth middleware via a
test-only dependency override.

AC coverage (mirrors ISSUE-029 spec):
- Valid request → 201 with ``{profile_id, chart_id, chart}``.
- ``birth_time=null`` → ``birth_time_known=false`` and ``chart.hour`` is
  ``None``.
- ``is_lunar=true`` → engine converts to solar before computing (we
  pin a date where the lunar→solar shift would produce a *different*
  4-pillar result than treating the same date as solar).
- Two users with identical inputs → identical ``chart_id`` via the
  ``chart_hash`` cache (re-uses the existing ``saju_charts`` row
  rather than inserting a duplicate).
- Same user posting twice → returns the existing profile (idempotent
  per architecture AP-10/AP-11 "on duplicate, return existing profile").
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator

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
    """Provide a deterministic ``LocalKMS`` for envelope encryption.

    Mirrors ``tests/unit/db/test_profile_model.py``: the model's
    ``birth_dt`` setter calls ``envelope.encrypt_field`` which reads
    ``LOCAL_KEK_BASE64`` from the environment. Inject a fixed-but-non-
    placeholder KEK so the test runs in any environment.
    """
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Per-test SQLite engine with the full ORM schema reflected."""
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


def _make_client(engine: AsyncEngine, user_id: str) -> TestClient:
    """Build a TestClient with DB + auth overrides bound to ``user_id``."""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    # The profile route depends on the resolved request.state.user being
    # set; we monkey-patch the auth middleware via a request-state hook
    # that the route reads directly. See `_get_current_user_id` below.
    from voicesaju.users.routers.profile import _get_current_user_id

    app.dependency_overrides[_get_current_user_id] = lambda: user_id

    return TestClient(app)


@pytest.fixture
def user_a(engine: AsyncEngine) -> str:
    return asyncio.run(_seed_user(engine, kakao_sub="kakao-a"))


@pytest.fixture
def user_b(engine: AsyncEngine) -> str:
    return asyncio.run(_seed_user(engine, kakao_sub="kakao-b"))


# ---------------------------------------------------------------------------
# AC 1 — happy path
# ---------------------------------------------------------------------------


def test_create_profile_returns_201_with_chart(
    engine: AsyncEngine,
    user_a: str,
) -> None:
    """AC: valid request → 201 with ``{profile_id, chart_id, chart}``."""
    client = _make_client(engine, user_a)

    resp = client.post(
        "/api/v1/profile",
        json={
            "birth_date": "1997-08-13",
            "birth_time": "07:30",
            "is_lunar": False,
            "gender": "F",
            "name": "민지",
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["profile_id"]
    assert body["chart_id"]
    chart = body["chart"]
    # Year/month/day pillars always present.
    assert chart["year"]["stem"] and chart["year"]["branch"]
    assert chart["month"]["stem"] and chart["month"]["branch"]
    assert chart["day"]["stem"] and chart["day"]["branch"]
    # Hour pillar present because birth_time was provided.
    assert chart["hour"] is not None
    assert chart["hour"]["stem"] and chart["hour"]["branch"]
    # Chart carries the engine version that produced it.
    assert chart["engine_version"].startswith("saju.v1")


# ---------------------------------------------------------------------------
# AC 2 — time unknown
# ---------------------------------------------------------------------------


def test_create_profile_with_null_birth_time_sets_unknown(
    engine: AsyncEngine,
    user_a: str,
) -> None:
    """AC: ``birth_time=null`` → ``birth_time_known=false`` and ``chart.hour=None``."""
    client = _make_client(engine, user_a)

    resp = client.post(
        "/api/v1/profile",
        json={
            "birth_date": "1997-08-13",
            "birth_time": None,
            "is_lunar": False,
            "gender": "F",
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["chart"]["hour"] is None

    # Verify persisted state matches.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read_profile() -> Profile:
        async with maker() as s:
            row = (
                await s.execute(select(Profile).where(Profile.id == body["profile_id"]))
            ).scalar_one()
            return row

    profile = asyncio.run(_read_profile())
    assert profile.birth_time_known is False


# ---------------------------------------------------------------------------
# AC 3 — lunar conversion
# ---------------------------------------------------------------------------


def test_create_profile_with_lunar_date_converts_to_solar(
    engine: AsyncEngine,
    user_a: str,
    user_b: str,
) -> None:
    """AC: ``is_lunar=true`` → chart differs from the solar-interpreted
    chart for the same numeric date (proving the engine converted)."""
    client_a = _make_client(engine, user_a)
    client_b = _make_client(engine, user_b)

    # Pin a date where lunar→solar shift produces a different month.
    # Lunar 1997-07-11 ≈ Solar 1997-08-13 — month pillar moves from
    # 정미 (solar 7월) → 무신 (solar 8월) so we expect a different
    # chart_hash.
    lunar_resp = client_a.post(
        "/api/v1/profile",
        json={
            "birth_date": "1997-07-11",
            "birth_time": "07:30",
            "is_lunar": True,
            "gender": "F",
        },
    )
    solar_resp = client_b.post(
        "/api/v1/profile",
        json={
            "birth_date": "1997-07-11",
            "birth_time": "07:30",
            "is_lunar": False,
            "gender": "F",
        },
    )

    assert lunar_resp.status_code == 201, lunar_resp.text
    assert solar_resp.status_code == 201, solar_resp.text
    assert lunar_resp.json()["chart_id"] != solar_resp.json()["chart_id"]


# ---------------------------------------------------------------------------
# AC 4 — chart_hash cache reuse across users
# ---------------------------------------------------------------------------


def test_two_users_same_inputs_share_chart_id(
    engine: AsyncEngine,
    user_a: str,
    user_b: str,
) -> None:
    """AC: two users with identical inputs → same ``chart_id`` (cache hit)."""
    payload = {
        "birth_date": "1990-01-01",
        "birth_time": "12:00",
        "is_lunar": False,
        "gender": "M",
    }

    a_resp = _make_client(engine, user_a).post("/api/v1/profile", json=payload)
    b_resp = _make_client(engine, user_b).post("/api/v1/profile", json=payload)

    assert a_resp.status_code == 201
    assert b_resp.status_code == 201
    # Profiles differ (each user has their own row) but chart is shared.
    assert a_resp.json()["profile_id"] != b_resp.json()["profile_id"]
    assert a_resp.json()["chart_id"] == b_resp.json()["chart_id"]

    # And only one ``saju_charts`` row exists.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _count_charts() -> int:
        async with maker() as s:
            rows = (await s.execute(select(SajuChart))).scalars().all()
            return len(rows)

    assert asyncio.run(_count_charts()) == 1


# ---------------------------------------------------------------------------
# Idempotency — same user posting twice returns existing profile
# ---------------------------------------------------------------------------


def test_same_user_posting_twice_returns_existing_profile(
    engine: AsyncEngine,
    user_a: str,
) -> None:
    """AP-10/AP-11: on duplicate, return existing profile (no error)."""
    client = _make_client(engine, user_a)
    payload = {
        "birth_date": "1985-05-15",
        "birth_time": "14:00",
        "is_lunar": False,
        "gender": "F",
    }

    first = client.post("/api/v1/profile", json=payload)
    second = client.post("/api/v1/profile", json=payload)

    assert first.status_code == 201, first.text
    # Architecture AP-10 says "on duplicate, return existing profile" —
    # we expect a 200 (or 201) with the *same* profile_id.
    assert second.status_code in (200, 201), second.text
    assert first.json()["profile_id"] == second.json()["profile_id"]
    assert first.json()["chart_id"] == second.json()["chart_id"]


def test_create_profile_requires_authentication(
    engine: AsyncEngine,
) -> None:
    """No auth override → 401 (the route must reject anonymous callers)."""
    # Note: we do NOT call _make_client which injects the user override.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/profile",
            json={
                "birth_date": "1990-01-01",
                "birth_time": "12:00",
                "is_lunar": False,
                "gender": "M",
            },
        )
    assert resp.status_code == 401
