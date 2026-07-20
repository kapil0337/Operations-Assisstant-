"""HTTP-facing pydantic models."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, description="Omit to start a new session.")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    escalated: bool = False
    awaiting_confirmation: bool = False
    tool_calls: list[str] = Field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""


# ── Async job queue ────────────────────────────────────────────────────────────

class JobSubmitted(BaseModel):
    job_id: str
    session_id: str
    status: str = "queued"


class JobStatus(str, Enum):
    queued = "queued"
    in_progress = "in_progress"
    complete = "complete"
    not_found = "not_found"
    failed = "failed"


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    result: ChatResponse | None = None
    error: str | None = None


# ── Health ─────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str = "unchecked"
    llm_configured: bool


# ── Auth ───────────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    scopes: list[str] = Field(default_factory=lambda: ["chat"])
    api_key: str = Field(..., description="Must match a configured API key to mint a JWT.")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Admin ──────────────────────────────────────────────────────────────────────

class EscalationUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(resolved|reopened)$")
    note: str = Field(default="", max_length=1000)


class InjectMessage(BaseModel):
    session_id: str
    content: str = Field(..., min_length=1, max_length=4000)
    role: str = Field(default="system", pattern=r"^(system|human)$")
