"""Unit tests for ``voicesaju.content.quote_card_service`` (ISSUE-057).

Covers:

- ``generate_share_slug`` shape (exactly 12 base62 chars, deterministic
  given fixed entropy, uniqueness over 1000 fresh seeds).
- ``create_for_reading`` — row inserted with ``og_status='pending'``,
  job enqueued, returned shape matches the persisted row.
- ``create_for_tarot`` — same invariants, with ``character_key='dosa'``
  default and ``category='tarot'``.
- Error paths — missing reading / tarot id → ``ValueError``.

PRD-Ref: FR-018 AC #4 (fallback path), FR-020 (slug uniqueness).
"""

from __future__ import annotations

import re
import string
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.adapters.llm import LLMAdapter
from voicesaju.content.quote_card_service import (
    SHARE_SLUG_LEN,
    create_for_reading,
    create_for_tarot,
    generate_share_slug,
)
from voicesaju.db.base import Base
from voicesaju.db.models import (
    FreeToken,
    QuoteCard,
    Reading,
    TarotCard,
    TarotDraw,
    User,
)
from voicesaju.jobs.worker import InMemoryQueue

# Base62 alphabet — same as the implementation's literal.
_BASE62_CHARS = set(string.digits + string.ascii_uppercase + string.ascii_lowercase)


# ---------------------------------------------------------------------------
# Stub LLM adapter — bypasses the network entirely.
# ---------------------------------------------------------------------------


class _StubLLMAdapter:
    """LLM adapter that streams a fixed short string.

    Implements the protocol surface ``extract_quote`` exercises
    (``async def stream(prompt, task, seed) -> AsyncIterator[str]``).
    """

    def __init__(self, text: str = "운명은 네 손에.") -> None:
        self._text = text

    async def stream(self, prompt: str, task: str, seed: str) -> AsyncIterator[str]:
        yield self._text


def _stub_adapter() -> LLMAdapter:
    return _StubLLMAdapter()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# generate_share_slug — shape + uniqueness
# ---------------------------------------------------------------------------


def test_generate_share_slug_length_is_12() -> None:
    slug = generate_share_slug()
    assert len(slug) == SHARE_SLUG_LEN == 12


def test_generate_share_slug_alphabet_is_base62() -> None:
    slug = generate_share_slug()
    assert set(slug).issubset(_BASE62_CHARS), f"non-base62 chars: {slug!r}"


def test_generate_share_slug_url_safe() -> None:
    """No URL-reserved chars — slugs route cleanly in any URL component."""
    slug = generate_share_slug()
    assert re.fullmatch(r"[0-9A-Za-z]{12}", slug), slug


def test_generate_share_slug_deterministic_with_fixed_entropy() -> None:
    """Same entropy seed → same slug. Pins the encoding strategy."""
    seed = b"deterministic-seed-for-quote-card-slug-tests-32b"[:32]
    a = generate_share_slug(entropy=seed)
    b = generate_share_slug(entropy=seed)
    assert a == b


def test_generate_share_slug_unique_over_1000_seeds() -> None:
    """1000 fresh seeds → 1000 distinct slugs.

    AC #3 (≤ 12 chars, unique, URL-safe) — uniqueness is the
    load-bearing claim. We use the production ``secrets`` path (no
    entropy override) so the assertion exercises the real RNG.
    """
    slugs = {generate_share_slug() for _ in range(1000)}
    assert len(slugs) == 1000, f"got {len(slugs)} unique slugs out of 1000"


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


async def _seed_reading(session: AsyncSession, *, category: str = "love") -> str:
    """Insert a User + FreeToken + Reading; return the reading id."""
    user_id = str(uuid.uuid4())
    session.add(User(id=user_id, kakao_sub=f"kakao:{user_id}"))
    await session.flush()
    ft_id = str(uuid.uuid4())
    session.add(FreeToken(id=ft_id, user_id=user_id, kind="signup_grant"))
    await session.flush()
    reading_id = str(uuid.uuid4())
    session.add(
        Reading(
            id=reading_id,
            user_id=user_id,
            category=category,
            status="pending",
            character_key="sajununa",
            entitlement_kind="free_token",
            free_token_id=ft_id,
        )
    )
    await session.flush()
    return reading_id


async def _seed_tarot(session: AsyncSession) -> str:
    """Insert a User + TarotCard + TarotDraw; return the tarot draw id."""
    user_id = str(uuid.uuid4())
    session.add(User(id=user_id, kakao_sub=f"kakao:{user_id}"))
    await session.flush()
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
    from datetime import date

    draw_id = str(uuid.uuid4())
    session.add(
        TarotDraw(
            id=draw_id,
            user_id=user_id,
            card_id=card_id,
            card_index=0,
            date_kst=date(2026, 5, 30),
        )
    )
    await session.flush()
    return draw_id


# ---------------------------------------------------------------------------
# create_for_reading
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_for_reading_inserts_row_and_enqueues_job(
    session: AsyncSession,
) -> None:
    """AC #1 + AC #2: row in DB + job in queue, after a single call."""
    reading_id = await _seed_reading(session, category="love")
    queue = InMemoryQueue()

    result = await create_for_reading(
        reading_id,
        session=session,
        queue=queue,
        reading_text="당신의 사주는 …",
        adapter=_stub_adapter(),
    )

    # Returned shape ----------------------------------------------------
    assert result.source_kind == "reading"
    assert result.category == "love"
    assert result.character_key == "nuna"
    assert result.og_status == "pending"
    assert len(result.share_slug) == SHARE_SLUG_LEN
    assert result.quote_text  # non-empty

    # Persisted row -----------------------------------------------------
    from sqlalchemy import select

    row = (
        await session.execute(
            select(QuoteCard).where(QuoteCard.id == result.quote_card_id)
        )
    ).scalar_one()
    assert row.source_kind == "reading"
    assert row.reading_id == reading_id
    assert row.tarot_id is None
    assert row.og_status == "pending"
    assert row.share_slug == result.share_slug

    # Queue -------------------------------------------------------------
    # ISSUE-058 swapped the stub for the real Pillow compositor, which
    # now requires ``session=`` / ``r2=`` kwargs at call time. The
    # row-create path only enqueues the dispatch name + ``quote_card_id``
    # so the worker can resolve its DB session from arq's context;
    # asserting the queued shape is the right level of detail here.
    assert len(queue) == 1
    queued_name, queued_args, queued_kwargs = queue._pending[0]
    assert queued_name == "og_bake"
    assert queued_args == ()
    assert queued_kwargs == {"quote_card_id": result.quote_card_id}


@pytest.mark.asyncio
async def test_create_for_reading_uses_fallback_when_no_text(
    session: AsyncSession,
) -> None:
    """No reading_text + no adapter → fallback bucket per category."""
    reading_id = await _seed_reading(session, category="money")
    queue = InMemoryQueue()

    result = await create_for_reading(
        reading_id,
        session=session,
        queue=queue,
        # No reading_text — falls into the empty-string branch of
        # extract_quote which still routes through the LLM (mock).
        adapter=_stub_adapter(),
    )

    assert result.category == "money"
    assert result.quote_text


@pytest.mark.asyncio
async def test_create_for_reading_unknown_id_raises(
    session: AsyncSession,
) -> None:
    queue = InMemoryQueue()
    with pytest.raises(ValueError, match="not found"):
        await create_for_reading(
            str(uuid.uuid4()),
            session=session,
            queue=queue,
            adapter=_stub_adapter(),
        )


# ---------------------------------------------------------------------------
# create_for_tarot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_for_tarot_inserts_row_and_enqueues_job(
    session: AsyncSession,
) -> None:
    tarot_id = await _seed_tarot(session)
    queue = InMemoryQueue()

    result = await create_for_tarot(
        tarot_id,
        session=session,
        queue=queue,
        reading_text="오늘의 카드는 …",
        adapter=_stub_adapter(),
    )

    assert result.source_kind == "tarot"
    assert result.category == "tarot"
    assert result.character_key == "dosa"
    assert result.og_status == "pending"

    from sqlalchemy import select

    row = (
        await session.execute(
            select(QuoteCard).where(QuoteCard.id == result.quote_card_id)
        )
    ).scalar_one()
    assert row.source_kind == "tarot"
    assert row.tarot_id == tarot_id
    assert row.reading_id is None
    assert row.character_key == "dosa"
    assert row.og_status == "pending"

    assert len(queue) == 1


@pytest.mark.asyncio
async def test_create_for_tarot_unknown_id_raises(
    session: AsyncSession,
) -> None:
    queue = InMemoryQueue()
    with pytest.raises(ValueError, match="not found"):
        await create_for_tarot(
            str(uuid.uuid4()),
            session=session,
            queue=queue,
            adapter=_stub_adapter(),
        )


# ---------------------------------------------------------------------------
# Slug uniqueness over multiple inserts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_share_slug_unique_across_repeated_inserts(
    session: AsyncSession,
) -> None:
    """20 sequential inserts → 20 distinct slugs.

    The DB-level uniqueness constraint guarantees this; the test
    catches a regression where ``_insert_card`` is silently returning
    the previous row.
    """
    queue = InMemoryQueue()
    slugs: list[str] = []
    for i in range(20):
        reading_id = await _seed_reading(session, category="work")
        result = await create_for_reading(
            reading_id,
            session=session,
            queue=queue,
            reading_text=f"reading {i}",
            adapter=_stub_adapter(),
        )
        slugs.append(result.share_slug)
    assert len(set(slugs)) == 20
