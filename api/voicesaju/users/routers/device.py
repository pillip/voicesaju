"""FastAPI router for `POST /api/v1/auth/device` (ISSUE-024).

Issues a server-side ``device_id`` (uuidv7) for an anonymous browser
session. The client passes its own ``device_id_client`` (uuidv4); the
server upserts the row and writes the server-side ``device_id`` to the
``vs_did`` HttpOnly cookie.

PRD-Ref: FR-003 (anonymous trial), FR-013 (free-token ledger for
non-members). Architecture §11.1 — ``vs_did`` HttpOnly cookie.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import UUID4, BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.engine import get_session
from voicesaju.users.services.device_service import DeviceService

# One year, in seconds (per AP-06).
_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


class DeviceUpsertRequest(BaseModel):
    """Body for ``POST /api/v1/auth/device``.

    ``device_id_client`` MUST be a valid UUID; pydantic's ``UUID4``
    discriminator rejects non-uuidv4 strings with a 422 before the
    route handler runs.
    """

    device_id_client: UUID4


class DeviceUpsertResponse(BaseModel):
    """Response body for the device endpoint."""

    device_id: str
    """Server-side device PK (uuidv7). Mirror of the ``vs_did`` cookie."""


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/device",
    response_model=DeviceUpsertResponse,
    status_code=200,
)
async def upsert_device_endpoint(
    body: DeviceUpsertRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> DeviceUpsertResponse:
    """Upsert an anonymous device row and set the ``vs_did`` cookie.

    AC (ISSUE-024):
    - No cookie + first call → row inserted + ``Set-Cookie: vs_did=...``.
    - Same ``device_id_client`` again → existing row's ``last_seen_at``
      updated (no duplicate row).
    - Invalid (non-UUID) ``device_id_client`` → 422 (handled by
      pydantic; never reaches this function body).
    """
    svc = DeviceService(session)
    device = await svc.upsert_device(str(body.device_id_client))
    await session.commit()

    device_id_str = str(device.id) if isinstance(device.id, uuid.UUID) else device.id

    response.set_cookie(
        key="vs_did",
        value=device_id_str,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    return DeviceUpsertResponse(device_id=device_id_str)
