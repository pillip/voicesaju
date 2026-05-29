"""Unit tests for `ToneViolationEvent` model + parent CHECK (ISSUE-018).

Verifies that the declarative model exposes the expected columns and
that ``tone_violation_events_parent_chk`` rejects rows where BOTH
``reading_id`` and ``tarot_id`` are NULL.

The smaller `TonePromptVersion` / `ToneEvalCase` models share unit
coverage in this file because they are siblings in the same migration.
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
from voicesaju.db.models import (
    FreeToken,
    Reading,
    TarotCard,
    TarotDraw,
    ToneEvalCase,
    TonePromptVersion,
    ToneViolationEvent,
    User,
)


def test_violation_event_has_expected_columns() -> None:
    cols = {c.name for c in inspect(ToneViolationEvent).columns}
    expected = {
        "id",
        "reading_id",
        "tarot_id",
        "severity",
        "layer",
        "evidence_text",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"ToneViolationEvent missing columns: {missing}"


def test_violation_event_fk_targets() -> None:
    table = Base.metadata.tables["tone_violation_events"]
    reading_fks = [fk.target_fullname for fk in table.c.reading_id.foreign_keys]
    tarot_fks = [fk.target_fullname for fk in table.c.tarot_id.foreign_keys]
    assert any(t.endswith("readings.id") for t in reading_fks)
    assert any(t.endswith("tarot_draws.id") for t in tarot_fks)


def test_eval_case_has_expected_columns() -> None:
    cols = {c.name for c in inspect(ToneEvalCase).columns}
    expected = {
        "id",
        "case_kind",
        "input_text",
        "expected_label",
        "category_tag",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"ToneEvalCase missing columns: {missing}"


def test_prompt_version_has_expected_columns() -> None:
    cols = {c.name for c in inspect(TonePromptVersion).columns}
    expected = {
        "id",
        "prompt_key",
        "version",
        "prompt_text",
        "is_active",
        "created_at",
        "activated_at",
    }
    missing = expected - cols
    assert not missing, f"TonePromptVersion missing columns: {missing}"


@pytest.mark.asyncio
async def test_violation_event_both_parents_null_violates_check() -> None:
    """Both ``reading_id`` and ``tarot_id`` NULL → CHECK fails (AC)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            bad = ToneViolationEvent(
                id=str(uuid.uuid4()),
                reading_id=None,
                tarot_id=None,
                severity="mild",
                layer="prompt",
                evidence_text="oops",
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


async def _seed_reading(session: AsyncSession, *, tag: str) -> str:
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
async def test_violation_event_reading_only_passes() -> None:
    """Only ``reading_id`` set → row persists."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            reading_id = await _seed_reading(session, tag="v-r")
            session.add(
                ToneViolationEvent(
                    id=str(uuid.uuid4()),
                    reading_id=reading_id,
                    severity="mild",
                    layer="prompt",
                    evidence_text="evidence",
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _seed_tarot_draw(session: AsyncSession, *, tag: str) -> str:
    user_id = str(uuid.uuid4())
    session.add(User(id=user_id, kakao_sub=f"kakao:{tag}-{uuid.uuid4()}"))
    await session.flush()
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
    draw_id = str(uuid.uuid4())
    session.add(
        TarotDraw(
            id=draw_id,
            user_id=user_id,
            card_id=card_id,
            card_index=0,
            date_kst=date(2026, 5, 28),
        )
    )
    await session.flush()
    return draw_id


@pytest.mark.asyncio
async def test_violation_event_tarot_only_passes() -> None:
    """Only ``tarot_id`` set → row persists."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            draw_id = await _seed_tarot_draw(session, tag="v-t")
            session.add(
                ToneViolationEvent(
                    id=str(uuid.uuid4()),
                    tarot_id=draw_id,
                    severity="severe",
                    layer="filter",
                    evidence_text="oops",
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_prompt_key_empty_violates_check() -> None:
    """Empty ``prompt_key`` → CHECK fails (AC)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            bad = TonePromptVersion(
                id=str(uuid.uuid4()),
                prompt_key="",
                version=1,
                prompt_text="text",
                is_active=False,
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_prompt_version_persists() -> None:
    """Non-empty prompt_key persists (happy path)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            session.add(
                TonePromptVersion(
                    id=str(uuid.uuid4()),
                    prompt_key="sajununa.system",
                    version=1,
                    prompt_text="be sharp but kind",
                    is_active=True,
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_eval_case_persists() -> None:
    """ToneEvalCase persists for all known labels (smoke)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            for label in ("ok", "spicy_ok", "violation_mild", "violation_severe"):
                session.add(
                    ToneEvalCase(
                        id=str(uuid.uuid4()),
                        case_kind="manual",
                        input_text=f"text for {label}",
                        expected_label=label,
                        category_tag="general",
                    )
                )
            await session.commit()
    finally:
        await engine.dispose()
