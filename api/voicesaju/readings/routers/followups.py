"""FastAPI router for the M2 follow-up question endpoints (ISSUE-041).

Exposes two endpoints that ride the SSE machinery from ISSUE-039:

* ``GET /api/v1/reading/{reading_id}/followups`` — returns three
  follow-up question suggestions (FR-009). The questions come from the
  LLM (Haiku 4.5 in prod, mock fixture in Phase-1) with a hardcoded
  category fallback bank baked into the service.

* ``POST /api/v1/reading/{reading_id}/followups/{slot_index}`` —
  streams the SSE answer for the chosen slot (FR-010). The first
  ``POST`` per slot creates the row; the second returns 409 (server-
  side button disable contract from the issue spec).

Auth + dependency wiring mirrors the pipeline router: the same
auth dependency, DB session, R2 client, and LLM/TTS adapters apply.

Architecture-Ref: §6.3, §7.1.
PRD-Ref: FR-009 (suggest fallback), FR-010 (answer duration), NFR-004
(first audio chunk within 2s).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from voicesaju.adapters import get_llm_adapter, get_tts_adapter
from voicesaju.db.engine import get_session
from voicesaju.db.models.reading_followups import ReadingFollowup
from voicesaju.db.models.readings import Reading
from voicesaju.readings.routers.pipeline import (
    _get_current_user_id,
    _get_r2_client,
)
from voicesaju.readings.services.followup_service import (
    FOLLOWUP_SUGGEST_COUNT,
    run_followup_answer,
    suggest_followups,
)
from voicesaju.storage.r2_client import R2Client

router = APIRouter(prefix="/api/v1/reading", tags=["reading"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class _FollowupSuggestion(BaseModel):
    """One suggestion row in the GET response."""

    slot_index: int = Field(..., ge=0, le=FOLLOWUP_SUGGEST_COUNT - 1)
    question_text: str


class _FollowupSuggestResponse(BaseModel):
    """200 envelope for ``GET .../followups``."""

    reading_id: str
    suggestions: list[_FollowupSuggestion]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_reading_for_user(
    *,
    session: AsyncSession,
    reading_id: str,
    user_id: str,
) -> Reading:
    """Return the Reading row owned by *user_id* or raise 404.

    Shared between both endpoints so the not-found shape stays
    consistent and we never leak ``reading_id`` ownership via a 200
    response.
    """
    reading = (
        await session.execute(
            select(Reading).where(Reading.id == reading_id, Reading.user_id == user_id)
        )
    ).scalar_one_or_none()
    if reading is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return reading


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/{reading_id}/followups",
    response_model=_FollowupSuggestResponse,
)
async def list_followups(
    reading_id: str,
    user_id: Annotated[str, Depends(_get_current_user_id)] = "",
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
) -> _FollowupSuggestResponse:
    """Return 3 follow-up question suggestions for *reading_id*.

    Idempotent: callers can re-fetch and (because the LLM stream
    is seeded deterministically per ``reading_id``) get the same
    three questions, modulo fallback.
    """
    reading = await _load_reading_for_user(
        session=session, reading_id=reading_id, user_id=user_id
    )

    llm = get_llm_adapter()
    questions = await suggest_followups(
        reading_id=str(reading.id),
        category=reading.category,
        llm=llm,
    )

    return _FollowupSuggestResponse(
        reading_id=str(reading.id),
        suggestions=[
            _FollowupSuggestion(slot_index=idx, question_text=q)
            for idx, q in enumerate(questions[:FOLLOWUP_SUGGEST_COUNT])
        ],
    )


@router.post("/{reading_id}/followups/{slot_index}")
async def start_followup_answer(
    reading_id: str,
    slot_index: int,
    request: Request,
    user_id: Annotated[str, Depends(_get_current_user_id)] = "",
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
    r2: Annotated[R2Client, Depends(_get_r2_client)] = ...,  # type: ignore[assignment]
) -> StreamingResponse:
    """Stream the SSE answer for *slot_index*.

    Server-side button disable (FR-009 contract): the **first** POST
    for a given ``(reading_id, slot_index)`` reserves the slot by
    inserting a ``ReadingFollowup`` row; a **second** POST detects
    the existing row and responds 409.

    The reserved row's ``answer_text`` + ``audio_r2_key`` are written
    after the SSE stream completes via the service-layer commit.
    """
    if not (0 <= slot_index < FOLLOWUP_SUGGEST_COUNT):
        # Defensive: the path constraint is also enforced by the schema's
        # CheckConstraint, but we surface 400 here for clarity.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"slot_index must be in [0, {FOLLOWUP_SUGGEST_COUNT - 1}]",
        )

    reading = await _load_reading_for_user(
        session=session, reading_id=reading_id, user_id=user_id
    )

    # Slot-conflict check BEFORE we look up the question, so a re-POST
    # never re-spends LLM tokens or TTS quota.
    existing = (
        await session.execute(
            select(ReadingFollowup).where(
                ReadingFollowup.reading_id == reading.id,
                ReadingFollowup.slot_index == slot_index,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "slot_already_consumed",
                    "message": (
                        f"follow-up slot {slot_index} already taken for "
                        f"reading {reading_id}"
                    ),
                }
            },
        )

    # Resolve the question text. We re-run ``suggest_followups`` because
    # the suggest call is deterministic in seed (same reading_id ⇒ same
    # 3 questions in mock mode, and the real Haiku path will eventually
    # cache the suggest payload — out of scope for ISSUE-041).
    llm = get_llm_adapter()
    questions = await suggest_followups(
        reading_id=str(reading.id),
        category=reading.category,
        llm=llm,
    )
    if slot_index >= len(questions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"no question available for slot {slot_index}",
        )
    question_text = questions[slot_index]

    # Reserve the slot atomically. If two requests race on the same
    # slot the partial unique index ``reading_followups_reading_slot_uq``
    # rejects the loser with IntegrityError; we translate that to 409
    # for the same contract as the pre-check path.
    new_row = ReadingFollowup(
        reading_id=reading.id,
        slot_index=slot_index,
        question_text=question_text,
    )
    session.add(new_row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "slot_already_consumed",
                    "message": (
                        f"follow-up slot {slot_index} already taken for "
                        f"reading {reading_id}"
                    ),
                }
            },
        ) from exc
    await session.refresh(new_row)

    tts = get_tts_adapter()

    return StreamingResponse(
        run_followup_answer(
            reading_id=str(reading.id),
            slot_index=slot_index,
            question_text=question_text,
            category=reading.category,
            llm=llm,
            tts=tts,
            r2=r2,
            db_session=session,
            followup_row=new_row,
        ),
        media_type="text/event-stream",
    )


__all__ = ["router"]
