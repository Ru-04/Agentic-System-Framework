"""Alembic environment. Raw-SQL migrations; no ORM autogenerate (see Increment 1 plan, T3)."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config


def _database_url() -> str:
    url = os.environ.get("WEBDESK_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "WEBDESK_DATABASE_URL is not set. Migrations need the owner-role URL; "
            "refusing to fall back to a default."
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
