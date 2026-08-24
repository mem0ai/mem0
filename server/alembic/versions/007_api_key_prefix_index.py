"""Add index on api_keys.key_prefix for auth lookups

Revision ID: 007
Revises: 006
Create Date: 2026-08-24

verify_auth resolves X-API-Key credentials with
WHERE key_prefix = ? AND revoked_at IS NULL on every request; without this
index that is a full sequential scan of api_keys per authenticated call.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_key_prefix ON api_keys (key_prefix)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_api_keys_key_prefix")
