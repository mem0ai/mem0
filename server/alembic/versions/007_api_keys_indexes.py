"""Add indexes on api_keys.key_prefix and api_keys.created_by

key_prefix is queried on every API-key authenticated request (WHERE key_prefix = ?
AND revoked_at IS NULL). Without an index this is a full table scan that grows
linearly with the number of keys.

created_by is queried when a user lists their own keys (GET /api-keys).

Revision ID: 007
Revises: 006
Create Date: 2026-08-14

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial index — only active (non-revoked) keys are looked up during auth.
    op.execute(
        text(
            "CREATE INDEX ix_api_keys_key_prefix_active"
            " ON api_keys (key_prefix)"
            " WHERE revoked_at IS NULL"
        )
    )
    op.create_index("ix_api_keys_created_by", "api_keys", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_key_prefix_active", table_name="api_keys")
    op.drop_index("ix_api_keys_created_by", table_name="api_keys")
