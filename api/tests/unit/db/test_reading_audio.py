"""Unit tests for `ReadingAudio` model + duration_ms range CHECK.

Verifies that the SQLAlchemy declarative model imports cleanly and that
the ``audio_duration_chk`` CHECK constraint rejects rows whose
``duration_ms`` falls outside the FR-007 60-120 sec window.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.db.base import Base
from voicesaju.db.models import (
    FreeToken,
    Reading,
    ReadingAudio,
    User,
)


def test_reading_audio_has_expected_columns() -> None:
    cols = {c.name for c in inspect(ReadingAudio).columns}
    expected = {"id", "reading_id", "r2_url", "duration_ms", "created_at"}
    missing = expected - cols
    assert not missing, f"ReadingAudio missing columns: {missing}"


def test_reading_audio_fk_to_readings() -> None:
    table = Base.metadata.tables["reading_audio"]
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
            status="complete",
            character_key="sajununa",
            entitlement_kind="free_token",
            free_token_id=ft_id,
        )
    )
    await session.flush()
    return reading_id


@pytest.mark.asyncio
@pytest.mark.parametrize("duration_ms", [60000, 90000, 120000])
async def test_audio_duration_in_window_persists(duration_ms: int) -> None:
    """Happy path: 60_000, 90_000, 120_000 ms all valid (inclusive bounds)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            reading_id = await _seed_reading(
                session, provider_tag=f"audio-ok-{duration_ms}"
            )
            session.add(
                ReadingAudio(
                    id=str(uuid.uuid4()),
                    reading_id=reading_id,
                    r2_url=f"https://r2/{reading_id}.mp3",
                    duration_ms=duration_ms,
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_audio_duration_below_min_violates_check() -> None:
    """`duration_ms=30000` -> CHECK fails (AC: below 60_000)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            reading_id = await _seed_reading(session, provider_tag="audio-short")
            bad = ReadingAudio(
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                r2_url=f"https://r2/{reading_id}.mp3",
                duration_ms=30000,
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_audio_duration_above_max_violates_check() -> None:
    """`duration_ms=121000` -> CHECK fails (above 120_000)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            reading_id = await _seed_reading(session, provider_tag="audio-long")
            bad = ReadingAudio(
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                r2_url=f"https://r2/{reading_id}.mp3",
                duration_ms=121000,
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()
