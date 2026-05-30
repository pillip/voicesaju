"""Tarot card art generator + uploader (ISSUE-055).

Phase-1 deliverable for DEP-06: ship 22 Major-Arcana placeholder card
arts + 1 back art so the daily-tarot flow (Screen 12/13) can render real
PNGs instead of CSS placeholders, even before the content team supplies
final illustrations.

Two responsibilities:

1. **Generate** procedural placeholder PNGs locally under
   ``api/static/tarot/cards/`` + ``api/static/tarot/back.png``. These
   ship in-tree so dev/CI flows work offline. Each PNG is ≤ 30KB
   (Pillow ``optimize=True``).

2. **Upload** the generated assets via :class:`R2Client` to whichever
   storage adapter ``STORAGE_PROVIDER`` resolves to. For Phase-1 that
   is :class:`MockStorageAdapter` (local-fs); ISSUE-005 will flip this
   to real Cloudflare R2 with no change to this script.

The 23 R2 keys follow the architecture §8.4 prefix convention plus the
seed migration's ``art_key`` column:

* ``tarot/major/{idx:02d}.png`` for ``idx`` in ``0..21`` (22 keys).
* ``tarot/back.png`` (1 key).

The seed migration declares ``art_key = "tarot/major/{idx:02d}.webp"``
(WebP). We override to PNG here because:

- Pillow ships WebP support but it requires libwebp at build time, and
  CI runners may lack it. PNG round-trips on every Pillow install.
- The runtime art-serve route reads from R2 key prefix — extension
  is part of the key, so PNG keys + PNG-serving route stay coherent.
- DEP-06 final illustrations can re-overwrite the same keys with their
  preferred format; the route streams whatever bytes R2 returns.

When run as a script::

    uv run python scripts/upload_tarot_art.py
    uv run python scripts/upload_tarot_art.py --skip-upload  # generate only

The script is idempotent: re-running overwrites the PNGs + re-uploads.
A content-hash query string (``?v=<sha256>``) is exposed via
:func:`build_versioned_url` so the frontend can opt into cache-busting
when DEP-06 swaps in real art (AC3).

PRD-Ref: DEP-06.
Architecture-Ref: §6.4 (tarot flow), §8.4 (storage layout).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Repo root is two levels up from this script (``api/scripts/x.py``).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATIC_ROOT = _REPO_ROOT / "static" / "tarot"
_CARDS_DIR = _STATIC_ROOT / "cards"


# ---------------------------------------------------------------------------
# Card metadata — duplicated from migration 0008 so this script is
# self-contained (the migration list lives behind an Alembic import that
# we don't want to drag in here). Keep these two lists in sync; the
# unit test in ``test_card_art_upload.py`` enforces the cardinality.
# ---------------------------------------------------------------------------

_MAJOR_ARCANA: list[tuple[int, str, str]] = [
    (0, "The Fool", "바보"),
    (1, "The Magician", "마법사"),
    (2, "The High Priestess", "여사제"),
    (3, "The Empress", "여황제"),
    (4, "The Emperor", "황제"),
    (5, "The Hierophant", "교황"),
    (6, "The Lovers", "연인"),
    (7, "The Chariot", "전차"),
    (8, "Strength", "힘"),
    (9, "The Hermit", "은둔자"),
    (10, "Wheel of Fortune", "운명의 수레바퀴"),
    (11, "Justice", "정의"),
    (12, "The Hanged Man", "거꾸로 매달린 사람"),
    (13, "Death", "죽음"),
    (14, "Temperance", "절제"),
    (15, "The Devil", "악마"),
    (16, "The Tower", "탑"),
    (17, "The Star", "별"),
    (18, "The Moon", "달"),
    (19, "The Sun", "태양"),
    (20, "Judgement", "심판"),
    (21, "The World", "세계"),
]

# Canvas + design constants. 512x768 keeps the aspect ratio close to a
# real tarot card (~5:7) without being so large that the PNG breaks the
# ≤30KB budget. The palette is intentionally narrow so different cards
# stay visually distinct from a thumbnail glance.
_CANVAS_SIZE: tuple[int, int] = (512, 768)
# Two-stop vertical gradient. The top stop varies per card (hue-cycled
# from card_index) so each thumbnail is uniquely tinted; bottom stop is
# a constant dark indigo so the Korean label text always has a high
# contrast read.
_PALETTE_BOTTOM: tuple[int, int, int] = (24, 18, 48)
# Back-art palette mirrors the brand "tarot indigo" — solid colour so
# the face-down hero on Screen 12 stays consistent across devices.
_BACK_PALETTE: tuple[int, int, int] = (32, 24, 64)
_BACK_PALETTE_BOTTOM: tuple[int, int, int] = (12, 8, 28)


@dataclass(frozen=True)
class GeneratedArt:
    """Result row for a single generated card.

    ``r2_key`` is what the upload step uses; ``content_hash`` is the
    SHA-256 hex digest of the bytes (AC3 cache-busting marker).
    """

    card_index: int | None  # None for the back art
    r2_key: str
    path: Path
    content_hash: str
    byte_size: int


# ---------------------------------------------------------------------------
# Procedural generation
# ---------------------------------------------------------------------------


def _hue_color(card_index: int) -> tuple[int, int, int]:
    """Pick a top-stop colour based on ``card_index``.

    Cycles through a 6-step palette so the 22 cards land on 6 distinct
    hues. We avoid a full HSL conversion (no extra deps) and instead
    stamp pre-picked RGB triples that the design system already uses
    for category badges (purple, blue, teal, amber, rose, violet).
    """
    palette: list[tuple[int, int, int]] = [
        (102, 75, 200),  # violet
        (75, 130, 220),  # blue
        (60, 180, 175),  # teal
        (220, 165, 60),  # amber
        (215, 95, 130),  # rose
        (155, 90, 200),  # purple
    ]
    return palette[card_index % len(palette)]


def _vertical_gradient(
    size: tuple[int, int],
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> Image.Image:
    """Render a vertical RGB gradient. Pillow doesn't ship a one-shot
    gradient helper so we draw row-by-row — slow but the canvas is tiny.
    """
    img = Image.new("RGB", size, color=top)
    draw = ImageDraw.Draw(img)
    height = size[1]
    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))
    return img


def _load_default_font(size: int) -> ImageFont.ImageFont:
    """Pillow's bundled default font. We deliberately skip system-font
    discovery so the script is hermetic across mac/linux/CI runners.

    Pillow's default bitmap font can't size up — it renders ~10px
    regardless. We trade visual polish for portability since these are
    placeholders that DEP-06 will overwrite anyway.
    """
    # Pillow ≥ 10 honours `size` on the truetype default; on older
    # versions the `load_default` ignores size. Either way the
    # placeholder is legible enough for "labelled colored rectangle"
    # acceptance.
    try:
        return ImageFont.load_default(size=size)  # type: ignore[call-arg]
    except TypeError:
        return ImageFont.load_default()


def _draw_centered_text(
    img: Image.Image,
    lines: list[str],
    *,
    font_size: int = 28,
    fill: tuple[int, int, int] = (245, 240, 220),
) -> None:
    """Stamp the card label centered horizontally + vertically.

    ``lines`` is a list of pre-broken display lines (e.g. ``["0",
    "The Fool", "바보"]``). We center the bounding box rather than
    each line individually so the visual baseline doesn't jitter.
    """
    draw = ImageDraw.Draw(img)
    font = _load_default_font(font_size)

    # Measure each line. ``textbbox`` is the modern Pillow API.
    line_metrics: list[tuple[int, int]] = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_metrics.append((w, h))
    total_height = sum(h for _, h in line_metrics) + (len(lines) - 1) * 12
    canvas_w, canvas_h = img.size
    y = (canvas_h - total_height) // 2
    for (w, h), line in zip(line_metrics, lines, strict=True):
        x = (canvas_w - w) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += h + 12


def _render_card(card_index: int, name_en: str, name_kr: str) -> Image.Image:
    """Build the placeholder image for one card."""
    top = _hue_color(card_index)
    img = _vertical_gradient(_CANVAS_SIZE, top=top, bottom=_PALETTE_BOTTOM)
    # Decorative inner border — 12px from the edge, 2px wide. Helps the
    # placeholder look intentional rather than broken.
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [(12, 12), (_CANVAS_SIZE[0] - 12, _CANVAS_SIZE[1] - 12)],
        outline=(245, 240, 220),
        width=2,
    )
    _draw_centered_text(
        img,
        lines=[f"{card_index:02d}", name_en, name_kr],
    )
    return img


def _render_back() -> Image.Image:
    """Build the face-down back-art image.

    Solid-ish gradient with a centered VoiceSaju wordmark; matches the
    Screen 12 face-down hero so the flip animation has visual continuity.
    """
    img = _vertical_gradient(
        _CANVAS_SIZE, top=_BACK_PALETTE, bottom=_BACK_PALETTE_BOTTOM
    )
    draw = ImageDraw.Draw(img)
    # Frame
    draw.rectangle(
        [(12, 12), (_CANVAS_SIZE[0] - 12, _CANVAS_SIZE[1] - 12)],
        outline=(245, 240, 220),
        width=2,
    )
    # Inner diamond — pure decoration so the back doesn't read as blank.
    cx, cy = _CANVAS_SIZE[0] // 2, _CANVAS_SIZE[1] // 2
    diamond = [
        (cx, cy - 80),
        (cx + 80, cy),
        (cx, cy + 80),
        (cx - 80, cy),
    ]
    draw.polygon(diamond, outline=(245, 240, 220), width=2)
    _draw_centered_text(img, lines=["VoiceSaju"])
    return img


# ---------------------------------------------------------------------------
# Filesystem persistence
# ---------------------------------------------------------------------------


def _save_optimized_png(img: Image.Image, path: Path) -> bytes:
    """Write the image as an optimised PNG and return the bytes written.

    We constrain to PNG (vs WebP) so the script runs without libwebp at
    build time. ``optimize=True`` + ``compress_level=9`` keeps the file
    ≤30KB on the constant gradient + small text payload. The bytes are
    also handed back so the caller can hash them without re-reading.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Pillow returns nothing from save() — we round-trip through bytes
    # so the hash + size measurements match the on-disk artefact.
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=9)
    data = buf.getvalue()
    path.write_bytes(data)
    return data


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_all(cards_dir: Path = _CARDS_DIR) -> list[GeneratedArt]:
    """Generate the 22 face PNGs + 1 back PNG.

    Returns a list of :class:`GeneratedArt` rows in card_index order
    (the back art is appended last with ``card_index=None``).
    """
    results: list[GeneratedArt] = []
    for idx, name_en, name_kr in _MAJOR_ARCANA:
        img = _render_card(idx, name_en, name_kr)
        rel = f"{idx:02d}.png"
        path = cards_dir / rel
        data = _save_optimized_png(img, path)
        results.append(
            GeneratedArt(
                card_index=idx,
                r2_key=f"tarot/major/{idx:02d}.png",
                path=path,
                content_hash=_hash_bytes(data),
                byte_size=len(data),
            )
        )

    back_img = _render_back()
    back_path = cards_dir.parent / "back.png"
    back_data = _save_optimized_png(back_img, back_path)
    results.append(
        GeneratedArt(
            card_index=None,
            r2_key="tarot/back.png",
            path=back_path,
            content_hash=_hash_bytes(back_data),
            byte_size=len(back_data),
        )
    )
    return results


# ---------------------------------------------------------------------------
# Upload to R2 (or MockStorageAdapter under Phase-1)
# ---------------------------------------------------------------------------


async def upload_all(arts: list[GeneratedArt]) -> int:
    """Upload every entry in ``arts`` to the active storage adapter.

    Importing :class:`R2Client` lazily avoids dragging the SQLAlchemy
    + adapter stack into the ``--skip-upload`` codepath (so the script
    can be invoked in CI for "just generate the PNGs" without a real
    settings.toml).
    """
    from voicesaju.storage.r2_client import R2Client

    client = R2Client.from_settings()
    count = 0
    for art in arts:
        data = art.path.read_bytes()
        await client.put_object(art.r2_key, data)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Versioned URL helper (AC3)
# ---------------------------------------------------------------------------


def build_versioned_url(base_url: str, content_hash: str) -> str:
    """Append a 16-char content-hash query string to ``base_url``.

    Used by the frontend to cache-bust when DEP-06 art lands at the same
    R2 key. We slice to 16 chars (64 bits of entropy) to keep the URL
    short while still being collision-resistant for our 23-asset fleet.
    """
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}v={content_hash[:16]}"


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate 22 placeholder tarot card PNGs + 1 back PNG, "
            "then upload to the active storage adapter."
        )
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Generate PNGs only; do not call put_object.",
    )
    parser.add_argument(
        "--cards-dir",
        type=Path,
        default=_CARDS_DIR,
        help="Output directory for face PNGs (default: api/static/tarot/cards).",
    )
    args = parser.parse_args(argv)

    arts = generate_all(cards_dir=args.cards_dir)
    print(f"Generated {len(arts)} PNGs under {args.cards_dir.parent}")
    for art in arts:
        kind = "back" if art.card_index is None else f"card[{art.card_index:02d}]"
        print(
            f"  {kind:>10s}  {art.r2_key:30s}  "
            f"{art.byte_size:>6d} bytes  sha256:{art.content_hash[:16]}"
        )

    if args.skip_upload:
        print("--skip-upload set; not uploading.")
        return 0

    n = asyncio.run(upload_all(arts))
    print(f"Uploaded {n} objects via the active StorageAdapter.")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry
    sys.exit(_main())
