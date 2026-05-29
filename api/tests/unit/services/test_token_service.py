"""Unit tests for `TokenService`.

The service is tested against a real `AsyncSession` backed by SQLite
in-memory so we exercise the model wiring + the dialect-aware fallback
path (`_grant_idempotent` non-Postgres branch). The Postgres-only
`ON CONFLICT` path is covered separately in the integration test.

Authoritative source: docs/data_model.md §4.7, §5.5.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from voicesaju.db.base import Base
from voicesaju.db.models import (  # noqa: F401 - register metadata
    Device,
    FreeToken,
    User,
)
from voicesaju.services.token_service import (
    TokenAlreadyConsumedError,
    TokenService,
)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Provide an isolated in-memory SQLite session per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _make_user(session: AsyncSession) -> User:
    user = User(id=str(uuid.uuid4()), kakao_sub=f"k-{uuid.uuid4()}")
    session.add(user)
    await session.flush()
    return user


async def _make_device(session: AsyncSession) -> Device:
    device = Device(id=str(uuid.uuid4()), device_id_client=f"c-{uuid.uuid4()}")
    session.add(device)
    await session.flush()
    return device


@pytest.mark.asyncio
async def test_grant_signup_bonus_inserts_row(session: AsyncSession) -> None:
    user = await _make_user(session)
    svc = TokenService(session)

    token = await svc.grant_signup_bonus(uuid.UUID(user.id))

    assert token is not None
    assert token.kind == "signup_grant"
    assert token.user_id == user.id
    assert token.device_id is None
    assert token.consumed_at is None


@pytest.mark.asyncio
async def test_grant_signup_bonus_is_idempotent(session: AsyncSession) -> None:
    """FR-017 AC: second grant for same user must return None."""
    user = await _make_user(session)
    svc = TokenService(session)

    first = await svc.grant_signup_bonus(uuid.UUID(user.id))
    second = await svc.grant_signup_bonus(uuid.UUID(user.id))

    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_grant_nonmember_trial_inserts_row(session: AsyncSession) -> None:
    device = await _make_device(session)
    svc = TokenService(session)

    token = await svc.grant_nonmember_trial(uuid.UUID(device.id))

    assert token is not None
    assert token.kind == "nonmember_trial"
    assert token.device_id == device.id
    assert token.user_id is None


@pytest.mark.asyncio
async def test_grant_nonmember_trial_is_idempotent(session: AsyncSession) -> None:
    """FR-003 AC: second grant for same device must return None."""
    device = await _make_device(session)
    svc = TokenService(session)

    first = await svc.grant_nonmember_trial(uuid.UUID(device.id))
    second = await svc.grant_nonmember_trial(uuid.UUID(device.id))

    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_grant_compensation_always_inserts(session: AsyncSession) -> None:
    """FR-023 AC: compensation grants are never deduped."""
    user = await _make_user(session)
    svc = TokenService(session)

    t1 = await svc.grant_compensation(uuid.UUID(user.id), reason="audio-timeout")
    t2 = await svc.grant_compensation(uuid.UUID(user.id), reason="audio-timeout")

    assert t1.id != t2.id
    assert t1.kind == "failure_compensation"
    assert t2.kind == "failure_compensation"


@pytest.mark.asyncio
async def test_consume_token_marks_row(session: AsyncSession) -> None:
    user = await _make_user(session)
    svc = TokenService(session)
    token = await svc.grant_signup_bonus(uuid.UUID(user.id))
    assert token is not None
    reading_id = uuid.uuid4()

    consumed = await svc.consume_token(uuid.UUID(token.id), reading_id)

    assert consumed.consumed_at is not None
    assert consumed.consumed_by_reading_id == str(reading_id)


@pytest.mark.asyncio
async def test_consume_token_twice_raises(session: AsyncSession) -> None:
    user = await _make_user(session)
    svc = TokenService(session)
    token = await svc.grant_signup_bonus(uuid.UUID(user.id))
    assert token is not None
    await svc.consume_token(uuid.UUID(token.id), uuid.uuid4())

    with pytest.raises(TokenAlreadyConsumedError):
        await svc.consume_token(uuid.UUID(token.id), uuid.uuid4())


@pytest.mark.asyncio
async def test_consume_unknown_token_raises_lookup(session: AsyncSession) -> None:
    svc = TokenService(session)
    with pytest.raises(LookupError):
        await svc.consume_token(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_owner_xor_check_rejects_both_null(session: AsyncSession) -> None:
    """CHECK ((user_id IS NULL) <> (device_id IS NULL)) — both NULL fails."""
    from sqlalchemy.exc import IntegrityError

    bad = FreeToken(kind="signup_grant")
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()
