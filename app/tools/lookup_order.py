"""Read-only, parameterized lookup against the seeded orders/tickets tables.

The agent must never invent order data -- this is the only source of truth,
and it explicitly reports `not_found` rather than letting the model guess.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from app.db import get_pool
from app.tools.base import ToolError
from langchain_core.tools import tool

_DIGITS_RE = re.compile(r"\d+")


class LookupOrderInput(BaseModel):
    order_id: str = Field(..., description="Order id, e.g. '1042' or '#1042'.")

    @field_validator("order_id")
    @classmethod
    def must_contain_digits(cls, v: str) -> str:
        if not _DIGITS_RE.search(v):
            raise ValueError("order_id must contain at least one digit")
        return v


@tool("lookup_order", args_schema=LookupOrderInput)
async def lookup_order(order_id: str) -> dict:
    """Look up an order (and any associated tickets) by id. Returns the
    real database record, or status='not_found' if no such order exists.
    Never fabricate order details -- only report what this tool returns."""
    match = _DIGITS_RE.search(order_id)
    if not match:
        raise ToolError("order_id must contain at least one digit")
    numeric_id = int(match.group())

    pool = get_pool()
    order = await pool.fetchrow(
        """
        SELECT order_id, customer_email, item, amount_cents, status, charge_count, created_at
        FROM orders WHERE order_id = $1
        """,
        numeric_id,
    )
    if order is None:
        return {"status": "not_found", "order_id": numeric_id}

    tickets = await pool.fetch(
        "SELECT ticket_id, type, status, reason, created_at FROM tickets WHERE order_id = $1 ORDER BY created_at",
        numeric_id,
    )
    return {
        "status": "found",
        "order": dict(order),
        "tickets": [dict(t) for t in tickets],
    }
