"""Alembic env.py — async runner using asyncpg via SQLAlchemy 2.0."""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override URL from environment (used by Docker compose)
db_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url", ""))
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        await conn.run_sync(_run_sync)
    await engine.dispose()


def _run_sync(conn):
    context.configure(connection=conn, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
