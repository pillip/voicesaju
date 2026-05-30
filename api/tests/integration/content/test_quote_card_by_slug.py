"""Integration tests for ``GET /api/v1/quote-cards/by-slug/{slug}`` (ISSUE-060).

Backs the Next.js OG route handler ``/api/og/[slug]`` — the route handler
calls this endpoint to learn whether the OG image has been baked and
which R2 key to redirect to.

AC coverage (mirrors ISSUE-060 + AP-43 spec):

* Existing slug + ``og_status='baked'`` → 200 with the full payload
  including the R2 key.
* Existing slug + ``og_status='pending'`` → 200 with ``og_r2_key=None``
  so the route handler knows to fall back to inline ``@vercel/og``.
* Existing slug + ``og_status='failed'`` → same 200 + None shape.
* Unknown slug → 404 (AC #3).
* No auth required — the slug itself is the capability.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models import (  # noqa: F401  (registered on metadata)
    QuoteCard,
    Reading,
    TarotCard,
    TarotDraw,
    User,
)
from voicesaju.main import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Per-test SQLite engine with the full ORM schema reflected."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


def _make_client(engine: AsyncEngine) -> TestClient:
    """Build a TestClient with DB override. No auth needed for this endpoint."""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    return TestClient(app)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_tarot_quote_card(
    engine: AsyncEngine,
    *,
    slug: str,
    og_status: str = "baked",
    og_r2_key: str | None = "og/abc-123.png",
    category: str = "tarot",
    character_key: str = "dosa",
    quote_text: str = "운명은 네 손 안에 있다.",
) -> str:
    """Insert a tarot-source quote card; return its id.

    Each quote_card needs a parent tarot_draws or readings row (XOR via
    ``source_kind``). We use the tarot path because it doesn't require
    the entitlement / payment plumbing that ``readings`` does.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        user_id = str(uuid.uuid4())
        s.add(User(id=user_id, kakao_sub=f"kakao:{user_id}"))
        await s.flush()

        card_id = str(uuid.uuid4())
        s.add(
            TarotCard(
                id=card_id,
                card_index=0,
                name_kr="바보",
                name_en="The Fool",
                meaning_kr="새로운 시작.",
                art_key="00_the_fool",
            )
        )
        await s.flush()

        draw_id = str(uuid.uuid4())
        s.add(
            TarotDraw(
                id=draw_id,
                user_id=user_id,
                card_id=card_id,
                card_index=0,
                date_kst=date(2026, 5, 30),
            )
        )
        await s.flush()

        qc_id = str(uuid.uuid4())
        s.add(
            QuoteCard(
                id=qc_id,
                source_kind="tarot",
                tarot_id=draw_id,
                reading_id=None,
                category=category,
                quote_text=quote_text,
                character_key=character_key,
                share_slug=slug,
                og_status=og_status,
                og_r2_key=og_r2_key,
            )
        )
        await s.commit()
        return qc_id


# ---------------------------------------------------------------------------
# AC 1 — baked card returns full payload
# ---------------------------------------------------------------------------


def test_by_slug_returns_baked_payload(engine: AsyncEngine) -> None:
    """AC: existing slug + baked status → 200 with R2 key + all metadata."""
    qc_id = asyncio.run(
        _seed_tarot_quote_card(
            engine,
            slug="abc123XYZdef",
            og_status="baked",
            og_r2_key="og/abc-123.png",
            category="tarot",
            character_key="dosa",
            quote_text="운명은 네 손 안에 있다.",
        )
    )

    client = _make_client(engine)
    resp = client.get("/api/v1/quote-cards/by-slug/abc123XYZdef")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quote_card_id"] == qc_id
    assert body["category"] == "tarot"
    assert body["character_key"] == "dosa"
    assert body["quote_text"] == "운명은 네 손 안에 있다."
    assert body["og_status"] == "baked"
    assert body["og_r2_key"] == "og/abc-123.png"


# ---------------------------------------------------------------------------
# AC 2 — pending card returns null r2 key (signals fallback to caller)
# ---------------------------------------------------------------------------


def test_by_slug_returns_pending_with_null_r2(engine: AsyncEngine) -> None:
    """og_status=pending → 200 with og_r2_key=null so route handler falls back."""
    asyncio.run(
        _seed_tarot_quote_card(
            engine,
            slug="pendingSlug1",
            og_status="pending",
            og_r2_key=None,
        )
    )

    client = _make_client(engine)
    resp = client.get("/api/v1/quote-cards/by-slug/pendingSlug1")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["og_status"] == "pending"
    assert body["og_r2_key"] is None


def test_by_slug_returns_failed_with_null_r2(engine: AsyncEngine) -> None:
    """og_status=failed → same 200 + null shape as pending.

    The bake worker (ISSUE-058) flips ``failed`` after retries exhaust.
    From the route handler's perspective failed and pending are
    indistinguishable — both fall back to inline ``@vercel/og``.
    """
    asyncio.run(
        _seed_tarot_quote_card(
            engine,
            slug="failedSlugX9",
            og_status="failed",
            og_r2_key=None,
        )
    )

    client = _make_client(engine)
    resp = client.get("/api/v1/quote-cards/by-slug/failedSlugX9")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["og_status"] == "failed"
    assert body["og_r2_key"] is None


# ---------------------------------------------------------------------------
# AC 3 — unknown slug returns 404
# ---------------------------------------------------------------------------


def test_by_slug_unknown_returns_404(engine: AsyncEngine) -> None:
    """AC #3: unknown slug → 404 so the social crawler / OG route 404s too."""
    client = _make_client(engine)
    resp = client.get("/api/v1/quote-cards/by-slug/doesNotExist1")
    assert resp.status_code == 404
    body = resp.json()
    assert "not found" in body["detail"].lower()


# ---------------------------------------------------------------------------
# AC 4 — endpoint is unauthenticated (no Authorization header)
# ---------------------------------------------------------------------------


def test_by_slug_no_auth_required(engine: AsyncEngine) -> None:
    """The share endpoint is intentionally public — slug IS the capability.

    No Authorization header in the request; we still get 200. This is
    the load-bearing assertion for FR-020's "shareable URL" semantics:
    the social crawler (Facebook / Kakao / Twitter) hits this endpoint
    without any session cookie.
    """
    asyncio.run(
        _seed_tarot_quote_card(
            engine,
            slug="publicSlug12",
            og_status="baked",
            og_r2_key="og/public.png",
        )
    )
    client = _make_client(engine)
    # No headers at all — explicit absence of auth.
    resp = client.get("/api/v1/quote-cards/by-slug/publicSlug12")
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "category,character_key",
    [
        ("love", "nuna"),
        ("work", "nuna"),
        ("money", "nuna"),
        ("tarot", "dosa"),
    ],
)
def test_by_slug_returns_each_category_character_combo(
    engine: AsyncEngine, category: str, character_key: str
) -> None:
    """The OG image render depends on category × character_key — make sure
    the endpoint echoes both faithfully across the four real combos."""
    asyncio.run(
        _seed_tarot_quote_card(
            engine,
            slug=f"slug-{category[:3]}-{character_key[:3]}",
            og_status="baked",
            og_r2_key=f"og/{category}-{character_key}.png",
            category=category,
            character_key=character_key,
        )
    )
    client = _make_client(engine)
    resp = client.get(
        f"/api/v1/quote-cards/by-slug/slug-{category[:3]}-{character_key[:3]}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == category
    assert body["character_key"] == character_key
