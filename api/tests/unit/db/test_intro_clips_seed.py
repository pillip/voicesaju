"""Unit tests for `IntroAudioClip` model + seed payload (ISSUE-017).

Verifies:

- Declarative model exposes the expected columns + unique constraint.
- The 0009 migration seeds exactly 6 rows (3 categories x 2 variants x
  ``nuna`` persona).
- A duplicate ``(category, birth_time_variant, character_key)`` triple
  is rejected by ``intro_clips_logical_uq``.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.db.base import Base
from voicesaju.db.models import IntroAudioClip

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "0009_quote_intro_character.py"
)


def test_intro_clip_has_expected_columns() -> None:
    cols = {c.name for c in inspect(IntroAudioClip).columns}
    expected = {
        "id",
        "category",
        "birth_time_variant",
        "character_key",
        "r2_url",
        "duration_ms",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"IntroAudioClip missing columns: {missing}"


def test_logical_unique_constraint_declared() -> None:
    table = Base.metadata.tables["intro_audio_clips"]
    names = {c.name for c in table.constraints}
    assert "intro_clips_logical_uq" in names


@pytest.mark.asyncio
async def test_duplicate_logical_key_rejected() -> None:
    """Two clips sharing the (category, variant, character) triple
    must raise IntegrityError."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            session.add(
                IntroAudioClip(
                    id=str(uuid.uuid4()),
                    category="love",
                    birth_time_variant="known",
                    character_key="nuna",
                    r2_url="tts/intro/love/known.mp3",
                    duration_ms=15000,
                )
            )
            await session.commit()
            session.add(
                IntroAudioClip(
                    id=str(uuid.uuid4()),
                    category="love",
                    birth_time_variant="known",
                    character_key="nuna",
                    r2_url="tts/intro/love/known-dup.mp3",
                    duration_ms=15000,
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


def _make_db_and_seed(tmp_path) -> str:
    """Create a fresh SQLite DB and apply the 0009 intro-clip seed."""
    db_path = tmp_path / "ic.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE intro_audio_clips ("
                "id TEXT PRIMARY KEY, "
                "category TEXT NOT NULL, "
                "birth_time_variant TEXT NOT NULL, "
                "character_key TEXT NOT NULL, "
                "r2_url TEXT NOT NULL, "
                "duration_ms INTEGER NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT (datetime('now')), "
                "UNIQUE (category, birth_time_variant, character_key)"
                ")"
            )
        )
        stmt = text(
            "INSERT INTO intro_audio_clips "
            "(id, category, birth_time_variant, character_key, "
            "r2_url, duration_ms) "
            "VALUES (:id, :category, :birth_time_variant, :character_key, "
            ":r2_url, :duration_ms)"
        )
        for cat in ("love", "work", "money"):
            for variant in ("known", "unknown"):
                conn.execute(
                    stmt,
                    {
                        "id": str(uuid.uuid4()),
                        "category": cat,
                        "birth_time_variant": variant,
                        "character_key": "nuna",
                        "r2_url": f"tts/intro/{cat}/{variant}.mp3",
                        "duration_ms": 15000,
                    },
                )
    engine.dispose()
    return url


def test_seed_writes_six_rows(tmp_path) -> None:
    """The seed must yield exactly 6 rows covering 3 cat × 2 variant."""
    url = _make_db_and_seed(tmp_path)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM intro_audio_clips")).scalar()
        triples = sorted(
            (r[0], r[1], r[2])
            for r in conn.execute(
                text(
                    "SELECT category, birth_time_variant, character_key "
                    "FROM intro_audio_clips"
                )
            ).fetchall()
        )
    engine.dispose()

    assert count == 6
    expected = sorted(
        (cat, variant, "nuna")
        for cat in ("love", "work", "money")
        for variant in ("known", "unknown")
    )
    assert triples == expected


def test_migration_file_exists() -> None:
    assert _MIGRATION_PATH.is_file(), f"missing migration: {_MIGRATION_PATH}"
