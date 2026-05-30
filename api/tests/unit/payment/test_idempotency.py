"""Idempotency unit test for ISSUE-044 (AC2)."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import func, select
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


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_KEK_BASE64", base64.b64encode(b"\x00" * 32).decode())
    monkeypatch.setenv("KMS_PROVIDER", "local")


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
        u = User(kakao_sub="idem-1")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


def _client(engine: AsyncEngine, user_id: str) -> TestClient:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override
    from voicesaju.payment.routes import _get_current_user_id

    app.dependency_overrides[_get_current_user_id] = lambda: user_id
    return TestClient(app)


def test_same_idempotency_key_returns_same_payment(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine))
    client = _client(engine, user_id)
    headers = {"Idempotency-Key": "client-abc-123"}

    r1 = client.post(
        "/api/v1/payments/checkout",
        json={"kind": "single", "method": "tosspay"},
        headers=headers,
    )
    r2 = client.post(
        "/api/v1/payments/checkout",
        json={"kind": "single", "method": "tosspay"},
        headers=headers,
    )
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["toss_order_id"] == r2.json()["toss_order_id"]

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _count() -> int:
        async with maker() as s:
            return int(
                (
                    await s.execute(select(func.count()).select_from(Payment))
                ).scalar_one()
            )

    assert asyncio.run(_count()) == 1


def test_different_idempotency_keys_create_separate_rows(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine))
    client = _client(engine, user_id)

    r1 = client.post(
        "/api/v1/payments/checkout",
        json={"kind": "single", "method": "tosspay"},
        headers={"Idempotency-Key": "key-A"},
    )
    r2 = client.post(
        "/api/v1/payments/checkout",
        json={"kind": "single", "method": "tosspay"},
        headers={"Idempotency-Key": "key-B"},
    )
    assert r1.json()["toss_order_id"] != r2.json()["toss_order_id"]
