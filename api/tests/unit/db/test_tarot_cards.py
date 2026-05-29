"""Unit tests for `TarotCard` model + seed (ISSUE-016).

Verifies:

- Declarative model exposes the expected columns + constraints.
- ``card_index`` UNIQUE constraint blocks duplicates.
- The seed data table in migration 0008 contains all 22 Major Arcana
  rows with ``card_index`` 0..21 present.
- The seed insert against a fresh SQLite DB is idempotent — running it
  twice still yields exactly 22 rows.

The migration's full ``upgrade()`` is exercised end-to-end against
Postgres in ``tests/integration/db/test_tarot_constraints.py``. The
SQLite-flavoured smoke test below imports the seed payload from the
migration module directly so it does not depend on alembic env.py
(which forces the URL to the configured Postgres instance).
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
from voicesaju.db.models import TarotCard

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "0008_tarot_tables_seed.py"
)


def test_tarot_card_has_expected_columns() -> None:
    cols = {c.name for c in inspect(TarotCard).columns}
    expected = {
        "id",
        "card_index",
        "name_kr",
        "name_en",
        "meaning_kr",
        "meaning_en",
        "art_key",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"TarotCard missing columns: {missing}"


def test_tarot_card_card_index_is_unique() -> None:
    table = Base.metadata.tables["tarot_cards"]
    assert table.c.card_index.unique is True


@pytest.mark.asyncio
async def test_tarot_card_duplicate_card_index_rejected() -> None:
    """Two rows with the same ``card_index`` → IntegrityError."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with session_factory() as session:
            session.add(
                TarotCard(
                    id=str(uuid.uuid4()),
                    card_index=0,
                    name_kr="A",
                    name_en="A",
                    meaning_kr="m",
                    art_key="tarot/major/00.webp",
                )
            )
            await session.commit()
            session.add(
                TarotCard(
                    id=str(uuid.uuid4()),
                    card_index=0,
                    name_kr="B",
                    name_en="B",
                    meaning_kr="m",
                    art_key="tarot/major/00.webp",
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


def _load_seed_module() -> object:
    """Load the 0008 migration module directly by file path.

    Alembic versions live in a non-package directory (no ``__init__.py``)
    and their filenames start with a digit, so neither
    ``importlib.import_module`` nor the regular ``import`` syntax can
    reach them. ``importlib.util.spec_from_file_location`` sidesteps
    both issues.
    """
    spec = importlib.util.spec_from_file_location(
        "_tarot_seed_migration", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seed_table_has_22_unique_cards() -> None:
    """The seed payload in 0008 lists all 22 Major Arcana with unique
    ``card_index`` values 0..21."""
    mod = _load_seed_module()
    rows = mod._MAJOR_ARCANA  # type: ignore[attr-defined]
    assert len(rows) == 22, f"expected 22 seed rows, got {len(rows)}"
    indexes = sorted(r[0] for r in rows)
    assert indexes == list(range(22))


def _insert_seed_sqlite(engine_url: str) -> None:
    """Manually create ``tarot_cards`` and apply the SQLite seed.

    Mirrors the SQLite branch of the migration so we can assert the
    ``INSERT OR IGNORE`` semantics without the alembic env shim.
    """
    mod = _load_seed_module()
    engine = sa.create_engine(engine_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE tarot_cards ("
                "id TEXT PRIMARY KEY, "
                "card_index INTEGER NOT NULL UNIQUE, "
                "name_kr TEXT NOT NULL, "
                "name_en TEXT NOT NULL, "
                "meaning_kr TEXT NOT NULL, "
                "meaning_en TEXT, "
                "art_key TEXT NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT (datetime('now'))"
                ")"
            )
        )
        stmt = text(
            "INSERT OR IGNORE INTO tarot_cards "
            "(id, card_index, name_kr, name_en, "
            "meaning_kr, meaning_en, art_key) "
            "VALUES (:id, :card_index, :name_kr, :name_en, "
            ":meaning_kr, :meaning_en, :art_key)"
        )
        for idx, name_en, name_kr, meaning_kr, meaning_en in mod._MAJOR_ARCANA:  # type: ignore[attr-defined]
            conn.execute(
                stmt,
                {
                    "id": str(uuid.uuid4()),
                    "card_index": idx,
                    "name_kr": name_kr,
                    "name_en": name_en,
                    "meaning_kr": meaning_kr,
                    "meaning_en": meaning_en,
                    "art_key": f"tarot/major/{idx:02d}.webp",
                },
            )
    engine.dispose()


def test_seed_sqlite_writes_22_rows(tmp_path) -> None:
    """End-to-end SQLite smoke: applying the seed yields 22 rows with
    consecutive ``card_index`` values."""
    db = tmp_path / "tarot.db"
    _insert_seed_sqlite(f"sqlite:///{db}")
    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM tarot_cards")).scalar()
        assert count == 22
        indexes = [
            r[0]
            for r in conn.execute(
                text("SELECT card_index FROM tarot_cards ORDER BY card_index")
            ).fetchall()
        ]
        assert indexes == list(range(22))
    engine.dispose()


def test_seed_sqlite_is_idempotent(tmp_path) -> None:
    """Re-running the SQLite seed leaves the row count at 22 — exercises
    ``INSERT OR IGNORE`` against the existing UNIQUE constraint."""
    db = tmp_path / "tarot.db"
    _insert_seed_sqlite(f"sqlite:///{db}")
    # Re-run the seed inserts only (table already exists).
    mod = _load_seed_module()
    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        stmt = text(
            "INSERT OR IGNORE INTO tarot_cards "
            "(id, card_index, name_kr, name_en, "
            "meaning_kr, meaning_en, art_key) "
            "VALUES (:id, :card_index, :name_kr, :name_en, "
            ":meaning_kr, :meaning_en, :art_key)"
        )
        for idx, name_en, name_kr, meaning_kr, meaning_en in mod._MAJOR_ARCANA:  # type: ignore[attr-defined]
            conn.execute(
                stmt,
                {
                    "id": str(uuid.uuid4()),
                    "card_index": idx,
                    "name_kr": name_kr,
                    "name_en": name_en,
                    "meaning_kr": meaning_kr,
                    "meaning_en": meaning_en,
                    "art_key": f"tarot/major/{idx:02d}.webp",
                },
            )
        count = conn.execute(text("SELECT COUNT(*) FROM tarot_cards")).scalar()
        assert count == 22
    engine.dispose()
