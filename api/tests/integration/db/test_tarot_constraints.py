"""Integration tests for the tarot-domain Postgres partial unique indexes.

Exercises the indexes documented in ISSUE-016's AC list:

- ``tarot_draws_user_date_uq`` — two draws sharing ``(user_id, date_kst)``
  must be rejected.
- ``tarot_draws_device_date_uq`` — two draws sharing
  ``(device_id, date_kst)`` must be rejected.

Marked ``integration`` and excluded from default CI. Run locally with::

    docker compose up -d db
    cd api && uv run pytest -m integration tests/integration/db/

Authoritative source: ISSUE-016.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date
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
    """Upgrade to 0008 once per module and tear back to 0001 afterwards."""
    cfg = _alembic_config()
    command.upgrade(cfg, "0008_tarot_tables_seed")
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


async def _fetch_card_id() -> str:
    engine = create_async_engine(_database_url(), future=True)
    try:
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT id FROM tarot_cards WHERE card_index = 0")
                )
            ).first()
            assert row is not None, "seed missing card_index=0"
            return str(row[0])
    finally:
        await engine.dispose()


def _mk_user_sync() -> str:
    user_id = str(uuid.uuid4())
    asyncio.run(_insert_async("users", id=user_id, kakao_sub=f"kakao-{uuid.uuid4()}"))
    return user_id


def _mk_device_sync() -> str:
    device_id = str(uuid.uuid4())
    asyncio.run(
        _insert_async(
            "devices",
            id=device_id,
            device_id_client=f"dev-{device_id}",
        )
    )
    return device_id


def test_seed_count_is_22(upgraded_db: None) -> None:
    """The 0008 seed inserts exactly 22 Major Arcana cards."""
    engine = create_async_engine(_database_url(), future=True)

    async def _count() -> int:
        async with engine.begin() as conn:
            row = (await conn.execute(text("SELECT COUNT(*) FROM tarot_cards"))).first()
            return int(row[0])

    try:
        assert asyncio.run(_count()) == 22
    finally:
        asyncio.run(engine.dispose())


def test_user_date_partial_unique(upgraded_db: None) -> None:
    """Two draws sharing (user_id, date_kst) must be rejected."""
    user_id = _mk_user_sync()
    card_id = asyncio.run(_fetch_card_id())
    d = date(2026, 5, 28)

    asyncio.run(
        _insert_async(
            "tarot_draws",
            id=str(uuid.uuid4()),
            user_id=user_id,
            card_id=card_id,
            card_index=0,
            date_kst=d,
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_async(
                "tarot_draws",
                id=str(uuid.uuid4()),
                user_id=user_id,
                card_id=card_id,
                card_index=0,
                date_kst=d,
            )
        )


def test_device_date_partial_unique(upgraded_db: None) -> None:
    """Two draws sharing (device_id, date_kst) must be rejected."""
    device_id = _mk_device_sync()
    card_id = asyncio.run(_fetch_card_id())
    d = date(2026, 5, 29)

    asyncio.run(
        _insert_async(
            "tarot_draws",
            id=str(uuid.uuid4()),
            device_id=device_id,
            card_id=card_id,
            card_index=0,
            date_kst=d,
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_async(
                "tarot_draws",
                id=str(uuid.uuid4()),
                device_id=device_id,
                card_id=card_id,
                card_index=0,
                date_kst=d,
            )
        )


def test_different_users_same_date_allowed(upgraded_db: None) -> None:
    """Two different users may draw on the same KST day."""
    u1 = _mk_user_sync()
    u2 = _mk_user_sync()
    card_id = asyncio.run(_fetch_card_id())
    d = date(2026, 5, 30)

    for uid in (u1, u2):
        asyncio.run(
            _insert_async(
                "tarot_draws",
                id=str(uuid.uuid4()),
                user_id=uid,
                card_id=card_id,
                card_index=0,
                date_kst=d,
            )
        )
