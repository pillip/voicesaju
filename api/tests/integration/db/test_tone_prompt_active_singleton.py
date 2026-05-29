"""Integration test for the ``tone_prompt_active_singleton_uq`` index.

Postgres-only partial unique index from ISSUE-018:

- At most one row per ``prompt_key`` may have ``is_active = true``.

Marked ``integration`` and excluded from default CI. Run locally with::

    docker compose up -d db
    cd api && uv run pytest -m integration tests/integration/db/

Authoritative source: ISSUE-018.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

pytestmark = pytest.mark.integration


API_DIR = Path(__file__).resolve().parents[3]


def _database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://voicesaju:voicesaju@localhost:5432/voicesaju",
    )


def _alembic_config() -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", _database_url())
    return cfg


@pytest.fixture(scope="module")
def upgraded_db() -> None:
    """Upgrade to 0010 once per module and tear back to 0001 afterwards."""
    cfg = _alembic_config()
    command.upgrade(cfg, "0010_tone_tables")
    try:
        yield
    finally:
        command.downgrade(cfg, "0001_initial")


async def _insert_async(table: str, **kwargs) -> None:
    engine = create_async_engine(_database_url(), future=True)
    try:
        async with engine.begin() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join(f":{k}" for k in kwargs)
            await conn.execute(
                text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"),
                kwargs,
            )
    finally:
        await engine.dispose()


def test_two_active_versions_same_key_rejected(upgraded_db: None) -> None:
    """Two rows with same ``prompt_key`` and ``is_active=true`` → fail."""
    key = f"sajununa.system.{uuid.uuid4()}"
    asyncio.run(
        _insert_async(
            "tone_prompt_versions",
            id=str(uuid.uuid4()),
            prompt_key=key,
            version=1,
            prompt_text="v1",
            is_active=True,
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_async(
                "tone_prompt_versions",
                id=str(uuid.uuid4()),
                prompt_key=key,
                version=2,
                prompt_text="v2",
                is_active=True,
            )
        )


def test_one_active_plus_inactive_allowed(upgraded_db: None) -> None:
    """Same key can have one active + many inactive rows (audit trail)."""
    key = f"tarodosa.system.{uuid.uuid4()}"
    asyncio.run(
        _insert_async(
            "tone_prompt_versions",
            id=str(uuid.uuid4()),
            prompt_key=key,
            version=1,
            prompt_text="v1-inactive",
            is_active=False,
        )
    )
    asyncio.run(
        _insert_async(
            "tone_prompt_versions",
            id=str(uuid.uuid4()),
            prompt_key=key,
            version=2,
            prompt_text="v2-active",
            is_active=True,
        )
    )
    asyncio.run(
        _insert_async(
            "tone_prompt_versions",
            id=str(uuid.uuid4()),
            prompt_key=key,
            version=3,
            prompt_text="v3-inactive",
            is_active=False,
        )
    )


def test_different_keys_each_have_one_active(upgraded_db: None) -> None:
    """Two distinct prompt_key values may both have an active row."""
    k1 = f"k1.{uuid.uuid4()}"
    k2 = f"k2.{uuid.uuid4()}"
    for k in (k1, k2):
        asyncio.run(
            _insert_async(
                "tone_prompt_versions",
                id=str(uuid.uuid4()),
                prompt_key=k,
                version=1,
                prompt_text="x",
                is_active=True,
            )
        )
