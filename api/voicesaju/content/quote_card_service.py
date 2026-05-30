"""Quote card row creation service (ISSUE-057, FR-018 / FR-020).

This module owns the *write* side of the M4 quote-card pipeline. The
session-end caller (reading-finalize or tarot-draw flow) invokes one
of the two factory functions and we:

1. Extract the spicy quote line via
   :func:`voicesaju.content.quote_card.extract_quote` (ISSUE-056).
2. Mint a unique base62 ``share_slug`` (≤ 12 chars, FR-020 short URL).
3. Insert a ``quote_cards`` row with ``og_status='pending'``.
4. Enqueue the ``og_bake`` arq job so the image bake worker
   (ISSUE-058) can run out-of-band.

Why a dedicated module (vs inlining into the reading-finalize / tarot
flow):

- The two upstream flows (saju vs tarot) share 80% of this code; the
  only divergence is the source-row lookup and the persona default.
- Decouples the row-write timing from the OG bake — the bake worker
  polls ``og_status='pending'`` so even if the enqueue races (e.g. the
  Redis-backed arq queue isn't ready), the row is still discoverable.

PRD-Ref: FR-018 AC #2 ("generated within 3 seconds"), FR-020 (OG meta).
Architecture-Ref: §7.1 (Haiku for short-form), §8.4 (worker boundary).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.adapters.llm import LLMAdapter
from voicesaju.content.quote_card import extract_quote
from voicesaju.db.models.quote_cards import QuoteCard
from voicesaju.db.models.readings import Reading
from voicesaju.db.models.tarot_draws import TarotDraw
from voicesaju.jobs.worker import InMemoryQueue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# FR-020 spec: ``share_slug`` is "≤ 12 chars" of base62. We pin to
# exactly 12 so the URL space is ~ 62**12 ≈ 3.2e21 — way more than the
# birthday-bound (~ 2**32) we'd risk a collision at production scale.
SHARE_SLUG_LEN: Final[int] = 12

# Base62 alphabet — ``string.digits + string.ascii_uppercase +
# string.ascii_lowercase``. Inlined as a literal so the value is
# import-time auditable and stable across CPython versions (the
# ``string`` module never changes the ordering, but we want to be
# explicit so the slug encoding is deterministic).
_BASE62_ALPHABET: Final[str] = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)

# Default personas per source kind. The character can be overridden by
# the caller — these are the spec defaults from data_model.md §4.16
# (`character_key` for saju vs tarot).
DEFAULT_CHARACTER_FOR_READING: Final[str] = "nuna"
DEFAULT_CHARACTER_FOR_TAROT: Final[str] = "dosa"

# Max retries when the slug we minted happens to collide with an
# existing row. With 12 base62 chars + secrets-derived entropy, this
# branch should be vanishingly rare — but the loop is the only
# safe-by-construction guarantee against ``share_slug`` UNIQUE
# violations under concurrent finalize calls.
_SLUG_COLLISION_MAX_RETRIES: Final[int] = 8


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class QuoteCardCreated:
    """Result of a successful ``create_for_*`` call.

    Lets the calling pipeline log structured success metrics and lets
    tests assert on the persisted shape without re-querying the DB.
    """

    quote_card_id: str
    share_slug: str
    quote_text: str
    category: str
    character_key: str
    source_kind: str
    og_status: str  # always "pending" at create-time; worker updates later.


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------


def _base62_encode(raw: bytes) -> str:
    """Encode *raw* as a base62 string.

    We treat the input as a big-endian unsigned integer, divmod into
    base 62, then prepend the alphabet's zero-character ('0') for
    any leading zero bytes. Length is determined by the input — the
    caller slices to :data:`SHARE_SLUG_LEN`.
    """
    if not raw:
        return _BASE62_ALPHABET[0]
    n = int.from_bytes(raw, byteorder="big", signed=False)
    if n == 0:
        return _BASE62_ALPHABET[0] * len(raw)
    chars: list[str] = []
    while n > 0:
        n, rem = divmod(n, 62)
        chars.append(_BASE62_ALPHABET[rem])
    return "".join(reversed(chars))


def generate_share_slug(*, entropy: bytes | None = None) -> str:
    """Mint a fresh ``share_slug`` of exactly :data:`SHARE_SLUG_LEN` chars.

    Strategy:
    - Mix 32 bytes of ``secrets.token_bytes`` entropy with a SHA-256
      digest so the output is uniform even if the OS source has subtle
      bias. The SHA-256 step is also where we get a stable 32-byte
      buffer to slice through ``_base62_encode``.
    - Take the **first** :data:`SHARE_SLUG_LEN` chars of the base62
      encoding. The leading chars of the SHA-256 are as uniformly
      distributed as the trailing — the slicing direction doesn't
      matter cryptographically.

    Args:
        entropy: Optional override for the random seed. Tests pin this
            to a fixed byte string for deterministic assertions; prod
            callers pass nothing and we read from ``secrets``.

    Returns:
        A URL-safe base62 string of exactly ``SHARE_SLUG_LEN`` chars.
    """
    seed = entropy if entropy is not None else secrets.token_bytes(32)
    digest = hashlib.sha256(seed).digest()
    encoded = _base62_encode(digest)
    # ``_base62_encode`` of a 32-byte digest produces ~ 43 chars (since
    # log_62(2**256) ≈ 43.0) — safe to slice the first 12.
    return encoded[:SHARE_SLUG_LEN]


# ---------------------------------------------------------------------------
# Public factory functions
# ---------------------------------------------------------------------------


async def create_for_reading(
    reading_id: str,
    *,
    session: AsyncSession,
    queue: InMemoryQueue,
    reading_text: str | None = None,
    character_key: str = DEFAULT_CHARACTER_FOR_READING,
    adapter: LLMAdapter | None = None,
) -> QuoteCardCreated:
    """Insert a ``quote_cards`` row for the finished saju *reading_id*.

    Args:
        reading_id: Parent ``readings.id`` row. Must exist; we read
            ``category`` off it so the OG bake can colour the
            background per FR-018 AC #3 (A-06).
        session: SQLAlchemy async session. Caller manages the
            transaction boundary so the insert composes with the
            reading-finalize pipeline's writes.
        queue: :class:`InMemoryQueue` (Phase-1) — the arq Redis-backed
            queue lands in ISSUE-074/075. Both share the same
            ``enqueue("og_bake", quote_card_id=...)`` signature.
        reading_text: Optional override for the quote extraction
            input. If ``None``, we use a single fallback quote per
            category (the LLM extraction needs the streamed body and
            in Phase-1 it's not yet stored back to the DB; ISSUE-039
            wires the persistence). The fallback path is documented as
            the FR-018 AC #4 safety net.
        character_key: Persona used for the quote — ``"nuna"`` for
            saju (default), ``"dosa"`` only for tarot. Threaded into
            both the prompt + the persisted column.
        adapter: Optional :class:`LLMAdapter` override. Defaults to the
            factory inside :func:`extract_quote`.

    Returns:
        :class:`QuoteCardCreated` with the persisted shape.

    Raises:
        ValueError: ``reading_id`` does not exist in the DB.
    """
    reading = await _load_reading(session, reading_id)
    quote_text = await extract_quote(
        reading_text or "",
        character_key=character_key,
        category=reading.category,
        adapter=adapter,
    )

    card = await _insert_card(
        session=session,
        source_kind="reading",
        reading_id=reading_id,
        tarot_id=None,
        category=reading.category,
        quote_text=quote_text,
        character_key=character_key,
    )

    await _enqueue_og_bake(queue, quote_card_id=card.id)

    return QuoteCardCreated(
        quote_card_id=card.id,
        share_slug=card.share_slug,
        quote_text=card.quote_text,
        category=card.category,
        character_key=card.character_key,
        source_kind=card.source_kind,
        og_status=card.og_status,
    )


async def create_for_tarot(
    tarot_id: str,
    *,
    session: AsyncSession,
    queue: InMemoryQueue,
    reading_text: str | None = None,
    character_key: str = DEFAULT_CHARACTER_FOR_TAROT,
    adapter: LLMAdapter | None = None,
) -> QuoteCardCreated:
    """Insert a ``quote_cards`` row for a finished daily *tarot_id* draw.

    Symmetric with :func:`create_for_reading`. The category for tarot
    is always the literal ``"tarot"`` so the bake worker can use the
    purple background colour per FR-018 AC #3.

    Args:
        tarot_id: Parent ``tarot_draws.id`` row. Must exist.
        session: SQLAlchemy async session.
        queue: Phase-1 in-memory queue (see :func:`create_for_reading`).
        reading_text: Optional tarot answer body for the quote LLM.
        character_key: Persona; defaults to ``"dosa"`` per data_model
            §4.16.
        adapter: Optional LLM adapter override.

    Returns:
        :class:`QuoteCardCreated`.

    Raises:
        ValueError: ``tarot_id`` does not exist in the DB.
    """
    await _load_tarot(session, tarot_id)
    category = "tarot"
    quote_text = await extract_quote(
        reading_text or "",
        character_key=character_key,
        category=category,
        adapter=adapter,
    )

    card = await _insert_card(
        session=session,
        source_kind="tarot",
        reading_id=None,
        tarot_id=tarot_id,
        category=category,
        quote_text=quote_text,
        character_key=character_key,
    )

    await _enqueue_og_bake(queue, quote_card_id=card.id)

    return QuoteCardCreated(
        quote_card_id=card.id,
        share_slug=card.share_slug,
        quote_text=card.quote_text,
        category=card.category,
        character_key=card.character_key,
        source_kind=card.source_kind,
        og_status=card.og_status,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _load_reading(session: AsyncSession, reading_id: str) -> Reading:
    """Return the ``Reading`` row or raise ``ValueError`` if missing."""
    row = (
        await session.execute(select(Reading).where(Reading.id == reading_id))
    ).scalar_one_or_none()
    if row is None:
        raise ValueError(
            "quote_card_service.create_for_reading: "
            f"reading_id={reading_id!r} not found"
        )
    return row


async def _load_tarot(session: AsyncSession, tarot_id: str) -> TarotDraw:
    """Return the ``TarotDraw`` row or raise ``ValueError`` if missing."""
    row = (
        await session.execute(select(TarotDraw).where(TarotDraw.id == tarot_id))
    ).scalar_one_or_none()
    if row is None:
        raise ValueError(
            f"quote_card_service.create_for_tarot: tarot_id={tarot_id!r} not found"
        )
    return row


async def _insert_card(
    *,
    session: AsyncSession,
    source_kind: str,
    reading_id: str | None,
    tarot_id: str | None,
    category: str,
    quote_text: str,
    character_key: str,
) -> QuoteCard:
    """Insert one ``quote_cards`` row, retrying on ``share_slug`` collision.

    The slug-collision retry is defensive — at 12 chars of base62 the
    expected collision probability over the v1 lifetime row count
    (≤ 10^7) is < 1e-8 — but the UNIQUE constraint is a real database
    error path and the only correct response is "try again with fresh
    entropy".
    """
    last_err: IntegrityError | None = None
    for _attempt in range(_SLUG_COLLISION_MAX_RETRIES):
        slug = generate_share_slug()
        card = QuoteCard(
            id=str(uuid.uuid4()),  # explicit so the result can echo it back
            source_kind=source_kind,
            reading_id=reading_id,
            tarot_id=tarot_id,
            category=category,
            quote_text=quote_text,
            character_key=character_key,
            share_slug=slug,
            og_status="pending",
        )
        session.add(card)
        try:
            await session.flush()
            return card
        except IntegrityError as exc:
            # SAVEPOINT rollback so the session is reusable. The retry
            # only fires for share_slug UNIQUE collisions in practice;
            # any other IntegrityError (FK violation, CHECK violation)
            # is re-raised after exhausting retries so the caller sees
            # the real shape of the bug.
            await session.rollback()
            last_err = exc
            logger.warning(
                "quote_card_service: insert collision (attempt %d/%d) slug=%s err=%s",
                _attempt + 1,
                _SLUG_COLLISION_MAX_RETRIES,
                slug,
                exc.__class__.__name__,
            )
            continue
    # Out of retries — surface the last error so the caller can
    # alert / 5xx the upstream request rather than swallow.
    raise RuntimeError(
        f"quote_card_service: share_slug collision exceeded "
        f"{_SLUG_COLLISION_MAX_RETRIES} retries; last error: {last_err!r}"
    )


async def _enqueue_og_bake(queue: InMemoryQueue, *, quote_card_id: str) -> None:
    """Enqueue the ``og_bake`` job for *quote_card_id*.

    Wraps the queue call so the caller doesn't have to remember the
    job name. The dispatcher uses the registry's ``__name__`` so
    ISSUE-058 can swap in the real bake worker without changing this
    signature.
    """
    await queue.enqueue("og_bake", quote_card_id=quote_card_id)


__all__ = [
    "DEFAULT_CHARACTER_FOR_READING",
    "DEFAULT_CHARACTER_FOR_TAROT",
    "QuoteCardCreated",
    "SHARE_SLUG_LEN",
    "create_for_reading",
    "create_for_tarot",
    "generate_share_slug",
]
