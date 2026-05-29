"""Unit tests for `Reading` ORM model + entitlement consistency CHECK.

Verifies that the SQLAlchemy declarative model imports cleanly, exposes
every column documented in `docs/data_model.md` §4.8 (subset documented
on ISSUE-015), registers on `Base.metadata`, and that the
``readings_entitlement_chk`` CHECK constraint blocks inconsistent
``(entitlement_kind, *_id)`` rows on the SQLite engine that backs unit
tests.
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
from voicesaju.db.models import (
    FreeToken,
    Payment,
    Reading,
    Subscription,
    User,
)

API_DIR = Path(__file__).resolve().parents[3]
MIGRATION_PATH = API_DIR / "alembic" / "versions" / "0007_readings_tables.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_0007_readings_tables", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# Column / metadata smoke tests                                                #
# --------------------------------------------------------------------------- #


def test_reading_model_has_expected_columns() -> None:
    cols = {c.name for c in inspect(Reading).columns}
    expected = {
        "id",
        "user_id",
        "category",
        "status",
        "chart_hash",
        "character_key",
        "idempotency_key",
        "entitlement_kind",
        "payment_id",
        "subscription_id",
        "free_token_id",
        "created_at",
        "started_at",
        "completed_at",
    }
    missing = expected - cols
    assert not missing, f"Reading missing columns: {missing}"


def test_reading_table_metadata_registered() -> None:
    assert "readings" in Base.metadata.tables
    table = Base.metadata.tables["readings"]
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"id"}


def test_reading_has_fk_to_users() -> None:
    table = Base.metadata.tables["readings"]
    user_col = table.c.user_id
    targets = [fk.target_fullname for fk in user_col.foreign_keys]
    assert any(t.endswith("users.id") for t in targets)


def test_reading_has_fk_to_payments() -> None:
    table = Base.metadata.tables["readings"]
    pay_col = table.c.payment_id
    targets = [fk.target_fullname for fk in pay_col.foreign_keys]
    assert any(t.endswith("payments.id") for t in targets)


def test_reading_has_fk_to_subscriptions() -> None:
    table = Base.metadata.tables["readings"]
    sub_col = table.c.subscription_id
    targets = [fk.target_fullname for fk in sub_col.foreign_keys]
    assert any(t.endswith("subscriptions.id") for t in targets)


def test_reading_has_fk_to_free_tokens() -> None:
    table = Base.metadata.tables["readings"]
    ft_col = table.c.free_token_id
    targets = [fk.target_fullname for fk in ft_col.foreign_keys]
    assert any(t.endswith("free_tokens.id") for t in targets)


# --------------------------------------------------------------------------- #
# Entitlement consistency CHECK enforcement (SQLite-backed)                    #
# --------------------------------------------------------------------------- #


async def _make_user(session: AsyncSession, *, provider_tag: str) -> str:
    user_id = str(uuid.uuid4())
    user = User(id=user_id, kakao_sub=f"kakao:{provider_tag}-{uuid.uuid4()}")
    session.add(user)
    await session.flush()
    return user_id


async def _make_payment(session: AsyncSession, *, user_id: str) -> str:
    payment_id = str(uuid.uuid4())
    payment = Payment(
        id=payment_id,
        user_id=user_id,
        kind="single",
        amount_krw=4900,
        method="card",
        status="paid",
    )
    session.add(payment)
    await session.flush()
    return payment_id


async def _make_subscription(session: AsyncSession, *, user_id: str) -> str:
    sub_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    sub = Subscription(
        id=sub_id,
        user_id=user_id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    session.add(sub)
    await session.flush()
    return sub_id


async def _make_free_token(session: AsyncSession, *, user_id: str) -> str:
    ft_id = str(uuid.uuid4())
    ft = FreeToken(id=ft_id, user_id=user_id, kind="signup_grant")
    session.add(ft)
    await session.flush()
    return ft_id


@pytest.mark.asyncio
async def test_reading_payment_entitlement_persists() -> None:
    """Happy path: `entitlement_kind='payment'` + `payment_id` present."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="rd-pay-ok")
            payment_id = await _make_payment(session, user_id=user_id)
            reading = Reading(
                id=str(uuid.uuid4()),
                user_id=user_id,
                category="love",
                status="pending",
                character_key="sajununa",
                entitlement_kind="payment",
                payment_id=payment_id,
            )
            session.add(reading)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reading_subscription_entitlement_persists() -> None:
    """Happy path: `entitlement_kind='subscription'` + `subscription_id`."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="rd-sub-ok")
            sub_id = await _make_subscription(session, user_id=user_id)
            reading = Reading(
                id=str(uuid.uuid4()),
                user_id=user_id,
                category="work",
                status="streaming",
                character_key="tarodosa",
                entitlement_kind="subscription",
                subscription_id=sub_id,
            )
            session.add(reading)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reading_free_token_entitlement_persists() -> None:
    """Happy path: `entitlement_kind='free_token'` + `free_token_id`."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="rd-ft-ok")
            ft_id = await _make_free_token(session, user_id=user_id)
            reading = Reading(
                id=str(uuid.uuid4()),
                user_id=user_id,
                category="money",
                status="pending",
                character_key="sajununa",
                entitlement_kind="free_token",
                free_token_id=ft_id,
            )
            session.add(reading)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reading_payment_entitlement_without_payment_id_violates_check() -> None:
    """`entitlement_kind='payment'` + `payment_id=NULL` -> CHECK fails (AC)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="rd-pay-null")
            bad = Reading(
                id=str(uuid.uuid4()),
                user_id=user_id,
                category="love",
                status="pending",
                character_key="sajununa",
                entitlement_kind="payment",
                payment_id=None,
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reading_subscription_entitlement_without_sub_id_violates_check() -> None:
    """`entitlement_kind='subscription'` + `subscription_id=NULL` -> CHECK fails."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="rd-sub-null")
            bad = Reading(
                id=str(uuid.uuid4()),
                user_id=user_id,
                category="work",
                status="pending",
                character_key="tarodosa",
                entitlement_kind="subscription",
                subscription_id=None,
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reading_free_token_entitlement_without_ft_id_violates_check() -> None:
    """`entitlement_kind='free_token'` + `free_token_id=NULL` -> CHECK fails."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        async with session_factory() as session:
            user_id = await _make_user(session, provider_tag="rd-ft-null")
            bad = Reading(
                id=str(uuid.uuid4()),
                user_id=user_id,
                category="money",
                status="pending",
                character_key="sajununa",
                entitlement_kind="free_token",
                free_token_id=None,
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
    assert module.revision == "0007_readings_tables"
    assert module.down_revision == "0006_payments_subscriptions_refunds"


def test_migration_declares_all_four_tables() -> None:
    src = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "create_table" in src
    assert '"readings"' in src
    assert '"reading_transcripts"' in src
    assert '"reading_followups"' in src
    assert '"reading_audio"' in src


@pytest.mark.parametrize(
    "ddl_phrase",
    [
        "readings_entitlement_chk",
        "followups_slot_range_chk",
        "audio_duration_chk",
        "reading_followups_reading_slot_uq",
    ],
)
def test_migration_declares_expected_constraints_and_indexes(ddl_phrase: str) -> None:
    src = MIGRATION_PATH.read_text(encoding="utf-8")
    assert ddl_phrase in src, f"migration missing phrase: {ddl_phrase}"
