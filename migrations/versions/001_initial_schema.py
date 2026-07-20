"""001 — initial schema (orders, tickets, escalations, kb_chunks).

Revision ID: 001_initial_schema
"""
from __future__ import annotations

from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id     INTEGER PRIMARY KEY,
            customer_email TEXT NOT NULL,
            item         TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            status       TEXT NOT NULL,
            charge_count INTEGER NOT NULL DEFAULT 1,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id  SERIAL PRIMARY KEY,
            order_id   INTEGER NOT NULL REFERENCES orders(order_id),
            type       TEXT NOT NULL,
            status     TEXT NOT NULL,
            reason     TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            id              SERIAL PRIMARY KEY,
            session_id      TEXT NOT NULL,
            reason          TEXT NOT NULL,
            summary         TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'open',
            resolution_note TEXT NOT NULL DEFAULT '',
            resolved_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS kb_chunks (
            id        SERIAL PRIMARY KEY,
            source    TEXT NOT NULL,
            content   TEXT NOT NULL,
            embedding VECTOR(384) NOT NULL
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx ON kb_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kb_chunks")
    op.execute("DROP TABLE IF EXISTS escalations")
    op.execute("DROP TABLE IF EXISTS tickets")
    op.execute("DROP TABLE IF EXISTS orders")
