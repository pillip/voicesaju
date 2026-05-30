"""Integration test for the Toss Payments checkout flow (ISSUE-044).

Covers AC1 (POST /api/v1/payments/checkout returns 201 + pending row),
AC2 (idempotency key returns same row), AC3 (POST /api/v1/payments/confirm
finalises the payment).
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
from voicesaju.db.models.payments import Payment
from voicesaju.db.models.users import User
from voicesaju.main import create_app
from voicesaju.payment.toss_client import TossConfirmation


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


async def _seed_user(engine: AsyncEngine) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub="checkout-1")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


class _StubTossClient:
    """Tests inject this to control confirm() shape."""

    def __init__(self, status: str = "DONE", amount_krw: int = 4900) -> None:
        self.status = status
        self.amount_krw = amount_krw
        self.calls: list[dict] = []

    async def confirm_payment(
        self, *, order_id: str, payment_key: str, amount_krw: int
    ) -> TossConfirmation:
        self.calls.append(
            {"order_id": order_id, "payment_key": payment_key, "amount_krw": amount_krw}
        )
        return TossConfirmation(
            order_id=order_id,
            payment_key=payment_key,
            status=self.status,
            amount_krw=self.amount_krw,
        )


def _make_client(
    engine: AsyncEngine, user_id: str, toss_stub: _StubTossClient | None = None
) -> TestClient:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    from voicesaju.payment.routes import _get_current_user_id, _get_toss_client

    app.dependency_overrides[_get_current_user_id] = lambda: user_id
    if toss_stub is not None:
        app.dependency_overrides[_get_toss_client] = lambda: toss_stub

    return TestClient(app)


def test_checkout_returns_201_with_pending_payment(engine: AsyncEngine) -> None:
    """AC1: POST /checkout → 201, payments row inserted with status=pending."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)

    resp = client.post(
        "/api/v1/payments/checkout",
        json={"kind": "single", "method": "tosspay"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["toss_order_id"]
    assert body["amount_krw"] == 4900
    assert "success_url" in body and "fail_url" in body

    # Verify the row landed.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Payment:
        async with maker() as s:
            return (await s.execute(select(Payment))).scalar_one()

    payment = asyncio.run(_read())
    assert payment.status == "pending"
    assert payment.kind == "single"
    assert payment.toss_order_id == body["toss_order_id"]


def test_checkout_then_confirm_flips_to_paid(engine: AsyncEngine) -> None:
    """AC3: POST /confirm after checkout flips status=paid and sets paid_at."""
    user_id = asyncio.run(_seed_user(engine))
    stub = _StubTossClient(status="DONE", amount_krw=4900)
    client = _make_client(engine, user_id, toss_stub=stub)

    checkout = client.post(
        "/api/v1/payments/checkout",
        json={"kind": "single", "method": "tosspay"},
    )
    order_id = checkout.json()["toss_order_id"]

    confirm = client.post(
        "/api/v1/payments/confirm",
        json={
            "toss_order_id": order_id,
            "payment_key": "tviva20250530abc",
            "amount_krw": 4900,
        },
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "paid"
    assert stub.calls == [
        {"order_id": order_id, "payment_key": "tviva20250530abc", "amount_krw": 4900}
    ]

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> Payment:
        async with maker() as s:
            return (await s.execute(select(Payment))).scalar_one()

    payment = asyncio.run(_read())
    assert payment.status == "paid"
    assert payment.paid_at is not None


def test_confirm_amount_mismatch_returns_400(engine: AsyncEngine) -> None:
    """AC4: amount mismatch in confirm body → 400 fraud guard."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id, toss_stub=_StubTossClient())

    checkout = client.post(
        "/api/v1/payments/checkout",
        json={"kind": "single", "method": "tosspay"},
    )
    order_id = checkout.json()["toss_order_id"]

    confirm = client.post(
        "/api/v1/payments/confirm",
        json={
            "toss_order_id": order_id,
            "payment_key": "tviva20250530abc",
            "amount_krw": 9900,  # mismatch
        },
    )
    assert confirm.status_code == 400, confirm.text
    body = confirm.json()
    error_block = body.get("error") or body.get("detail", {}).get("error", {})
    assert error_block.get("code") == "amount_mismatch"
