"""Domain services.

Service classes encapsulate cross-model invariants that don't belong on
a single ORM model (e.g. idempotent grants in `TokenService`). Each
service takes an `AsyncSession` and is expected to be created per-request
inside the FastAPI dependency chain.
"""

from __future__ import annotations

from voicesaju.services.token_service import TokenService

__all__ = ["TokenService"]
