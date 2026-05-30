"""FastAPI router for the Toss WebView bridge (ISSUE-046).

Two endpoints:

* ``POST /api/v1/auth/toss-bridge`` — verifies a Toss-signed JWT,
  upserts the matching ``users`` row by ``toss_id``, issues a
  ``vs_sess`` session cookie with ``SameSite=None; Secure`` (origin
  allowlist gate enforced first).
* ``GET /api/v1/reading/paywall`` — channel-aware payment-method
  enumeration. ``channel=toss_webview`` returns only ``tosspay``;
  default / ``web`` returns the full method list.

Architecture-Ref: §11.1 (cookie attributes), §11.4 (A08 OWASP).
PRD-Ref: FR-016, FR-024, US-14.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.config import Settings, get_settings
from voicesaju.db.engine import get_session
from voicesaju.db.models.users import User
from voicesaju.security.webview_guard import is_allowed_webview_origin
from voicesaju.users.services.toss_bridge_service import (
    InvalidTossBridgeToken,
    verify_toss_bridge_token,
)

bridge_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
paywall_router = APIRouter(prefix="/api/v1/reading", tags=["reading"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class _BridgeRequest(BaseModel):
    token: str


class _BridgeResponse(BaseModel):
    user_id: str
    toss_id: str
    outcome: Literal["created", "found"]


class _PaywallMethod(BaseModel):
    method: Literal["tosspay", "kakaopay"]
    label: str


class _PaywallResponse(BaseModel):
    channel: Literal["web", "toss_webview"]
    methods: list[_PaywallMethod]


# ---------------------------------------------------------------------------
# Bridge route
# ---------------------------------------------------------------------------


def _get_settings() -> Settings:
    return get_settings()


@bridge_router.post(
    "/toss-bridge",
    status_code=status.HTTP_200_OK,
    response_model=_BridgeResponse,
)
async def toss_bridge(
    body: _BridgeRequest,
    response: Response,
    origin: Annotated[str | None, Header(alias="Origin")] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
    settings: Annotated[Settings, Depends(_get_settings)] = ...,  # type: ignore[assignment]
) -> _BridgeResponse:
    """Verify the Toss bridge token + issue a SameSite=None session cookie."""
    if not is_allowed_webview_origin(
        origin or "", allowlist=settings.toss_webview_origin_allowlist
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "origin_not_allowlisted"}},
        )

    try:
        identity = verify_toss_bridge_token(
            token=body.token,
            secret=settings.toss_bridge_secret or "",
            audience=settings.toss_bridge_audience,
        )
    except InvalidTossBridgeToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_token", "message": str(exc)}},
        ) from exc

    existing = (
        await session.execute(select(User).where(User.toss_id == identity.toss_id))
    ).scalar_one_or_none()
    if existing is not None:
        outcome = "found"
        user = existing
    else:
        user = User(toss_id=identity.toss_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        outcome = "created"

    # SameSite=None requires Secure. The origin guard above ensures we
    # only ever do this for documented WebView origins.
    response.set_cookie(
        key="vs_sess",
        value=f"toss-bridge:{user.id}",
        httponly=True,
        secure=True,
        samesite="none",
        max_age=60 * 60 * 24 * 30,
    )

    return _BridgeResponse(
        user_id=str(user.id), toss_id=identity.toss_id, outcome=outcome
    )


# ---------------------------------------------------------------------------
# Paywall route
# ---------------------------------------------------------------------------


_ALL_METHODS: list[_PaywallMethod] = [
    _PaywallMethod(method="tosspay", label="토스로 결제"),
    _PaywallMethod(method="kakaopay", label="카카오페이로 결제"),
]


@paywall_router.get(
    "/paywall",
    status_code=status.HTTP_200_OK,
    response_model=_PaywallResponse,
)
async def paywall(
    channel: Literal["web", "toss_webview"] = "web",
) -> _PaywallResponse:
    """Return the channel-appropriate payment method list."""
    if channel == "toss_webview":
        return _PaywallResponse(
            channel="toss_webview",
            methods=[m for m in _ALL_METHODS if m.method == "tosspay"],
        )
    return _PaywallResponse(channel="web", methods=list(_ALL_METHODS))


__all__ = ["bridge_router", "paywall_router"]
