"""Integration tests for ``voicesaju.users.services.migration_service``.

Covers ISSUE-062 AC #1 + #2:

* AC #1 — happy path: a device with 1 tarot draw + 1 free token (and an
  attached quote card via the tarot draw) gets reassigned. The tarot
  draw and free token end up owned by the new user and
  ``devices.linked_user_id`` is set. The quote card row (which
  references ``tarot_id`` not ``device_id``) is reachable via the
  reassigned tarot draw — its ownership is transitive.

* AC #2 — atomicity: when an unrelated write fails mid-transaction
  (simulated by raising inside ``session.begin()``), the whole TX rolls
  back: the device stays unlinked, the tarot draw stays owned by the
  device, and the free token stays device-owned.

Plus edge cases worth pinning:

* Idempotent re-run: calling the function twice with the same
  (device_id, user_id) is a no-op the second time
  (``device_linked=False``, row counts = 0).
* Missing device → ``ValueError``.
* Device with no rows owned → returns zero counts but still links the
  device.

The fixture pattern mirrors
``api/tests/unit/content/test_quote_card_service.py::session`` — a
per-test in-memory SQLite with ``Base.metadata.create_all``. That gives
us the application-level CHECK constraints (XOR enforcement) without
needing the alembic migrations.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.db.base import Base
from voicesaju.db.models import (
    Device,
    FreeToken,
    QuoteCard,
    TarotCard,
    TarotDraw,
    User,
)
from voicesaju.users.services.migration_service import (
    MigrationResult,
    migrate_device_to_user,
)

# ---------------------------------------------------------------------------
# DB fixture — single async session per test
# ---------------------------------------------------------------------------


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Yield a clean in-memory SQLite session per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )
        async with factory() as sess:
            yield sess
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_device(session: AsyncSession) -> str:
    """Insert a non-member device row; return its server-side ``id``."""
    device_id = str(uuid.uuid4())
    session.add(
        Device(
            id=device_id,
            device_id_client=str(uuid.uuid4()),
        )
    )
    await session.flush()
    return device_id


async def _seed_user(session: AsyncSession) -> str:
    """Insert a fresh User; return ``id``.

    Matches the OAuth callback path — a freshly-created user with a
    provider sub but no profile / saju chart yet.
    """
    user_id = str(uuid.uuid4())
    session.add(User(id=user_id, kakao_sub=f"kakao:{user_id}"))
    await session.flush()
    return user_id


async def _seed_tarot_draw_for_device(
    session: AsyncSession,
    device_id: str,
) -> tuple[str, str]:
    """Seed a ``tarot_cards`` row + a device-owned ``tarot_draws`` row.

    Returns ``(card_id, draw_id)`` so a follow-up call can hang a
    ``quote_cards`` row off the draw.
    """
    card_id = str(uuid.uuid4())
    session.add(
        TarotCard(
            id=card_id,
            card_index=0,
            name_kr="바보",
            name_en="The Fool",
            meaning_kr="새로운 시작.",
            art_key="00_the_fool",
        )
    )
    await session.flush()

    draw_id = str(uuid.uuid4())
    session.add(
        TarotDraw(
            id=draw_id,
            device_id=device_id,  # device-owned (non-member trial)
            user_id=None,
            card_id=card_id,
            card_index=0,
            date_kst=date(2026, 5, 30),
        )
    )
    await session.flush()
    return card_id, draw_id


async def _seed_free_token_for_device(
    session: AsyncSession,
    device_id: str,
) -> str:
    """Seed a ``nonmember_trial`` token owned by the device."""
    ft_id = str(uuid.uuid4())
    session.add(
        FreeToken(
            id=ft_id,
            device_id=device_id,
            user_id=None,
            kind="nonmember_trial",
        )
    )
    await session.flush()
    return ft_id


async def _seed_quote_card_for_tarot(
    session: AsyncSession,
    tarot_id: str,
) -> str:
    """Seed a ``quote_cards`` row linked to *tarot_id* (no device ref).

    The quote card schema doesn't have a ``device_id`` column — it tracks
    ownership transitively through ``tarot_id`` / ``reading_id``. That
    is what makes AC #1 ("quote card transferred") work without needing
    an explicit UPDATE on quote_cards.
    """
    qc_id = str(uuid.uuid4())
    session.add(
        QuoteCard(
            id=qc_id,
            source_kind="tarot",
            tarot_id=tarot_id,
            reading_id=None,
            category="tarot",
            quote_text="운명은 네 손 안에 있다.",
            character_key="dosa",
            share_slug=f"slug-{qc_id[:8]}",
            og_status="pending",
        )
    )
    await session.flush()
    return qc_id


# ---------------------------------------------------------------------------
# AC #1 — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_migrates_tarot_token_and_links_device(
    session: AsyncSession,
) -> None:
    """AC #1: 1 tarot draw + 1 quote card + 1 free token + device link."""
    device_id = await _seed_device(session)
    user_id = await _seed_user(session)
    _card_id, draw_id = await _seed_tarot_draw_for_device(session, device_id)
    qc_id = await _seed_quote_card_for_tarot(session, draw_id)
    ft_id = await _seed_free_token_for_device(session, device_id)

    result = await migrate_device_to_user(
        device_id,
        user_id,
        session=session,
    )

    # Return shape -------------------------------------------------------
    assert isinstance(result, MigrationResult)
    assert result.tarot_draws_migrated == 1
    assert result.free_tokens_migrated == 1
    assert result.device_linked is True

    # Tarot draw: now user-owned, device cleared ------------------------
    draw = (
        await session.execute(select(TarotDraw).where(TarotDraw.id == draw_id))
    ).scalar_one()
    assert draw.user_id == user_id
    assert draw.device_id is None

    # Quote card: still attached to the same tarot_id (no schema change
    # needed — ownership flows through tarot_draws.user_id) -------------
    qc = (
        await session.execute(select(QuoteCard).where(QuoteCard.id == qc_id))
    ).scalar_one()
    assert qc.tarot_id == draw_id

    # Free token: user-owned ---------------------------------------------
    ft = (
        await session.execute(select(FreeToken).where(FreeToken.id == ft_id))
    ).scalar_one()
    assert ft.user_id == user_id
    assert ft.device_id is None

    # Device row: linked to user ----------------------------------------
    device = (
        await session.execute(select(Device).where(Device.id == device_id))
    ).scalar_one()
    assert device.linked_user_id == user_id


@pytest.mark.asyncio
async def test_happy_path_device_with_only_token_no_tarot(
    session: AsyncSession,
) -> None:
    """A device that never drew tarot but holds the nonmember-trial token.

    This is the common case for the M1/M2 free-saju trial flow: the
    device has the trial token but no tarot draw. The migration should
    still link the device + reassign the token.
    """
    device_id = await _seed_device(session)
    user_id = await _seed_user(session)
    ft_id = await _seed_free_token_for_device(session, device_id)

    result = await migrate_device_to_user(
        device_id,
        user_id,
        session=session,
    )

    assert result.tarot_draws_migrated == 0
    assert result.free_tokens_migrated == 1
    assert result.device_linked is True

    ft = (
        await session.execute(select(FreeToken).where(FreeToken.id == ft_id))
    ).scalar_one()
    assert ft.user_id == user_id
    assert ft.device_id is None


@pytest.mark.asyncio
async def test_happy_path_device_with_nothing_still_links(
    session: AsyncSession,
) -> None:
    """Device exists but holds nothing → counts are 0, link still flips.

    Models a user who installed the app, sat through onboarding, but
    never claimed the nonmember-trial token before signing in. The
    device→user link is still useful for FR-013 / future analytics.
    """
    device_id = await _seed_device(session)
    user_id = await _seed_user(session)

    result = await migrate_device_to_user(
        device_id,
        user_id,
        session=session,
    )

    assert result.tarot_draws_migrated == 0
    assert result.free_tokens_migrated == 0
    assert result.device_linked is True

    device = (
        await session.execute(select(Device).where(Device.id == device_id))
    ).scalar_one()
    assert device.linked_user_id == user_id


# ---------------------------------------------------------------------------
# AC #2 — atomicity (rollback on partway failure)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_atomic_rollback_on_failure_after_migration(
    session: AsyncSession,
) -> None:
    """AC #2: forcing a TX failure rolls back ALL migration writes.

    The migration service does not commit — the caller owns the
    transaction. We simulate the caller's "wrap-in-begin + then do
    something that fails" pattern: open a TX, run the migration, then
    raise. After the TX exits via rollback, every reassigned row should
    be back in its pre-migration state.

    This is the load-bearing test for the "no partial state" invariant
    that AP-07 promises the rest of the signup pipeline.
    """
    device_id = await _seed_device(session)
    user_id = await _seed_user(session)
    _card_id, draw_id = await _seed_tarot_draw_for_device(session, device_id)
    ft_id = await _seed_free_token_for_device(session, device_id)
    # Commit the seed state so the rollback below has something to
    # restore to.
    await session.commit()

    class _ForcedFailure(RuntimeError):
        """Sentinel raised inside the TX to trigger rollback."""

    # Caller pattern: nested begin so the outer rollback unwinds every
    # write the migration made.
    with pytest.raises(_ForcedFailure):
        async with session.begin():
            await migrate_device_to_user(
                device_id,
                user_id,
                session=session,
            )
            # Simulate a downstream caller failure (e.g. the signup
            # grant insert raising IntegrityError) — the outer TX
            # rollback must undo the migration writes.
            raise _ForcedFailure("simulated downstream insert failed")

    # Re-fetch every touched row and assert nothing migrated -----------
    draw = (
        await session.execute(select(TarotDraw).where(TarotDraw.id == draw_id))
    ).scalar_one()
    assert draw.device_id == device_id, "tarot_draws.device_id should be restored"
    assert draw.user_id is None, "tarot_draws.user_id should be restored to NULL"

    ft = (
        await session.execute(select(FreeToken).where(FreeToken.id == ft_id))
    ).scalar_one()
    assert ft.device_id == device_id, "free_tokens.device_id should be restored"
    assert ft.user_id is None, "free_tokens.user_id should be restored to NULL"

    device = (
        await session.execute(select(Device).where(Device.id == device_id))
    ).scalar_one()
    assert device.linked_user_id is None, "devices.linked_user_id should be restored"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_device_id_raises(session: AsyncSession) -> None:
    """Missing device → ``ValueError`` so the caller can decide how to surface."""
    user_id = await _seed_user(session)
    with pytest.raises(ValueError, match="not found"):
        await migrate_device_to_user(
            str(uuid.uuid4()),
            user_id,
            session=session,
        )


@pytest.mark.asyncio
async def test_idempotent_re_run_is_no_op(session: AsyncSession) -> None:
    """Second call with the same (device, user) reports zero migrations.

    Models the OAuth-retry path — the route is re-invoked with the same
    inputs (e.g. user reopens the link in a new tab). The migration
    should:

    1. Find no rows still owned by the device (we already migrated
       them) → counts = 0.
    2. See the device already linked to the same user → return
       ``device_linked=False``.

    The whole call is safe to repeat without duplicate state.
    """
    device_id = await _seed_device(session)
    user_id = await _seed_user(session)
    _card_id, draw_id = await _seed_tarot_draw_for_device(session, device_id)
    await _seed_free_token_for_device(session, device_id)

    first = await migrate_device_to_user(device_id, user_id, session=session)
    assert first.tarot_draws_migrated == 1
    assert first.free_tokens_migrated == 1
    assert first.device_linked is True

    second = await migrate_device_to_user(device_id, user_id, session=session)
    assert second.tarot_draws_migrated == 0
    assert second.free_tokens_migrated == 0
    assert second.device_linked is False, "second run should NOT re-flip linked_user_id"

    # The tarot draw is still attached to the user, not the device.
    draw = (
        await session.execute(select(TarotDraw).where(TarotDraw.id == draw_id))
    ).scalar_one()
    assert draw.user_id == user_id
    assert draw.device_id is None
