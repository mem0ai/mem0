"""Create core namespace tables.

Revision ID: 0001_create_core_tables
Revises:
Create Date: 2026-04-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_create_core_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "namespaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("source_systems", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_namespaces_name", "namespaces", ["name"], unique=True)

    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("namespace_id", sa.String(length=36), nullable=False),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace_id", "name", name="uq_agents_namespace_name"),
    )
    op.create_index("ix_agents_namespace_id", "agents", ["namespace_id"], unique=False)

    op.create_table(
        "memory_spaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("namespace_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("space_type", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parent_space_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["parent_space_id"], ["memory_spaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace_id", "agent_id", "space_type", name="uq_memory_spaces_scope"),
    )
    op.create_index("ix_memory_spaces_agent_id", "memory_spaces", ["agent_id"], unique=False)
    op.create_index("ix_memory_spaces_namespace_id", "memory_spaces", ["namespace_id"], unique=False)

    op.create_table(
        "memory_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("namespace_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("project_id", sa.String(length=255), nullable=True),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("event_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["space_id"], ["memory_spaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_events_agent_id", "memory_events", ["agent_id"], unique=False)
    op.create_index("ix_memory_events_dedupe_key", "memory_events", ["dedupe_key"], unique=False)
    op.create_index("ix_memory_events_namespace_id", "memory_events", ["namespace_id"], unique=False)
    op.create_index("ix_memory_events_session_id", "memory_events", ["session_id"], unique=False)
    op.create_index("ix_memory_events_space_id", "memory_events", ["space_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_memory_events_space_id", table_name="memory_events")
    op.drop_index("ix_memory_events_session_id", table_name="memory_events")
    op.drop_index("ix_memory_events_namespace_id", table_name="memory_events")
    op.drop_index("ix_memory_events_dedupe_key", table_name="memory_events")
    op.drop_index("ix_memory_events_agent_id", table_name="memory_events")
    op.drop_table("memory_events")

    op.drop_index("ix_memory_spaces_namespace_id", table_name="memory_spaces")
    op.drop_index("ix_memory_spaces_agent_id", table_name="memory_spaces")
    op.drop_table("memory_spaces")

    op.drop_index("ix_agents_namespace_id", table_name="agents")
    op.drop_table("agents")

    op.drop_index("ix_namespaces_name", table_name="namespaces")
    op.drop_table("namespaces")
