"""Enforce at-most-one admin via partial unique index

Revision ID: 004
Revises: 003
Create Date: 2026-04-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_users_only_one_admin",
        "users",
        ["role"],
        unique=True,
        postgresql_where=sa.text("role = 'admin'"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_only_one_admin", table_name="users")
