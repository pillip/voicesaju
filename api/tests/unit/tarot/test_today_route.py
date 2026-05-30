"""Tests for ``GET /api/v1/tarot/today`` (ISSUE-049 / FR-012).

Covers AC 1 from the issue: today's card metadata + free-quota envelope
returned within a tight latency budget. The route stitches together
three already-shipped pieces:

* ``voicesaju.tarot.seed.daily_card_index`` — ISSUE-047 deterministic
  card picker.
* ``voicesaju.tarot.quota.check_weekly_free`` — ISSUE-048 weekly free
  draw counter.
* ``voicesaju.db.models.TarotCard`` — ISSUE-016 seeded 22 Major Arcana.

Phase-1 ``card_art_url`` is a relative placeholder
(``/api/v1/tarot/cards/{card_index}/art``) — the real R2-signed CDN
URL lands in ISSUE-055.
"""

from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import AsyncIterator

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
    Device,
    Profile,
    TarotCard,
    TarotDraw,
    User,
)
from voicesaju.main import create_app
from voicesaju.tarot.seed import daily_card_index


@pytest.fixture(autouse=True)
def _local_kek_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide deterministic env for the mock-provider stack."""
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("STORAGE_PROVIDER", "mock")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_22_cards(engine: AsyncEngine) -> None:
    """Mirror migration ``0008_tarot_tables_seed`` for unit tests."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        for idx in range(22):
            s.add(
                TarotCard(
                    card_index=idx,
                    name_kr=f"메이저-{idx:02d}",
                    name_en=f"Major {idx:02d}",
                    meaning_kr=f"meaning_kr_{idx}",
                    art_key=f"tarot/major/{idx:02d}.webp",
                )
            )
        await s.commit()


async def _seed_user(engine: AsyncEngine, *, kakao_sub: str) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        # Profile is optional for the today route.
        return str(u.id)


def _make_client(engine: AsyncEngine, user_id: str | None) -> TestClient:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    if user_id is not None:
        from voicesaju.tarot.routers.today import _get_current_user_id

        app.dependency_overrides[_get_current_user_id] = lambda: user_id

    return TestClient(app)


# ---------------------------------------------------------------------------
# AC 1 — GET /tarot/today returns the expected envelope.
# ---------------------------------------------------------------------------


def test_get_today_returns_card_metadata_and_quota(engine: AsyncEngine) -> None:
    """AC 1: response carries card_index/card_name/card_art_url + quota."""
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-today-1"))
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/tarot/today")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Required fields per architecture §6.4.
    assert "card_index" in body
    assert isinstance(body["card_index"], int)
    assert 0 <= body["card_index"] < 22
    assert "card_name" in body and isinstance(body["card_name"], str)
    assert body["card_name"]  # non-empty
    assert "card_art_url" in body and isinstance(body["card_art_url"], str)
    # Phase-1 placeholder URL convention — kept relative so the frontend
    # can prefix with its own CDN host when ISSUE-055 lands.
    assert body["card_art_url"] == f"/api/v1/tarot/cards/{body['card_index']}/art"
    # Quota fields — fresh user this week → 1 remaining, not requiring payment.
    assert body["free_remaining"] == 1
    assert body["requires_payment"] is False


def test_get_today_card_is_deterministic_for_user(engine: AsyncEngine) -> None:
    """Two calls in the same KST day return the same card for the same user."""
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-today-stable"))
    client = _make_client(engine, user_id)

    resp1 = client.get("/api/v1/tarot/today")
    resp2 = client.get("/api/v1/tarot/today")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["card_index"] == resp2.json()["card_index"]
    assert resp1.json()["card_name"] == resp2.json()["card_name"]


def test_get_today_card_matches_seed_function(engine: AsyncEngine) -> None:
    """The chosen card_index equals daily_card_index(today_kst, user_id)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-today-seed-match"))
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/tarot/today")
    assert resp.status_code == 200
    body = resp.json()

    today_kst = datetime.now(ZoneInfo("Asia/Seoul")).date()
    expected = daily_card_index(today_kst, user_id)
    assert body["card_index"] == expected


def test_get_today_returns_within_latency_budget(engine: AsyncEngine) -> None:
    """AC 1 latency budget: GET /tarot/today returns in well under 1s on mock.

    Production budget is 100ms (NFR-003). The mock+SQLite stack has more
    overhead than prod (TestClient, in-memory DB, monkeypatch fixtures),
    so we relax the unit budget to 1s — enough to catch obvious O(N) or
    N+1 regressions without flaking on CI jitter.
    """
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-today-fast"))
    client = _make_client(engine, user_id)

    # Warm up (first request pays for app + DB setup).
    client.get("/api/v1/tarot/today")

    started = time.perf_counter()
    resp = client.get("/api/v1/tarot/today")
    elapsed = time.perf_counter() - started

    assert resp.status_code == 200
    assert elapsed < 1.0, f"GET /tarot/today took {elapsed:.3f}s (budget 1.0s)"


# ---------------------------------------------------------------------------
# Auth — anonymous (no user_id, no device cookie) should 401.
# ---------------------------------------------------------------------------


def test_get_today_requires_identification(engine: AsyncEngine) -> None:
    """Caller without user or device → 401 (auth boundary, before quota)."""
    asyncio.run(_seed_22_cards(engine))
    client = _make_client(engine, user_id=None)

    resp = client.get("/api/v1/tarot/today")
    assert resp.status_code == 401
