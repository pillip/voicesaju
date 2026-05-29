"""ORM model exports.

Importing this package registers every model on `Base.metadata`, so it is
safe (and required) to import here in `alembic/env.py` for autogenerate
and at startup before any session is opened.
"""

from __future__ import annotations

from voicesaju.db.models.devices import Device
from voicesaju.db.models.users import User

__all__ = ["Device", "User"]
