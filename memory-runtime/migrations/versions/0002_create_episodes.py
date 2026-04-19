"""Create episodes table.

Revision ID: 0002_create_episodes
Revises: 0001_create_core_tables
Create Date: 2026-04-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_create_episodes"
down_revision = "0001_create_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "episodes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("namespace_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("start_event_id", sa.String(length=36), nullable=False),
        sa.Column("end_event_id", sa.String(length=36), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("raw_text", sa.String(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("importance_hint", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["end_event_id"], ["memory_events.id"]),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["space_id"], ["memory_spaces.id"]),
        sa.ForeignKeyConstraint(["start_event_id"], ["memory_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_episodes_agent_id", "episodes", ["agent_id"], unique=False)
    op.create_index("ix_episodes_namespace_id", "episodes", ["namespace_id"], unique=False)
    op.create_index("ix_episodes_session_id", "episodes", ["session_id"], unique=False)
    op.create_index("ix_episodes_space_id", "episodes", ["space_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_episodes_space_id", table_name="episodes")
    op.drop_index("ix_episodes_session_id", table_name="episodes")
    op.drop_index("ix_episodes_namespace_id", table_name="episodes")
    op.drop_index("ix_episodes_agent_id", table_name="episodes")
    op.drop_table("episodes")
