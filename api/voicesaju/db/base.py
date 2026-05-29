"""SQLAlchemy 2.0 DeclarativeBase shared by all ORM models.

Concrete table models (added in later issues) should inherit from `Base`
so that `Base.metadata` collects every table for Alembic autogeneration.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide declarative base."""

    pass
