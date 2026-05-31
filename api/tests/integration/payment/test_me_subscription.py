"""Integration tests for ``GET /api/v1/subscriptions/me`` (ISSUE-067 backend).

The billing page reads this endpoint to learn whether the caller is an
active / cancel-at-period-end subscriber, and to fill the status pill
with ``current_period_end`` + ``status``.

Contract (mirrors `voicesaju.payment.subscription_routes`):

- 200 ``{"subscription": null}`` when there is no active / pending-cancel
  row → FE renders the non-subscriber empty state.
- 200 ``{"subscription": {...}}`` when an active or
  cancel-at-period-end row exists → FE renders the subscriber card.
- 401 when the caller is anonymous.
- Terminal-state rows (``canceled``, ``past_due``) are treated as if no
  row existed — once a subscription has terminated the user is back to
  the non-subscriber empty state per data_model §4.14.

AC mapping (ISSUE-067):
  AC1: subscriber → tier + period_end + 구독 해지 button → the
       FE depends on a ``subscription.status='active'`` + period fields.
  AC2: non-subscriber → empty state → the FE depends on
       ``subscription is null``.
  AC4: confirm cancel → status pill shows "해지 예정 — [date]까지" →
       the FE depends on ``subscription.status='cancel_at_period_end'``
       + ``current_period_end`` so the date can be formatted client-side.
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
from voicesaju.db.models.subscriptions import Subscription
from voicesaju.db.models.users import User
from voicesaju.main import create_app


@pytest.fixture(autouse=True)
def _env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")
    monkeypatch.setenv("PAYMENT_PROVIDER", "mock")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_user(engine: AsyncEngine, kakao_sub: str = "me-1") -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


async def _seed_subscription(
    engine: AsyncEngine,
    *,
    user_id: str,
    status: str,
    period_end: datetime | None = None,
    cancel_requested_at: datetime | None = None,
) -> str:
    """Seed a subscription row in the requested status for the user."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(tz=UTC)
    async with maker() as s:
        sub = Subscription(
            user_id=user_id,
            status=status,
            monthly_saju_remaining=1,
            current_period_start=now,
            current_period_end=period_end or (now + timedelta(days=30)),
            cancel_requested_at=cancel_requested_at,
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

    from voicesaju.payment.subscription_routes import _get_current_user_id

    if user_id is not None:
        app.dependency_overrides[_get_current_user_id] = lambda: user_id
    return TestClient(app)


def test_me_subscription_returns_active_row(engine: AsyncEngine) -> None:
    """AC1 enabler: active subscriber → subscription envelope with the row."""
    user_id = asyncio.run(_seed_user(engine))
    sub_id = asyncio.run(_seed_subscription(engine, user_id=user_id, status="active"))
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/subscriptions/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["subscription"] is not None
    assert body["subscription"]["id"] == sub_id
    assert body["subscription"]["status"] == "active"
    assert body["subscription"]["monthly_saju_remaining"] == 1
    assert body["subscription"]["current_period_end"] is not None
    assert body["subscription"]["cancel_requested_at"] is None


def test_me_subscription_returns_cancel_at_period_end_row(
    engine: AsyncEngine,
) -> None:
    """AC4 enabler: cancel-at-period-end row stays visible until terminal
    state so the FE can render the "해지 예정" pill copy.
    """
    user_id = asyncio.run(_seed_user(engine))
    cancel_at = datetime.now(tz=UTC)
    sub_id = asyncio.run(
        _seed_subscription(
            engine,
            user_id=user_id,
            status="cancel_at_period_end",
            cancel_requested_at=cancel_at,
        )
    )
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/subscriptions/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["subscription"] is not None
    assert body["subscription"]["id"] == sub_id
    assert body["subscription"]["status"] == "cancel_at_period_end"
    assert body["subscription"]["cancel_requested_at"] is not None


def test_me_subscription_returns_null_when_no_row(engine: AsyncEngine) -> None:
    """AC2 enabler: no subscription rows → ``{"subscription": null}``."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/subscriptions/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"subscription": None}


def test_me_subscription_ignores_terminal_canceled_row(
    engine: AsyncEngine,
) -> None:
    """A row in terminal ``canceled`` status is invisible to ``/me``.

    Once a subscription has fully terminated the user is back to the
    non-subscriber state — the billing page renders the empty state and
    the "구독 시작하기" CTA.
    """
    user_id = asyncio.run(_seed_user(engine))
    asyncio.run(_seed_subscription(engine, user_id=user_id, status="canceled"))
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/subscriptions/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"subscription": None}


def test_me_subscription_requires_auth(engine: AsyncEngine) -> None:
    """Anonymous caller → 401 from the shared dependency."""
    client = _make_client(engine, user_id=None)
    resp = client.get("/api/v1/subscriptions/me")
    assert resp.status_code == 401


def test_me_subscription_scoped_to_caller(engine: AsyncEngine) -> None:
    """A different user's active row must not leak through ``/me``."""
    other_user_id = asyncio.run(_seed_user(engine, kakao_sub="other-1"))
    asyncio.run(_seed_subscription(engine, user_id=other_user_id, status="active"))
    caller_user_id = asyncio.run(_seed_user(engine, kakao_sub="me-2"))
    client = _make_client(engine, caller_user_id)

    resp = client.get("/api/v1/subscriptions/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"subscription": None}
