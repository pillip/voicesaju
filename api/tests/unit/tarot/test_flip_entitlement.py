"""Entitlement tests for ``POST /api/v1/tarot/today/flip`` (ISSUE-049).

Covers AC 3 from the issue: when the caller has exhausted the weekly
free quota *and* has no active subscription, the flip endpoint MUST
respond with HTTP 402 carrying ``{"error": {"code": "payment_required"}}``.

The architecture (§6.4) layers entitlement as:

1. Active subscription → bypass quota → 200.
2. Free quota remaining (FR-014, ISSUE-048) → consume → 200.
3. Neither → 402 ``payment_required``.

These tests pin (3) without touching the SSE stream — they assert the
HTTP status + JSON envelope only. AC 2 (idempotency) and AC 4 (SSE
timing) live in ``tests/integration/tarot/test_pipeline.py``.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from datetime import date

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
    TarotCard,
    TarotDraw,
    User,
)
from voicesaju.main import create_app


@pytest.fixture(autouse=True)
def _local_kek_env(monkeypatch: pytest.MonkeyPatch) -> None:
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


async def _seed_22_cards(engine: AsyncEngine) -> dict[int, str]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    out: dict[int, str] = {}
    async with maker() as s:
        for idx in range(22):
            c = TarotCard(
                card_index=idx,
                name_kr=f"메이저-{idx:02d}",
                name_en=f"Major {idx:02d}",
                meaning_kr=f"meaning_kr_{idx}",
                art_key=f"tarot/major/{idx:02d}.webp",
            )
            s.add(c)
        await s.commit()
        # Re-read so we can return card ids for direct-insert fixtures.
        from sqlalchemy import select

        rows = (await s.execute(select(TarotCard))).scalars().all()
        for r in rows:
            out[r.card_index] = str(r.id)
    return out


async def _seed_user(engine: AsyncEngine, *, kakao_sub: str) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


async def _exhaust_weekly_quota(
    engine: AsyncEngine,
    *,
    user_id: str,
    card_id: str,
    card_index: int,
    on_date: date,
) -> None:
    """Insert a tarot_draws row earlier in the same ISO week.

    With ``WEEKLY_FREE_DRAWS=1`` (the Phase-1 setting in
    ``voicesaju.tarot.quota``), a single pre-existing draw is enough to
    drive the remaining count to zero.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(
            TarotDraw(
                user_id=user_id,
                card_id=card_id,
                card_index=card_index,
                date_kst=on_date,
            )
        )
        await s.commit()


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
# AC 3 — quota exhausted → 402 payment_required.
# ---------------------------------------------------------------------------


def test_flip_returns_402_when_quota_exhausted(engine: AsyncEngine) -> None:
    """AC 3: user has already drawn this week + no subscription → 402."""
    cards = asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-flip-exhausted"))

    # Pick any card_index for the seed draw — quota only cares about
    # the (user_id, week) pair, not the specific card.
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today_kst = datetime.now(ZoneInfo("Asia/Seoul")).date()
    # Use a different date in the same ISO week as today, to avoid the
    # idempotency path (which would return 200 with the existing draw).
    # We pick "today minus 1 day" but clamp to the Monday of this week
    # so the pre-seeded draw stays inside the same ISO week as `today`.
    from datetime import timedelta

    monday = today_kst - timedelta(days=today_kst.weekday())
    # If today IS Monday, "monday" == today_kst — use the next day
    # within the week (Tuesday) and re-aim today to also be Tuesday so
    # the test owns a stable date. Simpler: pre-seed Monday and use
    # today-as-is for the flip call. If today happens to be Monday, the
    # pre-seed row would collide with the idempotency key — we shift to
    # Tuesday in that case.
    seed_date = monday if monday != today_kst else (monday + timedelta(days=1))
    asyncio.run(
        _exhaust_weekly_quota(
            engine,
            user_id=user_id,
            card_id=cards[0],
            card_index=0,
            on_date=seed_date,
        )
    )

    # If we shifted seed_date to Tuesday because today is Monday, also
    # shift the "today" the client sees to Tuesday so the flip is a new
    # day-key. The route resolves today server-side, so we cannot
    # cleanly inject a clock here — accept that on Mondays the test
    # validates the same-day-different-day variant instead. Either way,
    # the quota is now 0, so the route MUST return 402.
    client = _make_client(engine, user_id)
    resp = client.post("/api/v1/tarot/today/flip")

    assert resp.status_code == 402, resp.text
    body = resp.json()
    # The router returns the architecture-spec envelope wrapped in
    # FastAPI's ``detail`` field (matches the reading-pipeline 402 from
    # ISSUE-039).
    detail = body.get("detail", body)
    error = detail.get("error", {}) if isinstance(detail, dict) else {}
    assert error.get("code") == "payment_required", body


def test_flip_returns_200_when_quota_available(engine: AsyncEngine) -> None:
    """AC 3 negative case: fresh user → flip endpoint accepts the call.

    We don't drain the SSE stream here (that's integration territory);
    we just assert the response status. The route returns 200 OK with
    a streaming body when entitlement passes.
    """
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-flip-fresh"))
    client = _make_client(engine, user_id)

    # Use stream=True semantics by checking the initial headers — but
    # TestClient buffers, so we just check the status code is not 402.
    resp = client.post("/api/v1/tarot/today/flip")

    assert resp.status_code == 200, resp.text
    # Streaming SSE: media type set by StreamingResponse.
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_flip_requires_identification(engine: AsyncEngine) -> None:
    """No user_id (and no device cookie) → 401 before any quota check."""
    asyncio.run(_seed_22_cards(engine))
    client = _make_client(engine, user_id=None)

    resp = client.post("/api/v1/tarot/today/flip")
    assert resp.status_code == 401
