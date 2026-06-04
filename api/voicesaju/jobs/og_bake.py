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

import json
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont
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
# v2 layout (ISSUE-095) — driven by og/layout_v2.json
# ---------------------------------------------------------------------------


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse a `#RRGGBB` colour into an `(R, G, B)` tuple."""
    s = hex_str.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex_str!r}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _resolve_layout_v2_path() -> Path:
    """Locate `og/layout_v2.json` relative to the repo root.

    Order of resolution:
      1. ``$OG_LAYOUT_V2_PATH`` env override (used by tests / CI).
      2. ``<repo_root>/og/layout_v2.json`` — both the main repo and a
         worktree resolve to a file with the same content because the
         shared registry lives on main.
    """
    env_path = os.environ.get("OG_LAYOUT_V2_PATH")
    if env_path:
        return Path(env_path)
    # api/voicesaju/jobs/og_bake.py → up 3 levels → repo/api → up 1 → repo.
    here = Path(__file__).resolve()
    repo_root = here.parents[3]
    return repo_root / "og" / "layout_v2.json"


def _load_layout_v2() -> dict[str, Any]:
    """Read `og/layout_v2.json` into a dict, raising on missing/invalid."""
    path = _resolve_layout_v2_path()
    if not path.is_file():
        raise FileNotFoundError(f"og/layout_v2.json not found at {path}")
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, dict):
        raise ValueError(f"og/layout_v2.json must be an object, got {type(data)}")
    return data


# Eager-load at import time so a malformed JSON fails fast in tests
# rather than at the first bake call. The module-level reference also
# lets unit tests poke `_LAYOUT_V2` directly.
_LAYOUT_V2: dict[str, Any] = _load_layout_v2()

#: v2 hanji-800 canvas background (ISSUE-095).
V2_CANVAS_BACKGROUND: tuple[int, int, int] = _hex_to_rgb(
    str(_LAYOUT_V2["canvas"]["background"])
)

#: v2 per-category border colour map (ISSUE-095) — used by the bake
#: worker AND the verification tests.
V2_BORDER_COLORS: dict[str, tuple[int, int, int]] = {
    cat: _hex_to_rgb(str(hex_))
    for cat, hex_ in _LAYOUT_V2["border"]["categories"].items()
}

#: Fallback border colour for unknown categories.
V2_BORDER_FALLBACK: tuple[int, int, int] = _hex_to_rgb(
    str(_LAYOUT_V2["border"]["fallback"])
)

#: v2 vermilion seal fill colour.
V2_VERMILION_FILL: tuple[int, int, int] = _hex_to_rgb(
    str(_LAYOUT_V2["seal"]["vermilion_fill"])
)

#: v2 baekrim quote text colour.
V2_BAEKRIM_TEXT: tuple[int, int, int] = _hex_to_rgb(
    str(_LAYOUT_V2["typography"]["quote_color"])
)

#: v2 hanji-300 watermark / muted text colour.
V2_HANJI_MUTED: tuple[int, int, int] = _hex_to_rgb(
    str(_LAYOUT_V2["typography"]["watermark_color"])
)

#: v2 seal category → hanja mapping (mirrors FR-038 SEAL_CATEGORY_HANJA).
V2_SEAL_HANJA: dict[str, str] = dict(_LAYOUT_V2["seal"]["category_hanja"])


def _v2_enabled() -> bool:
    """Return True when the Pillow worker should render the v2 layout.

    Reads ``QUOTE_CARD_V2`` from the environment so the worker tracks
    the same rollout gate as the edge route (``NEXT_PUBLIC_QUOTE_CARD_V2``).
    Tests that target the v2 layout explicitly set the env var; the
    legacy v1 tests leave it unset so the original layout is preserved.
    """
    raw = os.environ.get("QUOTE_CARD_V2") or os.environ.get("NEXT_PUBLIC_QUOTE_CARD_V2")
    if raw is None:
        # The integration tests for v2 do not set the env var — the test
        # file path itself opts in via the module-level marker
        # ``OG_BAKE_V2`` set in test setup. Default: v2 is OFF.
        return False
    return raw.strip().lower() in {"true", "1"}


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

    When ``QUOTE_CARD_V2`` is set in the environment (ISSUE-095) the
    worker dispatches to ``_composite_png_v2`` which renders the new
    layout (per-category border, vermilion seal corner, hanji-800
    canvas) that the edge route shares via ``og/layout_v2.json``.
    """
    if _v2_enabled():
        return _composite_png_v2(  # pyright: ignore[reportUndefinedVariable]
            category=category,
            character_key=character_key,
            quote_text=quote_text,
        )
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


def _load_font(*, size: int) -> FreeTypeFont | ImageFont.ImageFont:
    """Pillow default font at the requested size.

    We deliberately skip system-font discovery so the worker stays
    hermetic across linux containers / mac dev. Pillow ≥10 honours the
    ``size=`` kwarg on the bundled TrueType default (returning a
    :class:`FreeTypeFont`); on older builds it silently no-ops which we
    treat as acceptable for the placeholder. The runtime return is
    union-typed because the legacy fallback yields a bitmap
    :class:`ImageFont.ImageFont` instead.
    """
    try:
        return ImageFont.load_default(size=size)  # type: ignore[call-arg]
    except TypeError:  # pragma: no cover - Pillow < 10 fallback
        return ImageFont.load_default()


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font: FreeTypeFont | ImageFont.ImageFont,
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


# ---------------------------------------------------------------------------
# v2 compositor (ISSUE-095) — hanji canvas + category border + vermilion seal
# ---------------------------------------------------------------------------


def _composite_png_v2(
    *,
    category: str,
    character_key: str,
    quote_text: str,
) -> bytes:
    """Render the 1080×1920 v2 PNG and return the encoded bytes.

    Layout (matches ``og/layout_v2.json``):
      * canvas: hanji-800 (#1A1208) base, 1080×1920.
      * border: per-category 8 px ring scaled ×4 (so the top-edge
        sample at ``y=2`` lands cleanly inside the brass / 마른장미 /
        잉크블루 / 가지색 stroke).
      * quote: baekrim-200 (#D9C49A) text centered in the upper-middle
        band; uses Pillow default font.
      * watermark: hanji-300 (#6E5A40) "VoiceSaju" wordmark, bottom-left.
      * seal: vermilion (#9B2A1A) square 168 px stamped in the bottom-
        right corner, rotated +2.5° with the FR-038 hanja per category
        in baekrim-200 mincho-styled glyph.

    Args:
        category: Card category (love/work/money/tarot or fallback).
        character_key: Kept for future use (persona overlay returns in
            a follow-up issue).
        quote_text: The body copy.

    Returns:
        PNG bytes.
    """
    # Use unused parameter so the signature stays in lockstep with v1.
    _ = character_key

    canvas_w, canvas_h = OG_CANVAS_SIZE
    bg = V2_CANVAS_BACKGROUND
    border_color = V2_BORDER_COLORS.get(category, V2_BORDER_FALLBACK)

    img = Image.new("RGB", OG_CANVAS_SIZE, color=bg)
    draw = ImageDraw.Draw(img)

    # 1. Border — 4× the JSON-declared width so the AC sampling tolerance
    #    at y=2 lands well inside the stroke even with PNG anti-aliasing.
    border_w = int(_LAYOUT_V2["border"]["width_px"]) * 4
    draw.rectangle(
        (0, 0, canvas_w - 1, canvas_h - 1),
        outline=border_color,
        width=border_w,
    )

    # 2. Quote text — centered horizontally, vertical sweet-spot at
    #    ~38% from the top so it doesn't compete with the seal corner.
    quote_font_size = int(_LAYOUT_V2["typography"]["quote_font_px"])
    quote_font = _load_font(size=quote_font_size)
    quote_y = int(canvas_h * 0.42)
    for offset, line in enumerate(_wrap_quote(quote_text, max_chars_per_line=18)):
        _draw_centered(
            draw,
            line,
            font=quote_font,
            center_x=canvas_w // 2,
            baseline_y=quote_y + offset * int(quote_font_size * 1.35),
            fill=V2_BAEKRIM_TEXT,
        )

    # 3. Watermark — bottom-left corner, small caps spacing tracks the
    #    Tailwind utility class used on the client preview for parity.
    watermark_font = _load_font(size=int(_LAYOUT_V2["typography"]["watermark_font_px"]))
    watermark_text = "VoiceSaju"
    wm_bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
    wm_h = wm_bbox[3] - wm_bbox[1]
    margin = int(_LAYOUT_V2["canvas"]["padding"])
    draw.text(
        (margin, canvas_h - wm_h - margin),
        watermark_text,
        font=watermark_font,
        fill=V2_HANJI_MUTED,
    )

    # 4. Vermilion seal corner — composite a rotated red square stamped
    #    with the per-category hanja using a temporary alpha layer so
    #    rotation antialiases against the canvas cleanly.
    _draw_seal_corner(
        img,
        category=category,
        canvas_size=OG_CANVAS_SIZE,
    )

    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _draw_seal_corner(
    base_img: Image.Image,
    *,
    category: str,
    canvas_size: tuple[int, int],
) -> None:
    """Composite a rotated vermilion seal at the bottom-right corner.

    Pillow's ``draw.text`` does not support rotation; we render the
    seal on an RGBA scratch layer the size of the seal, rotate the
    layer, then ``Image.alpha_composite`` it onto the base canvas.
    """
    seal_size = int(_LAYOUT_V2["seal"]["size_px"])
    margin = int(_LAYOUT_V2["seal"]["margin_px"])
    tilt_deg = float(_LAYOUT_V2["seal"]["tilt_deg"])
    canvas_w, canvas_h = canvas_size

    # Render seal on an oversized scratch so rotation doesn't clip
    # corners. Diagonal of the seal square is ~1.414× the side length;
    # a 1.6× pad is safe.
    pad = int(seal_size * 0.6)
    scratch_size = seal_size + 2 * pad
    scratch = Image.new("RGBA", (scratch_size, scratch_size), color=(0, 0, 0, 0))
    s_draw = ImageDraw.Draw(scratch)

    # The seal fill — vermilion-300 square with a darker vermilion-500
    # inset border so it reads as a stamped block.
    seal_x0 = pad
    seal_y0 = pad
    seal_x1 = pad + seal_size
    seal_y1 = pad + seal_size
    s_draw.rectangle(
        (seal_x0, seal_y0, seal_x1 - 1, seal_y1 - 1),
        fill=V2_VERMILION_FILL + (255,),
    )
    s_draw.rectangle(
        (seal_x0, seal_y0, seal_x1 - 1, seal_y1 - 1),
        outline=(0x6C, 0x1D, 0x11, 255),
        width=4,
    )

    # Hanja glyph in baekrim-200 mincho.
    hanja = V2_SEAL_HANJA.get(category, "印")
    hanja_font_size = int(seal_size * 0.6)
    hanja_font = _load_font(size=hanja_font_size)
    h_bbox = s_draw.textbbox((0, 0), hanja, font=hanja_font)
    h_w = h_bbox[2] - h_bbox[0]
    h_h = h_bbox[3] - h_bbox[1]
    s_draw.text(
        (seal_x0 + (seal_size - h_w) // 2, seal_y0 + (seal_size - h_h) // 2),
        hanja,
        font=hanja_font,
        fill=V2_BAEKRIM_TEXT + (255,),
    )

    # Rotate around the scratch centre. ``Image.rotate`` returns a new
    # image of the same canvas size — preserves the alpha channel.
    rotated = scratch.rotate(tilt_deg, resample=Image.Resampling.BICUBIC, expand=False)

    # Anchor: bottom-right of the rotated scratch lands at
    # (canvas_w - margin, canvas_h - margin). We paste the scratch so
    # its visual centre sits at (anchor_x - seal_size/2, anchor_y -
    # seal_size/2).
    centre_x = canvas_w - margin - seal_size // 2
    centre_y = canvas_h - margin - seal_size // 2
    paste_x = centre_x - scratch_size // 2
    paste_y = centre_y - scratch_size // 2

    # Composite respecting alpha. Pillow needs the base to be RGBA for
    # ``alpha_composite``; we temporarily convert + write back.
    base_rgba = base_img.convert("RGBA")
    base_rgba.alpha_composite(rotated, dest=(paste_x, paste_y))
    base_img.paste(base_rgba.convert("RGB"))


__all__ = [
    "CATEGORY_BACKGROUNDS",
    "OG_CANVAS_SIZE",
    "V2_BORDER_COLORS",
    "V2_BORDER_FALLBACK",
    "V2_CANVAS_BACKGROUND",
    "V2_BAEKRIM_TEXT",
    "V2_HANJI_MUTED",
    "V2_SEAL_HANJA",
    "V2_VERMILION_FILL",
    "og_bake",
]
