"""Unit tests for `DeviceService.upsert_device` (ISSUE-024).

Exercises idempotency contract against a real in-memory SQLite engine
so model wiring + the dialect-portable SELECT-then-INSERT path are
covered. The Postgres-only partial unique index path lives in the
integration suite.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.models import Device  # noqa: F401 - register metadata
from voicesaju.users.services.device_service import DeviceService


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_first_call_inserts_new_row(session: AsyncSession) -> None:
    svc = DeviceService(session)
    client_id = str(uuid.uuid4())

    device = await svc.upsert_device(client_id)

    assert device.id is not None
    assert device.device_id_client == client_id
    assert device.first_seen_at is not None
    assert device.last_seen_at is not None
    # last_seen_at == first_seen_at on insert (modulo µs).
    assert device.last_seen_at >= device.first_seen_at

    # Row is persisted.
    count = (await session.execute(text("SELECT COUNT(*) FROM devices"))).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_second_call_with_same_client_id_updates_last_seen(
    session: AsyncSession,
) -> None:
    """AC: same `device_id_client` called again → existing row's
    `last_seen_at` updated (no duplicate row).
    """
    svc = DeviceService(session)
    client_id = str(uuid.uuid4())

    first = await svc.upsert_device(client_id)
    first_id = first.id
    first_seen = first.first_seen_at

    second = await svc.upsert_device(client_id)

    # Same row.
    assert second.id == first_id
    assert second.first_seen_at == first_seen
    # last_seen_at is updated on the second call.
    assert second.last_seen_at >= first_seen

    # No duplicate.
    count = (await session.execute(text("SELECT COUNT(*) FROM devices"))).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_different_client_ids_create_separate_rows(
    session: AsyncSession,
) -> None:
    svc = DeviceService(session)
    a = await svc.upsert_device(str(uuid.uuid4()))
    b = await svc.upsert_device(str(uuid.uuid4()))

    assert a.id != b.id
    assert a.device_id_client != b.device_id_client

    count = (await session.execute(text("SELECT COUNT(*) FROM devices"))).scalar_one()
    assert count == 2


@pytest.mark.asyncio
async def test_user_agent_hash_persisted_when_provided(
    session: AsyncSession,
) -> None:
    svc = DeviceService(session)
    client_id = str(uuid.uuid4())

    device = await svc.upsert_device(client_id, user_agent_hash="sha256-abc123")
    assert device.user_agent_hash == "sha256-abc123"


@pytest.mark.asyncio
async def test_user_agent_hash_updated_on_subsequent_call(
    session: AsyncSession,
) -> None:
    svc = DeviceService(session)
    client_id = str(uuid.uuid4())

    await svc.upsert_device(client_id, user_agent_hash="sha256-first")
    updated = await svc.upsert_device(client_id, user_agent_hash="sha256-second")

    assert updated.user_agent_hash == "sha256-second"

    count = (await session.execute(text("SELECT COUNT(*) FROM devices"))).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_returned_device_id_is_server_side_uuid_not_client_uuid(
    session: AsyncSession,
) -> None:
    """The server-side ``id`` MUST differ from the client-supplied
    ``device_id_client``. The cookie carries the server-side id so a
    leaked client uuid never identifies the row directly.
    """
    svc = DeviceService(session)
    client_id = str(uuid.uuid4())

    device = await svc.upsert_device(client_id)
    assert str(device.id) != client_id
