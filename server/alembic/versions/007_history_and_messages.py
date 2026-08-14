"""Create history and messages tables for shared history store

Revision ID: 007
Revises: 006
Create Date: 2026-08-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "history" not in tables:
        op.create_table(
            "history",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("memory_id", sa.Text(), nullable=True),
            sa.Column("old_memory", sa.Text(), nullable=True),
            sa.Column("new_memory", sa.Text(), nullable=True),
            sa.Column("event", sa.Text(), nullable=True),
            sa.Column("created_at", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.Text(), nullable=True),
            sa.Column("is_deleted", sa.Integer(), nullable=True),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("role", sa.Text(), nullable=True),
        )
        op.create_index("ix_history_memory_id_created_at", "history", ["memory_id", "created_at"])

    if "messages" not in tables:
        op.create_table(
            "messages",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("session_scope", sa.Text(), nullable=True),
            sa.Column("role", sa.Text(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("name", sa.Text(), nullable=True),
            sa.Column("created_at", sa.Text(), nullable=True),
        )
        op.create_index("ix_messages_session_scope_created_at", "messages", ["session_scope", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "messages" in tables:
        op.drop_index("ix_messages_session_scope_created_at", table_name="messages")
        op.drop_table("messages")
    if "history" in tables:
        op.drop_index("ix_history_memory_id_created_at", table_name="history")
        op.drop_table("history")
