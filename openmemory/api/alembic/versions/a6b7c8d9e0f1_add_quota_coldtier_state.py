"""add quota/cold-tier state: projects.last_activity_at + governancejobtype values

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-06-18 12:00:00.000000

Prontidão para produção task_04 / ADR-005: adiciona ``projects.last_activity_at``
(janela de inatividade do cold tier) e os valores ``enforce_quota`` e
``cold_tier`` ao enum ``governancejobtype``.

Enum: no PostgreSQL os valores são adicionados com ``ALTER TYPE ... ADD VALUE``
(idempotente via checagem em ``pg_enum``); no SQLite o enum é VARCHAR e não exige
alteração.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_JOB_TYPES = ("enforce_quota", "cold_tier")


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.add_column(
        "projects", sa.Column("last_activity_at", sa.DateTime(), nullable=True)
    )
    op.create_index(
        op.f("ix_projects_last_activity_at"), "projects", ["last_activity_at"], unique=False
    )

    if is_pg:
        for value in _NEW_JOB_TYPES:
            exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = 'governancejobtype' AND e.enumlabel = :v"
                ),
                {"v": value},
            ).scalar()
            if not exists:
                op.execute(f"ALTER TYPE governancejobtype ADD VALUE '{value}'")


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_last_activity_at"), table_name="projects")
    op.drop_column("projects", "last_activity_at")
    # PostgreSQL não remove labels de enum com segurança; os valores
    # enforce_quota/cold_tier permanecem no tipo até migração manual.
