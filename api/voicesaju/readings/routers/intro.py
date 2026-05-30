"""FastAPI router for ``GET /api/v1/reading/intro/{category}`` (ISSUE-031).

Architecture-Ref: §6.3 (intro audio + persona reading flow).
data_model-Ref: AP-46 (``intro_audio_clips`` lookup key).
PRD-Ref: FR-005 (persona intro before the LLM stream).

Flow (happy path):

1. Auth middleware has resolved ``request.state.user``; the dependency
   ``_get_current_user_id`` reads it. Anonymous callers → 401.
2. Load the caller's ``Profile`` to learn ``birth_time_known``. No
   profile → 404 (treated as "no clip available for this caller" so
   the client can fall back per ux_spec).
3. Map the bool to the seed variant key: ``True → "known"``,
   ``False → "unknown"`` (matches the migration
   ``0009_quote_intro_character.py`` constants).
4. Lookup the row in ``intro_audio_clips`` keyed by
   ``(category, birth_time_variant, character_key='nuna')``. The
   M2 persona is hardcoded to ``nuna``; ``dosa`` launches later
   and will share the same lookup shape.
5. Return ``{audio_url, subtitle, duration_ms}``.

Phase 1 placeholders documented per the issue scope:

* ``audio_url`` is the ``r2_url`` column value as-stored (e.g.
  ``tts/intro/love/known.mp3``). Real signed R2 URL generation
  lands with ISSUE-038 (the R2 storage client). The frontend
  player from ISSUE-032 consumes whatever URL pattern this
  endpoint emits.
* ``subtitle`` is a per-variant Korean copy string drawn from
  ``docs/copy_guide.md`` §5 (intro audio script) and §3 (the
  "시간을 모르면..." help text). LLM-generated dynamic subtitles
  land with the reading pipeline (ISSUE-039); until then the
  endpoint emits the cached intro script verbatim.

The route's dependencies (``_get_current_user_id``, ``get_session``)
are designed to be overridable in tests — see
``tests/integration/reading/test_get_intro.py``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.engine import get_session
from voicesaju.db.models.intro_audio_clips import IntroAudioClip
from voicesaju.db.models.profiles import Profile

router = APIRouter(prefix="/api/v1", tags=["reading"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# M2 persona: every intro clip uses the "시니컬 누님" voice. The
# "dosa" persona will reuse the same lookup tuple in a later milestone.
_M2_CHARACTER_KEY = "nuna"

# The seed migration stores the two birth-time variants as the strings
# below (see ``api/alembic/versions/0009_quote_intro_character.py``).
_VARIANT_KNOWN = "known"
_VARIANT_UNKNOWN = "unknown"

# Per-variant subtitle copy. Pulled from ``docs/copy_guide.md`` §5 (the
# "intro audio script" line) and §3 (the help text shown when the
# caller did not provide a birth time). These are M1 placeholders
# until the LLM pipeline (ISSUE-039) produces dynamic subtitles.
_SUBTITLE_KNOWN = "어디 보자… 1997년생 무자년… 음, 재미있네."
_SUBTITLE_UNKNOWN = "시간을 모르면 큰 줄기는 봐도 디테일은 조금 흐릿해. 괜찮아."


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_current_user_id(request: Request) -> str:
    """Return the authenticated user's id, or raise 401.

    Mirrors ``voicesaju.users.routers.profile._get_current_user_id``
    so tests can override the same hook shape.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user.user_id


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class IntroClipResponse(BaseModel):
    """Response body for ``GET /api/v1/reading/intro/{category}``.

    Architecture §6.3: the frontend player consumes ``audio_url``
    directly. Under Phase 2 (real R2) this will be a short-lived
    signed URL; under Phase 1 it is a relative storage path so the
    contract is identical from the client's perspective.
    """

    audio_url: str
    subtitle: str
    duration_ms: int


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get(
    "/reading/intro/{category}",
    response_model=IntroClipResponse,
)
async def get_intro_clip(
    category: str,
    user_id: str = Depends(_get_current_user_id),
    db_session: AsyncSession = Depends(get_session),  # noqa: B008
) -> IntroClipResponse:
    """Return the persona intro clip for ``(category, caller's birth_time_known)``.

    AC (ISSUE-031):
    - ``category=love`` + caller ``birth_time_known=true`` → ``known`` variant.
    - ``birth_time_known=false`` → ``unknown`` variant.
    - No clip for the category → 404.
    - Anonymous caller → 401 (enforced by ``_get_current_user_id``).
    """
    # Load the caller's profile to derive birth_time_known.
    profile = (
        await db_session.execute(select(Profile).where(Profile.user_id == user_id))
    ).scalar_one_or_none()

    if profile is None:
        # No profile → we can't pick a variant. Treat as "no clip
        # available for this caller" so the client falls back per
        # ux_spec, which surfaces the cached "잠시 별기운이 약하네"
        # error toast.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no profile — onboarding required",
        )

    variant = _VARIANT_KNOWN if profile.birth_time_known else _VARIANT_UNKNOWN

    clip = (
        await db_session.execute(
            select(IntroAudioClip).where(
                IntroAudioClip.category == category,
                IntroAudioClip.birth_time_variant == variant,
                IntroAudioClip.character_key == _M2_CHARACTER_KEY,
            )
        )
    ).scalar_one_or_none()

    if clip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"no intro clip seeded for category={category!r} variant={variant!r}"
            ),
        )

    subtitle = _SUBTITLE_KNOWN if variant == _VARIANT_KNOWN else _SUBTITLE_UNKNOWN

    return IntroClipResponse(
        audio_url=clip.r2_url,
        subtitle=subtitle,
        duration_ms=clip.duration_ms,
    )
