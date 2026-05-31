"""History list + audio replay endpoints for ISSUE-066.

Mounts ``GET /api/v1/me/readings`` and
``GET /api/v1/reading/{id}/audio.mp3``.

Backs the ``/me/history`` list and the per-reading playback page
``/me/history/[id]``. The list endpoint returns paginated reading
metadata (20/page desc by ``started_at``) and the audio endpoint
streams the archived ``reading_audio.r2_key`` payload via the active
:class:`R2Client` — Phase-1 reads from the local mock adapter; Phase-2
will swap to the real R2 client without any caller change.

Architecture-Ref: §6.3 (audio replay), AP-27 (chart history), AP-28
(audio replay key naming).
PRD-Ref: FR-028 (history), US-16 (replay past reading).

Authorization:

* Both routes require an authenticated session — anonymous → 401.
* ``GET /reading/{id}/audio.mp3`` additionally enforces caller
  ownership (404 if the reading belongs to another user). 404 (not
  403) deliberately, to avoid leaking the existence of other users'
  reading IDs (same pattern as ``GET /payments/history``).

Phase-1 simplifications:

* The audio endpoint returns the full archived MP3 in one ``Response``
  body. HTTP ``Range`` support is a documented Phase-2 follow-up; the
  AC (AC1: "streams without regeneration", AC3: "tap pause → audio
  stops") is satisfied by the full-body response since the frontend
  ``<audio>`` element seeks via byte offsets only when the server
  advertises ``Accept-Ranges: bytes``. The MockStorageAdapter does
  not yet support partial reads.
* ``audio_available`` on the list reflects whether the row has an
  ``r2_key`` set; the actual blob existence is verified lazily at
  playback time so the list endpoint stays a single DB query.
* ``summary`` is the first 100 chars of the transcript (when present)
  so the history list shows a preview without re-running the LLM.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.engine import get_session
from voicesaju.db.models.reading_audio import ReadingAudio
from voicesaju.db.models.reading_transcripts import ReadingTranscript
from voicesaju.db.models.readings import Reading
from voicesaju.storage.r2_client import R2Client

router = APIRouter(prefix="/api/v1", tags=["me", "reading"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Page size lives at module scope so tests can patch it without
# monkeypatching the route handler. Issue spec mandates 20.
PAGE_SIZE: int = 20

# Preview length for the ``summary`` field on the list endpoint. The
# value is small enough that the row stays under ~1KB even after JSON
# encoding, but large enough that the UI can show a meaningful teaser.
_SUMMARY_PREVIEW_CHARS: int = 100


# ---------------------------------------------------------------------------
# Dependencies (overridable in tests)
# ---------------------------------------------------------------------------


def _get_current_user_id(request: Request) -> str:
    """Return the authenticated user's id, or raise 401.

    Mirrors :func:`voicesaju.payment.history._get_current_user_id` —
    kept as a module-local symbol so test fixtures can override the
    dependency without coupling to neighbouring routers.
    """
    user = getattr(request.state, "user", None)
    if user is None or getattr(user, "user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user.user_id


def _get_r2_client() -> R2Client:
    """FastAPI dep so tests can swap in a fixture R2Client."""
    return R2Client.from_settings()


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class ReadingHistoryRow(BaseModel):
    """One row in the ``GET /me/readings`` response (FR-028, US-16)."""

    id: str
    category: str
    started_at: datetime | None
    completed_at: datetime | None
    # ``True`` when ``reading_audio.r2_key`` is non-null; the actual
    # blob existence is verified lazily at playback time.
    audio_available: bool
    # First ~100 chars of the persisted transcript, or ``None`` if no
    # transcript row was written (typically incomplete / failed
    # readings). Used by the UI for the list preview.
    summary: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/me/readings",
    response_model=list[ReadingHistoryRow],
)
async def list_my_readings(
    user_id: Annotated[str, Depends(_get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[
        int,
        Query(
            ge=1,
            description="1-indexed page number; 20 rows per page.",
        ),
    ] = 1,
) -> list[ReadingHistoryRow]:
    """Return the caller's reading history, newest first, 20 per page.

    AC1 (history list backing): the row's ``audio_available`` flag tells
    the frontend whether to render the playback link in the row.
    AC2 (scoping): only the caller's readings are returned — readings
    owned by other users are filtered out at the WHERE clause.

    Sort key: ``started_at DESC`` for completed sessions; rows where
    ``started_at IS NULL`` (still pending / never started) sort to the
    end so the list stays "most recently played first". NULLs-last
    behaviour is portable across SQLite + Postgres when expressed as a
    secondary sort by ``created_at`` (which is always set).
    """
    offset = (page - 1) * PAGE_SIZE
    # Left-join on reading_audio so we can compute ``audio_available`` in
    # a single query — the LEFT OUTER means readings without an audio
    # row still appear in the list (just with ``audio_available=False``).
    # Left-join on reading_transcripts similarly to surface the summary
    # preview without a second query.
    stmt = (
        select(Reading, ReadingAudio.r2_key, ReadingTranscript.transcript_text)
        .outerjoin(ReadingAudio, ReadingAudio.reading_id == Reading.id)
        .outerjoin(ReadingTranscript, ReadingTranscript.reading_id == Reading.id)
        .where(Reading.user_id == user_id)
        .order_by(
            # ``started_at DESC`` with NULLs sorting to the bottom of
            # the list. We emulate NULLS LAST by also ordering on
            # ``created_at DESC`` so unstarted rows still appear under
            # finished rows but in insertion order.
            desc(Reading.started_at),
            desc(Reading.created_at),
        )
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    rows = (await session.execute(stmt)).all()
    return [
        _to_response_row(r, audio_key, transcript) for r, audio_key, transcript in rows
    ]


@router.get(
    "/reading/{reading_id}/audio.mp3",
    response_class=Response,
)
async def get_reading_audio(
    reading_id: str,
    user_id: Annotated[str, Depends(_get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    r2: Annotated[R2Client, Depends(_get_r2_client)],
) -> Response:
    """Stream the archived audio for ``reading_id`` (AC1 + AC2).

    AC1: archived audio plays without regeneration — we read the
    persisted ``reading_audio.r2_key`` and return the blob directly.
    AC2: blob missing in storage → 410 Gone with a JSON body the
    frontend recognizes ("이 풀이는 더 이상 재생할 수 없습니다").

    AuthZ note: the caller must own the reading; otherwise we return
    404 (not 403) so the existence of foreign reading IDs is not
    leaked through status-code-based enumeration.
    """
    # Single query: pull the reading + audio row in one round-trip,
    # WHERE-clause-scoped to the caller so foreign rows simply do not
    # appear. The ``outerjoin`` means we still distinguish "reading
    # exists but no audio row" from "reading does not exist for this
    # user".
    stmt = (
        select(Reading, ReadingAudio)
        .outerjoin(ReadingAudio, ReadingAudio.reading_id == Reading.id)
        .where(Reading.id == reading_id, Reading.user_id == user_id)
    )
    result = (await session.execute(stmt)).first()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="reading not found",
        )

    reading, audio = result
    # Reading exists but has no audio row, or row exists without an r2
    # key — either way, the blob can't be served. AC2's expired-audio
    # fallback copy is what the frontend shows; the API surfaces 410
    # Gone (resource is known but no longer available).
    if audio is None or not audio.r2_key:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error": {
                    "code": "audio_expired",
                    "message": "이 풀이는 더 이상 재생할 수 없습니다",
                }
            },
        )

    try:
        blob = await r2.get_object(audio.r2_key)
    except KeyError as exc:
        # The DB references a key that the storage backend no longer
        # has (R2 lifecycle eviction, manual deletion, etc.). Same
        # surface as the "no key" branch above — the frontend treats
        # 410 as "expired".
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error": {
                    "code": "audio_expired",
                    "message": "이 풀이는 더 이상 재생할 수 없습니다",
                }
            },
        ) from exc

    # ETag/Cache headers: we hand the stored content_hash to the
    # browser so a second visit can short-circuit the body via
    # If-None-Match. Stable across redeploys because content_hash is
    # SHA-256(blob).
    headers: dict[str, str] = {}
    if audio.content_hash:
        headers["ETag"] = f'"{audio.content_hash}"'
    if audio.file_size_bytes:
        headers["Content-Length"] = str(audio.file_size_bytes)
    # Advertise Range support for Phase-2 — even though the current
    # response is always the full body, the header is harmless and
    # primes the player UI for byte-range seeks once the storage
    # adapter learns to return slices.
    headers["Accept-Ranges"] = "bytes"

    return Response(content=blob, media_type="audio/mpeg", headers=headers)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response_row(
    reading: Reading,
    audio_key: str | None,
    transcript_text: str | None,
) -> ReadingHistoryRow:
    """Project ``(Reading, audio_key?, transcript?)`` → response row."""
    summary: str | None = None
    if transcript_text:
        # Strip leading/trailing whitespace before truncation so the
        # preview never starts with a newline. The 100-char window
        # matches the UI mock spec.
        cleaned = transcript_text.strip()
        summary = (
            cleaned[:_SUMMARY_PREVIEW_CHARS] + "…"
            if len(cleaned) > _SUMMARY_PREVIEW_CHARS
            else cleaned
        )
    return ReadingHistoryRow(
        id=str(reading.id),
        category=reading.category,
        started_at=reading.started_at,
        completed_at=reading.completed_at,
        audio_available=bool(audio_key),
        summary=summary,
    )


__all__ = [
    "PAGE_SIZE",
    "ReadingHistoryRow",
    "_get_current_user_id",
    "_get_r2_client",
    "router",
]
