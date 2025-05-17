"""add_unique_constraint_owner_id_app_name

Revision ID: 143338ceedf6
Revises: 0b53c747049a
Create Date: 2025-05-17 02:25:42.990169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '143338ceedf6'
down_revision: Union[str, None] = '0b53c747049a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('apps', schema=None) as batch_op:
        try:
            batch_op.drop_index('ix_apps_name')
        except Exception:
            pass
        batch_op.create_unique_constraint('uq_user_app_name', ['owner_id', 'name'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('apps', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_app_name', type_='unique')
        batch_op.create_index('ix_apps_name', ['name'], unique=True)
