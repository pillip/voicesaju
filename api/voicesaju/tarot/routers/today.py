"""FastAPI router for the daily tarot pipeline (ISSUE-049).

Exposes two endpoints that together drive the M3 daily-tarot flow:

* ``GET /api/v1/tarot/today`` — returns today's card metadata + the
  caller's remaining weekly free draws. Pure read; idempotent.
* ``POST /api/v1/tarot/today/flip`` — creates (or reuses) the
  ``tarot_draws`` row for ``(subject, today_kst)`` and streams the
  Haiku-class LLM reading via SSE.

Phase-1 wiring: every external collaborator (LLM / TTS / storage) is
swapped for the M1 mock under ``*_PROVIDER=mock``. Tests override the
dependency callables below to inject in-memory fakes — same pattern as
:mod:`voicesaju.readings.routers.pipeline`.

Architecture-Ref: §6.4 (tarot flow), §10 (seed algorithm).
PRD-Ref: FR-012 (daily tarot), FR-013 (deterministic card),
FR-014 (weekly quota), FR-015 (paywall), NFR-003 (first audio budget).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from voicesaju.adapters import get_llm_adapter, get_tts_adapter
from voicesaju.db.engine import get_session
from voicesaju.db.models.tarot_cards import TarotCard
from voicesaju.db.models.tarot_draws import TarotDraw
from voicesaju.storage.r2_client import R2Client
from voicesaju.tarot.quota import check_weekly_free
from voicesaju.tarot.seed import daily_card_index
from voicesaju.tarot.services.tarot_pipeline_service import (
    TarotPipelineDeps,
    run_tarot_pipeline,
)

router = APIRouter(prefix="/api/v1/tarot", tags=["tarot"])

KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------------------------
# Dependencies (overridable in tests)
# ---------------------------------------------------------------------------


def _get_current_user_id(request: Request) -> str:
    """Resolve the caller's ``user_id`` from the auth session.

    Tests override this via ``app.dependency_overrides`` to inject a
    pre-seeded user. Production wires this to the ``AuthMiddleware``
    that populates ``request.state.user``.

    Returns 401 when no user is resolved — Phase-1 keeps the
    anonymous-device path out of scope for the daily tarot route
    (device_id support lands alongside the frontend in ISSUE-051+,
    which can re-enable it by overriding this dependency).
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


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class _TodayResponse(BaseModel):
    """Response envelope for ``GET /api/v1/tarot/today``.

    Mirrors the architecture §6.4 contract:
    ``{card_index, card_name, card_art_url, free_remaining, requires_payment}``.

    Phase-1 ``card_art_url`` is a relative placeholder
    (``/api/v1/tarot/cards/{card_index}/art``); the real R2-signed CDN
    URL lands in ISSUE-055.
    """

    card_index: int
    card_name: str
    card_art_url: str
    free_remaining: int
    requires_payment: bool


class _ErrorBlock(BaseModel):
    code: str
    message: str


class _ErrorResponse(BaseModel):
    """402 envelope. Top-level ``error`` matches the architecture spec."""

    error: _ErrorBlock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today_kst() -> "datetime.date":  # noqa: UP037
    """Resolve today's KST calendar date.

    Centralised so the GET + POST paths agree on the same boundary.
    Architecture §6.4 pins KST as the reset clock.
    """
    return datetime.now(KST).date()


def _card_art_url(card_index: int) -> str:
    """Phase-1 placeholder URL for the card art.

    Real CDN-signed R2 URLs land in ISSUE-055. Keeping this relative
    means the frontend can prefix with its own host when ready.
    """
    return f"/api/v1/tarot/cards/{card_index}/art"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/today",
    response_model=_TodayResponse,
    status_code=status.HTTP_200_OK,
)
async def get_today(
    user_id: Annotated[str, Depends(_get_current_user_id)] = "",
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
) -> _TodayResponse:
    """Return today's tarot card + quota envelope for the caller.

    Pure read — does NOT create a ``tarot_draws`` row. The flip
    endpoint is what consumes the daily quota.

    AC 1: response includes ``{card_index, card_name, card_art_url,
    free_remaining, requires_payment}`` and lands within 100ms in
    production. The unit tests assert a relaxed 1s budget (mock+SQLite
    overhead).
    """
    today_kst = _today_kst()
    card_index = daily_card_index(today_kst, user_id)

    # Card metadata lookup (22 rows seeded via migration 0008).
    card = (
        await session.execute(
            select(TarotCard).where(TarotCard.card_index == card_index)
        )
    ).scalar_one_or_none()
    if card is None:  # pragma: no cover — seed migration is mandatory
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"tarot_cards row missing for card_index={card_index}",
        )

    # Quota lookup — DB-fallback path (no Redis wired into the router
    # yet; ISSUE-049 leaves the Redis injection to a follow-up).
    quota = await check_weekly_free(session=session, user_id=user_id)
    free_remaining = max(0, quota.remaining) if not quota.is_unlimited else 1
    # Subscribers never see a paywall regardless of quota. Non-subs
    # need payment only after quota hits zero.
    requires_payment = (not quota.is_unlimited) and quota.remaining <= 0

    return _TodayResponse(
        card_index=card_index,
        card_name=card.name_kr,
        card_art_url=_card_art_url(card_index),
        free_remaining=free_remaining,
        requires_payment=requires_payment,
    )


@router.post(
    "/today/flip",
    responses={402: {"model": _ErrorResponse}},
)
async def flip_today(
    user_id: Annotated[str, Depends(_get_current_user_id)] = "",
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
    r2: Annotated[R2Client, Depends(_get_r2_client)] = ...,  # type: ignore[assignment]
) -> StreamingResponse:
    """Create (or reuse) today's draw and stream the reading.

    Flow:

    1. **Idempotency check** — look up an existing ``tarot_draws`` row
       for ``(user_id, today_kst)``. If present, skip the quota check
       (it was already consumed when the row was created) and re-stream
       the reading. Same draw_id, same SSE events.
    2. **Quota / entitlement check** — :func:`check_weekly_free`. If
       the caller has neither a subscription nor a free draw left,
       respond 402 with ``error.code=payment_required``.
    3. **Insert** — create the ``tarot_draws`` row with today's seeded
       ``card_index``.
    4. **Stream** — :func:`run_tarot_pipeline` yields SSE-framed
       ``subtitle`` / ``audio_ready`` / ``end`` events.

    AC 2 (idempotency): step (1) means two POSTs same KST day return
    the same draw_id and never insert a second row — the unique partial
    index on ``(user_id, date_kst)`` is an additional safety net on
    Postgres; SQLite tests rely on the application-level lookup.

    AC 3 (quota exhausted → 402): step (2) returns a structured error
    envelope. FastAPI's ``HTTPException(detail=...)`` wraps the dict
    inside ``{"detail": {...}}`` on the wire — the same shape used by
    the reading-pipeline route from ISSUE-039.
    """
    today_kst = _today_kst()

    # --- Step 1: idempotency lookup ----------------------------------
    existing_draw = (
        await session.execute(
            select(TarotDraw).where(
                TarotDraw.user_id == user_id,
                TarotDraw.date_kst == today_kst,
            )
        )
    ).scalar_one_or_none()

    if existing_draw is not None:
        draw_id = str(existing_draw.id)
        card_index = existing_draw.card_index
    else:
        # --- Step 2: quota / entitlement check -----------------------
        quota = await check_weekly_free(session=session, user_id=user_id)
        if (not quota.is_unlimited) and quota.remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": {
                        "code": "payment_required",
                        "message": (
                            "weekly free tarot quota exhausted; "
                            "subscription or one-off purchase required"
                        ),
                    }
                },
            )

        # --- Step 3: insert tarot_draws row --------------------------
        card_index = daily_card_index(today_kst, user_id)
        card = (
            await session.execute(
                select(TarotCard).where(TarotCard.card_index == card_index)
            )
        ).scalar_one_or_none()
        if card is None:  # pragma: no cover — seed migration is mandatory
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(f"tarot_cards row missing for card_index={card_index}"),
            )

        new_draw = TarotDraw(
            user_id=user_id,
            card_id=str(card.id),
            card_index=card_index,
            date_kst=today_kst,
        )
        session.add(new_draw)
        await session.commit()
        await session.refresh(new_draw)
        draw_id = str(new_draw.id)

    # --- Step 4: stream the reading ---------------------------------
    deps = TarotPipelineDeps(
        llm=get_llm_adapter(),
        tts=get_tts_adapter(),
        r2=r2,
        db_session=session,
    )
    return StreamingResponse(
        run_tarot_pipeline(
            draw_id=draw_id,
            card_index=card_index,
            deps=deps,
        ),
        media_type="text/event-stream",
    )


__all__ = [
    "_get_current_user_id",
    "_get_r2_client",
    "router",
]
