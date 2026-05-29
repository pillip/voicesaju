"""Integration test for migration 0002_postgres_enums.

This test exercises the actual Postgres enum creation/drop cycle.
It requires a running Postgres 16 instance (docker-compose `db` service)
and is excluded from the default CI run via the `integration` marker.

To run locally:

    docker compose up -d db
    cd api && uv run pytest -m integration \
        tests/integration/test_migration_0002_enums.py

Authoritative source: docs/data_model.md §4.1.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

pytestmark = pytest.mark.integration


API_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_DIR / "alembic" / "versions" / "0002_postgres_enums.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_0002_postgres_enums", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _enum_names() -> list[str]:
    module = _load_migration_module()
    return [name for name, _ in module.ENUMS]


def _alembic_config() -> Config:
    return Config(str(API_DIR / "alembic.ini"))


def _database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://voicesaju:voicesaju@localhost:5432/voicesaju",
    )


@pytest.fixture(scope="module")
def alembic_cfg() -> Config:
    cfg = _alembic_config()
    cfg.set_main_option("sqlalchemy.url", _database_url())
    return cfg


async def _list_enums(url: str) -> list[str]:
    engine = create_async_engine(url, future=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT typname FROM pg_type "
                    "WHERE typtype='e' AND typname LIKE '%_enum' "
                    "ORDER BY typname"
                )
            )
            return [row[0] for row in result.fetchall()]
    finally:
        await engine.dispose()


def test_upgrade_creates_all_13_enums(alembic_cfg: Config) -> None:
    """upgrade must register exactly the 13 enums from data_model.md §4.1."""
    expected_names = _enum_names()
    assert len(expected_names) == 13

    command.upgrade(alembic_cfg, "head")
    try:
        names = asyncio.run(_list_enums(_database_url()))
        for expected in expected_names:
            assert expected in names, f"missing enum: {expected}"
    finally:
        command.downgrade(alembic_cfg, "0001_initial")


def test_downgrade_drops_all_13_enums(alembic_cfg: Config) -> None:
    """Downgrade must remove every enum cleanly so the schema is empty."""
    expected_names = _enum_names()

    command.upgrade(alembic_cfg, "0002_postgres_enums")
    command.downgrade(alembic_cfg, "0001_initial")
    names = asyncio.run(_list_enums(_database_url()))
    for expected in expected_names:
        assert expected not in names, f"enum still present after downgrade: {expected}"
