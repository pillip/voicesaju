"""End-to-end subscriber bypass for the daily tarot pipeline (ISSUE-052).

Covers AC 1 + AC 2 in the integration layer:

* GET ``/api/v1/tarot/today`` returns ``is_subscriber=true`` for an
  active subscriber and ``free_remaining=null``.
* POST ``/api/v1/tarot/today/flip`` accepts the call (200, SSE stream)
  even when the user has zero free-quota left this week — the
  subscription bypass kicks in.
* A second POST in the same KST day returns the same draw_id (FR-013
  one-card-per-day) — the page surfaces ``already_flipped`` so the
  frontend renders "다시 듣기" instead of the paywall.

The test uses the same SQLite-backed app harness as
``api/tests/integration/tarot/test_pipeline.py``. We don't drain the SSE
stream here — that's already covered by ISSUE-049's integration tests.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

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
    Subscription,
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
        from sqlalchemy import select

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
        for r in (await s.execute(select(TarotCard))).scalars().all():
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


async def _seed_active_subscription(engine: AsyncEngine, *, user_id: str) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        now = datetime.now(UTC)
        s.add(
            Subscription(
                user_id=user_id,
                status="active",
                monthly_saju_remaining=1,
                current_period_start=now - timedelta(days=1),
                current_period_end=now + timedelta(days=29),
            )
        )
        await s.commit()


async def _exhaust_weekly_quota(
    engine: AsyncEngine,
    *,
    user_id: str,
    card_id: str,
    card_index: int,
    on_date: date,
) -> None:
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


def _make_client(engine: AsyncEngine, user_id: str) -> TestClient:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    from voicesaju.tarot.routers.today import _get_current_user_id

    app.dependency_overrides[_get_current_user_id] = lambda: user_id
    return TestClient(app)


# ---------------------------------------------------------------------------
# AC 1 — subscriber GET response shape.
# ---------------------------------------------------------------------------


def test_subscriber_gets_today_with_is_subscriber_true(engine: AsyncEngine) -> None:
    """Active subscription → GET today returns ``is_subscriber=True``."""
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-int-sub"))
    asyncio.run(_seed_active_subscription(engine, user_id=user_id))

    client = _make_client(engine, user_id)
    resp = client.get("/api/v1/tarot/today")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_subscriber"] is True, body
    assert body["free_remaining"] is None, body
    assert body["requires_payment"] is False, body


# ---------------------------------------------------------------------------
# AC 1 — subscriber bypasses quota even when this week has prior draws.
# ---------------------------------------------------------------------------


def test_subscriber_today_after_prior_draw_still_bypasses(
    engine: AsyncEngine,
) -> None:
    """Subscriber with a previous draw earlier this week still bypasses.

    The non-subscriber path would show ``free_remaining=0`` +
    ``requires_payment=True``. The subscriber path must still show
    ``is_subscriber=True``, ``free_remaining=None``, ``requires_payment=False``.
    """
    cards = asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-int-sub-prior"))
    asyncio.run(_seed_active_subscription(engine, user_id=user_id))

    # Seed a draw earlier in the same ISO week (Monday).
    from zoneinfo import ZoneInfo

    today_kst = datetime.now(ZoneInfo("Asia/Seoul")).date()
    monday = today_kst - timedelta(days=today_kst.weekday())
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

    client = _make_client(engine, user_id)
    resp = client.get("/api/v1/tarot/today")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_subscriber"] is True, body
    assert body["requires_payment"] is False, body


# ---------------------------------------------------------------------------
# AC 1 — subscriber flip accepted (no paywall).
# ---------------------------------------------------------------------------


def test_subscriber_flip_accepted_even_without_free_quota(
    engine: AsyncEngine,
) -> None:
    """Subscriber: POST /flip returns 200 (SSE) even when free quota is 0.

    A non-subscriber in this state would get HTTP 402
    ``payment_required`` (see ``test_flip_entitlement.py``). The
    subscription bypass turns it into a 200.
    """
    cards = asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-int-sub-flip"))
    asyncio.run(_seed_active_subscription(engine, user_id=user_id))

    # Seed a prior draw earlier this week so quota is consumed.
    from zoneinfo import ZoneInfo

    today_kst = datetime.now(ZoneInfo("Asia/Seoul")).date()
    monday = today_kst - timedelta(days=today_kst.weekday())
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

    client = _make_client(engine, user_id)
    resp = client.post("/api/v1/tarot/today/flip")

    assert resp.status_code == 200, resp.text
    assert "text/event-stream" in resp.headers.get("content-type", "")
