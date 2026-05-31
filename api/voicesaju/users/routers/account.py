"""FastAPI router for account-management endpoints (ISSUE-072).

Currently mounts ``POST /api/v1/users/me/delete`` — the user-initiated
soft-delete that powers the "회원 탈퇴" button on `/me/account`
(Screen 19/20).

Architecture-Ref: §11 (account lifecycle), AP-08 (soft-delete via
``deleted_at`` columns + downstream cron worker for hard-delete after
the 30-day grace window — the cron worker lands in ISSUE-088).
PRD-Ref: NFR-005 (GDPR/PIPA — user-initiated deletion).

Flow:
1. The auth middleware has resolved ``request.state.user``; we read it
   through the same ``_get_current_user_id`` dependency the profile
   router uses, so the test override stays consistent.
2. Stamp ``users.deleted_at`` + ``profiles.deleted_at`` with ``utcnow()``
   inside a single transaction.
3. Drop the caller's session row (so the `vs_sess` they hold becomes
   useless even before the cookie is cleared client-side).
4. Clear the ``vs_sess`` cookie on the response so the very next
   request is anonymous.

Idempotency: a second call is a no-op — the timestamps are not
re-stamped, the session row is already gone. Phase-1 deliberately does
NOT scrub PII (email_hash, birth_dt_enc, name_optional) inside this
route; that's the cron worker's job after the 30-day grace per the
data_model §11 retention policy.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.engine import get_session
from voicesaju.db.models.profiles import Profile
from voicesaju.db.models.users import User
from voicesaju.users.routers.auth import _SESSION_COOKIE_NAME
from voicesaju.users.services.session_service import (
    SessionStore,
    get_session_store,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _get_current_user_id(request: Request) -> str:
    """Return the authenticated user's id, or raise 401.

    Mirrors ``voicesaju.users.routers.profile._get_current_user_id`` —
    we keep a *separate* local symbol so the test harness can override
    this hook independently of the profile route.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user.user_id


def _get_session_store_dep() -> SessionStore:
    """FastAPI dep so tests can swap in an InMemorySessionStore."""
    return get_session_store()


@router.post(
    "/me/delete",
    status_code=status.HTTP_200_OK,
)
async def delete_me(
    request: Request,
    response: Response,
    user_id: str = Depends(_get_current_user_id),
    db_session: AsyncSession = Depends(get_session),  # noqa: B008
    session_store: SessionStore = Depends(_get_session_store_dep),  # noqa: B008
) -> dict[str, bool]:
    """Soft-delete the caller's account.

    Architecture §11 / AP-08: stamp ``deleted_at`` on both ``users`` and
    ``profiles`` rows, drop the session, clear the cookie. The actual
    PII scrubbing + downstream Stripe/Toss subscription cancellation
    happens out-of-band via the hard-delete cron worker (ISSUE-088).

    AC2 (ISSUE-072): users.deleted_at set + logged out.
    AC3 (ISSUE-072): same-provider re-login → new account. That contract
    holds because the ``find_or_create_by_provider`` path already
    treats soft-deleted rows as absent (the unique index on
    ``kakao_sub`` / ``apple_sub`` is a *partial* index against
    ``deleted_at IS NULL`` per the 0003 migration), so a fresh callback
    after delete mints a brand-new ``users`` row.
    """
    now = datetime.now(UTC)

    user = (
        await db_session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        # Shouldn't happen — the auth dep verified the session points
        # at this user — but stay defensive so a deleted-row race never
        # 500s.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    # Idempotent: don't re-stamp if already soft-deleted; just continue
    # to the session/cookie cleanup so a retry from a stale client
    # observably logs them out.
    if user.deleted_at is None:
        user.deleted_at = now

    profile = (
        await db_session.execute(select(Profile).where(Profile.user_id == user_id))
    ).scalar_one_or_none()
    if profile is not None and profile.deleted_at is None:
        profile.deleted_at = now

    await db_session.commit()

    # Drop the session row server-side, then clear the cookie so a
    # stale browser session is hardened.
    sid = request.cookies.get(_SESSION_COOKIE_NAME)
    if sid:
        await session_store.delete_session(sid)
    response.delete_cookie(
        key=_SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )

    return {"ok": True}


__all__ = [
    "_get_current_user_id",  # exported for test dependency override
    "_get_session_store_dep",
    "router",
]
