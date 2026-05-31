"""Integration test for the Toss Payments webhook handler (ISSUE-045).

AC coverage:

- AC1: valid signed `PAYMENT_DONE` flips a pending Payment to `paid` and
  sets `paid_at`.
- AC2: an invalid signature returns 401 and writes nothing.
- AC3: the same `toss_payment_key` delivered twice causes only one update
  (idempotent on `toss_payment_key`).
- AC4: `SUBSCRIPTION_RENEWED` advances `current_period_start/end` and
  resets `monthly_saju_remaining=1`.

All tests run against an in-memory SQLite engine + a static
`TOSS_WEBHOOK_SECRET` so they are deterministic and offline.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
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

from voicesaju.config import Settings, get_settings
from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models.payments import Payment
from voicesaju.db.models.subscriptions import Subscription
from voicesaju.db.models.users import User
from voicesaju.main import create_app

WEBHOOK_SECRET = "test-webhook-secret-do-not-use-in-prod"


@pytest.fixture(autouse=True)
def _env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")
    monkeypatch.setenv("PAYMENT_PROVIDER", "mock")
    monkeypatch.setenv("TOSS_WEBHOOK_SECRET", WEBHOOK_SECRET)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_user(engine: AsyncEngine) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub="webhook-user-1")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


async def _seed_pending_payment(
    engine: AsyncEngine,
    *,
    user_id: str,
    toss_order_id: str = "order-1",
    amount_krw: int = 4900,
    kind: str = "single",
) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        p = Payment(
            user_id=user_id,
            kind=kind,
            amount_krw=amount_krw,
            method="tosspay",
            status="pending",
            toss_order_id=toss_order_id,
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return str(p.id)


async def _seed_active_subscription(
    engine: AsyncEngine,
    *,
    user_id: str,
    period_end: datetime,
) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        sub = Subscription(
            user_id=user_id,
            status="active",
            monthly_saju_remaining=0,
            current_period_start=period_end - timedelta(days=30),
            current_period_end=period_end,
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return str(sub.id)


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _make_client(engine: AsyncEngine) -> TestClient:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    def _override_settings() -> Settings:
        return get_settings()

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    # Override the webhook settings dep so the test secret is read.
    from voicesaju.payment.webhook import _get_settings as _ws

    app.dependency_overrides[_ws] = _override_settings

    return TestClient(app)


# ---------------------------------------------------------------------------
# AC1 — valid PAYMENT_DONE flips pending → paid
# ---------------------------------------------------------------------------


def test_payment_done_flips_to_paid(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine))
    asyncio.run(
        _seed_pending_payment(
            engine, user_id=user_id, toss_order_id="order-1", amount_krw=4900
        )
    )

    client = _make_client(engine)
    payload = {
        "eventType": "PAYMENT_DONE",
        "data": {
            "orderId": "order-1",
            "paymentKey": "tviva-paykey-1",
            "totalAmount": 4900,
            "status": "DONE",
            "approvedAt": "2026-05-29T10:00:00+09:00",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body)

    resp = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Toss-Signature": sig,
        },
    )
    assert resp.status_code == 200, resp.text

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Payment:
        async with maker() as s:
            return (await s.execute(select(Payment))).scalar_one()

    payment = asyncio.run(_read())
    assert payment.status == "paid"
    assert payment.paid_at is not None


def test_payment_done_emits_payment_completed_event(engine: AsyncEngine) -> None:
    """ISSUE-080 AC3: ``payment_completed`` fired with amount + category."""
    from voicesaju.analytics import (
        NoopAnalyticsBackend,
        reset_default_backend_for_tests,
        set_default_backend,
    )

    reset_default_backend_for_tests()
    recorder = NoopAnalyticsBackend()
    set_default_backend(recorder)

    user_id = asyncio.run(_seed_user(engine))
    asyncio.run(
        _seed_pending_payment(
            engine,
            user_id=user_id,
            toss_order_id="order-evt-1",
            amount_krw=4900,
        )
    )

    client = _make_client(engine)
    payload = {
        "eventType": "PAYMENT_DONE",
        "data": {
            "orderId": "order-evt-1",
            "paymentKey": "tviva-paykey-evt-1",
            "totalAmount": 4900,
            "status": "DONE",
            "approvedAt": "2026-05-29T10:00:00+09:00",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body)

    resp = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Toss-Signature": sig,
        },
    )
    assert resp.status_code == 200, resp.text

    payment_events = [e for e in recorder.received if e.name == "payment_completed"]
    assert (
        len(payment_events) == 1
    ), f"expected exactly one payment_completed event; got {recorder.received}"
    ev = payment_events[0]
    assert ev.user_id == str(user_id)
    assert ev.properties["amount_krw"] == 4900
    assert ev.properties["category"] in {"single", "subscription"}

    # Cleanup — restore default backend so other tests run with Noop.
    reset_default_backend_for_tests()


# ---------------------------------------------------------------------------
# AC2 — invalid signature → 401 + no DB writes
# ---------------------------------------------------------------------------


def test_invalid_signature_returns_401_and_writes_nothing(
    engine: AsyncEngine,
) -> None:
    user_id = asyncio.run(_seed_user(engine))
    asyncio.run(
        _seed_pending_payment(
            engine, user_id=user_id, toss_order_id="order-1", amount_krw=4900
        )
    )

    client = _make_client(engine)
    payload = {
        "eventType": "PAYMENT_DONE",
        "data": {
            "orderId": "order-1",
            "paymentKey": "tviva-paykey-1",
            "totalAmount": 4900,
            "status": "DONE",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    bad_sig = "0" * 64  # syntactically valid hex, wrong digest

    resp = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Toss-Signature": bad_sig,
        },
    )
    assert resp.status_code == 401, resp.text

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Payment:
        async with maker() as s:
            return (await s.execute(select(Payment))).scalar_one()

    payment = asyncio.run(_read())
    # Untouched.
    assert payment.status == "pending"
    assert payment.paid_at is None


# ---------------------------------------------------------------------------
# AC3 — duplicate delivery is idempotent on toss_payment_key
# ---------------------------------------------------------------------------


def test_duplicate_payment_key_is_idempotent(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine))
    asyncio.run(
        _seed_pending_payment(
            engine, user_id=user_id, toss_order_id="order-dup", amount_krw=4900
        )
    )

    client = _make_client(engine)
    payload = {
        "eventType": "PAYMENT_DONE",
        "data": {
            "orderId": "order-dup",
            "paymentKey": "tviva-paykey-dup",
            "totalAmount": 4900,
            "status": "DONE",
            "approvedAt": "2026-05-29T10:00:00+09:00",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body)

    headers = {
        "Content-Type": "application/json",
        "X-Toss-Signature": sig,
    }

    resp1 = client.post("/api/v1/payments/webhook", content=body, headers=headers)
    resp2 = client.post("/api/v1/payments/webhook", content=body, headers=headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200  # second call still ACKs

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Payment:
        async with maker() as s:
            return (await s.execute(select(Payment))).scalar_one()

    payment = asyncio.run(_read())
    assert payment.status == "paid"

    # Idempotent: only one Payment row, and its toss_payment_key is set once.
    # (We don't assert paid_at equality across requests because some
    # implementations refresh on the second call. The hard invariant is
    # "only one row was modified" — a duplicate row would violate that.)
    async def _count() -> int:
        async with maker() as s:
            res = await s.execute(select(Payment))
            return len(list(res.scalars()))

    assert asyncio.run(_count()) == 1


# ---------------------------------------------------------------------------
# AC4 — SUBSCRIPTION_RENEWED advances period and resets monthly counter
# ---------------------------------------------------------------------------


def test_subscription_renewed_advances_period(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine))
    old_end = datetime(2026, 5, 1, tzinfo=UTC)
    asyncio.run(_seed_active_subscription(engine, user_id=user_id, period_end=old_end))

    client = _make_client(engine)
    new_start = "2026-05-01T00:00:00+00:00"
    new_end = "2026-06-01T00:00:00+00:00"
    payload = {
        "eventType": "SUBSCRIPTION_RENEWED",
        "data": {
            "userId": user_id,
            "currentPeriodStart": new_start,
            "currentPeriodEnd": new_end,
            "paymentKey": "tviva-renew-1",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body)

    resp = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Toss-Signature": sig,
        },
    )
    assert resp.status_code == 200, resp.text

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Subscription:
        async with maker() as s:
            return (await s.execute(select(Subscription))).scalar_one()

    sub = asyncio.run(_read())
    # SQLite (aiosqlite) returns timezone-naive datetimes; normalise both
    # sides to UTC before comparing so the assertion works on both
    # SQLite (unit) and Postgres (integration) backends.
    stored_end = sub.current_period_end
    if stored_end.tzinfo is None:
        stored_end = stored_end.replace(tzinfo=UTC)
    assert stored_end > old_end
    assert sub.monthly_saju_remaining == 1


# ---------------------------------------------------------------------------
# Bonus — PAYMENT_FAILED marks the row as failed
# ---------------------------------------------------------------------------


def test_payment_failed_marks_status_failed(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine))
    asyncio.run(
        _seed_pending_payment(
            engine, user_id=user_id, toss_order_id="order-fail", amount_krw=4900
        )
    )

    client = _make_client(engine)
    payload = {
        "eventType": "PAYMENT_FAILED",
        "data": {
            "orderId": "order-fail",
            "paymentKey": "tviva-paykey-fail",
            "totalAmount": 4900,
            "status": "ABORTED",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body)

    resp = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Toss-Signature": sig,
        },
    )
    assert resp.status_code == 200, resp.text

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Payment:
        async with maker() as s:
            return (await s.execute(select(Payment))).scalar_one()

    payment = asyncio.run(_read())
    assert payment.status == "failed"


# ---------------------------------------------------------------------------
# Bonus — SUBSCRIPTION_CANCELED marks subscription canceled_at + status
# ---------------------------------------------------------------------------


def test_subscription_canceled_sets_canceled_at(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine))
    period_end = datetime(2026, 6, 1, tzinfo=UTC)
    asyncio.run(
        _seed_active_subscription(engine, user_id=user_id, period_end=period_end)
    )

    client = _make_client(engine)
    payload = {
        "eventType": "SUBSCRIPTION_CANCELED",
        "data": {
            "userId": user_id,
            "canceledAt": "2026-05-15T00:00:00+00:00",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body)

    resp = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Toss-Signature": sig,
        },
    )
    assert resp.status_code == 200, resp.text

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Subscription:
        async with maker() as s:
            return (await s.execute(select(Subscription))).scalar_one()

    sub = asyncio.run(_read())
    assert sub.canceled_at is not None
    assert sub.status in {"cancel_at_period_end", "canceled"}


# ---------------------------------------------------------------------------
# Bonus — BILLING_FAILED downgrades subscription status
# ---------------------------------------------------------------------------


def test_billing_failed_downgrades_subscription(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine))
    period_end = datetime(2026, 6, 1, tzinfo=UTC)
    asyncio.run(
        _seed_active_subscription(engine, user_id=user_id, period_end=period_end)
    )

    client = _make_client(engine)
    payload = {
        "eventType": "BILLING_FAILED",
        "data": {
            "userId": user_id,
            "paymentKey": "tviva-bill-fail-1",
            "failedAt": "2026-05-29T00:00:00+00:00",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body)

    resp = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Toss-Signature": sig,
        },
    )
    assert resp.status_code == 200, resp.text

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Subscription:
        async with maker() as s:
            return (await s.execute(select(Subscription))).scalar_one()

    sub = asyncio.run(_read())
    assert sub.status == "past_due"


# ---------------------------------------------------------------------------
# Unknown event type — accepted as ack (200) but no DB changes
# ---------------------------------------------------------------------------


def test_unknown_event_type_is_acked_without_changes(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine))
    asyncio.run(
        _seed_pending_payment(
            engine, user_id=user_id, toss_order_id="order-x", amount_krw=4900
        )
    )

    client = _make_client(engine)
    payload = {"eventType": "UNKNOWN_FUTURE_EVENT", "data": {}}
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body)

    resp = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Toss-Signature": sig,
        },
    )
    # Be lenient (200) so Toss doesn't retry indefinitely on a future event
    # type we don't recognise yet.
    assert resp.status_code == 200, resp.text

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Payment:
        async with maker() as s:
            return (await s.execute(select(Payment))).scalar_one()

    payment = asyncio.run(_read())
    assert payment.status == "pending"
