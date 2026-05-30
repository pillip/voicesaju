"""FastAPI router for the M2 reading pipeline (ISSUE-039).

Exposes two endpoints that together drive the M2 saju reading flow:

* ``POST /api/v1/reading`` — validates entitlement, creates the
  :class:`Reading` row, returns the SSE + audio URLs. Honours an
  ``Idempotency-Key`` header so duplicate POSTs return the same
  ``reading_id`` rather than creating a second row.
* ``GET /api/v1/reading/{reading_id}/stream`` — orchestrates the
  ``chart_lookup → LLM → guardrail → TTS → R2 upload → SSE emit``
  pipeline implemented in :mod:`voicesaju.readings.services.pipeline_service`.

Phase-1 wiring: every external collaborator (LLM / TTS / storage) is
swapped for the M1 mock under the corresponding ``*_PROVIDER=mock``
setting. Tests override the dependency callables below to inject
in-memory fakes (engine sessions, ``MockStorageAdapter`` roots, etc.).

Architecture-Ref: §6.3 (pipeline stages), §7.1 (LLM streaming), §8.2
(TTS streaming).
PRD-Ref: FR-007 (real-time reading), NFR-001 (3s first-chunk budget),
NFR-011 (idempotency).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from voicesaju.adapters import get_llm_adapter, get_tts_adapter
from voicesaju.db.engine import get_session
from voicesaju.db.models.readings import Reading
from voicesaju.entitlement.service import check_entitlement
from voicesaju.jobs.worker import InMemoryQueue
from voicesaju.readings.services.pipeline_service import (
    PipelineDeps,
    run_pipeline,
)
from voicesaju.storage.r2_client import R2Client

router = APIRouter(prefix="/api/v1/reading", tags=["reading"])


# ---------------------------------------------------------------------------
# Dependencies (overridable in tests)
# ---------------------------------------------------------------------------


def _get_current_user_id(request: Request) -> str:
    """Resolve the caller's ``user_id`` from the auth session.

    Tests override this via ``app.dependency_overrides`` to inject a
    pre-seeded user; production wires this to the ``AuthMiddleware``
    that already populates ``request.state.user``.
    """
    user = getattr(request.state, "user", None)
    if user is None or getattr(user, "user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user.user_id


def _get_r2_client() -> R2Client:
    """Build a :class:`R2Client` from settings — tests override this."""
    return R2Client.from_settings()


# Module-level singleton queue so the same InMemoryQueue persists
# across requests in dev. In production, arq's Redis-backed queue
# replaces this via the Phase-2 deploy.
_DEFAULT_FINALIZE_QUEUE = InMemoryQueue()


def _get_finalize_queue() -> InMemoryQueue:
    """Return the queue ``finalize_audio`` jobs are enqueued onto."""
    return _DEFAULT_FINALIZE_QUEUE


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class _CreateReadingRequest(BaseModel):
    """Request body for ``POST /api/v1/reading``."""

    category: str = Field(..., pattern=r"^(love|work|money)$")
    character_key: str = Field(default="nuna", pattern=r"^(nuna|dosa)$")


class _CreateReadingResponse(BaseModel):
    """201 envelope for ``POST /api/v1/reading``."""

    reading_id: str
    sse_url: str
    audio_stream_url: str


class _ErrorBlock(BaseModel):
    code: str
    message: str


class _ErrorResponse(BaseModel):
    """402 envelope. Top-level ``error`` matches the architecture spec."""

    error: _ErrorBlock


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=_CreateReadingResponse,
    responses={402: {"model": _ErrorResponse}},
)
async def create_reading(
    body: _CreateReadingRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user_id: Annotated[str, Depends(_get_current_user_id)] = "",
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
) -> _CreateReadingResponse:
    """Validate entitlement → create Reading → return SSE URLs.

    Idempotency: when ``Idempotency-Key`` is present and matches an
    existing Reading for the caller, the existing reading is returned
    (no second row created). This is the FR-007 retry-safety contract.
    """
    # Idempotency check — return the existing row before doing any
    # entitlement or DB writes.
    if idempotency_key:
        existing = (
            await session.execute(
                select(Reading).where(
                    Reading.user_id == user_id,
                    Reading.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _build_response(request, str(existing.id))

    # Entitlement check — 402 with structured envelope on miss.
    entitlement = await check_entitlement(session=session, user_id=user_id)
    if not entitlement.has_anything:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": {
                    "code": "payment_required",
                    "message": "no entitlement available for this reading",
                }
            },
        )

    # Phase-1: pair the Reading row with whichever entitlement source
    # the service preferred. Real consumption (free_token marked spent,
    # subscription decremented) lands alongside ISSUE-044's payment work.
    free_token_id = (
        entitlement.token_id if entitlement.preferred_kind == "free_token" else None
    )
    entitlement_kind = (
        entitlement.preferred_kind
        if entitlement.preferred_kind != "none"
        else "free_token"
    )

    reading = Reading(
        user_id=user_id,
        category=body.category,
        character_key=body.character_key,
        entitlement_kind=entitlement_kind,
        free_token_id=free_token_id,
        idempotency_key=idempotency_key,
        status="streaming",
    )
    session.add(reading)
    await session.commit()
    await session.refresh(reading)

    return _build_response(request, str(reading.id))


def _build_response(request: Request, reading_id: str) -> _CreateReadingResponse:
    """Compose the 201 envelope with absolute SSE + audio URLs."""
    base = str(request.base_url).rstrip("/")
    return _CreateReadingResponse(
        reading_id=reading_id,
        sse_url=f"{base}/api/v1/reading/{reading_id}/stream",
        audio_stream_url=f"{base}/api/v1/reading/{reading_id}/audio",
    )


@router.get("/{reading_id}/stream")
async def stream_reading(
    reading_id: str,
    user_id: Annotated[str, Depends(_get_current_user_id)] = "",
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
    r2: Annotated[R2Client, Depends(_get_r2_client)] = ...,  # type: ignore[assignment]
    queue: Annotated[InMemoryQueue, Depends(_get_finalize_queue)] = ...,  # type: ignore[assignment]
) -> StreamingResponse:
    """Stream the SSE events for *reading_id*.

    Loads the Reading row, builds the :class:`PipelineDeps`, and yields
    SSE-framed events through :func:`run_pipeline`. The stream closes
    after the terminal ``end`` event.
    """
    reading = (
        await session.execute(
            select(Reading).where(Reading.id == reading_id, Reading.user_id == user_id)
        )
    ).scalar_one_or_none()
    if reading is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    deps = PipelineDeps(
        llm=get_llm_adapter(),
        tts=get_tts_adapter(),
        r2=r2,
        queue=queue,
        db_session=session,
    )

    return StreamingResponse(
        run_pipeline(
            reading_id=str(reading.id),
            category=reading.category,
            character_key=reading.character_key,
            deps=deps,
        ),
        media_type="text/event-stream",
    )


__all__ = [
    "_get_current_user_id",
    "_get_finalize_queue",
    "_get_r2_client",
    "router",
]
