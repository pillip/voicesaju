"""Integration tests for subscription create + cancel (ISSUE-068).

Covers:

- AC1: valid ``POST /api/v1/subscriptions {method:'tosspay'}`` creates a row
  with ``status='active'``, ``monthly_saju_remaining=1``,
  ``current_period_start/end`` (now + 30d).
- AC2: ``POST /api/v1/subscriptions/cancel`` by a subscriber flips
  ``status='cancel_at_period_end'``, stamps ``cancel_requested_at`` and
  preserves access until ``current_period_end``.
- AC3: a Toss API failure on cancel triggers up to three retry attempts
  via the arq-registered job (tenacity loop).

PRD-Ref: FR-022, US-12.
Architecture-Ref: §6.5, AP-38, AP-40.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

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


async def _seed_user(engine: AsyncEngine, kakao_sub: str = "subs-1") -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


async def _seed_active_subscription(
    engine: AsyncEngine,
    *,
    user_id: str,
    period_end: datetime | None = None,
) -> str:
    """Seed an active subscription so the cancel path has a row to update."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(tz=UTC)
    async with maker() as s:
        sub = Subscription(
            user_id=user_id,
            status="active",
            monthly_saju_remaining=1,
            current_period_start=now,
            current_period_end=period_end or now + timedelta(days=30),
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


def test_create_subscription_returns_active_row_with_period(
    engine: AsyncEngine,
) -> None:
    """AC1: POST /subscriptions → active row with monthly_saju_remaining=1."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)

    resp = client.post(
        "/api/v1/subscriptions",
        json={"method": "tosspay"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "active"
    assert body["monthly_saju_remaining"] == 1
    assert "id" in body
    assert "current_period_start" in body and "current_period_end" in body

    # Verify the row hit the DB exactly as advertised.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _row() -> Subscription | None:
        async with maker() as s:
            row = (
                await s.execute(
                    select(Subscription).where(Subscription.user_id == user_id)
                )
            ).scalar_one_or_none()
            # Force load period fields before session closes.
            if row is not None:
                _ = row.current_period_end
                _ = row.current_period_start
                _ = row.monthly_saju_remaining
            return row

    sub = asyncio.run(_row())
    assert sub is not None
    assert sub.status == "active"
    assert sub.monthly_saju_remaining == 1
    # Period should be approximately 30 days.
    delta = sub.current_period_end - sub.current_period_start
    assert timedelta(days=29) < delta <= timedelta(days=31)


def test_create_subscription_requires_auth(engine: AsyncEngine) -> None:
    """Anonymous → 401."""
    client = _make_client(engine, user_id=None)
    resp = client.post("/api/v1/subscriptions", json={"method": "tosspay"})
    assert resp.status_code == 401


def test_create_subscription_idempotent_when_already_active(
    engine: AsyncEngine,
) -> None:
    """A user with an existing active subscription gets the same row back, not
    a duplicate. Mirrors the data_model §4.14 partial-unique invariant.
    """
    user_id = asyncio.run(_seed_user(engine))
    existing_id = asyncio.run(_seed_active_subscription(engine, user_id=user_id))
    client = _make_client(engine, user_id)

    resp = client.post("/api/v1/subscriptions", json={"method": "tosspay"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == existing_id
    assert body["status"] == "active"


def test_cancel_subscription_sets_cancel_at_period_end(engine: AsyncEngine) -> None:
    """AC2: cancel → status='cancel_at_period_end', cancel_requested_at=now."""
    user_id = asyncio.run(_seed_user(engine))
    sub_id = asyncio.run(_seed_active_subscription(engine, user_id=user_id))
    client = _make_client(engine, user_id)

    resp = client.post("/api/v1/subscriptions/cancel")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == sub_id
    assert body["status"] == "cancel_at_period_end"
    assert body["cancel_requested_at"] is not None

    # DB-side: row updated, period preserved → access until period_end.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _row() -> Subscription | None:
        async with maker() as s:
            row = (
                await s.execute(select(Subscription).where(Subscription.id == sub_id))
            ).scalar_one_or_none()
            if row is not None:
                _ = row.current_period_end
                _ = row.cancel_requested_at
                _ = row.status
            return row

    row = asyncio.run(_row())
    assert row is not None
    assert row.status == "cancel_at_period_end"
    assert row.cancel_requested_at is not None
    # current_period_end must NOT be advanced or cleared — access continues.
    assert row.current_period_end is not None


def test_cancel_subscription_404_when_no_active_subscription(
    engine: AsyncEngine,
) -> None:
    """Cancel without an active row → 404 (the UI shouldn't expose the button
    in this case; the route stays defensive so a stale tab doesn't double-fire).
    """
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)

    resp = client.post("/api/v1/subscriptions/cancel")
    assert resp.status_code == 404


def test_cancel_retry_job_uses_three_attempts() -> None:
    """AC3: the cancel retry job retries up to 3× via tenacity."""
    from voicesaju.jobs.subscription_cancel_retry import (
        MAX_CANCEL_ATTEMPTS,
        _cancel_with_retry,
    )

    assert MAX_CANCEL_ATTEMPTS == 3

    calls: list[int] = []

    async def _flaky_call(subscription_id: str) -> str:
        calls.append(1)
        # First two attempts fail; third succeeds.
        if len(calls) < 3:
            raise RuntimeError("simulated Toss outage")
        return f"canceled:{subscription_id}"

    result = asyncio.run(_cancel_with_retry(subscription_id="sub-x", call=_flaky_call))
    assert result == "canceled:sub-x"
    assert len(calls) == 3


def test_cancel_retry_job_exhausts_after_three_attempts() -> None:
    """If every retry fails the job raises so arq surfaces the failure for
    follow-up handling (logging, alerting, manual replay).
    """
    from voicesaju.jobs.subscription_cancel_retry import _cancel_with_retry

    calls: list[int] = []

    async def _always_fails(subscription_id: str) -> str:
        calls.append(1)
        raise RuntimeError("simulated Toss outage")

    with pytest.raises(RuntimeError):
        asyncio.run(_cancel_with_retry(subscription_id="sub-y", call=_always_fails))
    assert len(calls) == 3


def test_subscription_cancel_retry_is_registered_with_worker() -> None:
    """The retry job is discoverable via the arq worker registry so
    SUBSCRIPTION_CANCELED webhook (or a manual replay) can dispatch it.
    """
    from voicesaju.jobs.worker import _JOB_REGISTRY  # noqa: PLC2701

    assert "subscription_cancel_retry" in _JOB_REGISTRY
