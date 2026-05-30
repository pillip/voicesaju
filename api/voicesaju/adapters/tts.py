"""TTS adapter Protocol + Phase 1 mock implementation (ISSUE-102).

Phase 1 ships ``MockTTSAdapter`` which streams 10 pre-baked silent MP3
chunks at a realistic 200ms inter-chunk pacing. The pacing is intentional
— it exercises NFR-002 first-chunk latency budgets and the chunked audio
player from ISSUE-033 against realistic timing in tests without depending
on a real Supertone account.

``SupertoneAdapter`` is a Phase 2 stub — instantiating succeeds so the
app boots under ``TTS_PROVIDER=supertone``, but calling ``stream()``
raises ``NotImplementedError`` pointing at ISSUE-036.

PRD-Ref: FR-010 (streaming TTS), NFR-002 (first-chunk latency budget).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol, runtime_checkable

# Inter-chunk pacing. 200ms × 9 = 1.8s wall-clock for 10 chunks (sleep
# happens BETWEEN chunks, mirroring Anthropic/Supertone SSE behaviour
# where the first chunk lands immediately). Matched to ISSUE-033's
# chunked-audio-player timing assumptions and NFR-002's first-chunk
# latency budget.
CHUNK_DELAY_SECONDS: float = 0.2

# Number of chunks emitted per stream() call. Together with
# CHUNK_DELAY_SECONDS this yields ~2s of audio per request, matching a
# typical TTS-of-short-saju-utterance budget.
CHUNK_COUNT: int = 10

# MPEG audio frame sync. The first 11 bits are all 1s (`0xFF 0xE_` for
# MPEG-1/2/2.5). Some MP3s also carry an ID3v2 header (`b"ID3"`) before
# the first audio frame, so we accept either as "valid".
_ID3V2_MAGIC = b"ID3"
_MPEG_FRAME_SYNC_MASK = 0xFFE0
_MPEG_FRAME_SYNC_VALUE = 0xFFE0


def _looks_like_mp3(blob: bytes) -> bool:
    """Cheap header check: ID3v2 tag OR MPEG frame sync in the first bytes.

    Used at adapter load time so a corrupted/missing fixture surfaces
    loudly during module import instead of mid-stream.
    """
    if len(blob) < 4:
        return False
    if blob.startswith(_ID3V2_MAGIC):
        return True
    first_two = int.from_bytes(blob[:2], "big")
    return (first_two & _MPEG_FRAME_SYNC_MASK) == _MPEG_FRAME_SYNC_VALUE


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class TTSAdapter(Protocol):
    """Provider-agnostic streaming TTS client used by reading pipelines.

    The Protocol is ``runtime_checkable`` so ``isinstance(obj, TTSAdapter)``
    works in tests without requiring a concrete base class.
    """

    def stream(self, text: str, voice_id: str) -> AsyncIterator[bytes]:
        """Yield raw MP3 byte chunks for the given text.

        Implementations MUST yield in playback order. The contract does
        NOT specify whether implementations pace yields — the mock does
        (200ms between chunks), the real Supertone client will yield
        as fast as the SSE arrives.
        """
        ...


# ---------------------------------------------------------------------------
# Fixture loading + load-time validation
# ---------------------------------------------------------------------------


_FIXTURE_PATH: Path = Path(__file__).resolve().parent / "tts_fixtures" / "silent.mp3"


def _load_silent_chunk() -> bytes:
    """Read the bundled silent MP3 fixture once at import time.

    Raises:
        FileNotFoundError: when the fixture is missing — surfaces during
            module import so deploys with a broken bundle fail fast.
        ValueError: when the fixture exists but is not a recognisable MP3
            (no ID3v2 header AND no MPEG frame sync in the first 2 bytes).
    """
    if not _FIXTURE_PATH.is_file():
        raise FileNotFoundError(
            f"TTS fixture not found at {_FIXTURE_PATH}. "
            "Re-generate with `ffmpeg -f lavfi -i anullsrc=r=22050:cl=mono "
            "-t 0.2 -c:a libmp3lame -b:a 32k silent.mp3`."
        )
    blob = _FIXTURE_PATH.read_bytes()
    if not _looks_like_mp3(blob):
        raise ValueError(
            f"TTS fixture {_FIXTURE_PATH} is not a valid MP3 "
            "(no ID3v2 header and no MPEG frame sync in the first 2 bytes)."
        )
    return blob


# Read once at import — the fixture is small (~1.3 KB) and never changes
# at runtime. Tests that need a different fixture pass `chunk_bytes`
# to MockTTSAdapter directly.
_SILENT_CHUNK: bytes = _load_silent_chunk()


# ---------------------------------------------------------------------------
# MockTTSAdapter
# ---------------------------------------------------------------------------


class MockTTSAdapter:
    """Fixture-based streaming TTS for the Phase 1 PoC stack.

    Yields ``CHUNK_COUNT`` (10) copies of a pre-baked ~200ms silent MP3
    chunk with ``CHUNK_DELAY_SECONDS`` (0.2s) pacing between chunks.
    Total wall-clock time per ``stream()`` call: ~1.8s (9 inter-chunk
    sleeps), independent of ``text`` and ``voice_id``.

    Concatenating the 10 emitted chunks yields a valid playable MP3 of
    roughly 2s of silence — exercises the chunked-audio-player path in
    ISSUE-033 without burning Supertone credits.
    """

    def __init__(self, chunk_bytes: bytes | None = None) -> None:
        # Tests can inject a different fixture (e.g. a corrupted blob
        # for negative tests); production code always uses the module-
        # level fixture loaded at import.
        self._chunk = chunk_bytes if chunk_bytes is not None else _SILENT_CHUNK

    async def stream(self, text: str, voice_id: str) -> AsyncIterator[bytes]:
        """Stream ``CHUNK_COUNT`` MP3 chunks with ``CHUNK_DELAY_SECONDS`` pacing.

        ``text`` and ``voice_id`` are accepted to match the Protocol but
        do not influence output — the mock always returns the same
        silent chunks. The real Supertone client will branch on both.
        """
        # Sentinel reads so static analysers don't flag the params as
        # unused; also matches the Protocol's call shape during typing.
        _ = text
        _ = voice_id

        for idx in range(CHUNK_COUNT):
            if idx > 0:
                # Pacing happens BETWEEN chunks only, so 10 chunks
                # produce 9 sleeps. First chunk is emitted immediately
                # to mirror Supertone SSE first-byte behaviour.
                await asyncio.sleep(CHUNK_DELAY_SECONDS)
            yield self._chunk


# ---------------------------------------------------------------------------
# SupertoneAdapter — ISSUE-037 (structural) + ISSUE-036 (real key)
# ---------------------------------------------------------------------------


class SupertoneAdapter:
    """Real-Supertone adapter, structurally wired in ISSUE-037.

    ``stream()`` delegates to :func:`voicesaju.tts.supertone_client.synthesize_stream`
    which owns the httpx connection, sentence chunking, 429-backoff and
    first-chunk timeout. The adapter merely adapts the
    ``stream(text, voice_id) -> AsyncIterator[bytes]`` Protocol shape
    expected by the reading pipeline.

    Phase-1 vs Phase-2 (per ISSUE-037 spec):

    - ``TTS_PROVIDER=mock`` (default) — the adapter factory does not
      instantiate this class; ``MockTTSAdapter`` runs instead.
    - ``TTS_PROVIDER=supertone`` (Phase-2) — needs ``SUPERTONE_API_KEY``
      in the environment. The error is raised at *request* time (not
      import) so the app still boots without a key for canary or test
      processes that never call ``stream()``.
    """

    async def stream(self, text: str, voice_id: str) -> AsyncIterator[bytes]:
        # Defer the import so the rest of ``voicesaju.adapters`` does
        # not pay for httpx + the chunker at import time (the mock
        # path doesn't need them).
        from voicesaju.tts.supertone_client import synthesize_stream

        async def _single_fragment() -> AsyncIterator[str]:
            # The Protocol's ``text`` arg is a single completed string.
            # ``synthesize_stream`` consumes an async-iterable so wrap.
            yield text

        async for chunk in synthesize_stream(
            _single_fragment(),
            voice_id=voice_id,
        ):
            yield chunk.data


__all__ = [
    "CHUNK_COUNT",
    "CHUNK_DELAY_SECONDS",
    "MockTTSAdapter",
    "SupertoneAdapter",
    "TTSAdapter",
]
