"""FastAPI router for ``GET /api/v1/quote-cards/by-slug/{slug}`` (ISSUE-060).

PRD-Ref: FR-020 (share slug → quote card lookup).
data_model-Ref: AP-43 (``Read QuoteCard by public share_slug``).
Architecture-Ref: §6.6 (quote card / share endpoints).

Backs the Next.js Route Handler ``/api/og/[slug]`` (ISSUE-060) and the
SSR share landing page ``/share/[slug]`` (ISSUE-061). Both callers need
the same JSON payload — the quote card metadata that drives either a
redirect to the baked R2 image or an inline ``@vercel/og`` fallback.

The payload is minimal on purpose: the share endpoints don't need PII or
the full row shape, only what the OG image needs (text / character /
category / bake status / R2 key for redirect).

Lookup is O(1) — ``share_slug`` is UNIQUE per ``quote_cards`` schema
(data_model §4.16, ``quote_cards_share_slug_uq``). No auth required:
this endpoint is the public share-graph surface and the slug itself is
the capability.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.engine import get_session
from voicesaju.db.models.quote_cards import QuoteCard

router = APIRouter(prefix="/api/v1/quote-cards", tags=["quote-cards"])


class QuoteCardBySlugResponse(BaseModel):
    """Payload returned by ``GET /quote-cards/by-slug/{slug}``.

    Shape mirrors what the Next.js OG route handler and the SSR share
    page need — strict subset of the ``QuoteCard`` ORM row. We don't
    expose internal columns (``id``, ``expires_at``, ``og_image_url``
    legacy field) because the share consumers only need the bake state
    plus the rendering inputs.

    Field semantics:

    * ``quote_card_id`` — opaque to the consumer; useful for log
      correlation when the SSR page reports a render failure.
    * ``category`` — drives the background colour in the OG image
      (matches ``CATEGORY_BACKGROUNDS`` in :mod:`voicesaju.jobs.og_bake`).
    * ``character_key`` — drives the persona label ("누나" / "도사") in
      the rendered card.
    * ``quote_text`` — the actual ≤40 char quote line.
    * ``og_status`` — ``pending`` / ``baked`` / ``failed``. The OG route
      handler branches on this: ``baked`` → redirect to ``og_r2_key``;
      anything else → inline ``@vercel/og`` fallback.
    * ``og_r2_key`` — the R2 object key the bake worker wrote to. May be
      None when ``og_status != 'baked'``; the route handler must guard
      against that.
    """

    quote_card_id: str
    category: str
    character_key: str
    quote_text: str
    og_status: str
    og_r2_key: str | None


@router.get(
    "/by-slug/{slug}",
    response_model=QuoteCardBySlugResponse,
    responses={
        404: {"description": "No quote card with this share_slug"},
    },
)
async def get_quote_card_by_slug(
    slug: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> QuoteCardBySlugResponse:
    """Return the public quote-card payload for *slug* or 404 if unknown.

    The UNIQUE constraint on ``share_slug`` guarantees we either return
    the single matching row or 404 — no disambiguation logic needed.

    AC #3 (ISSUE-060): unknown slug → 404. The Next.js route handler
    propagates the 404 status to the caller so the social crawler
    surfaces a broken-link card rather than rendering a misleading
    fallback image.
    """
    stmt = select(QuoteCard).where(QuoteCard.share_slug == slug)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"quote card slug={slug!r} not found",
        )
    return QuoteCardBySlugResponse(
        quote_card_id=str(row.id),
        category=row.category,
        character_key=row.character_key,
        quote_text=row.quote_text,
        og_status=row.og_status,
        og_r2_key=row.og_r2_key,
    )


__all__ = ["QuoteCardBySlugResponse", "router"]
