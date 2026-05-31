"""FastAPI router for ``POST /api/v1/profile`` (ISSUE-029).

Architecture-Ref: §6.2 (onboarding + saju chart shape), AP-10 / AP-11
(on duplicate, return existing profile / cache saju_charts by chart_hash).
PRD-Ref: FR-001 (onboarding inputs), FR-002 (saju compute), FR-027
(envelope encryption of birth_dt), FR-030 (chart cache reuse).

Flow (happy path):

1. Auth middleware has resolved ``request.state.user``; the dependency
   ``_get_current_user_id`` reads it. Anonymous callers → 401.
2. Pydantic ``ProfileCreateRequest`` validates the body.
3. If a ``Profile`` already exists for ``user_id`` → return the cached
   chart (AP-10 idempotency). This sidesteps the unique constraint and
   the per-user correction quota.
4. Otherwise compute the saju chart via
   :func:`voicesaju.saju.engine.compute_chart`.
5. Up-sert the ``SajuChart`` row keyed by ``chart_hash`` (AP-11 cache).
   Two users with identical inputs share the row.
6. Insert the ``Profile`` row (birth_dt encrypted via the model's
   property setter, which calls ``envelope.encrypt_field``).
7. Return ``{profile_id, chart_id, chart}``.

The route's dependencies (``_get_current_user_id``, ``get_session``) are
designed to be overridable in tests — see
``tests/integration/profile/test_create_profile.py``.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.engine import get_session
from voicesaju.db.models.profiles import Profile
from voicesaju.db.models.saju_charts import SajuChart as SajuChartRow
from voicesaju.saju.engine import compute_chart
from voicesaju.saju.models import SajuChart as SajuChartValue

router = APIRouter(prefix="/api/v1", tags=["profile"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_current_user_id(request: Request) -> str:
    """Return the authenticated user's id, or raise 401.

    Reads the ``UserContext`` attached to ``request.state.user`` by
    :class:`voicesaju.middleware.auth.AuthMiddleware`. Tests override
    this dependency directly so they don't have to mint a JWT.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user.user_id


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ProfileCreateRequest(BaseModel):
    """Request body for ``POST /api/v1/profile`` (architecture §6.2).

    Mirrors the spec exactly:
      ``{ birth_date: "1997-08-13",
          birth_time: "07:30" | null,
          is_lunar: false,
          gender: "F" | "M",
          name?: string }``
    """

    birth_date: str = Field(..., description="ISO-8601 date, e.g. '1997-08-13'.")
    birth_time: str | None = Field(
        default=None,
        description="ISO-8601 time-of-day 'HH:MM'. ``None`` → time unknown.",
    )
    is_lunar: bool = False
    gender: str = Field(..., description="'M' or 'F'.")
    name: str | None = Field(default=None, max_length=10)

    @field_validator("birth_date")
    @classmethod
    def _validate_birth_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError("birth_date must be YYYY-MM-DD") from e
        return v

    @field_validator("birth_time")
    @classmethod
    def _validate_birth_time(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError as e:
            raise ValueError("birth_time must be HH:MM") from e
        return v

    @field_validator("gender")
    @classmethod
    def _validate_gender(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ("M", "F"):
            raise ValueError("gender must be 'M' or 'F'")
        return upper


class PillarOut(BaseModel):
    """One pillar of the 명식."""

    stem: str
    branch: str
    element: str
    ten_god: str | None = None


class SajuChartOut(BaseModel):
    """Serialized form of :class:`voicesaju.saju.models.SajuChart`."""

    year: PillarOut
    month: PillarOut
    day: PillarOut
    hour: PillarOut | None
    engine_version: str


class ProfileCreateResponse(BaseModel):
    """Response body for ``POST /api/v1/profile``."""

    profile_id: str
    chart_id: str
    chart: SajuChartOut


class ProfileMeResponse(BaseModel):
    """Response body for ``GET /api/v1/profile/me`` (ISSUE-064).

    Returns the caller's persisted saju chart so the frontend
    ``/me/saju`` page (Screen 17) can render the 4-pillar grid without
    re-running the engine. ``birth_time_known`` is mirrored from the
    ``profiles`` row so the page can render "모름" handling per AC2.
    """

    profile_id: str
    chart_id: str
    chart: SajuChartOut
    birth_time_known: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chart_value_to_out(chart: SajuChartValue) -> SajuChartOut:
    """Convert the engine's frozen-dataclass chart into the Pydantic shape."""

    def pillar(p: object) -> PillarOut:
        # ``Pillar`` is a frozen dataclass with str-enum fields. The
        # ``to_dict`` form coerces enums to their underlying str values,
        # which Pydantic accepts directly.
        d = p.to_dict()  # type: ignore[attr-defined]
        return PillarOut(**d)

    return SajuChartOut(
        year=pillar(chart.year),
        month=pillar(chart.month),
        day=pillar(chart.day),
        hour=pillar(chart.hour) if chart.hour else None,
        engine_version=chart.engine_version,
    )


def _chart_row_to_out(row: SajuChartRow) -> SajuChartOut:
    """Convert a persisted ``saju_charts`` row back into the response shape.

    Used when AP-10 idempotency replays an existing profile — we don't
    re-run the engine; we hydrate from the stored ``pillars`` JSONB.
    """
    p = row.pillars
    return SajuChartOut(
        year=PillarOut(**p["year"]),
        month=PillarOut(**p["month"]),
        day=PillarOut(**p["day"]),
        hour=PillarOut(**p["hour"]) if p.get("hour") else None,
        engine_version=row.engine_version,
    )


def _parse_birth_dt(birth_date: str, birth_time: str | None) -> datetime:
    """Combine ``birth_date`` + ``birth_time`` into a naive ``datetime``.

    The saju engine ignores tzinfo beyond the wall-clock components, so a
    naive value is sufficient (and matches the engine's contract).
    """
    if birth_time:
        return datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    # Use noon as a placeholder; the engine ignores hour when
    # ``time_unknown=True`` so the value is never read.
    return datetime.strptime(f"{birth_date} 12:00", "%Y-%m-%d %H:%M")


def _format_birth_dt_plaintext(birth_date: str, birth_time: str | None) -> str:
    """Canonical plaintext form stored inside the envelope ciphertext.

    Keeping this stable lets the future PATCH path (ISSUE-071) round-trip
    the value without re-deriving it from the encrypted blob.
    """
    if birth_time:
        return f"{birth_date}T{birth_time}"
    return f"{birth_date}T00:00"


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post(
    "/profile",
    response_model=ProfileCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    body: ProfileCreateRequest,
    user_id: str = Depends(_get_current_user_id),
    db_session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ProfileCreateResponse:
    """Create a profile + compute & cache the saju chart.

    AC (ISSUE-029):
    - Valid request → 201 with ``{profile_id, chart_id, chart}``.
    - ``birth_time=null`` → ``birth_time_known=false`` + ``chart.hour=None``.
    - ``is_lunar=true`` → engine converts to solar before compute.
    - Two users with identical inputs → shared ``chart_id`` (AP-11 cache).
    - Same user posting twice → existing profile returned (AP-10 idempotency).
    """
    # AP-10: idempotency check — does this user already have a profile?
    existing = (
        await db_session.execute(select(Profile).where(Profile.user_id == user_id))
    ).scalar_one_or_none()

    if existing is not None:
        chart_row = (
            await db_session.execute(
                select(SajuChartRow).where(SajuChartRow.user_id == user_id)
            )
        ).scalar_one_or_none()
        if chart_row is None:
            # Theoretically unreachable — every profile insert also writes
            # a chart row in the same transaction. Guard anyway.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="profile present without chart",
            )
        return ProfileCreateResponse(
            profile_id=str(existing.id),
            chart_id=str(chart_row.id),
            chart=_chart_row_to_out(chart_row),
        )

    # Compute the chart (pure function; safe inside the txn).
    birth_dt = _parse_birth_dt(body.birth_date, body.birth_time)
    time_unknown = body.birth_time is None
    chart_value = compute_chart(
        birth_dt,
        is_lunar=body.is_lunar,
        gender=body.gender,
        time_unknown=time_unknown,
    )

    # AP-11: chart cache — reuse an existing row by chart_hash if present.
    chart_row = (
        await db_session.execute(
            select(SajuChartRow).where(
                SajuChartRow.chart_hash == chart_value.chart_hash
            )
        )
    ).scalar_one_or_none()

    if chart_row is None:
        chart_row = SajuChartRow(
            user_id=user_id,
            chart_hash=chart_value.chart_hash,
            engine_version=chart_value.engine_version,
            pillars={
                "year": chart_value.year.to_dict(),
                "month": chart_value.month.to_dict(),
                "day": chart_value.day.to_dict(),
                "hour": chart_value.hour.to_dict() if chart_value.hour else None,
            },
            time_known=not time_unknown,
        )
        db_session.add(chart_row)
        await db_session.flush()  # populate chart_row.id

    # Insert the profile row. ``birth_dt`` plaintext goes through the
    # envelope-encryption property setter on the model — birth_dt at
    # rest is JSONB ciphertext only (FR-027).
    profile = Profile(
        user_id=user_id,
        birth_dt=_format_birth_dt_plaintext(body.birth_date, body.birth_time),
        birth_is_lunar=body.is_lunar,
        birth_time_known=not time_unknown,
        name_optional=body.name,
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.commit()

    return ProfileCreateResponse(
        profile_id=str(profile.id),
        chart_id=str(chart_row.id),
        chart=_chart_value_to_out(chart_value),
    )


@router.get(
    "/profile/me",
    response_model=ProfileMeResponse,
)
async def get_profile_me(
    user_id: str = Depends(_get_current_user_id),
    db_session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ProfileMeResponse:
    """Return the caller's persisted profile + saju chart (ISSUE-064).

    Architecture-Ref: §6.2.
    PRD-Ref: FR-011 (My Page chart visualization), US-05.

    Drives the ``/me/saju`` page (Screen 17). The chart row is read
    straight from ``saju_charts`` — we do NOT re-compute. ``birth_time_known``
    comes from the ``profiles`` row so the page can render the "모름"
    treatment on the Hour Pillar (AC2).

    Auth: 401 when anonymous (consistent with ``POST /api/v1/profile``).
    404 when the caller is signed in but has no profile yet (typical of
    a user that completed OAuth but skipped onboarding — the page should
    bounce them to `/onboarding`).

    Soft-deleted profiles (``deleted_at IS NOT NULL``) are treated as
    "not present" so the chart isn't served from a tombstoned row.
    """
    profile = (
        await db_session.execute(
            select(Profile).where(
                Profile.user_id == user_id,
                Profile.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="profile not found",
        )

    chart_row = (
        await db_session.execute(
            select(SajuChartRow).where(SajuChartRow.user_id == user_id)
        )
    ).scalar_one_or_none()
    if chart_row is None:
        # Same defensive guard as the POST path — profile + chart are
        # always written in the same transaction, so this should be
        # unreachable; raise 500 rather than silently 404.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="profile present without chart",
        )

    return ProfileMeResponse(
        profile_id=str(profile.id),
        chart_id=str(chart_row.id),
        chart=_chart_row_to_out(chart_row),
        birth_time_known=profile.birth_time_known,
    )


__all__ = [
    "_get_current_user_id",  # exported for test dependency override
    "router",
]
