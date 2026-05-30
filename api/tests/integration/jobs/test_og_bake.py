"""Integration tests for the OG image bake worker (ISSUE-058).

Covers:

* AC1 — ``og_status='pending'`` → worker → 1080×1920 PNG in storage,
  ``og_status`` flips to ``'baked'`` and ``og_r2_key`` is set.
* AC2 — ``category='love'`` produces a background that matches the
  A-06 pink hex (``#FFB6C1``). We sample the top-left pixel since the
  bake uses a single-tone background for the persona panel.
* AC3 — three transient failures drive ``og_status`` to ``'failed'``;
  the worker swallows the exception so the queue stays drained.

The MockStorageAdapter is rooted at the per-test ``tmp_path`` so
artefacts don't leak between cases.
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
    CATEGORY_BACKGROUNDS,
    OG_CANVAS_SIZE,
    og_bake,
)
from voicesaju.storage.r2_client import R2Client

pytestmark = pytest.mark.integration


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
    quote_text: str = "오늘의 운세는 빛난다",
    tag: str = "og-bake",
) -> str:
    """Seed user → free_token → reading → quote_card; return card id."""
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
# AC1 — bake produces 1080×1920 PNG and flips the row to baked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_og_bake_writes_1080x1920_png_and_updates_row(
    engine: AsyncEngine, tmp_path
) -> None:
    card_id = await _seed_quote_card(engine, category="love", tag="ac1-shape")
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        await og_bake(card_id, session=s, r2=r2)
        await s.commit()

    expected_key = f"og/{card_id}.png"
    raw = await adapter.get_object(expected_key)
    img = Image.open(BytesIO(raw))
    assert img.format == "PNG"
    assert img.size == OG_CANVAS_SIZE  # (1080, 1920)

    async with maker() as s:
        row = (
            await s.execute(select(QuoteCard).where(QuoteCard.id == card_id))
        ).scalar_one()
        assert row.og_status == "baked"
        assert row.og_r2_key == expected_key


# ---------------------------------------------------------------------------
# AC2 — category=love → pink background (#FFB6C1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "category, expected_rgb",
    [
        ("love", (0xFF, 0xB6, 0xC1)),
        ("work", (0x87, 0xCE, 0xEB)),
        ("money", (0xFF, 0xD7, 0x00)),
        ("tarot", (0x93, 0x70, 0xDB)),
    ],
)
async def test_og_bake_background_matches_category(
    engine: AsyncEngine,
    tmp_path,
    category: str,
    expected_rgb: tuple[int, int, int],
) -> None:
    card_id = await _seed_quote_card(engine, category=category, tag=f"ac2-{category}")
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        await og_bake(card_id, session=s, r2=r2)
        await s.commit()

    raw = await adapter.get_object(f"og/{card_id}.png")
    img = Image.open(BytesIO(raw)).convert("RGB")
    # Sample a top-left corner pixel — the background fills the canvas
    # before any persona/quote ink lands, so the corner is guaranteed
    # background.
    assert img.getpixel((4, 4)) == expected_rgb
    # And confirm the registry table is canonical.
    assert CATEGORY_BACKGROUNDS[category] == expected_rgb


# ---------------------------------------------------------------------------
# AC3 — three transient failures → og_status='failed'
# ---------------------------------------------------------------------------


class _FlakyAdapter:
    """Storage adapter that raises ``OSError`` on every ``put_object``.

    Mirrors the public StorageAdapter Protocol so :class:`R2Client`
    accepts it. We don't subclass — duck-typing via the runtime-checked
    Protocol is enough.
    """

    def __init__(self) -> None:
        self.put_attempts = 0

    async def put_object(self, key: str, data: bytes) -> str:
        self.put_attempts += 1
        raise OSError("simulated storage outage")

    async def get_object(self, key: str) -> bytes:  # pragma: no cover - unused
        raise KeyError(key)

    async def list_objects(self, prefix: str) -> list[str]:  # pragma: no cover
        return []

    async def delete_object(self, key: str) -> None:  # pragma: no cover
        return None


@pytest.mark.asyncio
async def test_og_bake_marks_failed_after_three_retries(
    engine: AsyncEngine,
) -> None:
    card_id = await _seed_quote_card(engine, tag="ac3-fail")
    flaky = _FlakyAdapter()
    r2 = R2Client(adapter=flaky)  # type: ignore[arg-type]
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        # Job swallows the failure and persists the failed state so
        # the queue doesn't poison-loop.
        await og_bake(card_id, session=s, r2=r2)
        await s.commit()

    assert flaky.put_attempts == 3

    async with maker() as s:
        row = (
            await s.execute(select(QuoteCard).where(QuoteCard.id == card_id))
        ).scalar_one()
        assert row.og_status == "failed"
        assert row.og_r2_key is None


@pytest.mark.asyncio
async def test_og_bake_unknown_card_id_is_noop(engine: AsyncEngine, tmp_path) -> None:
    """An id with no row should log + return without raising.

    Mirrors the audio-finalize guard pattern — workers must be safe to
    retry across DB drops so a missing parent row degrades gracefully.
    """
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        await og_bake(str(uuid.uuid4()), session=s, r2=r2)
        await s.commit()

    # Nothing should have been uploaded.
    assert await adapter.list_objects("og/") == []
