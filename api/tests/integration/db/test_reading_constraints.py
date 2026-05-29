"""Integration tests for the readings-domain Postgres constraints.

Exercises the Postgres-only partial unique index documented in
``docs/data_model.md`` §5.7:

- ``reading_followups_reading_slot_uq`` — two follow-up rows sharing
  ``(reading_id, slot_index)`` must be rejected.

Marked ``integration`` and excluded from default CI. Run locally with::

    docker compose up -d db
    cd api && uv run pytest -m integration tests/integration/db/

Authoritative source: docs/data_model.md §4.10, §5.7.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
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
    """Upgrade to 0007 once per module and tear back down to 0001 afterwards."""
    cfg = _alembic_config()
    command.upgrade(cfg, "0007_readings_tables")
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


def _mk_user_sync() -> str:
    user_id = str(uuid.uuid4())
    asyncio.run(_insert_async("users", id=user_id, kakao_sub=f"kakao-{uuid.uuid4()}"))
    return user_id


def _mk_free_token_sync(user_id: str) -> str:
    ft_id = str(uuid.uuid4())
    asyncio.run(
        _insert_async("free_tokens", id=ft_id, user_id=user_id, kind="signup_grant")
    )
    return ft_id


def _mk_reading_sync(user_id: str, ft_id: str) -> str:
    reading_id = str(uuid.uuid4())
    asyncio.run(
        _insert_async(
            "readings",
            id=reading_id,
            user_id=user_id,
            category="love",
            status="pending",
            character_key="sajununa",
            entitlement_kind="free_token",
            free_token_id=ft_id,
        )
    )
    return reading_id


def test_followups_reading_slot_partial_unique(upgraded_db: None) -> None:
    """Two follow-ups sharing (reading_id, slot_index) must be rejected."""
    user_id = _mk_user_sync()
    ft_id = _mk_free_token_sync(user_id)
    reading_id = _mk_reading_sync(user_id, ft_id)

    asyncio.run(
        _insert_async(
            "reading_followups",
            id=str(uuid.uuid4()),
            reading_id=reading_id,
            slot_index=0,
            question_text="Q0",
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_async(
                "reading_followups",
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                slot_index=0,
                question_text="Q0-dup",
            )
        )


def test_followups_different_slots_allowed(upgraded_db: None) -> None:
    """Three follow-ups with slot_index 0, 1, 2 must coexist for one reading."""
    user_id = _mk_user_sync()
    ft_id = _mk_free_token_sync(user_id)
    reading_id = _mk_reading_sync(user_id, ft_id)

    for idx in (0, 1, 2):
        asyncio.run(
            _insert_async(
                "reading_followups",
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                slot_index=idx,
                question_text=f"Q{idx}",
            )
        )


def test_audio_reading_id_unique(upgraded_db: None) -> None:
    """`reading_audio.reading_id` is UNIQUE (1:1 with reading)."""
    user_id = _mk_user_sync()
    ft_id = _mk_free_token_sync(user_id)
    reading_id = _mk_reading_sync(user_id, ft_id)

    asyncio.run(
        _insert_async(
            "reading_audio",
            id=str(uuid.uuid4()),
            reading_id=reading_id,
            r2_url=f"https://r2/{reading_id}.mp3",
            duration_ms=90000,
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_async(
                "reading_audio",
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                r2_url=f"https://r2/{reading_id}-dup.mp3",
                duration_ms=90000,
            )
        )


def test_transcript_reading_id_unique(upgraded_db: None) -> None:
    """`reading_transcripts.reading_id` is UNIQUE (1:1 with reading)."""
    user_id = _mk_user_sync()
    ft_id = _mk_free_token_sync(user_id)
    reading_id = _mk_reading_sync(user_id, ft_id)

    asyncio.run(
        _insert_async(
            "reading_transcripts",
            id=str(uuid.uuid4()),
            reading_id=reading_id,
            transcript_text="hello",
            model_name="claude-sonnet-4-6",
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _insert_async(
                "reading_transcripts",
                id=str(uuid.uuid4()),
                reading_id=reading_id,
                transcript_text="dup",
                model_name="claude-sonnet-4-6",
            )
        )
    # The dummy used to keep stdlib imports referenced for lint.
    _ = datetime.now(UTC), timedelta(days=1)
