"""Integration tests for OG bake v2 (ISSUE-095).

Covers the QuoteCard v2 spec applied to the Pillow worker:

* AC2 — category=money → 1080×1920 PNG, top-edge pixel ≈ ``#B68B3F``
  (±2 per channel for Pillow rendering tolerance).
* Per-category border colour at the top edge midpoint for love/work/
  money/tarot (regression guard for the canvas frame).
* Layout-JSON drift guard — Pillow reads the same constants as the
  TS mirror, so a hex change in ``og/layout_v2.json`` flips both sides
  together.

v1 tests in ``test_og_bake.py`` keep covering the legacy palette so the
``NEXT_PUBLIC_QUOTE_CARD_V2=false`` rollback path stays guaranteed.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from io import BytesIO

import pytest
import pytest_asyncio
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.adapters.storage import MockStorageAdapter
from voicesaju.db.base import Base
from voicesaju.db.models.free_tokens import FreeToken
from voicesaju.db.models.quote_cards import QuoteCard
from voicesaju.db.models.readings import Reading
from voicesaju.db.models.users import User
from voicesaju.jobs.og_bake import (
    OG_CANVAS_SIZE,
    V2_BORDER_COLORS,
    V2_CANVAS_BACKGROUND,
    og_bake,
)
from voicesaju.storage.r2_client import R2Client

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _enable_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    """All tests in this module exercise the v2 layout — opt the worker in."""
    monkeypatch.setenv("QUOTE_CARD_V2", "true")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_quote_card(
    engine: AsyncEngine,
    *,
    category: str = "love",
    character_key: str = "nuna",
    quote_text: str = "오늘은 마음이 가는 곳에 답이 있다",
    tag: str = "og-bake-v2",
) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        user = User(kakao_sub=f"kakao:{tag}-{uuid.uuid4()}")
        s.add(user)
        await s.flush()
        token = FreeToken(user_id=user.id, kind="signup_grant")
        s.add(token)
        await s.flush()
        reading = Reading(
            user_id=user.id,
            category=category,
            entitlement_kind="free_token",
            free_token_id=token.id,
            character_key=character_key,
            status="completed",
        )
        s.add(reading)
        await s.flush()
        card = QuoteCard(
            reading_id=reading.id,
            source_kind="reading",
            quote_text=quote_text,
            category=category,
            character_key=character_key,
            share_slug=f"slug-{tag}-{uuid.uuid4()}",
        )
        s.add(card)
        await s.commit()
        await s.refresh(card)
        return str(card.id)


# ---------------------------------------------------------------------------
# v2 layout constants are exported from the worker
# ---------------------------------------------------------------------------


def test_v2_constants_match_spec() -> None:
    """The Python worker MUST publish the v2 colours the issue specifies."""
    assert V2_BORDER_COLORS == {
        "love": (0xB7, 0x41, 0x4B),
        "work": (0x16, 0x34, 0x4E),
        "money": (0xB6, 0x8B, 0x3F),
        "tarot": (0x5A, 0x36, 0x66),
    }
    # hanji-800 canvas — the v2 background, NOT the v1 per-category fill.
    assert V2_CANVAS_BACKGROUND == (0x1A, 0x12, 0x08)


# ---------------------------------------------------------------------------
# AC2 — money produces 1080×1920 PNG with #B68B3F top-edge pixel (±2)
# ---------------------------------------------------------------------------


def _channels_within(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    *,
    tolerance: int,
) -> bool:
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected, strict=True))


@pytest.mark.asyncio
async def test_og_bake_v2_money_top_edge_is_brass(
    engine: AsyncEngine, tmp_path
) -> None:
    """AC2: category=money → 1080×1920 PNG, top-edge pixel ≈ #B68B3F."""
    card_id = await _seed_quote_card(engine, category="money", tag="ac2-v2-money")
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        await og_bake(card_id, session=s, r2=r2)
        await s.commit()

    raw = await adapter.get_object(f"og/{card_id}.png")
    img = Image.open(BytesIO(raw)).convert("RGB")
    assert img.size == OG_CANVAS_SIZE  # (1080, 1920)

    # Top edge midpoint at y=2 (well inside the border stroke even at the
    # thinnest 8 px width). x=540 is the dead centre of the canvas so we
    # land in the middle of the brass-coloured border stroke.
    top_pixel = img.getpixel((540, 2))
    assert _channels_within(top_pixel, (0xB6, 0x8B, 0x3F), tolerance=2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "category, expected_rgb",
    [
        ("love", (0xB7, 0x41, 0x4B)),
        ("work", (0x16, 0x34, 0x4E)),
        ("money", (0xB6, 0x8B, 0x3F)),
        ("tarot", (0x5A, 0x36, 0x66)),
    ],
)
async def test_og_bake_v2_top_edge_per_category(
    engine: AsyncEngine,
    tmp_path,
    category: str,
    expected_rgb: tuple[int, int, int],
) -> None:
    """Regression guard: every category renders the right border colour."""
    card_id = await _seed_quote_card(engine, category=category, tag=f"ac-v2-{category}")
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        await og_bake(card_id, session=s, r2=r2)
        await s.commit()

    raw = await adapter.get_object(f"og/{card_id}.png")
    img = Image.open(BytesIO(raw)).convert("RGB")
    assert img.size == OG_CANVAS_SIZE

    top_pixel = img.getpixel((540, 2))
    assert _channels_within(top_pixel, expected_rgb, tolerance=2), (
        f"top edge for {category} expected ~{expected_rgb}, got {top_pixel}"
    )


@pytest.mark.asyncio
async def test_og_bake_v2_canvas_interior_uses_hanji_background(
    engine: AsyncEngine, tmp_path
) -> None:
    """The interior canvas (inside the border) is hanji-800 (#1A1208)."""
    card_id = await _seed_quote_card(engine, category="love", tag="ac-v2-bg")
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        await og_bake(card_id, session=s, r2=r2)
        await s.commit()

    raw = await adapter.get_object(f"og/{card_id}.png")
    img = Image.open(BytesIO(raw)).convert("RGB")
    # Sample a point well inside the border, above the quote text band:
    # x=120 (inside the 96px padding + 8px border), y=400 (top quarter,
    # avoiding the quote text vertically centered around y=960).
    interior = img.getpixel((120, 400))
    assert _channels_within(interior, (0x1A, 0x12, 0x08), tolerance=8), (
        f"interior expected hanji-800, got {interior}"
    )


@pytest.mark.asyncio
async def test_og_bake_v2_row_status_baked(engine: AsyncEngine, tmp_path) -> None:
    """The row still flips pending → baked after a v2 render."""
    card_id = await _seed_quote_card(engine, category="tarot", tag="ac-v2-status")
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        await og_bake(card_id, session=s, r2=r2)
        await s.commit()

    async with maker() as s:
        row = (
            await s.execute(select(QuoteCard).where(QuoteCard.id == card_id))
        ).scalar_one()
        assert row.og_status == "baked"
        assert row.og_r2_key == f"og/{card_id}.png"


@pytest.mark.asyncio
async def test_og_bake_v2_seal_corner_has_vermilion_fill(
    engine: AsyncEngine, tmp_path
) -> None:
    """The bottom-right seal block paints a vermilion patch (~#9B2A1A).

    We sample inside the seal's geometric centre (computed from the
    canvas + margin + size constants the worker exports). Pillow font
    hinting can paint the hanja over part of this patch, so we sample
    a point near the seal corner BUT outside the central glyph.
    """
    card_id = await _seed_quote_card(engine, category="tarot", tag="ac-v2-seal")
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        await og_bake(card_id, session=s, r2=r2)
        await s.commit()

    raw = await adapter.get_object(f"og/{card_id}.png")
    img = Image.open(BytesIO(raw)).convert("RGB")

    # The seal sits at bottom-right with size 168 and margin 96. The
    # tilt is a thin rotation so the bounding box around (840, 1656) →
    # (1008, 1824) contains vermilion fill near the corners. Sample
    # 16 px inside the bounding box top-left corner.
    seal_sample = img.getpixel((856, 1672))
    # Tolerance is wide because rotation produces sub-pixel blending at
    # the seal edge — we only need to confirm the patch is unambiguously
    # red, not the hanji background.
    r, g, b = seal_sample
    assert r > g and r > b and r > 0x60, (
        f"seal sample at (856, 1672) should be vermilion-ish, got {seal_sample}"
    )
