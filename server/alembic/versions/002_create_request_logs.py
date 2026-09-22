"""Create request_logs table

Revision ID: 002
Revises: 001
Create Date: 2026-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "request_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("auth_type", sa.String(32), nullable=False, server_default="none"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_request_logs_created_at", "request_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_request_logs_created_at", table_name="request_logs")
    op.drop_table("request_logs")
