"""Postgres-backed LangGraph checkpointer.

Replaces MemorySaver so conversation state survives process restarts and
multiple stateless workers can share a single source of truth.

Uses a dedicated psycopg3 connection pool (separate from the asyncpg pool
used by the tools) because langgraph-checkpoint-postgres requires psycopg3.

Setup note
----------
AsyncPostgresSaver.setup() runs all schema migrations in a single transaction
context.  Migrations 6-8 use CREATE INDEX CONCURRENTLY which Postgres forbids
inside a transaction block (raises ActiveSqlTransaction).  We work around this
by running setup() on a direct autocommit=True connection first, then creating
the pool-based saver for all subsequent runtime checkpointing.
"""
from __future__ import annotations

import psycopg
from psycopg_pool import AsyncConnectionPool

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:
    AsyncPostgresSaver = None  # type: ignore[assignment,misc]

from app.config import get_settings

_pool: AsyncConnectionPool | None = None
_saver: "AsyncPostgresSaver | None" = None


async def _run_setup(conninfo: str) -> None:
    """Run AsyncPostgresSaver.setup() on a direct autocommit connection.

    CREATE INDEX CONCURRENTLY (migrations 6-8) cannot run inside a transaction
    block, so we use a single non-pooled connection with autocommit=True.
    setup() is idempotent: it checks checkpoint_migrations and skips already-
    applied steps, so calling it on every startup is safe.
    """
    async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as conn:
        tmp = AsyncPostgresSaver(conn)
        await tmp.setup()


async def init_checkpointer() -> "AsyncPostgresSaver":
    global _pool, _saver
    if _saver is not None:
        return _saver

    if AsyncPostgresSaver is None:
        raise RuntimeError(
            "langgraph-checkpoint-postgres is not installed; "
            "run: pip install 'langgraph-checkpoint-postgres>=2.0.0,<3.0.0'"
        )

    settings = get_settings()

    # Phase 1: run schema migrations on a direct autocommit connection.
    await _run_setup(settings.checkpoint_conninfo)

    # Phase 2: create the pool-based saver for runtime use.
    _pool = AsyncConnectionPool(
        conninfo=settings.checkpoint_conninfo,
        min_size=settings.checkpoint_pool_min,
        max_size=settings.checkpoint_pool_max,
        open=False,
    )
    await _pool.open()
    _saver = AsyncPostgresSaver(_pool)
    return _saver


async def close_checkpointer() -> None:
    global _pool, _saver
    _saver = None
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_checkpointer() -> "AsyncPostgresSaver":
    if _saver is None:
        raise RuntimeError("checkpointer not initialized; call init_checkpointer() first")
    return _saver
