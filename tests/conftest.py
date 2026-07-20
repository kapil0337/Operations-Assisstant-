"""Shared fixtures: fake pool, fake graph, patched embedder.

All tests run offline and fast — no real Postgres, Redis, or Groq needed.
"""
from __future__ import annotations

import os

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("API_KEYS", "test-api-key")

import pytest

from app import db as app_db
from langgraph.checkpoint.memory import MemorySaver
from app.agent.graph import init_graph


class FakePool:
    """Minimal asyncpg.Pool stand-in dispatching on query substrings."""

    def __init__(self, orders: dict, tickets_by_order: dict | None = None):
        self.orders = orders
        self.tickets_by_order = tickets_by_order or {}
        self.inserted_tickets: list[dict] = []
        self.inserted_escalations: list[dict] = []
        self._ticket_seq = 1
        self._escalation_seq = 1

    async def fetchrow(self, query: str, *args):
        q = query.lower()
        if "insert into tickets" in q:
            order_id, ttype, reason = args[0], args[1], args[2]
            idem = args[3] if len(args) > 3 else None
            row = {
                "ticket_id": self._ticket_seq,
                "order_id": order_id,
                "type": ttype,
                "status": "open",
                "reason": reason,
                "created_at": "2024-01-01T00:00:00Z",
            }
            self._ticket_seq += 1
            self.inserted_tickets.append(row)
            return row
        if "idempotency_key" in q and "select" in q:
            return None  # no existing idempotent ticket
        if "insert into escalations" in q:
            session_id, reason, summary = args[0], args[1], args[2]
            row = {
                "id": self._escalation_seq,
                "session_id": session_id,
                "reason": reason,
                "summary": summary,
                "created_at": "2024-01-01T00:00:00Z",
            }
            self._escalation_seq += 1
            self.inserted_escalations.append(row)
            return row
        if "from orders" in q:
            order_id = args[0]
            order = self.orders.get(order_id)
            return dict(order) if order else None
        raise AssertionError(f"FakePool.fetchrow: unexpected query: {query!r}")

    async def fetch(self, query: str, *args):
        q = query.lower()
        if "from tickets" in q:
            order_id = args[0]
            return [dict(t) for t in self.tickets_by_order.get(order_id, [])]
        if "from kb_chunks" in q:
            return [{"source": "refund_policy.md", "content": "Fake KB passage.", "score": 0.9}]
        if "from user_facts" in q:
            return []
        if "from episodes" in q:
            return []
        raise AssertionError(f"FakePool.fetch: unexpected query: {query!r}")

    async def fetchval(self, query: str, *args):
        return 1

    async def execute(self, query: str, *args):
        return "OK"


DEFAULT_ORDERS = {
    1042: {
        "order_id": 1042,
        "customer_email": "alex@example.com",
        "item": "Wireless Mouse",
        "amount_cents": 2999,
        "status": "processing",
        "charge_count": 2,
        "created_at": "2024-01-01T00:00:00Z",
    },
    2001: {
        "order_id": 2001,
        "customer_email": "jordan@example.com",
        "item": "USB-C Cable",
        "amount_cents": 1299,
        "status": "shipped",
        "charge_count": 1,
        "created_at": "2024-01-01T00:00:00Z",
    },
    4090: {
        "order_id": 4090,
        "customer_email": "riley@example.com",
        "item": "Mechanical Keyboard",
        "amount_cents": 8999,
        "status": "delivered",
        "charge_count": 1,
        "created_at": "2024-01-01T00:00:00Z",
    },
}


@pytest.fixture
def fake_pool(monkeypatch):
    pool = FakePool(orders=dict(DEFAULT_ORDERS))
    app_db.set_pool(pool)
    monkeypatch.setattr("app.tools.embeddings.embed_text", lambda *_a, **_kw: [0.0] * 384)
    # Use MemorySaver in tests (no real Postgres checkpointer needed)
    init_graph(MemorySaver())
    yield pool
    app_db.set_pool(None)
    # Reset graph so next test gets a fresh one
    import app.agent.graph as g
    g._graph = None
