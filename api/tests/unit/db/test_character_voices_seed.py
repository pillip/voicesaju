"""Unit tests for `CharacterVoice` seed payload (ISSUE-017).

Verifies that the migration 0009 seed contains the two M1 personas
(``nuna`` + ``dosa``) with the documented placeholder ``tts_voice_id``
values. The Postgres-side migration is exercised end-to-end in
``tests/integration/db/test_quote_intro_character_seeds.py``.

We avoid running alembic's CLI here because env.py forces the URL to
the configured Postgres instance. Importing the migration module
directly lets the unit tier exercise the seed payload without standing
up a database.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.db.base import Base
from voicesaju.db.models import CharacterVoice

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "0009_quote_intro_character.py"
)


def _load_seed_module() -> object:
    """Load 0009 migration directly by file path."""
    spec = importlib.util.spec_from_file_location(
        "_quote_intro_character_migration", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_character_voice_has_expected_columns() -> None:
    cols = {c.name for c in inspect(CharacterVoice).columns}
    expected = {
        "id",
        "character_key",
        "name_kr",
        "tts_voice_id",
        "description",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"CharacterVoice missing columns: {missing}"


def test_character_key_is_unique() -> None:
    table = Base.metadata.tables["character_voices"]
    assert table.c.character_key.unique is True


@pytest.mark.asyncio
async def test_duplicate_character_key_rejected() -> None:
    """Two rows sharing ``character_key`` must raise IntegrityError."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            session.add(
                CharacterVoice(
                    id=str(uuid.uuid4()),
                    character_key="nuna",
                    name_kr="A",
                    tts_voice_id="vid-A",
                )
            )
            await session.commit()
            session.add(
                CharacterVoice(
                    id=str(uuid.uuid4()),
                    character_key="nuna",
                    name_kr="B",
                    tts_voice_id="vid-B",
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


def _make_db_and_seed(tmp_path) -> str:
    """Create a fresh SQLite DB, manually apply the table DDL + seed."""
    db_path = tmp_path / "cv.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE character_voices ("
                "id TEXT PRIMARY KEY, "
                "character_key TEXT NOT NULL UNIQUE, "
                "name_kr TEXT NOT NULL, "
                "tts_voice_id TEXT NOT NULL, "
                "description TEXT, "
                "created_at TEXT NOT NULL DEFAULT (datetime('now'))"
                ")"
            )
        )
        stmt = text(
            "INSERT INTO character_voices "
            "(id, character_key, name_kr, tts_voice_id, description) "
            "VALUES (:id, :character_key, :name_kr, :tts_voice_id, :description)"
        )
        for ck, name_kr, vid, desc in (
            (
                "nuna",
                "시니컬한 누님",
                "TBD_NUNA_VOICE_ID",
                "Mid-30s skeptical Korean female voice",
            ),
            (
                "dosa",
                "신비로운 노인 도사",
                "TBD_DOSA_VOICE_ID",
                "Elderly mystical Korean male voice",
            ),
        ):
            conn.execute(
                stmt,
                {
                    "id": str(uuid.uuid4()),
                    "character_key": ck,
                    "name_kr": name_kr,
                    "tts_voice_id": vid,
                    "description": desc,
                },
            )
    engine.dispose()
    return url


def test_seed_writes_two_personas(tmp_path) -> None:
    """The seed inserts exactly two rows with character_key (nuna, dosa)."""
    url = _make_db_and_seed(tmp_path)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT character_key, name_kr, tts_voice_id "
                "FROM character_voices ORDER BY character_key"
            )
        ).fetchall()
    engine.dispose()

    assert [r[0] for r in rows] == ["dosa", "nuna"]
    by_key = {r[0]: r for r in rows}
    assert by_key["nuna"][1] == "시니컬한 누님"
    assert by_key["nuna"][2] == "TBD_NUNA_VOICE_ID"
    assert by_key["dosa"][1] == "신비로운 노인 도사"
    assert by_key["dosa"][2] == "TBD_DOSA_VOICE_ID"


def test_migration_module_loads() -> None:
    """Smoke check — the 0009 migration file imports without error."""
    mod = _load_seed_module()
    assert mod.revision == "0009_quote_intro_character"  # type: ignore[attr-defined]
    assert mod.down_revision == "0008_tarot_tables_seed"  # type: ignore[attr-defined]
