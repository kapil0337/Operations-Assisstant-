"""ARQ worker — runs as a separate process via `arq app.queue.worker.WorkerSettings`.

Each job is a single agent turn (one HTTP request worth of work).  The worker
initialises the DB pool, Postgres checkpointer, and compiled graph on startup
and tears them down on shutdown so the heavy one-time costs are paid once per
process, not per job.
"""
from __future__ import annotations

import logging

from arq.connections import RedisSettings

from app.config import get_settings
from app.logging_conf import configure_logging, log_event

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    configure_logging()
    from app.db import init_pool
    from app.memory.checkpointer import init_checkpointer
    from app.agent.graph import init_graph
    from app.tools.embeddings import get_model

    await init_pool()
    checkpointer = await init_checkpointer()
    init_graph(checkpointer)
    get_model()   # eager-load embedding model once
    log_event("worker.startup")


async def shutdown(ctx: dict) -> None:
    from app.db import close_pool
    from app.memory.checkpointer import close_checkpointer

    await close_pool()
    await close_checkpointer()
    log_event("worker.shutdown")


async def process_chat(
    ctx: dict,
    message: str,
    session_id: str,
    tenant_id: str,
    user_id: str,
) -> dict:
    """Main job function — drives one agent turn and returns a serialisable result."""
    from app.agent.runner import handle_message

    result = await handle_message(
        message=message,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return {
        "session_id": result.session_id,
        "reply": result.reply,
        "escalated": result.escalated,
        "awaiting_confirmation": result.awaiting_confirmation,
        "tool_calls": result.tool_calls,
        "blocked": result.blocked,
        "block_reason": result.block_reason,
    }


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    on_startup = startup
    on_shutdown = shutdown
    functions = [process_chat]
    job_timeout = get_settings().job_timeout
    max_jobs = 10
    # Keep results in Redis for job_ttl seconds so /result/{id} can poll
    keep_result = get_settings().job_ttl
