"""Integration tests for ``PATCH /api/v1/profile`` (ISSUE-071, FR-029).

Covers the AC list verbatim:

AC1: 0 corrections used + PATCH new birth_date → counter increments
     to 1 + a new ``saju_charts`` row is created.
AC2: 2 corrections used + PATCH → 403 with
     ``error.code='correction_quota_exceeded'``.
AC3: counter is 2/2 → handled by the frontend reading the response
     (asserted via the response body's ``corrections_remaining=0`` field).
AC4: past readings keep referencing the OLD chart_id after a
     correction (chart history is preserved per AP-14).

Plus auth + 404 guards.

Architecture-Ref: §6.2, AP-14. PRD-Ref: FR-029, US-17.
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
    """Deterministic ``LocalKMS`` for envelope encryption (mirrors POST tests)."""
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


async def _seed_user(engine: AsyncEngine, kakao_sub: str = "patch-1") -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


def _make_client(engine: AsyncEngine, user_id: str | None) -> TestClient:
    """Build a TestClient with DB + auth overrides bound to ``user_id``."""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    from voicesaju.users.routers.profile import _get_current_user_id

    if user_id is not None:
        app.dependency_overrides[_get_current_user_id] = lambda: user_id
    return TestClient(app)


async def _seed_profile(
    client: TestClient,
    *,
    birth_date: str = "1997-08-13",
    birth_time: str | None = "07:30",
    is_lunar: bool = False,
    gender: str = "F",
    name: str | None = "민지",
) -> dict:
    """POST a profile and return the response body."""
    resp = client.post(
        "/api/v1/profile",
        json={
            "birth_date": birth_date,
            "birth_time": birth_time,
            "is_lunar": is_lunar,
            "gender": gender,
            "name": name,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# AC1: first correction increments counter + creates a new chart row
# ---------------------------------------------------------------------------


def test_patch_first_correction_increments_counter_and_inserts_chart(
    engine: AsyncEngine,
) -> None:
    """AC1: 0 corrections + PATCH → counter=1 + new ``saju_charts`` row."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)
    created = asyncio.run(_seed_profile(client))
    original_chart_id = created["chart_id"]

    # Sanity: pre-PATCH counter is 0.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read_counter() -> int:
        async with maker() as s:
            p = (
                await s.execute(select(Profile).where(Profile.user_id == user_id))
            ).scalar_one()
            return p.correction_count

    assert asyncio.run(_read_counter()) == 0

    async def _count_charts() -> int:
        async with maker() as s:
            rows = (
                (await s.execute(select(SajuChart).where(SajuChart.user_id == user_id)))
                .scalars()
                .all()
            )
            return len(rows)

    assert asyncio.run(_count_charts()) == 1

    # PATCH with a different birth_date so the new chart_hash differs.
    resp = client.patch(
        "/api/v1/profile",
        json={
            "birth_date": "1998-09-14",
            "birth_time": "09:45",
            "is_lunar": False,
            "gender": "F",
            "name": "민지",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # AC1: chart_id is NEW (not the original).
    assert body["chart_id"] != original_chart_id
    # Response surfaces the post-mutation counter for the banner UI.
    assert body["corrections_remaining"] == 1

    # AC1: counter is now 1.
    assert asyncio.run(_read_counter()) == 1
    # AC1: a NEW saju_charts row exists for this user (in addition to
    # the original — chart history is preserved per AP-14).
    assert asyncio.run(_count_charts()) == 2


# ---------------------------------------------------------------------------
# AC2: at quota → 403 with the correct error code
# ---------------------------------------------------------------------------


def test_patch_returns_403_when_quota_exhausted(engine: AsyncEngine) -> None:
    """AC2: 2 corrections + PATCH → 403 ``correction_quota_exceeded``."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)
    asyncio.run(_seed_profile(client))

    # Burn through both corrections.
    for i, date in enumerate(["1998-09-14", "1999-10-15"]):
        resp = client.patch(
            "/api/v1/profile",
            json={
                "birth_date": date,
                "birth_time": "09:45",
                "is_lunar": False,
                "gender": "F",
                "name": "민지",
            },
        )
        assert resp.status_code == 200, (i, resp.text)
        assert resp.json()["corrections_remaining"] == 1 - i

    # 3rd PATCH must surface 403.
    resp = client.patch(
        "/api/v1/profile",
        json={
            "birth_date": "2000-11-16",
            "birth_time": "10:00",
            "is_lunar": False,
            "gender": "F",
        },
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    # FastAPI wraps the ``detail`` key around our dict.
    assert body["detail"]["error"]["code"] == "correction_quota_exceeded"
    assert body["detail"]["error"]["corrections_remaining"] == 0


# ---------------------------------------------------------------------------
# AC4: past readings keep referencing the old chart_id
# ---------------------------------------------------------------------------


def test_patch_preserves_old_chart_row_for_history(
    engine: AsyncEngine,
) -> None:
    """AC4: after PATCH, the OLD chart row is intact (history references it)."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)
    created = asyncio.run(_seed_profile(client))
    original_chart_id = created["chart_id"]
    original_chart_hash = created["chart"]["year"]["stem"]  # any deterministic field

    # PATCH new inputs.
    resp = client.patch(
        "/api/v1/profile",
        json={
            "birth_date": "1998-09-14",
            "birth_time": "09:45",
            "is_lunar": False,
            "gender": "F",
            "name": "민지",
        },
    )
    assert resp.status_code == 200

    # Original chart row STILL exists with the original chart_hash.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read_old_chart() -> SajuChart:
        async with maker() as s:
            return (
                await s.execute(
                    select(SajuChart).where(SajuChart.id == original_chart_id)
                )
            ).scalar_one()

    old = asyncio.run(_read_old_chart())
    assert str(old.id) == original_chart_id
    # The pillars dict still reflects the original year-pillar stem.
    assert old.pillars["year"]["stem"] == original_chart_hash


# ---------------------------------------------------------------------------
# AC: same-input PATCH still increments + reuses cached chart row
# ---------------------------------------------------------------------------


def test_patch_with_same_inputs_still_increments_counter(
    engine: AsyncEngine,
) -> None:
    """A re-submission of the SAME inputs still counts as a correction.

    The chart row may be reused (AP-11 cache hit by chart_hash) but
    the counter still increments — the spec frames "수정 횟수" as a
    user-action count, not a chart-change count.
    """
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)
    asyncio.run(_seed_profile(client))

    resp = client.patch(
        "/api/v1/profile",
        json={
            # Same as the seed.
            "birth_date": "1997-08-13",
            "birth_time": "07:30",
            "is_lunar": False,
            "gender": "F",
            "name": "민지",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["corrections_remaining"] == 1


# ---------------------------------------------------------------------------
# Guards: auth + 404
# ---------------------------------------------------------------------------


def test_patch_returns_401_when_anonymous(engine: AsyncEngine) -> None:
    """Anonymous PATCH → 401."""
    client = _make_client(engine, user_id=None)
    resp = client.patch(
        "/api/v1/profile",
        json={
            "birth_date": "1997-08-13",
            "birth_time": "07:30",
            "is_lunar": False,
            "gender": "F",
        },
    )
    assert resp.status_code == 401


def test_patch_returns_404_when_profile_absent(engine: AsyncEngine) -> None:
    """PATCH before POST → 404 (no profile to correct)."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)

    resp = client.patch(
        "/api/v1/profile",
        json={
            "birth_date": "1997-08-13",
            "birth_time": "07:30",
            "is_lunar": False,
            "gender": "F",
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Validation: bad shape → 422
# ---------------------------------------------------------------------------


def test_patch_rejects_bad_birth_date_shape(engine: AsyncEngine) -> None:
    """Invalid birth_date format → 422."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)
    asyncio.run(_seed_profile(client))

    resp = client.patch(
        "/api/v1/profile",
        json={
            "birth_date": "97-08-13",  # missing century
            "birth_time": "07:30",
            "is_lunar": False,
            "gender": "F",
        },
    )
    assert resp.status_code == 422
