"""Create memory units, jobs, and audit log tables.

Revision ID: 0003_create_memory_units_jobs_and_audit
Revises: 0002_create_episodes
Create Date: 2026-04-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_create_memory_units_jobs_and_audit"
down_revision = "0002_create_episodes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_job_type", "jobs", ["job_type"], unique=False)
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)

    op.create_table(
        "memory_units",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("namespace_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("primary_space_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("importance_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("freshness_score", sa.Float(), nullable=False),
        sa.Column("durability_score", sa.Float(), nullable=False),
        sa.Column("access_count", sa.Integer(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_from_episode_id", sa.String(length=36), nullable=True),
        sa.Column("supersedes_memory_id", sa.String(length=36), nullable=True),
        sa.Column("merge_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["created_from_episode_id"], ["episodes.id"]),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["primary_space_id"], ["memory_spaces.id"]),
        sa.ForeignKeyConstraint(["supersedes_memory_id"], ["memory_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_units_agent_id", "memory_units", ["agent_id"], unique=False)
    op.create_index("ix_memory_units_merge_key", "memory_units", ["merge_key"], unique=False)
    op.create_index("ix_memory_units_namespace_id", "memory_units", ["namespace_id"], unique=False)
    op.create_index("ix_memory_units_primary_space_id", "memory_units", ["primary_space_id"], unique=False)
    op.create_index("ix_memory_units_status", "memory_units", ["status"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("namespace_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_agent_id", "audit_log", ["agent_id"], unique=False)
    op.create_index("ix_audit_log_namespace_id", "audit_log", ["namespace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_log_namespace_id", table_name="audit_log")
    op.drop_index("ix_audit_log_agent_id", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_memory_units_status", table_name="memory_units")
    op.drop_index("ix_memory_units_primary_space_id", table_name="memory_units")
    op.drop_index("ix_memory_units_namespace_id", table_name="memory_units")
    op.drop_index("ix_memory_units_merge_key", table_name="memory_units")
    op.drop_index("ix_memory_units_agent_id", table_name="memory_units")
    op.drop_table("memory_units")

    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_job_type", table_name="jobs")
    op.drop_table("jobs")
