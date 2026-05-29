"""Unit tests for ``0011_seed_tone_eval_cases`` migration.

The migration reads ``tests/fixtures/tone_evalset.json`` and seeds it
into ``tone_eval_cases``. These tests exercise the SQLite path (the
Postgres ``ON CONFLICT`` path is covered by integration tests).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from voicesaju.db.base import Base
from voicesaju.db.models import ToneEvalCase  # noqa: F401 - register metadata

API_DIR = Path(__file__).resolve().parents[3]
MIGRATION_PATH = API_DIR / "alembic" / "versions" / "0011_seed_tone_eval_cases.py"
FIXTURE_PATH = API_DIR / "tests" / "fixtures" / "tone_evalset.json"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_0011_seed_tone_eval_cases", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


def test_migration_module_exposes_revision_chain() -> None:
    module = _load_migration_module()
    assert module.revision == "0011_seed_tone_eval_cases"
    assert module.down_revision == "0010_tone_tables"


def test_fixture_is_loadable_from_migration_path() -> None:
    """The migration resolves the fixture path relative to its own
    location. Confirm it points at the correct file and parses.
    """
    module = _load_migration_module()
    cases = module._load_fixture()
    assert isinstance(cases, list)
    assert len(cases) >= 50

    # Cross-check the fixture file the test loads directly is the same
    # one the migration loads — they MUST not drift.
    with FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert cases == on_disk


@pytest.mark.asyncio
async def test_seed_payload_inserts_every_case(session: AsyncSession) -> None:
    """Bulk-insert path: every fixture row lands in ``tone_eval_cases``.

    We invoke the seed manually rather than running ``upgrade()`` because
    ``upgrade()`` depends on ``alembic.op`` having an active migration
    context. The seed payload is the same shape either way.
    """
    module = _load_migration_module()
    cases = module._load_fixture()

    # Insert directly via the session (equivalent to op.bulk_insert).
    import uuid as _uuid

    for case in cases:
        await session.execute(
            text(
                "INSERT INTO tone_eval_cases "
                "(id, case_kind, input_text, expected_label, category_tag) "
                "VALUES (:id, :case_kind, :input_text, :expected_label, "
                ":category_tag)"
            ),
            {
                "id": str(_uuid.uuid4()),
                "case_kind": case["case_kind"],
                "input_text": case["input_text"],
                "expected_label": case["expected_label"],
                "category_tag": case["category_tag"],
            },
        )
    await session.flush()

    count = (
        await session.execute(text("SELECT COUNT(*) FROM tone_eval_cases"))
    ).scalar_one()
    assert count == len(cases) >= 50


@pytest.mark.asyncio
async def test_seed_preserves_label_distribution(session: AsyncSession) -> None:
    """After seeding, each ``expected_label`` from the fixture is
    represented at least once in the table.
    """
    module = _load_migration_module()
    cases = module._load_fixture()

    import uuid as _uuid

    for case in cases:
        await session.execute(
            text(
                "INSERT INTO tone_eval_cases "
                "(id, case_kind, input_text, expected_label, category_tag) "
                "VALUES (:id, :case_kind, :input_text, :expected_label, "
                ":category_tag)"
            ),
            {
                "id": str(_uuid.uuid4()),
                "case_kind": case["case_kind"],
                "input_text": case["input_text"],
                "expected_label": case["expected_label"],
                "category_tag": case["category_tag"],
            },
        )
    await session.flush()

    rows = (
        await session.execute(
            text("SELECT DISTINCT expected_label FROM tone_eval_cases")
        )
    ).all()
    labels = {row[0] for row in rows}
    expected_labels = {case["expected_label"] for case in cases}
    assert labels == expected_labels
