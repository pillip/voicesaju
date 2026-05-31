"""FastAPI router for OAuth callbacks (ISSUE-026).

Mounts four endpoints per architecture §6.1:

- ``GET  /api/v1/auth/kakao/start``   — initiates Kakao OAuth.
- ``GET  /api/v1/auth/kakao/callback``— exchanges code, creates session.
- ``GET  /api/v1/auth/apple/start``   — initiates Apple Sign-In.
- ``POST /api/v1/auth/apple/callback``— Apple ``form_post`` callback.

Phase 1 ships against the **mock auth adapter** (``AUTH_PROVIDER=mock``):
the adapter's ``resolve_oauth_callback(provider, code)`` returns a
deterministic synthetic ``(subject_id, email)`` so the full vertical
slice (find-or-create user + signup grant + session cookie) runs in CI
without external HTTP. ISSUE-025 (Authlib + Kakao/Apple credentials) is
explicitly **deferred** for Phase 1; the real provider stubs in
:mod:`voicesaju.adapters.auth` raise ``NotImplementedError`` only at call
time so the app still boots under non-mock ``AUTH_PROVIDER`` values.

Architecture-Ref: §6.1 (endpoint shapes), §11.1 (``vs_sess`` cookie +
Redis session), §11 (provider dup-detection by ``email_hash``).
PRD-Ref: FR-016 (user authentication), FR-017 (signup grant).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.adapters import get_auth_adapter
from voicesaju.adapters.auth import AuthAdapter, OAuthCallbackUser, Provider
from voicesaju.db.engine import get_session
from voicesaju.services.token_service import TokenService
from voicesaju.users.services.session_service import (
    SessionStore,
    get_session_store,
)
from voicesaju.users.services.user_service import (
    FindOrCreateOutcome,
    UserResolution,
    UserService,
)

# Mirror architecture §11.1 — 30-day rolling session lifetime, in seconds.
_SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30

# Architecture-defined cookie name (also referenced by middleware once it
# lands in a subsequent users-domain issue).
_SESSION_COOKIE_NAME = "vs_sess"


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _get_auth_adapter_dep() -> AuthAdapter:
    """FastAPI dependency hook so tests can override the adapter cleanly."""
    return get_auth_adapter()


def _get_session_store_dep() -> SessionStore:
    """FastAPI dependency hook so tests can override the session store."""
    return get_session_store()


# ---------------------------------------------------------------------------
# Shared callback finalisation
# ---------------------------------------------------------------------------


async def _finalise_oauth_callback(
    *,
    provider: Provider,
    callback_user: OAuthCallbackUser,
    response: Response,
    db_session: AsyncSession,
    session_store: SessionStore,
) -> dict[str, str | bool]:
    """Resolve a User, mint signup grant if new, issue ``vs_sess`` cookie.

    This is the shared tail of the Kakao + Apple callback flows. Pulling
    it into a single helper keeps both providers behaviourally identical
    (the ISSUE-026 AC explicitly requires Apple callbacks to "create the
    session the same as Kakao") and makes the unit tests provider-agnostic.

    Returns a JSON-serialisable dict so the route handlers can ship it
    straight back to the client; the response is intentionally minimal
    (architecture §6.1) — the cookie is the canonical session carrier.
    """
    user_service = UserService(db_session)
    resolution: UserResolution = await user_service.find_or_create_by_provider(
        provider=provider,
        subject_id=callback_user.subject_id,
        email=callback_user.email,
    )

    # FR-017 — only the freshly-created path mints a signup grant. Found
    # users (either by sub or by email_hash link) keep their existing
    # grant (or lack thereof — historical accounts without one stay so).
    granted = False
    if resolution.outcome == "created":
        token_service = TokenService(db_session)
        # Coerce the str-typed PK back into a UUID for the service call —
        # the model stores it as String(36) for SQLite portability but
        # TokenService's idempotency path expects ``uuid.UUID``.
        user_uuid = (
            resolution.user.id
            if isinstance(resolution.user.id, uuid.UUID)
            else uuid.UUID(str(resolution.user.id))
        )
        grant = await token_service.grant_signup_bonus(user_uuid)
        granted = grant is not None

    # Commit the TX so the session-store-side row (which lives outside
    # the SQL session) cannot reference a user that does not exist.
    await db_session.commit()

    # Mint the server-side session id and write the ``vs_sess`` cookie.
    user_id_str = str(resolution.user.id)
    sid = await session_store.create_session(user_id_str)
    response.set_cookie(
        key=_SESSION_COOKIE_NAME,
        value=sid,
        max_age=_SESSION_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    return {
        "user_id": user_id_str,
        "outcome": resolution.outcome,
        "signup_grant_minted": granted,
        "provider": provider,
    }


# ---------------------------------------------------------------------------
# Kakao
# ---------------------------------------------------------------------------


@router.get(
    "/kakao/start",
    status_code=status.HTTP_200_OK,
)
async def kakao_start(
    adapter: AuthAdapter = Depends(_get_auth_adapter_dep),  # noqa: B008
) -> dict[str, str]:
    """Initiate the Kakao OAuth flow.

    Real providers (ISSUE-025) will 302 to the Kakao consent URL; the mock
    returns a synthetic redirect target so e2e tests can branch on the
    return shape without managing OAuth state.
    """
    redirect_url = adapter.start_login()
    return {"redirect_url": redirect_url, "provider": "kakao"}


@router.get(
    "/kakao/callback",
    status_code=status.HTTP_200_OK,
)
async def kakao_callback(
    code: str,
    response: Response,
    adapter: AuthAdapter = Depends(_get_auth_adapter_dep),  # noqa: B008
    db_session: AsyncSession = Depends(get_session),  # noqa: B008
    session_store: SessionStore = Depends(_get_session_store_dep),  # noqa: B008
) -> dict[str, str | bool]:
    """Handle the Kakao OAuth callback.

    AC (ISSUE-026):
    - Valid Kakao callback → User row created or found by ``kakao_sub``,
      session in store, ``vs_sess`` cookie set.
    - New user signup → exactly one ``free_tokens`` row with
      ``kind='signup_grant'`` (idempotent on retry).
    - Two providers returning the same ``email_hash`` → both link to the
      same User row (architecture §11 dup-detection).
    """
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing OAuth code",
        )
    callback_user = adapter.resolve_oauth_callback(provider="kakao", code=code)
    return await _finalise_oauth_callback(
        provider="kakao",
        callback_user=callback_user,
        response=response,
        db_session=db_session,
        session_store=session_store,
    )


# ---------------------------------------------------------------------------
# Apple
# ---------------------------------------------------------------------------


@router.get(
    "/apple/start",
    status_code=status.HTTP_200_OK,
)
async def apple_start(
    adapter: AuthAdapter = Depends(_get_auth_adapter_dep),  # noqa: B008
) -> dict[str, str]:
    """Initiate the Apple Sign-In flow.

    Real providers (ISSUE-025) will 302 to the Apple authorise URL with
    ``response_mode=form_post``; the mock returns a synthetic target.
    """
    redirect_url = adapter.start_login()
    return {"redirect_url": redirect_url, "provider": "apple"}


@router.post(
    "/apple/callback",
    status_code=status.HTTP_200_OK,
)
async def apple_callback(
    response: Response,
    code: str = Form(...),
    adapter: AuthAdapter = Depends(_get_auth_adapter_dep),  # noqa: B008
    db_session: AsyncSession = Depends(get_session),  # noqa: B008
    session_store: SessionStore = Depends(_get_session_store_dep),  # noqa: B008
) -> dict[str, str | bool]:
    """Handle the Apple ``form_post`` callback.

    Apple convention dictates ``POST application/x-www-form-urlencoded``
    with ``code`` and (optionally) ``id_token`` in the body. ISSUE-026
    ships the ``code`` path; the real ``id_token`` JWKS verification
    arrives with ISSUE-025.

    AC: session created identically to Kakao callback (per ISSUE-026 AC).
    """
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing OAuth code",
        )
    callback_user = adapter.resolve_oauth_callback(provider="apple", code=code)
    return await _finalise_oauth_callback(
        provider="apple",
        callback_user=callback_user,
        response=response,
        db_session=db_session,
        session_store=session_store,
    )


# ---------------------------------------------------------------------------
# Logout (ISSUE-072)
# ---------------------------------------------------------------------------


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
async def logout(
    request: Request,
    response: Response,
    session_store: SessionStore = Depends(_get_session_store_dep),  # noqa: B008
) -> dict[str, bool]:
    """Destroy the caller's session and clear the ``vs_sess`` cookie.

    Architecture-Ref: §11.1 (vs_sess cookie + Redis-backed session).
    PRD-Ref: ISSUE-072 AC1 ("session destroyed and redirected to /").

    Idempotent: callers without a session still get ``{ok: true}`` so
    the frontend can fire-and-forget. The cookie is always cleared on
    the response so a stale browser session is hardened on logout.
    """
    sid = request.cookies.get(_SESSION_COOKIE_NAME)
    if sid:
        # Idempotent — `delete_session` is a no-op for unknown sids.
        await session_store.delete_session(sid)
    # Mirror the cookie attrs from the login path (HttpOnly + Secure +
    # SameSite=lax + path=/) so browsers reliably match the cookie for
    # deletion. We don't set max_age=0 alongside `delete_cookie` because
    # Starlette's `delete_cookie` already emits the canonical "expired"
    # Set-Cookie header.
    response.delete_cookie(
        key=_SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return {"ok": True}


__all__ = [
    "FindOrCreateOutcome",  # re-export for test convenience
    "router",
]
