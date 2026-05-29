"""Unit tests for Payment, Subscription, and Refund models.

Verifies that the SQLAlchemy declarative models import cleanly, expose
every column documented in `docs/data_model.md` §4.13–§4.15, register on
`Base.metadata`, and enforce their application-level CHECK constraints
against an in-memory SQLite engine.

Postgres-specific behaviour (partial unique indexes for `toss_order_id`,
`(user_id, idempotency_key)`, and the active-subscription guard) is
exercised in `tests/integration/db/test_payment_constraints.py`.
"""

from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.db.base import Base
from voicesaju.db.models import Payment, Refund, Subscription, User

API_DIR = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    API_DIR / "alembic" / "versions" / "0006_payments_subscriptions_refunds.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_0006_payments_subscriptions_refunds", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# Column / metadata smoke tests                                                #
# --------------------------------------------------------------------------- #


def test_payment_model_has_expected_columns() -> None:
    cols = {c.name for c in inspect(Payment).columns}
    expected = {
        "id",
        "user_id",
        "kind",
        "amount_krw",
        "method",
        "status",
        "toss_order_id",
        "paid_at",
        "refunded_amount_krw",
        "idempotency_key",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"Payment missing columns: {missing}"


def test_subscription_model_has_expected_columns() -> None:
    cols = {c.name for c in inspect(Subscription).columns}
    expected = {
        "id",
        "user_id",
        "status",
        "monthly_saju_remaining",
        "current_period_start",
        "current_period_end",
        "created_at",
        "canceled_at",
    }
    missing = expected - cols
    assert not missing, f"Subscription missing columns: {missing}"


def test_refund_model_has_expected_columns() -> None:
    cols = {c.name for c in inspect(Refund).columns}
    expected = {"id", "payment_id", "amount_krw", "reason", "created_at"}
    missing = expected - cols
    assert not missing, f"Refund missing columns: {missing}"


def test_payment_table_metadata_registered() -> None:
    assert "payments" in Base.metadata.tables
    table = Base.metadata.tables["payments"]
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"id"}


def test_subscription_table_metadata_registered() -> None:
    assert "subscriptions" in Base.metadata.tables
    table = Base.metadata.tables["subscriptions"]
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"id"}


def test_refund_table_metadata_registered() -> None:
    assert "refunds" in Base.metadata.tables
    table = Base.metadata.tables["refunds"]
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"id"}


def test_payment_has_fk_to_users() -> None:
    table = Base.metadata.tables["payments"]
    user_col = table.c.user_id
    targets = [fk.target_fullname for fk in user_col.foreign_keys]
    assert any(t.endswith("users.id") for t in targets)


def test_subscription_has_fk_to_users() -> None:
    table = Base.metadata.tables["subscriptions"]
    user_col = table.c.user_id
    targets = [fk.target_fullname for fk in user_col.foreign_keys]
    assert any(t.endswith("users.id") for t in targets)


def test_refund_has_fk_to_payments() -> None:
    table = Base.metadata.tables["refunds"]
    payment_col = table.c.payment_id
    targets = [fk.target_fullname for fk in payment_col.foreign_keys]
    assert any(t.endswith("payments.id") for t in targets)


# --------------------------------------------------------------------------- #
# CHECK-constraint enforcement (SQLite-backed)                                 #
# --------------------------------------------------------------------------- #


async def _make_user(session: AsyncSession, *, provider_tag: str) -> str:
    user_id = str(uuid.uuid4())
    user = User(id=user_id, kakao_sub=f"kakao:{provider_tag}-{uuid.uuid4()}")
    session.add(user)
    await session.flush()
    return user_id


@pytest.mark.asyncio
async def test_payment_with_valid_fields_persists() -> None:
    """Happy-path insert: amount>0 and refunded inside bounds — no error."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="pay-ok")
            payment = Payment(
                id=str(uuid.uuid4()),
                user_id=user_id,
                kind="single",
                amount_krw=4900,
                method="card",
                status="paid",
                toss_order_id="order-1",
                refunded_amount_krw=0,
                idempotency_key="idem-1",
            )
            session.add(payment)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_payment_amount_zero_violates_check() -> None:
    """`amount_krw=0` must trigger `payments_amount_positive_chk`."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="pay-zero")
            bad = Payment(
                id=str(uuid.uuid4()),
                user_id=user_id,
                kind="single",
                amount_krw=0,
                method="card",
                status="pending",
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_payment_refunded_exceeds_amount_violates_check() -> None:
    """`refunded_amount_krw > amount_krw` must trigger
    `payments_refund_bound_chk`."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="pay-overrefund")
            bad = Payment(
                id=str(uuid.uuid4()),
                user_id=user_id,
                kind="single",
                amount_krw=4900,
                method="card",
                status="paid",
                refunded_amount_krw=5000,
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_subscription_monthly_remaining_above_bound_violates_check() -> None:
    """`monthly_saju_remaining=2` must trigger `subs_monthly_remaining_chk`."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="sub-overcount")
            now = datetime.now(UTC)
            bad = Subscription(
                id=str(uuid.uuid4()),
                user_id=user_id,
                status="active",
                monthly_saju_remaining=2,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_refund_amount_zero_violates_check() -> None:
    """`amount_krw=0` must trigger `refunds_amount_positive_chk`."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="refund-zero")
            payment = Payment(
                id=str(uuid.uuid4()),
                user_id=user_id,
                kind="single",
                amount_krw=4900,
                method="card",
                status="paid",
            )
            session.add(payment)
            await session.flush()

            bad = Refund(
                id=str(uuid.uuid4()),
                payment_id=payment.id,
                amount_krw=0,
                reason="user_request",
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


# --------------------------------------------------------------------------- #
# Migration source smoke tests                                                 #
# --------------------------------------------------------------------------- #


def test_migration_revision_chain() -> None:
    module = _load_migration_module()
    assert module.revision == "0006_payments_subscriptions_refunds"
    assert module.down_revision == "0005_free_tokens"


def test_migration_declares_all_three_tables() -> None:
    src = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "create_table" in src
    assert '"payments"' in src
    assert '"subscriptions"' in src
    assert '"refunds"' in src


@pytest.mark.parametrize(
    "ddl_phrase",
    [
        "payments_amount_positive_chk",
        "payments_refund_bound_chk",
        "subs_monthly_remaining_chk",
        "refunds_amount_positive_chk",
        "payments_toss_order_id_uk",
        "payments_idempotency_uk",
        "subscriptions_one_active_per_user",
    ],
)
def test_migration_declares_expected_constraints_and_indexes(ddl_phrase: str) -> None:
    src = MIGRATION_PATH.read_text(encoding="utf-8")
    assert ddl_phrase in src, f"migration missing phrase: {ddl_phrase}"
