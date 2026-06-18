"""add governance state: quarantined memory state + governance tables

Revision ID: f5a6b7c8d9e0
Revises: e4d5f6a7b8c9
Create Date: 2026-06-18 00:00:00.000000

Fase 3 task_01: ``quarantined`` memory state, ``quarantined_at`` column, and
governance queue/policy/schedule tables (ADR-002, ADR-003, ADR-005).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4d5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOB_TYPE_VALUES = ("dedup", "ttl_prune", "consolidate", "purge")
_JOB_STATUS_VALUES = ("queued", "processing", "done", "failed")


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
                "WHERE t.typname = 'memorystate' AND e.enumlabel = 'quarantined'"
            )
        ).scalar()
        if not exists:
            op.execute("ALTER TYPE memorystate ADD VALUE 'quarantined'")

    op.add_column("memories", sa.Column("quarantined_at", sa.DateTime(), nullable=True))
    op.create_index(
        op.f("ix_memories_quarantined_at"), "memories", ["quarantined_at"], unique=False
    )

    if is_pg:
        postgresql.ENUM(*_JOB_TYPE_VALUES, name="governancejobtype").create(bind, checkfirst=True)
        postgresql.ENUM(*_JOB_STATUS_VALUES, name="governancejobstatus").create(
            bind, checkfirst=True
        )
        job_type_col = postgresql.ENUM(
            *_JOB_TYPE_VALUES, name="governancejobtype", create_type=False
        )
        job_status_col = postgresql.ENUM(
            *_JOB_STATUS_VALUES, name="governancejobstatus", create_type=False
        )
    else:
        job_type_col = sa.String()
        job_status_col = sa.String()

    op.create_table(
        "governance_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_type", job_type_col, nullable=False),
        sa.Column("project", sa.String(), nullable=True),
        sa.Column("status", job_status_col, nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_governance_jobs_job_type"), "governance_jobs", ["job_type"], unique=False
    )
    op.create_index(
        op.f("ix_governance_jobs_project"), "governance_jobs", ["project"], unique=False
    )
    op.create_index(
        op.f("ix_governance_jobs_status"), "governance_jobs", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_governance_jobs_created_at"), "governance_jobs", ["created_at"], unique=False
    )
    op.create_index(
        "idx_governance_jobs_status_created",
        "governance_jobs",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "governance_policies",
        sa.Column("project_name", sa.String(), nullable=False),
        sa.Column("overrides", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_name"], ["projects.name"]),
        sa.PrimaryKeyConstraint("project_name"),
    )

    op.create_table(
        "governance_schedule",
        sa.Column("job_type", job_type_col, nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("job_type", "scope"),
    )
    op.create_index(
        op.f("ix_governance_schedule_last_run_at"),
        "governance_schedule",
        ["last_run_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.drop_index(op.f("ix_governance_schedule_last_run_at"), table_name="governance_schedule")
    op.drop_table("governance_schedule")
    op.drop_table("governance_policies")

    op.drop_index("idx_governance_jobs_status_created", table_name="governance_jobs")
    op.drop_index(op.f("ix_governance_jobs_created_at"), table_name="governance_jobs")
    op.drop_index(op.f("ix_governance_jobs_status"), table_name="governance_jobs")
    op.drop_index(op.f("ix_governance_jobs_project"), table_name="governance_jobs")
    op.drop_index(op.f("ix_governance_jobs_job_type"), table_name="governance_jobs")
    op.drop_table("governance_jobs")

    op.drop_index(op.f("ix_memories_quarantined_at"), table_name="memories")
    op.drop_column("memories", "quarantined_at")

    if is_pg:
        postgresql.ENUM(name="governancejobstatus").drop(bind, checkfirst=True)
        postgresql.ENUM(name="governancejobtype").drop(bind, checkfirst=True)
        # PostgreSQL cannot remove a single enum label from memorystate safely;
        # existing rows retain ``quarantined`` until manually migrated.
