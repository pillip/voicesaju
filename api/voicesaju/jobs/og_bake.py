"""``og_bake`` job (ISSUE-058).

Composites the 1080×1920 Open-Graph "viral asset" PNG for a
``quote_cards`` row and uploads it via :class:`R2Client` to the
canonical ``og/{quote_card_id}.png`` key. On success, the row's
``og_status`` flips ``pending`` → ``baked`` and ``og_r2_key`` is set.
On exhausted retries the row is marked ``failed`` so the SSR share
endpoint (ISSUE-061) can decide between the baked image and the
fallback static card.

Layout (Phase-1 placeholder — real illustration + Pretendard font
land via DEP-06/DEP-XX):

* Background: solid category colour per A-06
  (love → ``#FFB6C1``, work → ``#87CEEB``, money → ``#FFD700``,
  tarot → ``#9370DB``). Unknown categories fall back to a neutral
  grey so a missing palette entry doesn't crash the worker.
* Character placeholder ("누나" or "도사") in the upper third.
* Quote text centered in the middle band, wrapped to ≤2 lines.
* "VoiceSaju" watermark in the bottom-right corner.

Robustness — three attempts with exponential backoff via :mod:`tenacity`.
We keep the retry inside a single ``og_bake`` invocation (rather than
re-enqueueing) so the row state machine has one writer:

1. queue dispatches → ``og_bake``
2. ``og_bake`` retries internally
3. ``og_bake`` writes either ``baked`` or ``failed``

PRD-Ref: FR-018, FR-020, A-06.
Architecture-Ref: §8.4 (storage layout), §2 (worker pipeline).
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from voicesaju.config import Settings, get_settings
from voicesaju.db.models.quote_cards import QuoteCard
from voicesaju.storage.r2_client import R2Client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layout constants — load-bearing for the AC tests (1080×1920, A-06 hexes)
# ---------------------------------------------------------------------------

#: Open-Graph canvas size (FR-018: 1080×1920 PNG).
OG_CANVAS_SIZE: tuple[int, int] = (1080, 1920)

#: Category → solid background RGB per design system A-06.
#:
#: Keys mirror :data:`voicesaju.db.models.readings.Reading.category` and
#: the tarot source-kind (the four-way enum is closed at the data model
#: layer — ``love``/``work``/``money``/``tarot``).
CATEGORY_BACKGROUNDS: dict[str, tuple[int, int, int]] = {
    "love": (0xFF, 0xB6, 0xC1),  # pink — A-06 love
    "work": (0x87, 0xCE, 0xEB),  # sky blue — A-06 work
    "money": (0xFF, 0xD7, 0x00),  # gold — A-06 money
    "tarot": (0x93, 0x70, 0xDB),  # medium purple — A-06 tarot
}

#: Fallback colour when a card's category is outside the registry. We
#: prefer a neutral grey so a future category rollout doesn't ship
#: pink for a "career_v2" string and confuse reviewers.
_FALLBACK_BACKGROUND: tuple[int, int, int] = (0xE0, 0xE0, 0xE0)

#: Character key → display label for the upper-third placeholder.
#: Real illustrations land via DEP-06; until then a hangul label is
#: enough to disambiguate the persona at thumbnail size.
_CHARACTER_LABELS: dict[str, str] = {
    "nuna": "누나",
    "sajununa": "누나",
    "dosa": "도사",
    "sajudosa": "도사",
}

#: Storage key prefix for baked OG images (architecture §8.4).
_OG_KEY_PREFIX: str = "og"

#: Retry budget — AC3 spec: three attempts → mark failed.
_MAX_ATTEMPTS: int = 3


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def og_bake(
    quote_card_id: str,
    *,
    session: AsyncSession,
    r2: R2Client | None = None,
    settings: Settings | None = None,
    **_unused: Any,
) -> None:
    """Composite + upload the OG image for *quote_card_id*.

    The worker is intentionally tolerant of unknown ids and storage
    transients: arq retry semantics dispatch the same job name on
    schedule slips, so a missing row must not raise and a 5xx from
    storage must be retried in-process rather than poison-looping the
    queue.

    Args:
        quote_card_id: Target ``quote_cards.id`` (uuidv7 as str).
        session: SQLAlchemy async session. Caller manages the
            transaction boundary — the worker only ``flush()`` es so the
            ISSUE-057 row-create path can compose with this in a single
            commit at the FastAPI layer if desired.
        r2: Storage client override. If ``None`` we resolve via
            ``STORAGE_PROVIDER`` (Phase-1: MockStorageAdapter).
        settings: ``Settings`` override; only used when ``r2 is None``.
        **_unused: Forward-compat sink for arq kwargs (``ctx``, ``job_id``).

    Returns:
        ``None``. State is communicated via the row's ``og_status`` /
        ``og_r2_key`` columns so multiple readers (SSR endpoint, admin
        dashboard, smoke tests) share a single source of truth.
    """
    settings = settings or get_settings()
    r2 = r2 or R2Client.from_settings(settings=settings)

    # 1. Pull the row. A missing card is treated as a no-op — the queue
    #    can outrun a roll-back without the worker exploding.
    row = (
        await session.execute(select(QuoteCard).where(QuoteCard.id == quote_card_id))
    ).scalar_one_or_none()
    if row is None:
        logger.warning(
            "og_bake: quote_card_id=%s not found; skipping",
            quote_card_id,
        )
        return None

    key = f"{_OG_KEY_PREFIX}/{quote_card_id}.png"

    # 2. Composite + upload under a retry budget. Anything raised from
    #    inside the loop counts towards the three-attempt cap.
    try:
        await _bake_and_upload(
            row=row,
            r2=r2,
            key=key,
        )
    except RetryError as exc:
        logger.error(
            "og_bake: upload failed after %d attempts for quote_card_id=%s: %s",
            _MAX_ATTEMPTS,
            quote_card_id,
            exc,
        )
        row.og_status = "failed"
        await session.flush()
        return None
    except Exception:  # pragma: no cover - defensive
        # A non-retryable error (e.g. coding bug) still has to leave the
        # row in a known state so the SSR share endpoint doesn't render
        # against a phantom "pending" forever.
        logger.exception(
            "og_bake: unexpected error for quote_card_id=%s", quote_card_id
        )
        row.og_status = "failed"
        await session.flush()
        return None

    row.og_status = "baked"
    row.og_r2_key = key
    await session.flush()
    return None


# ---------------------------------------------------------------------------
# Bake + upload with tenacity-backed retry
# ---------------------------------------------------------------------------


async def _bake_and_upload(
    *,
    row: QuoteCard,
    r2: R2Client,
    key: str,
) -> None:
    """Composite the PNG and upload at *key*, retrying transient errors.

    The composite step is deterministic so we re-run it inside the
    retry: a corrupted PIL buffer from a half-write retry would be
    worse than a few extra ms of CPU on rebake.
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.01, min=0.01, max=0.05),
        retry=retry_if_exception_type((OSError, RuntimeError)),
        reraise=False,
    ):
        with attempt:
            png_bytes = _composite_png(
                category=row.category,
                character_key=row.character_key,
                quote_text=row.quote_text,
            )
            await r2.put_object(key, png_bytes)


# ---------------------------------------------------------------------------
# Pillow compositor — Phase-1 placeholder layout
# ---------------------------------------------------------------------------


def _composite_png(
    *,
    category: str,
    character_key: str,
    quote_text: str,
) -> bytes:
    """Render the 1080×1920 PNG and return the encoded bytes.

    Pure-function so it's trivially unit-testable: same inputs → same
    PNG bytes. The persona + quote layers use Pillow's default bitmap
    font; DEP-XX swaps to Pretendard once the licensed TTF is mounted
    in the worker image.
    """
    bg = CATEGORY_BACKGROUNDS.get(category, _FALLBACK_BACKGROUND)
    img = Image.new("RGB", OG_CANVAS_SIZE, color=bg)
    draw = ImageDraw.Draw(img)

    canvas_w, canvas_h = OG_CANVAS_SIZE

    # Persona label — upper third, centered. Real illustration lands
    # with DEP-06; until then the hangul nickname disambiguates the
    # persona at thumbnail size.
    persona_label = _CHARACTER_LABELS.get(character_key, character_key)
    persona_font = _load_font(size=96)
    _draw_centered(
        draw,
        persona_label,
        font=persona_font,
        center_x=canvas_w // 2,
        baseline_y=canvas_h // 3,
        fill=(255, 255, 255),
    )

    # Quote text — middle band, wrapped to two lines max (the DB
    # CHECK caps quote_text at 40 chars so a naïve mid-string split is
    # fine for the placeholder; real wrap kerning lands with DEP-XX).
    quote_font = _load_font(size=72)
    for offset, line in enumerate(_wrap_quote(quote_text)):
        _draw_centered(
            draw,
            line,
            font=quote_font,
            center_x=canvas_w // 2,
            baseline_y=canvas_h // 2 + offset * 96,
            fill=(0, 0, 0),
        )

    # Watermark — bottom-right corner. Stays small so it doesn't draw
    # the eye away from the quote; the "VoiceSaju" wordmark is a
    # brand anchor for unfurled-link previews.
    watermark_font = _load_font(size=36)
    watermark_text = "VoiceSaju"
    wm_bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
    wm_w = wm_bbox[2] - wm_bbox[0]
    wm_h = wm_bbox[3] - wm_bbox[1]
    draw.text(
        (canvas_w - wm_w - 40, canvas_h - wm_h - 40),
        watermark_text,
        font=watermark_font,
        fill=(80, 80, 80),
    )

    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _load_font(*, size: int) -> ImageFont.ImageFont:
    """Pillow default font at the requested size.

    We deliberately skip system-font discovery so the worker stays
    hermetic across linux containers / mac dev. Pillow ≥10 honours the
    ``size=`` kwarg on the bundled TrueType default; on older builds
    it silently no-ops which we treat as acceptable for the
    placeholder.
    """
    try:
        return ImageFont.load_default(size=size)  # type: ignore[call-arg]
    except TypeError:  # pragma: no cover - Pillow < 10 fallback
        return ImageFont.load_default()


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font: ImageFont.ImageFont,
    center_x: int,
    baseline_y: int,
    fill: tuple[int, int, int],
) -> None:
    """Stamp *text* centered horizontally on *center_x* at *baseline_y*."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(
        (center_x - w // 2, baseline_y - h // 2),
        text,
        font=font,
        fill=fill,
    )


def _wrap_quote(text: str, *, max_chars_per_line: int = 20) -> list[str]:
    """Naïve word-wrap for the placeholder quote layer.

    The DB CHECK caps ``quote_text`` at 40 chars so two lines is the
    worst case. We split at the nearest whitespace below the limit so
    Korean particle-attached words stay together where possible.
    """
    text = text.strip()
    if len(text) <= max_chars_per_line:
        return [text]
    # Search backwards for whitespace below the cap; fall back to a
    # hard split if the string has no spaces (typical for Korean).
    split_at = max_chars_per_line
    for idx in range(max_chars_per_line, 0, -1):
        if text[idx - 1].isspace():
            split_at = idx
            break
    return [text[:split_at].strip(), text[split_at:].strip()]


__all__ = [
    "CATEGORY_BACKGROUNDS",
    "OG_CANVAS_SIZE",
    "og_bake",
]
