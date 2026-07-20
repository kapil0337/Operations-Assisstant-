"""State-changing write tool (flag_refund / create_ticket).

This function performs the actual write ONLY when called by actions_agent
after:
  1. _order_verified_in_history() guard passed (code-level, not prompt)
  2. interrupt() confirmation received from the human

Idempotency: the caller passes an `idempotency_key` (UUID deterministically
derived from session_id + order_id + action_type).  If a ticket with the same
key already exists we return it without writing again — safe to replay.
"""
from __future__ import annotations

import re
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from app.db import get_pool
from app.tools.base import ToolError

_DIGITS_RE = re.compile(r"\d+")


class TakeActionInput(BaseModel):
    action_type: Literal["flag_refund", "create_ticket"]
    order_id: str = Field(..., description="Order id this action applies to.")
    reason: str = Field(..., min_length=3, max_length=500)
    idempotency_key: str = Field(default="", description="Caller-supplied UUID to prevent double-writes on replay.")

    @field_validator("order_id")
    @classmethod
    def must_contain_digits(cls, v: str) -> str:
        if not _DIGITS_RE.search(v):
            raise ValueError("order_id must contain at least one digit")
        return v


@tool("take_action", args_schema=TakeActionInput)
async def take_action(action_type: str, order_id: str, reason: str, idempotency_key: str = "") -> dict:
    """Perform a state-changing action: flag_refund or create_ticket.
    Only called after explicit human confirmation via interrupt/resume."""
    match = _DIGITS_RE.search(order_id)
    if not match:
        raise ToolError("order_id must contain at least one digit")
    numeric_id = int(match.group())

    pool = get_pool()
    order = await pool.fetchrow("SELECT order_id FROM orders WHERE order_id = $1", numeric_id)
    if order is None:
        raise ToolError(f"cannot act on unknown order_id {numeric_id}")

    # Idempotency check
    if idempotency_key:
        existing = await pool.fetchrow(
            "SELECT ticket_id, order_id, type, status, reason, created_at FROM tickets WHERE idempotency_key = $1",
            idempotency_key,
        )
        if existing is not None:
            return {"status": "completed", "ticket": dict(existing), "idempotent_replay": True}

    ticket_type = "refund" if action_type == "flag_refund" else "support_ticket"
    row = await pool.fetchrow(
        """
        INSERT INTO tickets (order_id, type, status, reason, idempotency_key)
        VALUES ($1, $2, 'open', $3, $4)
        RETURNING ticket_id, order_id, type, status, reason, created_at
        """,
        numeric_id,
        ticket_type,
        reason,
        idempotency_key or None,
    )
    return {"status": "completed", "ticket": dict(row)}
