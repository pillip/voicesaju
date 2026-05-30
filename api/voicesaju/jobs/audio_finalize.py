"""``finalize_audio`` job (ISSUE-038, Phase-1).

Stitches the per-sentence MP3 chunks for a reading into a single
``main.mp3``, uploads to the canonical ``audio/readings/<id>/main.mp3``
key, deletes the chunks, and persists metadata back to
``reading_audio``.

Phase-1 vs Phase-2:

- **Phase-1 stitch strategy** — naïve binary concat (``b"".join(chunks)``)
  of the silent MP3 chunks from ``MockTTSAdapter``. MPEG-1 Layer 3
  streams are concat-safe at the byte level for our silent fixtures
  (each chunk is a complete playable frame), so the player from
  ISSUE-033 keeps treating the result as a continuous stream.
- **Phase-2 stitch strategy** — real Supertone audio needs proper
  re-muxing (LAME tag fixup + frame-aligned splicing). The real path
  shells out to ``ffmpeg`` via ``ffmpeg-python concat`` once
  ``STORAGE_PROVIDER=r2`` is wired. For Phase-1 we explicitly raise
  ``NotImplementedError`` if the caller asks for the ``r2`` provider
  with no ``ffmpeg`` available, so the gap surfaces loudly.

PRD-Ref: FR-028, Architecture §8.4.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.adapters.storage import content_sha256
from voicesaju.config import Settings, get_settings
from voicesaju.db.models.reading_audio import ReadingAudio
from voicesaju.storage.r2_client import R2Client

# Phase-1 default duration for the silent-MP3 chunks. The real path
# (Phase-2) will compute this from the audio decoder; for Phase-1 the
# pipeline (ISSUE-039) passes the real ``duration_ms`` it measured
# during streaming so we don't trip the FR-007 60-120s CHECK.
DEFAULT_PLACEHOLDER_DURATION_MS: int = 60_000


@dataclass(slots=True, frozen=True)
class AudioFinalizeResult:
    """Return value of :func:`finalize_audio`.

    Lets the worker log structured success metrics and lets unit tests
    assert on the persisted shape without re-querying the DB.
    """

    reading_id: str
    r2_url: str
    r2_key: str
    content_hash: str
    file_size_bytes: int
    duration_ms: int
    chunks_deleted: int


async def finalize_audio(
    reading_id: str,
    *,
    session: AsyncSession,
    duration_ms: int = DEFAULT_PLACEHOLDER_DURATION_MS,
    r2: R2Client | None = None,
    settings: Settings | None = None,
) -> AudioFinalizeResult:
    """Stitch per-sentence chunks → ``main.mp3`` and persist metadata.

    Args:
        reading_id: Target reading id; chunks live under
            ``audio/readings/<reading_id>/chunks/``.
        session: SQLAlchemy async session. Caller manages the
            transaction boundary so the worker can be composed with
            the rest of the pipeline's writes (FR-028 atomic update).
        duration_ms: Measured duration of the stitched audio. The
            pipeline (ISSUE-039) knows this from the streaming step;
            defaults to ``DEFAULT_PLACEHOLDER_DURATION_MS`` so unit
            tests don't have to thread it through.
        r2: Storage client. If ``None``, one is constructed from
            ``settings`` — tests inject a custom one over
            ``MockStorageAdapter(tmp_path)``.
        settings: ``Settings`` override. ``r2 is not None`` already
            short-circuits the provider read; this is only used to
            decide the stitch strategy (mock-concat vs ffmpeg).

    Returns:
        :class:`AudioFinalizeResult` with the persisted metadata.

    Raises:
        ValueError: no chunks found for *reading_id*.
        NotImplementedError: real R2 path requested but ``ffmpeg`` is
            missing (Phase-2 prerequisite).
    """
    settings = settings or get_settings()
    r2 = r2 or R2Client.from_settings(settings=settings)

    # 1. Pull every chunk in upload order. ``list_chunks`` returns
    #    keys sorted lexicographically — we pad seq numbers in
    #    ``R2Client.put_chunk`` so the sort gives us source order.
    chunk_keys = await r2.list_chunks(reading_id)
    if not chunk_keys:
        raise ValueError(
            f"finalize_audio: no chunks found for reading_id={reading_id!r}"
        )
    chunks_data: list[bytes] = []
    for key in chunk_keys:
        chunks_data.append(await r2.get_object(key))

    # 2. Stitch. Strategy depends on the configured storage provider —
    #    the Phase-2 R2 path needs real re-muxing, the Phase-1 mock
    #    path concats the silent MP3 frames byte-wise.
    stitched = _stitch(
        chunks_data,
        storage_provider=settings.storage_provider,
    )

    # 3. Upload main.mp3.
    main_key = f"audio/readings/{reading_id}/main.mp3"
    main_url = await r2.put_main(reading_id, stitched)

    # 4. Delete the per-sentence chunks. We do this BEFORE the DB
    #    write so a crash in the middle leaves the audio recoverable
    #    via the main.mp3 path (the chunks are now redundant copies).
    chunks_deleted = await r2.delete_chunks(reading_id)

    # 5. Persist to reading_audio. Update if a row exists (re-runs of
    #    the finalize job for the same reading are idempotent), else
    #    insert.
    audio_row = await _upsert_reading_audio(
        session=session,
        reading_id=reading_id,
        r2_url=main_url,
        r2_key=main_key,
        content_hash=content_sha256(stitched),
        file_size_bytes=len(stitched),
        duration_ms=duration_ms,
    )

    return AudioFinalizeResult(
        reading_id=reading_id,
        r2_url=audio_row.r2_url,
        r2_key=audio_row.r2_key or main_key,
        content_hash=audio_row.content_hash or "",
        file_size_bytes=audio_row.file_size_bytes or 0,
        duration_ms=audio_row.duration_ms,
        chunks_deleted=chunks_deleted,
    )


# ---------------------------------------------------------------------------
# Stitch strategy
# ---------------------------------------------------------------------------


def _stitch(chunks: list[bytes], *, storage_provider: str) -> bytes:
    """Concat *chunks* using the strategy matching *storage_provider*.

    - ``mock`` → naïve binary concat. Safe for the silent MP3 frames
      from ``MockTTSAdapter`` (each chunk is a complete playable
      stream and the player from ISSUE-033 handles back-to-back
      streams via MSE).
    - ``r2``  → real ffmpeg concat. Phase-2 path; raises
      ``NotImplementedError`` if the ``ffmpeg`` binary is missing
      since the install is a deploy-time prerequisite.
    """
    if storage_provider == "mock":
        return b"".join(chunks)

    # Phase-2 R2 path. The real implementation calls
    # ``ffmpeg-python concat`` against a temp directory + a manifest
    # file. We guard for the binary so the deployer sees a clear
    # error message instead of a cryptic subprocess failure.
    if shutil.which("ffmpeg") is None:
        raise NotImplementedError(
            "Phase-2 audio stitch requires ffmpeg on PATH. "
            "Install ffmpeg in the worker container (see Architecture §8.4) "
            "or run with STORAGE_PROVIDER=mock for the Phase-1 PoC stack."
        )
    raise NotImplementedError(
        "Real ffmpeg concat is implemented alongside ISSUE-005. "
        "Until R2 provisioning lands, STORAGE_PROVIDER=mock is the "
        "supported Phase-1 path."
    )


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------


async def _upsert_reading_audio(
    *,
    session: AsyncSession,
    reading_id: str,
    r2_url: str,
    r2_key: str,
    content_hash: str,
    file_size_bytes: int,
    duration_ms: int,
) -> ReadingAudio:
    """Idempotent upsert into ``reading_audio``.

    Returns the persisted row so the caller can build the structured
    result without re-querying.
    """
    existing = (
        await session.execute(
            select(ReadingAudio).where(ReadingAudio.reading_id == reading_id)
        )
    ).scalar_one_or_none()
    if existing is None:
        row = ReadingAudio(
            reading_id=reading_id,
            r2_url=r2_url,
            r2_key=r2_key,
            content_hash=content_hash,
            file_size_bytes=file_size_bytes,
            duration_ms=duration_ms,
        )
        session.add(row)
    else:
        existing.r2_url = r2_url
        existing.r2_key = r2_key
        existing.content_hash = content_hash
        existing.file_size_bytes = file_size_bytes
        existing.duration_ms = duration_ms
        row = existing
    await session.flush()
    return row


__all__ = [
    "DEFAULT_PLACEHOLDER_DURATION_MS",
    "AudioFinalizeResult",
    "finalize_audio",
]
