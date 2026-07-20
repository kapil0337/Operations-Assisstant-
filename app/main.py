"""FastAPI application.

Endpoints:
  POST /chat           — async: enqueue job, return job_id + session_id
  GET  /result/{id}    — poll for job result
  POST /chat/sync      — synchronous path (eval harness, dev, tests)
  GET  /health
  POST /token          — mint a JWT for a user
  POST /admin/escalations/{id}  — resolve / reopen an escalation
  POST /admin/sessions/{id}/inject  — inject a system message into a session
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from arq.jobs import Job, JobStatus as ArqJobStatus
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.auth.middleware import Principal, get_principal, get_principal_optional
from app.auth.jwt_utils import create_access_token
from app.config import get_settings
from app.db import close_pool, get_pool, init_pool
from app.guardrails.input_guard import InputGuard
from app.guardrails.output_guard import OutputGuard
from app.logging_conf import configure_logging, log_event
from app.memory.checkpointer import close_checkpointer, init_checkpointer
from app.observability.otel import instrument_fastapi
from app.queue.client import close_redis_pool, enqueue_chat, get_redis_pool, init_redis_pool
from app.schemas import (
    ChatRequest, ChatResponse, EscalationUpdate, HealthResponse,
    InjectMessage, JobResult, JobStatus, JobSubmitted, TokenRequest, TokenResponse,
)

_input_guard = InputGuard()
_output_guard = OutputGuard()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await init_pool()
    checkpointer = await init_checkpointer()

    from app.agent.graph import init_graph
    from app.tools.embeddings import get_model
    init_graph(checkpointer)
    get_model()  # eager-load embedding model

    await init_redis_pool()
    log_event("app.startup")
    instrument_fastapi(app)
    yield
    await close_pool()
    await close_checkpointer()
    await close_redis_pool()
    log_event("app.shutdown")


app = FastAPI(title="Operations Assistant (multi-agent)", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth endpoint ──────────────────────────────────────────────────────────────

@app.post("/token", response_model=TokenResponse)
async def mint_token(req: TokenRequest) -> TokenResponse:
    if req.api_key not in settings.api_key_set:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
    token = create_access_token(req.user_id, req.tenant_id, req.scopes)
    return TokenResponse(access_token=token)


# ── Chat endpoints ─────────────────────────────────────────────────────────────

@app.post("/chat", response_model=JobSubmitted)
async def chat_async(
    request: ChatRequest,
    principal: Principal = Depends(get_principal_optional),
) -> JobSubmitted:
    """Enqueue an agent turn; returns job_id for polling."""
    guard = _input_guard.check(request.message)
    if not guard.allowed:
        log_event("guardrail.input_blocked", reason=guard.block_reason)
        raise HTTPException(status_code=400, detail=guard.block_reason)

    session_id = request.session_id or str(uuid.uuid4())
    job_id = await enqueue_chat(
        message=request.message,
        session_id=session_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )
    return JobSubmitted(job_id=job_id, session_id=session_id)


@app.get("/result/{job_id}", response_model=JobResult)
async def get_job_result(
    job_id: str,
    _principal: Principal = Depends(get_principal_optional),
) -> JobResult:
    """Poll for the result of a previously enqueued chat job."""
    pool = get_redis_pool()
    job = Job(job_id, pool)
    info = await job.info()

    if info is None:
        return JobResult(job_id=job_id, status=JobStatus.not_found)

    if info.status in (ArqJobStatus.deferred, ArqJobStatus.queued):
        return JobResult(job_id=job_id, status=JobStatus.queued)

    if info.status == ArqJobStatus.in_progress:
        return JobResult(job_id=job_id, status=JobStatus.in_progress)

    if info.status == ArqJobStatus.not_found:
        return JobResult(job_id=job_id, status=JobStatus.not_found)

    # complete or failed
    try:
        raw = await job.result(timeout=0)
    except Exception as exc:
        return JobResult(job_id=job_id, status=JobStatus.failed, error=str(exc))

    if raw is None:
        return JobResult(job_id=job_id, status=JobStatus.failed, error="job returned no result")

    # Apply output guardrail (PII redaction)
    reply = _output_guard._redact_pii(raw.get("reply", ""))
    return JobResult(
        job_id=job_id,
        status=JobStatus.complete,
        result=ChatResponse(
            session_id=raw["session_id"],
            reply=reply,
            escalated=raw.get("escalated", False),
            awaiting_confirmation=raw.get("awaiting_confirmation", False),
            tool_calls=raw.get("tool_calls", []),
            blocked=raw.get("blocked", False),
            block_reason=raw.get("block_reason", ""),
        ),
    )


@app.post("/chat/sync", response_model=ChatResponse)
async def chat_sync(
    request: ChatRequest,
    principal: Principal = Depends(get_principal_optional),
) -> ChatResponse:
    """Synchronous chat — runs the agent in-process.  For eval harness and dev."""
    guard = _input_guard.check(request.message)
    if not guard.allowed:
        log_event("guardrail.input_blocked", reason=guard.block_reason)
        return ChatResponse(
            session_id=request.session_id or str(uuid.uuid4()),
            reply="I'm sorry, I can't help with that request.",
            blocked=True,
            block_reason=guard.block_reason,
        )

    from app.agent.runner import handle_message
    try:
        result = await handle_message(
            request.message,
            session_id=request.session_id,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
        )
    except Exception as exc:
        log_event("chat.error", error=str(exc))
        raise HTTPException(status_code=500, detail="agent failed to process the request") from exc

    reply = _output_guard.check_and_redact(result.reply, [])
    return ChatResponse(
        session_id=result.session_id,
        reply=reply,
        escalated=result.escalated,
        awaiting_confirmation=result.awaiting_confirmation,
        tool_calls=result.tool_calls,
        blocked=result.blocked,
        block_reason=result.block_reason,
    )


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_status = "ok"
    try:
        await get_pool().fetchval("SELECT 1")
    except Exception as exc:
        db_status = f"error: {exc}"

    redis_status = "ok"
    try:
        await get_redis_pool().ping()
    except Exception as exc:
        redis_status = f"error: {exc}"

    return HealthResponse(
        status="ok",
        database=db_status,
        redis=redis_status,
        llm_configured=settings.llm_configured,
    )


# ── Admin endpoints ────────────────────────────────────────────────────────────

@app.patch("/admin/escalations/{escalation_id}")
async def update_escalation(
    escalation_id: int,
    body: EscalationUpdate,
    principal: Principal = Depends(get_principal),
) -> dict:
    if not principal.can("admin"):
        raise HTTPException(status_code=403, detail="admin scope required")
    pool = get_pool()
    row = await pool.fetchrow(
        """
        UPDATE escalations
        SET status = $1, resolution_note = $2, resolved_at = CASE WHEN $1 = 'resolved' THEN now() ELSE NULL END
        WHERE id = $3
        RETURNING id, status, resolution_note, resolved_at
        """,
        body.status, body.note, escalation_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"escalation {escalation_id} not found")
    return dict(row)


@app.post("/admin/sessions/{session_id}/inject")
async def inject_message(
    session_id: str,
    body: InjectMessage,
    principal: Principal = Depends(get_principal),
) -> dict:
    """Inject a system or human message into an existing session's checkpoint state."""
    if not principal.can("admin"):
        raise HTTPException(status_code=403, detail="admin scope required")

    from app.agent.graph import get_graph
    from langchain_core.messages import HumanMessage, SystemMessage
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")

    msg = SystemMessage(content=body.content) if body.role == "system" else HumanMessage(content=body.content)
    await graph.aupdate_state(config, {"messages": [msg]})
    log_event("admin.inject_message", session_id=session_id, role=body.role)
    return {"ok": True, "session_id": session_id}
