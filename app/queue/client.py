"""ARQ Redis client — used by the API to enqueue agent jobs."""
from __future__ import annotations

import arq
from arq.connections import RedisSettings

from app.config import get_settings

_pool: arq.ArqRedis | None = None


def _redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(settings.redis_url)


async def init_redis_pool() -> arq.ArqRedis:
    global _pool
    if _pool is None:
        _pool = await arq.create_pool(_redis_settings())
    return _pool


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


def get_redis_pool() -> arq.ArqRedis:
    if _pool is None:
        raise RuntimeError("Redis pool not initialised; call init_redis_pool() first")
    return _pool


async def enqueue_chat(
    message: str,
    session_id: str,
    tenant_id: str,
    user_id: str,
) -> str:
    """Enqueue a chat turn and return the job_id."""
    settings = get_settings()
    pool = get_redis_pool()
    job = await pool.enqueue_job(
        "process_chat",
        message,
        session_id,
        tenant_id,
        user_id,
        _job_try=1,
        _expires=settings.job_ttl,
    )
    return job.job_id
