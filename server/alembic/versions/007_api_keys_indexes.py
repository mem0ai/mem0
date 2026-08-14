"""Index api_keys lookup columns (key_prefix, created_by)

Revision ID: 007
Revises: 006
Create Date: 2026-08-14

Every API-key authenticated request resolves the caller with
``WHERE key_prefix = ? AND revoked_at IS NULL`` (see auth._resolve_user_from_api_key),
and the key-listing endpoint filters on ``created_by``. Neither column was
indexed, so both queries fell back to a sequential scan whose cost grows with
the number of keys. Add:

  * a partial index on ``key_prefix`` restricted to live keys, so it stays small
    and matches the auth query's ``revoked_at IS NULL`` predicate exactly;
  * a plain index on ``created_by`` for the per-user listing query.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_api_keys_key_prefix_active "
        "ON api_keys (key_prefix) WHERE revoked_at IS NULL"
    )
    op.create_index("ix_api_keys_created_by", "api_keys", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_created_by", table_name="api_keys")
    op.drop_index("ix_api_keys_key_prefix_active", table_name="api_keys")
