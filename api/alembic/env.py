"""Alembic environment configured for SQLAlchemy 2.0 async.

The connection URL is read from `Settings.database_url` at runtime
(not from `alembic.ini`) so the same migration set works against
local docker-compose, staging, and prod without editing config files.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from voicesaju.config import get_settings
from voicesaju.db import (
    models as _models,  # noqa: F401  (registers models on Base.metadata)
)
from voicesaju.db.base import Base
from voicesaju.db.engine import build_async_url

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the async DB URL from Settings so alembic.ini stays env-agnostic.
settings = get_settings()
config.set_main_option("sqlalchemy.url", build_async_url(settings.database_url))

# Target metadata: every model importing Base will populate this.
# Future issues will import their models here so autogenerate sees them.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In 'online' mode, build an AsyncEngine and run migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
