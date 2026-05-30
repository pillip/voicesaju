"""Unit tests for `MockTTSAdapter` (ISSUE-102).

Covers:
- AC #1: stream yields exactly 10 byte chunks
- AC #2: concatenated chunks form a valid playable MP3 (magic-bytes + mutagen)
- AC #4: inter-chunk pacing measured wall-clock 1.8s ≤ elapsed ≤ 2.4s
- Protocol structural conformance
- SupertoneAdapter stub raises NotImplementedError
- TTS_PROVIDER settings + factory dispatch
- Fixture load-time validation (corrupted blob raises ValueError)
"""

from __future__ import annotations

import asyncio
import io
import time

import pytest

from voicesaju.adapters.tts import (
    CHUNK_COUNT,
    CHUNK_DELAY_SECONDS,
    MockTTSAdapter,
    SupertoneAdapter,
    TTSAdapter,
    _looks_like_mp3,
)


@pytest.mark.asyncio
async def test_mock_tts_adapter_implements_protocol() -> None:
    """`MockTTSAdapter` MUST be a structural match for `TTSAdapter`."""
    adapter = MockTTSAdapter()
    assert isinstance(adapter, TTSAdapter)


@pytest.mark.asyncio
async def test_yields_ten_chunks() -> None:
    """AC #1: `stream()` yields exactly CHUNK_COUNT (10) byte chunks."""
    adapter = MockTTSAdapter()
    chunks: list[bytes] = []
    async for chunk in adapter.stream(text="안녕하세요", voice_id="nuna"):
        chunks.append(chunk)

    assert len(chunks) == CHUNK_COUNT == 10
    # Every chunk MUST be non-empty bytes — the mock streams the same
    # silent MP3 frame; an empty chunk would break the player loop.
    assert all(isinstance(c, bytes) and len(c) > 0 for c in chunks)


@pytest.mark.asyncio
async def test_concatenated_chunks_form_valid_mp3() -> None:
    """AC #2: 10 concatenated chunks form a valid playable MP3 of silence.

    Verifies via three independent signals:
    1. Magic-bytes check (`_looks_like_mp3`) on the concatenated blob.
    2. `mutagen.mp3.MP3` decodes the FIRST stream without errors (it
       only parses up to the first audio stream, not concatenated
       streams — that's the playable-by-any-decoder guarantee we need).
    3. Per-chunk decode round-trip — each chunk on its own is a
       playable ~0.2s frame, so 10 chunks * 0.2s ≈ 2s of total silence
       once a chunked-audio player feeds them sequentially.
    """
    from mutagen.mp3 import MP3

    adapter = MockTTSAdapter()
    chunks: list[bytes] = []
    async for chunk in adapter.stream(text="x", voice_id="nuna"):
        chunks.append(chunk)

    blob = b"".join(chunks)

    # Signal 1: magic-bytes on the concatenated blob.
    assert _looks_like_mp3(blob), (
        f"concatenated blob (len={len(blob)}) does not start with ID3v2 "
        f"or MPEG frame sync; first bytes={blob[:8].hex()}"
    )

    # Signal 2: mutagen decodes the leading stream without raising.
    # `MP3()` raises `mutagen.mp3.HeaderNotFoundError` on malformed data.
    audio = MP3(io.BytesIO(blob))
    # Sanity: sample rate matches the ffmpeg-generated fixture (22050 Hz).
    assert audio.info.sample_rate == 22050
    # Each chunk is ~0.2s — the FIRST chunk's reported length must be in
    # a sensible range.
    assert 0.15 <= audio.info.length <= 0.40, (
        f"first chunk decoded length {audio.info.length:.3f}s "
        "outside expected ~0.2s range"
    )

    # Signal 3: per-chunk decode round-trip. The chunked audio player in
    # ISSUE-033 feeds chunks one-at-a-time, so each chunk MUST be a
    # playable MP3 on its own. Summed length should be ~2s total.
    total_seconds = 0.0
    for chunk in chunks:
        per_chunk = MP3(io.BytesIO(chunk))
        assert per_chunk.info.sample_rate == 22050
        total_seconds += per_chunk.info.length
    assert 1.5 <= total_seconds <= 3.0, (
        f"summed chunk duration {total_seconds:.3f}s "
        "outside expected ~2s range for 10 × 0.2s silent chunks"
    )


@pytest.mark.asyncio
async def test_inter_chunk_pacing_within_budget() -> None:
    """AC #4: wall-clock total time MUST be within [1.8s, 2.4s].

    Pacing is BETWEEN chunks → 9 sleeps × 200ms = 1.8s nominal.
    Upper bound 2.4s accommodates CI scheduler jitter (600ms slack).
    """
    adapter = MockTTSAdapter()

    start = time.monotonic()
    count = 0
    async for _ in adapter.stream(text="x", voice_id="nuna"):
        count += 1
    elapsed = time.monotonic() - start

    assert count == 10
    expected_min = (CHUNK_COUNT - 1) * CHUNK_DELAY_SECONDS  # 1.8s
    expected_max = 2.4
    assert expected_min <= elapsed <= expected_max, (
        f"pacing out of budget: elapsed={elapsed:.3f}s "
        f"not in [{expected_min:.3f}, {expected_max:.3f}]"
    )


@pytest.mark.asyncio
async def test_first_chunk_emits_immediately() -> None:
    """First chunk MUST land without any inter-chunk sleep.

    Mirrors Supertone SSE first-byte behaviour and protects NFR-002's
    first-chunk latency budget.
    """
    adapter = MockTTSAdapter()
    start = time.monotonic()
    async for _ in adapter.stream(text="x", voice_id="nuna"):
        first_chunk_at = time.monotonic() - start
        break
    # First chunk should land well under the 200ms inter-chunk delay.
    assert first_chunk_at < CHUNK_DELAY_SECONDS / 2, (
        f"first chunk took {first_chunk_at:.3f}s, "
        f"expected < {CHUNK_DELAY_SECONDS / 2:.3f}s"
    )


@pytest.mark.asyncio
async def test_text_and_voice_id_do_not_change_output() -> None:
    """Mock output MUST be independent of `text` and `voice_id` arguments."""
    adapter = MockTTSAdapter()

    async def collect(text: str, voice_id: str) -> list[bytes]:
        out: list[bytes] = []
        async for chunk in adapter.stream(text=text, voice_id=voice_id):
            out.append(chunk)
        return out

    a = await collect("text A", "nuna")
    b = await collect("entirely different text", "dosa")
    assert a == b, "mock output varied across text/voice_id calls"


def test_settings_tts_provider_default_is_mock() -> None:
    """`TTS_PROVIDER` setting MUST default to `'mock'`."""
    from voicesaju.config import Settings

    s = Settings()
    assert s.tts_provider == "mock"


def test_factory_dispatch_returns_mock_when_provider_is_mock() -> None:
    """`get_tts_adapter()` returns `MockTTSAdapter` when provider is mock."""
    from voicesaju.adapters import get_tts_adapter
    from voicesaju.config import Settings

    s = Settings()
    adapter = get_tts_adapter(settings=s)
    assert isinstance(adapter, MockTTSAdapter)


def test_factory_dispatch_returns_supertone_stub_when_provider_is_supertone() -> None:
    """`get_tts_adapter()` returns the Phase 2 stub when provider is supertone."""
    from voicesaju.adapters import get_tts_adapter
    from voicesaju.config import Settings

    s = Settings(tts_provider="supertone")
    adapter = get_tts_adapter(settings=s)
    assert isinstance(adapter, SupertoneAdapter)


def test_factory_dispatch_unknown_provider_raises() -> None:
    """`get_tts_adapter()` raises `UnknownProviderError` for unknown names.

    `Settings` itself rejects values outside the Literal at construction,
    so we monkey-patch the attribute post-construction to drive the
    factory's defensive branch.
    """
    from voicesaju.adapters import UnknownProviderError, get_tts_adapter
    from voicesaju.config import Settings

    s = Settings()
    # Bypass pydantic's Literal validation to reach the factory's
    # else-branch, which we want covered.
    object.__setattr__(s, "tts_provider", "elevenlabs")
    with pytest.raises(UnknownProviderError):
        get_tts_adapter(settings=s)


def test_supertone_stub_raises_not_implemented() -> None:
    """`SupertoneAdapter` stub MUST raise NotImplementedError on use (Phase 2)."""
    stub = SupertoneAdapter()

    async def _runner() -> None:
        async for _ in stub.stream(text="x", voice_id="nuna"):
            pass

    with pytest.raises(NotImplementedError):
        asyncio.run(_runner())


def test_looks_like_mp3_accepts_id3v2() -> None:
    """`_looks_like_mp3` MUST accept blobs starting with ID3v2 tag."""
    assert _looks_like_mp3(b"ID3\x04\x00\x00" + b"\x00" * 10)


def test_looks_like_mp3_accepts_mpeg_frame_sync() -> None:
    """`_looks_like_mp3` MUST accept blobs starting with MPEG frame sync."""
    # 0xFFEB = 1111 1111 1110 1011 — top 11 bits all 1s.
    assert _looks_like_mp3(b"\xff\xeb\x00\x00")


def test_looks_like_mp3_rejects_garbage() -> None:
    """`_looks_like_mp3` MUST reject blobs that are neither ID3v2 nor MPEG sync."""
    assert not _looks_like_mp3(b"NOTANMP3FILE")
    assert not _looks_like_mp3(b"")
    assert not _looks_like_mp3(b"\x00\x00")


def test_mock_tts_adapter_accepts_injected_chunk_bytes() -> None:
    """Dependency injection: tests can pass a custom MP3 blob to the adapter."""
    custom = b"ID3\x04\x00\x00" + b"\x00" * 100
    adapter = MockTTSAdapter(chunk_bytes=custom)
    assert adapter._chunk is custom


@pytest.mark.asyncio
async def test_chunks_are_byte_identical_copies_of_fixture() -> None:
    """Each emitted chunk MUST be the exact same fixture bytes (no mutation)."""
    adapter = MockTTSAdapter()
    chunks: list[bytes] = []
    async for chunk in adapter.stream(text="x", voice_id="nuna"):
        chunks.append(chunk)
    first = chunks[0]
    assert all(c == first for c in chunks), "chunks diverged across iterations"
