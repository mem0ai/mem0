"""Create refresh_token_jtis table for single-use refresh tokens

Revision ID: 005
Revises: 004
Create Date: 2026-04-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_token_jtis",
        sa.Column("jti", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_token_jtis_expires_at", "refresh_token_jtis", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_token_jtis_expires_at", table_name="refresh_token_jtis")
    op.drop_table("refresh_token_jtis")
