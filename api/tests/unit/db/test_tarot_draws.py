"""Unit tests for `TarotDraw` model + XOR owner CHECK (ISSUE-016).

Verifies that the declarative model exposes the expected columns and
that the ``tarot_draws_owner_xor_chk`` CHECK rejects rows where:

- both ``user_id`` and ``device_id`` are ``NULL`` (no owner)
- both ``user_id`` and ``device_id`` are set (two owners)
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.db.base import Base
from voicesaju.db.models import Device, TarotCard, TarotDraw, User


def test_tarot_draw_has_expected_columns() -> None:
    cols = {c.name for c in inspect(TarotDraw).columns}
    expected = {
        "id",
        "user_id",
        "device_id",
        "card_id",
        "card_index",
        "date_kst",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"TarotDraw missing columns: {missing}"


def test_tarot_draw_fk_targets() -> None:
    table = Base.metadata.tables["tarot_draws"]
    user_fks = [fk.target_fullname for fk in table.c.user_id.foreign_keys]
    device_fks = [fk.target_fullname for fk in table.c.device_id.foreign_keys]
    card_fks = [fk.target_fullname for fk in table.c.card_id.foreign_keys]
    assert any(t.endswith("users.id") for t in user_fks)
    assert any(t.endswith("devices.id") for t in device_fks)
    assert any(t.endswith("tarot_cards.id") for t in card_fks)


async def _seed_card(session: AsyncSession) -> str:
    card_id = str(uuid.uuid4())
    session.add(
        TarotCard(
            id=card_id,
            card_index=0,
            name_kr="바보",
            name_en="The Fool",
            meaning_kr="m",
            art_key="tarot/major/00.webp",
        )
    )
    await session.flush()
    return card_id


@pytest.mark.asyncio
async def test_owner_xor_both_null_violates_check() -> None:
    """Both ``user_id`` and ``device_id`` NULL → CHECK fails."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            card_id = await _seed_card(session)
            bad = TarotDraw(
                id=str(uuid.uuid4()),
                user_id=None,
                device_id=None,
                card_id=card_id,
                card_index=0,
                date_kst=date(2026, 5, 28),
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_owner_xor_both_set_violates_check() -> None:
    """Both ``user_id`` and ``device_id`` set → CHECK fails."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            card_id = await _seed_card(session)
            user_id = str(uuid.uuid4())
            device_id = str(uuid.uuid4())
            session.add(User(id=user_id, kakao_sub=f"kakao:xor-{uuid.uuid4()}"))
            session.add(Device(id=device_id, device_id_client=f"dev-{device_id}"))
            await session.flush()

            bad = TarotDraw(
                id=str(uuid.uuid4()),
                user_id=user_id,
                device_id=device_id,
                card_id=card_id,
                card_index=0,
                date_kst=date(2026, 5, 28),
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_owner_xor_user_only_passes() -> None:
    """Only ``user_id`` set → row persists."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            card_id = await _seed_card(session)
            user_id = str(uuid.uuid4())
            session.add(User(id=user_id, kakao_sub=f"kakao:u-{uuid.uuid4()}"))
            await session.flush()

            row = TarotDraw(
                id=str(uuid.uuid4()),
                user_id=user_id,
                card_id=card_id,
                card_index=0,
                date_kst=date(2026, 5, 28),
            )
            session.add(row)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_owner_xor_device_only_passes() -> None:
    """Only ``device_id`` set → row persists."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            card_id = await _seed_card(session)
            device_id = str(uuid.uuid4())
            session.add(Device(id=device_id, device_id_client=f"dev-{device_id}"))
            await session.flush()

            row = TarotDraw(
                id=str(uuid.uuid4()),
                device_id=device_id,
                card_id=card_id,
                card_index=0,
                date_kst=date(2026, 5, 28),
            )
            session.add(row)
            await session.commit()
    finally:
        await engine.dispose()
