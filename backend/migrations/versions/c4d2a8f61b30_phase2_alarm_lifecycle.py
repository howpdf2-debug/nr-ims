"""phase2: alarm lifecycle columns (occurrence_count, resolved_at, resolved_by, resolve_note)

Revision ID: c4d2a8f61b30
Revises: b7e19c3a5d20
Create Date: 2026-10-25

Chained AFTER the Phase 3a-1 migration b7e19c3a5d20 (already applied on the Cloud Shell database). Additive only:
every new column is nullable or has a server default, so existing rows and the running code are unaffected.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d2a8f61b30"
down_revision: str | None = "b7e19c3a5d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("alarms", sa.Column("occurrence_count", sa.Integer(), server_default=sa.text("1"), nullable=False))
    op.add_column("alarms", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alarms", sa.Column("resolved_by", sa.String(length=100), nullable=True))
    op.add_column("alarms", sa.Column("resolve_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("alarms", "resolve_note")
    op.drop_column("alarms", "resolved_by")
    op.drop_column("alarms", "resolved_at")
    op.drop_column("alarms", "occurrence_count")