"""Integration tests for payments + subscriptions Postgres constraints.

Exercises Postgres-only partial unique indexes that the SQLite shape
can't represent:

- `payments_toss_order_id_uk` — two payments sharing the same
  non-null `toss_order_id` must be rejected.
- `subscriptions_one_active_per_user` — a user can have at most one
  `status='active'` subscription at a time.

Marked `integration` and excluded from default CI. Run locally with:

    docker compose up -d db
    cd api && uv run pytest -m integration tests/integration/db/

Authoritative source: docs/data_model.md §4.13, §4.14, §5.9, §5.10.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

pytestmark = pytest.mark.integration


API_DIR = Path(__file__).resolve().parents[3]


def _database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://voicesaju:voicesaju@localhost:5432/voicesaju",
    )


def _alembic_config() -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", _database_url())
    return cfg


@pytest.fixture(scope="module")
def upgraded_db() -> None:
    """Upgrade to 0006 once per module and tear back down to 0001 afterwards."""
    cfg = _alembic_config()
    command.upgrade(cfg, "0006_payments_subscriptions_refunds")
    try:
        yield
    finally:
        command.downgrade(cfg, "0001_initial")


async def _insert_user_async(**kwargs) -> str:
    engine = create_async_engine(_database_url(), future=True)
    try:
        async with engine.begin() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join(f":{k}" for k in kwargs)
            await conn.execute(
                text(f"INSERT INTO users ({cols}) VALUES ({placeholders})"),
                kwargs,
            )
    finally:
        await engine.dispose()
    return kwargs["id"]


async def _insert_payment_async(**kwargs) -> None:
    engine = create_async_engine(_database_url(), future=True)
    try:
        async with engine.begin() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join(f":{k}" for k in kwargs)
            await conn.execute(
                text(f"INSERT INTO payments ({cols}) VALUES ({placeholders})"),
                kwargs,
            )
    finally:
        await engine.dispose()


async def _insert_subscription_async(**kwargs) -> None:
    engine = create_async_engine(_database_url(), future=True)
    try:
        async with engine.begin() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join(f":{k}" for k in kwargs)
            await conn.execute(
                text(f"INSERT INTO subscriptions ({cols}) VALUES ({placeholders})"),
                kwargs,
            )
    finally:
        await engine.dispose()


def _mk_user_sync() -> str:
    user_id = str(uuid.uuid4())
    asyncio.run(_insert_user_async(id=user_id, kakao_sub=f"kakao-{uuid.uuid4()}"))
    return user_id


def test_payments_toss_order_id_partial_unique(upgraded_db: None) -> None:
    """Two payments sharing the same non-null `toss_order_id` must be rejected."""
    user_id = _mk_user_sync()
    order = f"order-{uuid.uuid4()}"
    asyncio.run(
        _insert_payment_async(
            id=str(uuid.uuid4()),
            user_id=user_id,
            kind="single",
            amount_krw=4900,
            method="card",
            status="paid",
            toss_order_id=order,
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_payment_async(
                id=str(uuid.uuid4()),
                user_id=user_id,
                kind="single",
                amount_krw=4900,
                method="card",
                status="paid",
                toss_order_id=order,
            )
        )


def test_payments_idempotency_partial_unique(upgraded_db: None) -> None:
    """Two payments for one user sharing an `idempotency_key` must be rejected."""
    user_id = _mk_user_sync()
    key = f"idem-{uuid.uuid4()}"
    asyncio.run(
        _insert_payment_async(
            id=str(uuid.uuid4()),
            user_id=user_id,
            kind="single",
            amount_krw=4900,
            method="card",
            status="pending",
            idempotency_key=key,
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_payment_async(
                id=str(uuid.uuid4()),
                user_id=user_id,
                kind="single",
                amount_krw=4900,
                method="card",
                status="pending",
                idempotency_key=key,
            )
        )


def test_payments_null_idempotency_does_not_collide(upgraded_db: None) -> None:
    """Partial unique on (user_id, idempotency_key) WHERE NOT NULL must
    allow many NULL rows for one user."""
    user_id = _mk_user_sync()
    asyncio.run(
        _insert_payment_async(
            id=str(uuid.uuid4()),
            user_id=user_id,
            kind="single",
            amount_krw=4900,
            method="card",
            status="paid",
        )
    )
    asyncio.run(
        _insert_payment_async(
            id=str(uuid.uuid4()),
            user_id=user_id,
            kind="single",
            amount_krw=4900,
            method="card",
            status="paid",
        )
    )


def test_subscriptions_one_active_per_user(upgraded_db: None) -> None:
    """Inserting a second `status='active'` row for the same user must be
    rejected by the partial unique index."""
    user_id = _mk_user_sync()
    now = datetime.now(UTC)
    period_end = now + timedelta(days=30)
    asyncio.run(
        _insert_subscription_async(
            id=str(uuid.uuid4()),
            user_id=user_id,
            status="active",
            current_period_start=now,
            current_period_end=period_end,
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_subscription_async(
                id=str(uuid.uuid4()),
                user_id=user_id,
                status="active",
                current_period_start=now,
                current_period_end=period_end,
            )
        )
