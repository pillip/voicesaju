"""Unit tests for `ReadingFollowup` model + slot_index range CHECK.

Verifies that the SQLAlchemy declarative model imports cleanly, exposes
the expected columns, and that the ``followups_slot_range_chk`` CHECK
constraint rejects rows with ``slot_index`` outside ``[0, 2]``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.db.base import Base
from voicesaju.db.models import (
    FreeToken,
    Reading,
    ReadingFollowup,
    User,
)


def test_reading_followup_has_expected_columns() -> None:
    cols = {c.name for c in inspect(ReadingFollowup).columns}
    expected = {
        "id",
        "reading_id",
        "slot_index",
        "question_text",
        "answer_text",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"ReadingFollowup missing columns: {missing}"


def test_reading_followup_fk_to_readings() -> None:
    table = Base.metadata.tables["reading_followups"]
    fk_targets = [fk.target_fullname for fk in table.c.reading_id.foreign_keys]
    assert any(t.endswith("readings.id") for t in fk_targets)


async def _seed_reading(session: AsyncSession, *, provider_tag: str) -> str:
    user_id = str(uuid.uuid4())
    session.add(User(id=user_id, kakao_sub=f"kakao:{provider_tag}-{uuid.uuid4()}"))
    await session.flush()
    ft_id = str(uuid.uuid4())
    session.add(FreeToken(id=ft_id, user_id=user_id, kind="signup_grant"))
    await session.flush()
    reading_id = str(uuid.uuid4())
    session.add(
        Reading(
            id=reading_id,
            user_id=user_id,
            category="love",
            status="pending",
            character_key="sajununa",
            entitlement_kind="free_token",
            free_token_id=ft_id,
        )
    )
    await session.flush()
    return reading_id


@pytest.mark.asyncio
async def test_followup_slot_index_in_range_persists() -> None:
    """Happy path: slot_index 0, 1, 2 are all valid."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            reading_id = await _seed_reading(session, provider_tag="slot-ok")
            for idx in (0, 1, 2):
                session.add(
                    ReadingFollowup(
                        id=str(uuid.uuid4()),
                        reading_id=reading_id,
                        slot_index=idx,
                        question_text=f"Q{idx}",
                    )
                )
            await session.commit()
            # The dummy used for shared FreeToken so unused import lint quiet
            _ = datetime.now(UTC), timedelta(days=1)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_followup_slot_index_three_violates_check() -> None:
    """`slot_index=3` -> CHECK fails (AC: range 0..2)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            reading_id = await _seed_reading(session, provider_tag="slot-3")
            bad = ReadingFollowup(
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                slot_index=3,
                question_text="Q3",
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_followup_slot_index_negative_violates_check() -> None:
    """`slot_index=-1` -> CHECK fails (AC: range 0..2)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            reading_id = await _seed_reading(session, provider_tag="slot-neg")
            bad = ReadingFollowup(
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                slot_index=-1,
                question_text="Q-",
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()
