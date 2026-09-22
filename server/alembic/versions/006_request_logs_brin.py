"""Swap request_logs.created_at btree index for a BRIN index

Revision ID: 006
Revises: 005
Create Date: 2026-04-21

"""

from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_request_logs_created_at", table_name="request_logs")
    op.execute("CREATE INDEX ix_request_logs_created_at ON request_logs USING BRIN (created_at)")


def downgrade() -> None:
    op.drop_index("ix_request_logs_created_at", table_name="request_logs")
    op.create_index("ix_request_logs_created_at", "request_logs", ["created_at"])
