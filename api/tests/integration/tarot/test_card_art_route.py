"""Integration tests for ``GET /api/v1/tarot/cards/{card_index}/art``
(ISSUE-055).

Covers AC2 of the issue: when the upload script has run, the frontend
can fetch a card-art URL and receive real PNG bytes. We exercise the
route end-to-end against the FastAPI ``TestClient`` with an injected
:class:`MockStorageAdapter` so the assertion doesn't depend on a real
R2 bucket.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from scripts.upload_tarot_art import generate_all
from voicesaju.adapters.storage import MockStorageAdapter
from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models import (  # noqa: F401 - register metadata
    Device,
    Profile,
    TarotCard,
    TarotDraw,
    User,
)
from voicesaju.main import create_app
from voicesaju.storage.r2_client import R2Client
from voicesaju.tarot.routers.cards_art import _get_r2_client


@pytest.fixture(autouse=True)
def _local_kek_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same minimal env shim the other tarot route tests use."""
    import base64

    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("STORAGE_PROVIDER", "mock")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


def _make_client(
    engine: AsyncEngine,
    *,
    storage_root: Path,
    seed_assets: bool = True,
) -> tuple[TestClient, MockStorageAdapter]:
    """Build a client wired to a fresh MockStorageAdapter.

    When ``seed_assets`` is True we pre-populate the storage with the
    23 generated PNGs — mirrors a post-upload-script state. When False
    we hand back an empty adapter so 404 paths can be exercised.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    adapter = MockStorageAdapter(root=storage_root)
    client_r2 = R2Client(adapter=adapter)

    if seed_assets:
        arts = generate_all(cards_dir=storage_root.parent / "cards-tmp")

        async def _seed() -> None:
            for art in arts:
                await client_r2.put_object(art.r2_key, art.path.read_bytes())

        asyncio.run(_seed())

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[_get_r2_client] = lambda: client_r2

    return TestClient(app), adapter


# ---------------------------------------------------------------------------
# AC2 — happy path
# ---------------------------------------------------------------------------


def test_get_card_art_returns_png_bytes(engine: AsyncEngine, tmp_path: Path) -> None:
    """GET /tarot/cards/0/art returns image/png with a non-empty body."""
    client, _ = _make_client(engine, storage_root=tmp_path / "storage")

    resp = client.get("/api/v1/tarot/cards/0/art")

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    body = resp.content
    # PNG magic bytes — sanity-check the wire payload is a real PNG.
    assert body[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(body) > 0


def test_get_card_art_works_for_all_22_indices(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """Every seeded card_index in 0..21 yields a PNG."""
    client, _ = _make_client(engine, storage_root=tmp_path / "storage")
    for idx in range(22):
        resp = client.get(f"/api/v1/tarot/cards/{idx}/art")
        assert resp.status_code == 200, f"idx={idx}: {resp.status_code}"
        assert resp.headers["content-type"] == "image/png"


# ---------------------------------------------------------------------------
# AC3 — cache-busting query param flips Cache-Control
# ---------------------------------------------------------------------------


def test_get_card_art_with_v_query_sets_immutable_cache(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """``?v=<hash>`` opts into year-long immutable caching."""
    client, _ = _make_client(engine, storage_root=tmp_path / "storage")

    resp = client.get("/api/v1/tarot/cards/0/art?v=abcdef0123456789")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_get_card_art_without_v_query_uses_short_cache(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """No ``v=`` → short cache so DEP-06 overwrites surface quickly."""
    client, _ = _make_client(engine, storage_root=tmp_path / "storage")

    resp = client.get("/api/v1/tarot/cards/0/art")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=300"


# ---------------------------------------------------------------------------
# 404 paths
# ---------------------------------------------------------------------------


def test_get_card_art_404_when_storage_empty(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """No object at the key → 404 (frontend can fall back to CSS art)."""
    client, _ = _make_client(
        engine, storage_root=tmp_path / "storage", seed_assets=False
    )

    resp = client.get("/api/v1/tarot/cards/0/art")
    assert resp.status_code == 404


def test_get_card_art_404_when_index_out_of_range(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """``card_index`` outside 0..21 → 404 before storage is touched."""
    client, _ = _make_client(engine, storage_root=tmp_path / "storage")

    resp = client.get("/api/v1/tarot/cards/99/art")
    assert resp.status_code == 404

    resp = client.get("/api/v1/tarot/cards/-1/art")
    # Negative ints don't match FastAPI's `int` path converter the same
    # way — FastAPI accepts negative ints, then our handler rejects.
    assert resp.status_code in {404, 422}
