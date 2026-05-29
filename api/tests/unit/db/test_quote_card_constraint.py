"""Unit tests for `QuoteCard` model + length CHECK (ISSUE-017).

Verifies:

- The declarative model exposes the expected columns + UNIQUE
  constraints.
- The ``quote_text_max_40_chr_chk`` CHECK rejects rows with
  ``quote_text`` longer than 40 characters.
- A 40-char quote is accepted (boundary).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.db.base import Base
from voicesaju.db.models import FreeToken, QuoteCard, Reading, User


def test_quote_card_has_expected_columns() -> None:
    cols = {c.name for c in inspect(QuoteCard).columns}
    expected = {
        "id",
        "reading_id",
        "quote_text",
        "category",
        "share_slug",
        "og_image_url",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"QuoteCard missing columns: {missing}"


def test_quote_card_unique_constraints() -> None:
    table = Base.metadata.tables["quote_cards"]
    assert table.c.reading_id.unique is True
    assert table.c.share_slug.unique is True


async def _seed_reading(session: AsyncSession, *, tag: str) -> str:
    """Make a parent Reading row so the FK + CHECKs are satisfied."""
    user_id = str(uuid.uuid4())
    session.add(User(id=user_id, kakao_sub=f"kakao:{tag}-{uuid.uuid4()}"))
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
async def test_quote_text_41_chars_violates_check() -> None:
    """A 41-character ``quote_text`` must raise IntegrityError."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            reading_id = await _seed_reading(session, tag="quote-41")
            bad = QuoteCard(
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                quote_text="x" * 41,
                category="love",
                share_slug=f"slug-{uuid.uuid4()}",
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_quote_text_40_chars_boundary_passes() -> None:
    """A 40-character ``quote_text`` (boundary) must persist."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            reading_id = await _seed_reading(session, tag="quote-40")
            ok = QuoteCard(
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                quote_text="y" * 40,
                category="love",
                share_slug=f"slug-{uuid.uuid4()}",
            )
            session.add(ok)
            await session.commit()
    finally:
        await engine.dispose()
