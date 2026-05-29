"""Unit tests for `UserService.find_or_create_by_provider` (ISSUE-026).

Exercises the three-way resolution order against in-memory SQLite:

1. Existing user located by provider sub.
2. Existing user located by ``email_hash`` (cross-provider dup detection).
3. Fresh insert when neither lookup hits.

Architecture-Ref: §11 (email_hash dup-detection).
PRD-Ref: FR-016.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.models import User  # noqa: F401 - register metadata
from voicesaju.users.services.user_service import UserService, hash_email


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
async def test_first_call_creates_new_user(session: AsyncSession) -> None:
    """No matching sub, no matching email → fresh insert."""
    svc = UserService(session)
    resolution = await svc.find_or_create_by_provider(
        provider="kakao",
        subject_id="kakao-abc123",
        email="new@voicesaju.dev",
    )
    assert resolution.outcome == "created"
    assert resolution.user.kakao_sub == "kakao-abc123"
    assert resolution.user.email_hash == hash_email("new@voicesaju.dev")
    assert resolution.user.apple_sub is None


@pytest.mark.asyncio
async def test_second_call_with_same_sub_finds_existing(
    session: AsyncSession,
) -> None:
    """Same provider sub → ``found_by_sub`` (no new row)."""
    svc = UserService(session)
    first = await svc.find_or_create_by_provider(
        provider="kakao",
        subject_id="kakao-abc123",
        email="stable@voicesaju.dev",
    )
    second = await svc.find_or_create_by_provider(
        provider="kakao",
        subject_id="kakao-abc123",
        email="stable@voicesaju.dev",
    )
    assert second.outcome == "found_by_sub"
    assert str(second.user.id) == str(first.user.id)


@pytest.mark.asyncio
async def test_email_hash_dup_links_across_providers(
    session: AsyncSession,
) -> None:
    """AC: two providers, same email_hash → one User row (architecture §11)."""
    svc = UserService(session)
    first = await svc.find_or_create_by_provider(
        provider="kakao",
        subject_id="kakao-xyz",
        email="shared@voicesaju.dev",
    )
    second = await svc.find_or_create_by_provider(
        provider="apple",
        subject_id="apple-xyz",
        email="shared@voicesaju.dev",
    )
    assert first.outcome == "created"
    assert second.outcome == "linked_by_email"
    assert str(second.user.id) == str(first.user.id)
    # Both provider subs now attached to the single row.
    assert second.user.kakao_sub == "kakao-xyz"
    assert second.user.apple_sub == "apple-xyz"

    # And the DB really only carries one user row.
    rows = (await session.execute(select(User))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_email_case_is_normalised(session: AsyncSession) -> None:
    """``Foo@Gmail`` and ``foo@gmail`` MUST hash to the same value."""
    svc = UserService(session)
    first = await svc.find_or_create_by_provider(
        provider="kakao",
        subject_id="k-1",
        email="Foo@Gmail.com",
    )
    second = await svc.find_or_create_by_provider(
        provider="apple",
        subject_id="a-1",
        email="foo@gmail.com",
    )
    assert second.outcome == "linked_by_email"
    assert str(second.user.id) == str(first.user.id)


@pytest.mark.asyncio
async def test_none_email_creates_user_without_link(
    session: AsyncSession,
) -> None:
    """Apple-after-first-signin: email=None → fresh user, no link attempt."""
    svc = UserService(session)
    first = await svc.find_or_create_by_provider(
        provider="apple",
        subject_id="apple-no-email-1",
        email=None,
    )
    second = await svc.find_or_create_by_provider(
        provider="apple",
        subject_id="apple-no-email-2",
        email=None,
    )
    assert first.outcome == "created"
    assert second.outcome == "created"
    assert str(first.user.id) != str(second.user.id)
    assert first.user.email_hash is None
    assert second.user.email_hash is None


@pytest.mark.asyncio
async def test_existing_user_backfills_email_hash(
    session: AsyncSession,
) -> None:
    """If first signin had email=None, the next callback with an email
    persists ``email_hash`` so future dup-detection works."""
    svc = UserService(session)
    first = await svc.find_or_create_by_provider(
        provider="apple",
        subject_id="apple-late-email",
        email=None,
    )
    assert first.user.email_hash is None

    second = await svc.find_or_create_by_provider(
        provider="apple",
        subject_id="apple-late-email",
        email="late@voicesaju.dev",
    )
    assert second.outcome == "found_by_sub"
    assert second.user.email_hash == hash_email("late@voicesaju.dev")
