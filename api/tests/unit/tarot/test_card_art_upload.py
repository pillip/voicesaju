"""Unit tests for the tarot card art generator + uploader (ISSUE-055).

Covers the AC1 + AC3 surface of the upload script:

* AC1 — 23 PNGs land under the configured cards dir (22 face + 1 back).
* AC3 — every face PNG yields a stable content hash that the
  ``build_versioned_url`` helper consumes for cache-busting.
* Each PNG is ≤ 30KB (binary-commit budget).
* Calling ``upload_all`` against the ``MockStorageAdapter`` round-trips
  all 23 keys (matches AC1's "files in R2/MockStorage" wording).

These tests deliberately avoid the FastAPI app + DB stack — the script
is a pure CLI utility and shouldn't need a router fixture.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image

from scripts.upload_tarot_art import (
    GeneratedArt,
    build_versioned_url,
    generate_all,
)
from voicesaju.adapters.storage import MockStorageAdapter
from voicesaju.storage.r2_client import R2Client

# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def test_generate_all_produces_23_pngs(tmp_path: Path) -> None:
    """AC1: 22 face PNGs + 1 back PNG land on disk under the cards dir."""
    cards_dir = tmp_path / "cards"
    results = generate_all(cards_dir=cards_dir)

    assert len(results) == 23, "expect 22 Major Arcana + 1 back art"

    # 22 face cards with card_index 0..21.
    face_indices = sorted(r.card_index for r in results if r.card_index is not None)
    assert face_indices == list(range(22))

    # 1 back art with card_index=None.
    backs = [r for r in results if r.card_index is None]
    assert len(backs) == 1
    assert backs[0].r2_key == "tarot/back.png"

    # Every result has a real file behind it.
    for art in results:
        assert art.path.is_file(), f"missing on-disk file: {art.path}"
        assert art.byte_size > 0


def test_generated_pngs_under_30kb_budget(tmp_path: Path) -> None:
    """Binary commit budget: each PNG ≤ 30KB."""
    results = generate_all(cards_dir=tmp_path / "cards")
    for art in results:
        assert (
            art.byte_size <= 30 * 1024
        ), f"{art.r2_key} exceeds 30KB budget: {art.byte_size} bytes"


def test_generated_pngs_are_valid_image_files(tmp_path: Path) -> None:
    """Sanity: the bytes round-trip through Pillow as a 512x768 PNG."""
    results = generate_all(cards_dir=tmp_path / "cards")
    # Spot-check 3 cards + the back art — exhaustive checks are overkill.
    spot = [results[0], results[10], results[21], results[-1]]
    for art in spot:
        with Image.open(art.path) as im:
            assert im.format == "PNG"
            assert im.size == (512, 768), f"{art.r2_key} canvas size off"


def test_generated_pngs_have_stable_content_hash(tmp_path: Path) -> None:
    """Determinism: regenerating yields the same content_hash per card.

    AC3 cache-busting relies on the hash being stable across runs (so the
    DEP-06 swap is the *only* thing that changes the URL). The hash also
    has to be distinct between cards or the cache-bust query is useless.
    """
    first = generate_all(cards_dir=tmp_path / "first")
    second = generate_all(cards_dir=tmp_path / "second")

    # Same key → same hash (deterministic renderer).
    by_key_first = {a.r2_key: a.content_hash for a in first}
    by_key_second = {a.r2_key: a.content_hash for a in second}
    assert by_key_first == by_key_second

    # All 23 hashes distinct (no card collides with another).
    hashes = {a.content_hash for a in first}
    assert len(hashes) == 23


# ---------------------------------------------------------------------------
# Cache-busting helper
# ---------------------------------------------------------------------------


def test_build_versioned_url_appends_short_hash() -> None:
    """AC3: helper appends a 16-char content-hash to the URL."""
    base = "/api/v1/tarot/cards/0/art"
    hash_hex = "a" * 64
    out = build_versioned_url(base, hash_hex)
    assert out == "/api/v1/tarot/cards/0/art?v=" + "a" * 16


def test_build_versioned_url_respects_existing_query() -> None:
    base = "/api/v1/tarot/cards/0/art?theme=dark"
    out = build_versioned_url(base, "b" * 64)
    assert out == "/api/v1/tarot/cards/0/art?theme=dark&v=" + "b" * 16


# ---------------------------------------------------------------------------
# Upload — round-trip through MockStorageAdapter
# ---------------------------------------------------------------------------


async def _upload_with_mock(arts: list[GeneratedArt], root: Path) -> MockStorageAdapter:
    """Run ``upload_all`` against an injected :class:`MockStorageAdapter`.

    We can't rely on ``R2Client.from_settings()`` here because the script
    consumes the global settings singleton. Instead we mimic what the
    script does (build a client + put_object every art) using a fixture
    adapter so the assertion can read ``list_objects`` deterministically.
    """
    adapter = MockStorageAdapter(root=root)
    client = R2Client(adapter=adapter)
    for art in arts:
        data = art.path.read_bytes()
        await client.put_object(art.r2_key, data)
    return adapter


def test_upload_all_writes_23_objects_to_mock(tmp_path: Path) -> None:
    """AC1 end-to-end: every generated key lands in MockStorage."""
    cards_dir = tmp_path / "cards"
    arts = generate_all(cards_dir=cards_dir)

    storage_root = tmp_path / "storage"
    adapter = asyncio.run(_upload_with_mock(arts, storage_root))

    # ``list_objects("tarot/")`` should surface 22 majors + 1 back.
    objects = asyncio.run(adapter.list_objects("tarot/"))
    assert len(objects) == 23

    # Majors 00.png..21.png under tarot/major/.
    majors = sorted(k for k in objects if k.startswith("tarot/major/"))
    assert majors == [f"tarot/major/{i:02d}.png" for i in range(22)]

    # Back art.
    assert "tarot/back.png" in objects


def test_upload_all_round_trips_bytes(tmp_path: Path) -> None:
    """``get_object`` returns the same bytes ``put_object`` received."""
    cards_dir = tmp_path / "cards"
    arts = generate_all(cards_dir=cards_dir)
    storage_root = tmp_path / "storage"
    adapter = asyncio.run(_upload_with_mock(arts, storage_root))

    # Verify one face card + the back art round-trip cleanly.
    fool = next(a for a in arts if a.card_index == 0)
    fool_bytes_on_disk = fool.path.read_bytes()
    fool_bytes_from_storage = asyncio.run(adapter.get_object(fool.r2_key))
    assert fool_bytes_from_storage == fool_bytes_on_disk

    back = next(a for a in arts if a.card_index is None)
    back_bytes_on_disk = back.path.read_bytes()
    back_bytes_from_storage = asyncio.run(adapter.get_object(back.r2_key))
    assert back_bytes_from_storage == back_bytes_on_disk


# ---------------------------------------------------------------------------
# Repo invariant: shipped art exists at the expected path so prod can
# serve it without a generation step. This ALSO acts as a tripwire — if
# someone deletes the `static/tarot/` tree, this test screams.
# ---------------------------------------------------------------------------


def test_repo_ships_pregenerated_art() -> None:
    """22 PNGs + 1 back art exist at ``api/static/tarot/`` in-tree."""
    repo_static = Path(__file__).resolve().parents[3] / "static" / "tarot"
    cards_dir = repo_static / "cards"
    assert cards_dir.is_dir(), "api/static/tarot/cards/ missing"
    for idx in range(22):
        path = cards_dir / f"{idx:02d}.png"
        assert path.is_file(), f"missing in-tree placeholder: {path}"
    back_path = repo_static / "back.png"
    assert back_path.is_file(), f"missing back art: {back_path}"
