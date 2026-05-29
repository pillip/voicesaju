"""`SessionService` — server-side session store for `vs_sess` cookie.

PRD-Ref: Architecture §11.1 — `vs_sess` HttpOnly cookie + Redis-backed
session. Phase 1 ships an **in-process** backend so unit tests and the
local dev server work without a Redis instance; the real Redis backend
slots into the same Protocol when ISSUE-100 / ISSUE-NN wires
``redis.asyncio`` (no route-layer changes required).

Contract:
- `create_session(user_id)` returns a fresh `sid` (uuidv7-string) and
  persists `(sid -> user_id)` with a configurable TTL.
- `read_session(sid)` returns the bound `user_id` or `None` if the sid
  is unknown / expired.
- `delete_session(sid)` removes the row; idempotent.

The in-process backend uses a module-level dict guarded by an `asyncio`
lock. Each `Settings`-driven `SessionService` instance reads/writes the
same dict so a process-wide test that mints a session in one request
and reads it in another works without ceremony.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from voicesaju.db.models.users import uuid7

# Default lifetime mirrors the ISSUE-024 device cookie cadence (1 year).
# Real Redis backend should clamp this to whatever the security review
# settles on (architecture §11 hints at 30 days for `vs_sess`).
DEFAULT_SESSION_TTL = timedelta(days=30)


# ---------------------------------------------------------------------------
# Protocol — what the route handlers depend on
# ---------------------------------------------------------------------------


class SessionStore(Protocol):
    """Provider-agnostic session store used by the OAuth callback routes."""

    async def create_session(self, user_id: str) -> str:
        """Mint a fresh session id bound to `user_id` and return it."""
        ...

    async def read_session(self, sid: str) -> str | None:
        """Return the bound `user_id` for `sid`, or None if unknown/expired."""
        ...

    async def delete_session(self, sid: str) -> None:
        """Remove the session row; idempotent."""
        ...


# ---------------------------------------------------------------------------
# In-process backend (Phase 1 default)
# ---------------------------------------------------------------------------


@dataclass
class _SessionRecord:
    user_id: str
    expires_at: datetime


@dataclass
class InMemorySessionStore:
    """Phase 1 default — `dict`-backed session store with TTL enforcement.

    The store is keyed on the session id (uuidv7 string). Expiry is
    checked lazily on read; a dedicated sweeper isn't needed for the
    PoC stack because the test harness recreates the dict per test.
    """

    ttl: timedelta = DEFAULT_SESSION_TTL
    _data: dict[str, _SessionRecord] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def create_session(self, user_id: str) -> str:
        sid = str(uuid7())
        now = datetime.now(UTC)
        async with self._lock:
            self._data[sid] = _SessionRecord(user_id=user_id, expires_at=now + self.ttl)
        return sid

    async def read_session(self, sid: str) -> str | None:
        async with self._lock:
            rec = self._data.get(sid)
            if rec is None:
                return None
            if rec.expires_at < datetime.now(UTC):
                # Lazy expiry — drop the row and treat as missing.
                self._data.pop(sid, None)
                return None
            return rec.user_id

    async def delete_session(self, sid: str) -> None:
        async with self._lock:
            self._data.pop(sid, None)


# Process-wide singleton for the default backend so requests share
# state without each route re-instantiating the dict.
_default_store = InMemorySessionStore()


def get_session_store() -> SessionStore:
    """Return the active session store (in-process for Phase 1)."""
    return _default_store


def reset_default_store_for_tests() -> None:
    """Wipe the in-process backend — used by test fixtures, never in prod."""
    _default_store._data.clear()  # noqa: SLF001 - test helper


__all__ = [
    "DEFAULT_SESSION_TTL",
    "InMemorySessionStore",
    "SessionStore",
    "get_session_store",
    "reset_default_store_for_tests",
]


# Re-export for callers that want type-imports without dragging the
# module path. Mirrors the pattern used by `auth.py`.
def _stable_uuid() -> uuid.UUID:  # pragma: no cover - reserved for future use
    return uuid7()
