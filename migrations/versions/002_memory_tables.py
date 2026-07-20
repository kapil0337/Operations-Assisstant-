"""002 — long-term user facts + episodic memory tables.

Revision ID: 002_memory_tables
"""
from __future__ import annotations

from alembic import op

revision = "002_memory_tables"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_facts (
            id         SERIAL PRIMARY KEY,
            tenant_id  TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            fact       TEXT NOT NULL,
            embedding  VECTOR(384),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, user_id, fact)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS user_facts_embedding_idx "
        "ON user_facts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id          SERIAL PRIMARY KEY,
            tenant_id   TEXT NOT NULL,
            session_id  TEXT NOT NULL,
            problem     TEXT NOT NULL,
            resolution  TEXT NOT NULL,
            tools_used  TEXT[] NOT NULL DEFAULT '{}',
            outcome     TEXT NOT NULL,
            embedding   VECTOR(384),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS episodes_embedding_idx "
        "ON episodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS episodes")
    op.execute("DROP TABLE IF EXISTS user_facts")
