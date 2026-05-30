"""Tarot card art serving route (ISSUE-055).

Backs the placeholder URL emitted by ISSUE-049's ``_card_art_url`` —
``GET /api/v1/tarot/cards/{card_index}/art`` — with real bytes from the
active storage adapter (``MockStorageAdapter`` under Phase-1, real R2
under ISSUE-005).

Behaviour by ``STORAGE_PROVIDER``:

* ``mock`` → stream the bytes inline (the adapter's local-fs root is on
  the same host, so we round-trip through ``put/get_object`` and respond
  with ``image/png``). This keeps Phase-1 dev runs hermetic.
* ``r2`` → ideally we'd 302 to a signed URL, but the Phase-2 stub raises
  ``NotImplementedError``. For now we proxy the bytes the same way as
  ``mock``; the Phase-2 swap can replace this with a presigned-URL
  redirect without touching the route signature.

Cache-busting (AC3): clients append ``?v=<short_hash>`` and we honour it
by setting a long ``Cache-Control: public, max-age=31536000, immutable``
when the query param is present. Without the param the cache is shorter
(5 minutes) so a same-key overwrite during DEP-06 is picked up promptly.

PRD-Ref: DEP-06.
Architecture-Ref: §6.4 (tarot flow), §8.4 (storage layout).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from voicesaju.storage.r2_client import R2Client

router = APIRouter(prefix="/api/v1/tarot/cards", tags=["tarot"])


# Match the seed migration's ``card_index`` range (0..21 inclusive).
_MIN_CARD_INDEX = 0
_MAX_CARD_INDEX = 21


def _get_r2_client() -> R2Client:
    """Factory dependency — tests override this to inject a fixture."""
    return R2Client.from_settings()


def _r2_key_for(card_index: int) -> str:
    """Mirror the upload script's key convention.

    The upload script writes ``tarot/major/{idx:02d}.png``; we read back
    the same key here. Kept as a private helper so a future refactor
    (e.g. content-team uploading webp) can swap the extension in one
    place.
    """
    return f"tarot/major/{card_index:02d}.png"


@router.get(
    "/{card_index}/art",
    responses={
        200: {"content": {"image/png": {}}},
        404: {"description": "Card art not yet uploaded for this index"},
    },
)
async def get_card_art(
    card_index: int,
    # ``v`` is honoured purely for caching semantics — the bytes are
    # served from the storage adapter regardless of the value. The query
    # param signals "the caller knows the content hash, so we can mark
    # the response immutable for a year".
    v: Annotated[str | None, Query(max_length=64)] = None,
    r2: Annotated[R2Client, Depends(_get_r2_client)] = ...,  # type: ignore[assignment]
) -> Response:
    """Return the PNG bytes for ``card_index``.

    Returns 404 if the storage adapter has no object at the expected key
    (e.g. ``upload_tarot_art.py`` was never run). The frontend reading
    page (ISSUE-051) treats 404 as "fall back to the CSS placeholder"
    so a missing upload degrades gracefully rather than blocking flow.

    AC2: ``GET /api/v1/tarot/cards/0/art`` returns the asset bytes.
    AC3: ``?v=<hash>`` flips the Cache-Control to year-long immutable.
    """
    if not (_MIN_CARD_INDEX <= card_index <= _MAX_CARD_INDEX):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"card_index {card_index} out of range",
        )

    key = _r2_key_for(card_index)
    try:
        data = await r2.get_object(key)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"card art not uploaded for card_index={card_index}",
        ) from exc

    cache_control = (
        "public, max-age=31536000, immutable"
        if v is not None
        else "public, max-age=300"
    )
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": cache_control},
    )


__all__ = [
    "_get_r2_client",
    "router",
]
