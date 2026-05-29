"""`DeviceService` — anonymous device upsert (ISSUE-024).

Schema source of truth: ``docs/data_model.md`` §4.4 (devices) and AP-06
(``vs_did`` HttpOnly cookie). Implements FR-003 (anonymous trial) and
FR-013 (free-token ledger for non-members).

Idempotency contract:

- The client passes a ``device_id_client`` (uuidv4 from the browser).
  This is the **stable** identifier across sessions until the user
  clears their storage.
- The first call inserts a new ``devices`` row whose server-side
  primary key (``id``, uuidv7) is returned to the caller and persisted
  in the ``vs_did`` cookie.
- Subsequent calls with the same ``device_id_client`` update
  ``last_seen_at`` and return the existing row — no duplicate rows.

The service does NOT commit — the caller (the route) controls the
transaction boundary so a failure later in the request still rolls the
upsert back.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.models.devices import Device
from voicesaju.db.models.users import uuid7


class DeviceService:
    """Anonymous device upsert (idempotent on ``device_id_client``)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_device(
        self,
        device_id_client: str,
        *,
        user_agent_hash: str | None = None,
    ) -> Device:
        """Insert-or-update a device row keyed on ``device_id_client``.

        Returns the persisted ``Device`` (either the newly inserted row
        or the existing row with ``last_seen_at`` refreshed). The
        ``Device.id`` is what the caller writes to the ``vs_did``
        cookie.
        """
        stmt = select(Device).where(Device.device_id_client == device_id_client)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()

        now = datetime.now(UTC)
        if existing is not None:
            existing.last_seen_at = now
            if user_agent_hash is not None:
                existing.user_agent_hash = user_agent_hash
            # `flush` keeps the change visible to subsequent reads
            # inside the same transaction without committing it.
            await self._session.flush()
            return existing

        device = Device(
            id=str(uuid7()),
            device_id_client=device_id_client,
            first_seen_at=now,
            last_seen_at=now,
            user_agent_hash=user_agent_hash,
        )
        self._session.add(device)
        await self._session.flush()
        return device
