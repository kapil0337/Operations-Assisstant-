"""004 — add idempotency_key column to tickets for safe replay.

Revision ID: 004_tickets_idempotency_key
"""
from __future__ import annotations

from alembic import op

revision = "004_tickets_idempotency_key"
down_revision = "003_escalation_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='tickets' AND column_name='idempotency_key'
            ) THEN
                ALTER TABLE tickets ADD COLUMN idempotency_key TEXT UNIQUE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE tickets DROP COLUMN IF EXISTS idempotency_key")
