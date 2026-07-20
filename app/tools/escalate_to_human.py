"""Escalation tool: used when confidence is low or the request is out of scope."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.db import get_pool
from langchain_core.tools import tool


class EscalateInput(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300, description="Why this needs a human.")
    summary: str = Field(..., min_length=3, max_length=1000, description="Summary of the request for the human agent.")


@tool("escalate_to_human", args_schema=EscalateInput)
async def escalate_to_human(reason: str, summary: str, session_id: str = "unknown") -> dict:
    """Hand the conversation off to a human agent. Use this when the request is
    out of scope, unanswerable from the KB/order data, or confidence is low --
    never guess instead of escalating."""
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO escalations (session_id, reason, summary)
        VALUES ($1, $2, $3)
        RETURNING id, session_id, reason, summary, created_at
        """,
        session_id,
        reason,
        summary,
    )
    return {"status": "escalated", "escalation": dict(row)}
