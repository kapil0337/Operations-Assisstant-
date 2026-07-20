"""003 — add status + resolution_note columns to escalations (for admin PATCH).

Revision ID: 003_escalation_status
"""
from __future__ import annotations

from alembic import op

revision = "003_escalation_status"
down_revision = "002_memory_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safe: IF NOT EXISTS via DO block to guard re-runs.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='escalations' AND column_name='status'
            ) THEN
                ALTER TABLE escalations ADD COLUMN status TEXT NOT NULL DEFAULT 'open';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='escalations' AND column_name='resolution_note'
            ) THEN
                ALTER TABLE escalations ADD COLUMN resolution_note TEXT NOT NULL DEFAULT '';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='escalations' AND column_name='resolved_at'
            ) THEN
                ALTER TABLE escalations ADD COLUMN resolved_at TIMESTAMPTZ;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE escalations DROP COLUMN IF EXISTS resolved_at")
    op.execute("ALTER TABLE escalations DROP COLUMN IF EXISTS resolution_note")
    op.execute("ALTER TABLE escalations DROP COLUMN IF EXISTS status")
