"""Integration tests for users + devices Postgres constraints.

Exercises Postgres-only features that the SQLite shape can't represent:

- Multi-column CHECK requiring ≥1 provider on `users`.
- Partial unique indexes on `kakao_sub`, `apple_sub`, `toss_id`.
- `device_id_client` unique constraint on `devices`.

Marked `integration` and excluded from default CI. Run locally with:

    docker compose up -d db
    cd api && uv run pytest -m integration tests/integration/db/

Authoritative source: docs/data_model.md §4.2, §4.4, §5.1, §5.2.
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
    """Upgrade to 0003 once per module and tear back down to 0001 afterwards."""
    cfg = _alembic_config()
    command.upgrade(cfg, "0003_users_devices")
    try:
        yield
    finally:
        command.downgrade(cfg, "0001_initial")


async def _insert_user_async(**kwargs) -> None:
    engine = create_async_engine(_database_url(), future=True)
    try:
        async with engine.begin() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join(f":{k}" for k in kwargs)
            await conn.execute(
                text(f"INSERT INTO users ({cols}) VALUES ({placeholders})"),
                kwargs,
            )
    finally:
        await engine.dispose()


async def _insert_device_async(**kwargs) -> None:
    engine = create_async_engine(_database_url(), future=True)
    try:
        async with engine.begin() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join(f":{k}" for k in kwargs)
            await conn.execute(
                text(f"INSERT INTO devices ({cols}) VALUES ({placeholders})"),
                kwargs,
            )
    finally:
        await engine.dispose()


def test_user_check_constraint_rejects_no_provider(upgraded_db: None) -> None:
    """All three provider columns NULL must violate the CHECK."""
    with pytest.raises(IntegrityError):
        asyncio.run(_insert_user_async(id=str(uuid.uuid4())))


def test_user_with_kakao_sub_succeeds(upgraded_db: None) -> None:
    asyncio.run(
        _insert_user_async(
            id=str(uuid.uuid4()),
            kakao_sub=f"kakao-{uuid.uuid4()}",
        )
    )


def test_user_kakao_sub_partial_unique(upgraded_db: None) -> None:
    """Two users with the same non-null kakao_sub must be rejected."""
    sub = f"kakao-dup-{uuid.uuid4()}"
    asyncio.run(_insert_user_async(id=str(uuid.uuid4()), kakao_sub=sub))
    with pytest.raises(IntegrityError):
        asyncio.run(_insert_user_async(id=str(uuid.uuid4()), kakao_sub=sub))


def test_multiple_users_with_null_kakao_sub_allowed(upgraded_db: None) -> None:
    """Partial unique index must allow many NULL kakao_sub rows."""
    asyncio.run(
        _insert_user_async(id=str(uuid.uuid4()), apple_sub=f"apple-{uuid.uuid4()}")
    )
    asyncio.run(
        _insert_user_async(id=str(uuid.uuid4()), apple_sub=f"apple-{uuid.uuid4()}")
    )


def test_device_client_id_unique(upgraded_db: None) -> None:
    client_id = f"client-{uuid.uuid4()}"
    asyncio.run(_insert_device_async(id=str(uuid.uuid4()), device_id_client=client_id))
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_device_async(id=str(uuid.uuid4()), device_id_client=client_id)
        )
