"""Tests for subscriber bypass on ``GET /api/v1/tarot/today`` (ISSUE-052).

Covers AC 1 from ISSUE-052: an active subscriber visiting `/tarot`
sees the "구독 중" banner — i.e. the GET endpoint surfaces a clean
``is_subscriber=true`` flag so the page can branch on it.

Phase-1 wiring: ISSUE-048's ``check_weekly_free`` already returns
``QuotaResult.is_unlimited=True`` for subscribers. The today route in
ISSUE-049 quietly mapped that to ``free_remaining=1, requires_payment=False``
which the frontend could not distinguish from a vanilla first-of-the-week
free draw. ISSUE-052 changes the response shape:

* ``is_subscriber: True`` — active subscription bypass.
* ``free_remaining: None`` — subscriber has no quota counter.

For non-subscribers nothing changes: ``is_subscriber=False`` and
``free_remaining`` remains an integer.

These tests inject a real ``Subscription`` row (status='active',
monthly_saju_remaining=1) so the entitlement service grants the bypass
naturally. We avoid stubbing ``check_entitlement`` here to keep the
verification end-to-end (per ISSUE-052 goal).
"""

from __future__ import annotations

import asyncio
import base64
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
        return str(u.id)


async def _seed_active_subscription(engine: AsyncEngine, *, user_id: str) -> str:
    """Insert an active subscription row that grants tarot bypass.

    Mirrors ``data_model §4.14``: ``status='active'`` and
    ``monthly_saju_remaining`` is the saju quota only — tarot bypass
    fires whenever the row is active, regardless of saju remaining.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        now = datetime.now(UTC)
        sub = Subscription(
            user_id=user_id,
            status="active",
            monthly_saju_remaining=1,
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=29),
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return str(sub.id)


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
# AC 1 — Subscriber surface flag.
# ---------------------------------------------------------------------------


def test_subscriber_today_response_marks_is_subscriber(engine: AsyncEngine) -> None:
    """ISSUE-052 AC1: active subscription → ``is_subscriber=True``.

    Also asserts ``free_remaining`` is null/None on the wire so the
    frontend can distinguish a subscriber from a "fresh first draw"
    non-subscriber (both would otherwise look identical with the
    previous payload).
    """
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-052-sub"))
    asyncio.run(_seed_active_subscription(engine, user_id=user_id))

    client = _make_client(engine, user_id)
    resp = client.get("/api/v1/tarot/today")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # New ISSUE-052 fields:
    assert body.get("is_subscriber") is True, body
    # free_remaining must be ``None`` (JSON null) for subscribers — the
    # banner reads "구독 중" instead of "N회 남음".
    assert body.get("free_remaining") is None, body
    # Subscribers never see a paywall.
    assert body.get("requires_payment") is False, body


def test_nonsubscriber_today_response_marks_is_subscriber_false(
    engine: AsyncEngine,
) -> None:
    """ISSUE-052 AC1 negative: no subscription → ``is_subscriber=False``.

    Ensures we didn't regress the existing non-subscriber payload —
    ``free_remaining`` is still an integer and ``is_subscriber=False``.
    """
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-052-nonsub"))

    client = _make_client(engine, user_id)
    resp = client.get("/api/v1/tarot/today")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("is_subscriber") is False, body
    # Non-subscriber still gets the integer counter (1 free this week).
    assert body.get("free_remaining") == 1, body
    assert body.get("requires_payment") is False, body
