"""Unit tests for ``voicesaju.entitlement.service.check_entitlement`` (ISSUE-040).

Covers each AC permutation from ``issues.md``:

- User with unconsumed ``signup_grant`` token → has_token=True.
- Subscriber with ``monthly_saju_remaining=1`` → has_subscription_credit=True.
- Subscriber with ``monthly_saju_remaining=0`` → has_subscription_credit=False.
- Non-member (device only) with no trial token → has_anything=False,
  requires_payment=True.

The service follows architecture §6.4 + data_model AP-16/17/20/21:

- AP-16: list active FreeTokens for a User.
- AP-17: read FreeToken for a Device (non-member trial).
- AP-21: read active Subscription for a User.

Tests use an in-memory SQLite engine — same convention as the existing
``tests/integration/profile/test_create_profile.py`` flow — so the real
ORM models participate without external DB. Each test seeds the
relevant rows then asserts on the returned ``EntitlementResult``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.models import (  # noqa: F401 - register metadata
    Device,
    FreeToken,
    Payment,
    Profile,
    SajuChart,
    Subscription,
    User,
)
from voicesaju.entitlement.service import (
    EntitlementResult,
    check_entitlement,
)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Per-test SQLite engine with the full ORM schema reflected."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s


async def _seed_user(session: AsyncSession, kakao_sub: str = "ksub") -> User:
    """Insert a ``users`` row and return it."""
    u = User(kakao_sub=kakao_sub)
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


async def _seed_device(
    session: AsyncSession, device_id_client: str = "client-dev-1"
) -> Device:
    """Insert a ``devices`` row and return it.

    Explicit string ``id`` mirrors ``tests/unit/db/test_tarot_draws.py``:
    the Device model defaults its PK to ``uuid7`` (returns ``uuid.UUID``)
    which aiosqlite cannot bind for the ``String(36)`` column. Production
    (asyncpg) handles either form.
    """
    import uuid as _uuid

    d = Device(id=str(_uuid.uuid4()), device_id_client=device_id_client)
    session.add(d)
    await session.commit()
    await session.refresh(d)
    return d


# ---------------------------------------------------------------------------
# AC 1: User with unconsumed signup_grant token → has_token=True.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_with_unconsumed_signup_grant_returns_has_token(
    session: AsyncSession,
) -> None:
    """AC 1 (ISSUE-040): unconsumed signup_grant → has_token=True, has_anything=True."""
    user = await _seed_user(session)
    token = FreeToken(user_id=str(user.id), kind="signup_grant")
    session.add(token)
    await session.commit()
    await session.refresh(token)

    result = await check_entitlement(
        session=session, user_id=str(user.id), kind="reading"
    )

    assert isinstance(result, EntitlementResult)
    assert result.has_token is True
    assert result.token_id == str(token.id)
    assert result.has_anything is True
    assert result.requires_payment is False


@pytest.mark.asyncio
async def test_user_with_consumed_signup_grant_does_not_have_token(
    session: AsyncSession,
) -> None:
    """A consumed signup_grant must not count as an active entitlement."""
    user = await _seed_user(session)
    token = FreeToken(
        user_id=str(user.id),
        kind="signup_grant",
        consumed_at=datetime.now(UTC),
    )
    session.add(token)
    await session.commit()

    result = await check_entitlement(
        session=session, user_id=str(user.id), kind="reading"
    )

    assert result.has_token is False
    assert result.token_id is None
    assert result.has_anything is False
    assert result.requires_payment is True


# ---------------------------------------------------------------------------
# AC 2: Subscriber with monthly_saju_remaining=1 → has_subscription_credit=True.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscriber_with_remaining_credit_returns_credit_true(
    session: AsyncSession,
) -> None:
    """AC 2 (ISSUE-040): active sub with quota=1 → has_subscription_credit=True."""
    user = await _seed_user(session)
    now = datetime.now(UTC)
    sub = Subscription(
        user_id=str(user.id),
        status="active",
        monthly_saju_remaining=1,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)

    result = await check_entitlement(
        session=session, user_id=str(user.id), kind="reading"
    )

    assert result.has_subscription_credit is True
    assert result.subscription_id == str(sub.id)
    assert result.has_anything is True
    assert result.requires_payment is False


# ---------------------------------------------------------------------------
# AC 3: Subscriber with monthly_saju_remaining=0 → has_subscription_credit=False.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscriber_with_zero_remaining_credit_returns_credit_false(
    session: AsyncSession,
) -> None:
    """AC 3 (ISSUE-040): active sub with quota=0 → has_subscription_credit=False."""
    user = await _seed_user(session)
    now = datetime.now(UTC)
    sub = Subscription(
        user_id=str(user.id),
        status="active",
        monthly_saju_remaining=0,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    session.add(sub)
    await session.commit()

    result = await check_entitlement(
        session=session, user_id=str(user.id), kind="reading"
    )

    # Subscription exists but quota is exhausted.
    assert result.has_subscription_credit is False
    assert result.has_anything is False
    assert result.requires_payment is True


# ---------------------------------------------------------------------------
# AC 4: Non-member with no trial token → has_anything=False, requires_payment=True.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_member_device_without_trial_token_requires_payment(
    session: AsyncSession,
) -> None:
    """AC 4 (ISSUE-040): device-only caller, no token → requires_payment=True."""
    device = await _seed_device(session)

    result = await check_entitlement(
        session=session, device_id=str(device.id), kind="reading"
    )

    assert result.has_token is False
    assert result.has_subscription_credit is False
    assert result.has_anything is False
    assert result.requires_payment is True


@pytest.mark.asyncio
async def test_non_member_device_with_trial_token_returns_has_token(
    session: AsyncSession,
) -> None:
    """Companion to AC 4: device with a trial token → has_token=True."""
    device = await _seed_device(session)
    token = FreeToken(device_id=str(device.id), kind="nonmember_trial")
    session.add(token)
    await session.commit()
    await session.refresh(token)

    result = await check_entitlement(
        session=session, device_id=str(device.id), kind="reading"
    )

    assert result.has_token is True
    assert result.token_id == str(token.id)
    assert result.has_anything is True
    assert result.requires_payment is False


# ---------------------------------------------------------------------------
# Cross-cutting: argument validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_entitlement_requires_user_or_device(
    session: AsyncSession,
) -> None:
    """Passing neither ``user_id`` nor ``device_id`` is a programmer error."""
    with pytest.raises(ValueError):
        await check_entitlement(session=session, kind="reading")


@pytest.mark.asyncio
async def test_token_preferred_over_subscription_credit(
    session: AsyncSession,
) -> None:
    """When both exist, the service returns BOTH but token_id wins for consumption.

    Architecture §6.4: free tokens are consumed before the subscription quota
    (cheaper to grant another free token than to refund the subscription).
    """
    user = await _seed_user(session)
    now = datetime.now(UTC)
    token = FreeToken(user_id=str(user.id), kind="signup_grant")
    sub = Subscription(
        user_id=str(user.id),
        status="active",
        monthly_saju_remaining=1,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    session.add_all([token, sub])
    await session.commit()
    await session.refresh(token)
    await session.refresh(sub)

    result = await check_entitlement(
        session=session, user_id=str(user.id), kind="reading"
    )

    assert result.has_token is True
    assert result.has_subscription_credit is True
    # Preferred consumption order: token first.
    assert result.preferred_kind == "free_token"
    assert result.token_id == str(token.id)
    assert result.subscription_id == str(sub.id)


@pytest.mark.asyncio
async def test_cancel_at_period_end_subscription_still_grants_credit(
    session: AsyncSession,
) -> None:
    """``status='cancel_at_period_end'`` is still an active entitlement.

    architecture §6.4 + data_model AP-21: the partial unique index includes
    ``cancel_at_period_end`` and ``past_due`` because the user has paid for
    the current period.
    """
    user = await _seed_user(session)
    now = datetime.now(UTC)
    sub = Subscription(
        user_id=str(user.id),
        status="cancel_at_period_end",
        monthly_saju_remaining=1,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    session.add(sub)
    await session.commit()

    result = await check_entitlement(
        session=session, user_id=str(user.id), kind="reading"
    )

    assert result.has_subscription_credit is True
    assert result.has_anything is True
