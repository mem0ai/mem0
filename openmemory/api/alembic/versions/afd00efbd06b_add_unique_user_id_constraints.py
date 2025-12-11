"""remove_global_unique_constraint_on_app_name_add_composite_unique

Revision ID: afd00efbd06b
Revises: add_config_table
Create Date: 2025-06-04 01:59:41.637440

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'afd00efbd06b'
down_revision: Union[str, None] = 'add_config_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    from sqlalchemy import inspect

    # Check if table and indexes exist
    conn = op.get_bind()
    inspector = inspect(conn)

    # Only proceed if apps table exists
    if 'apps' not in inspector.get_table_names():
        return

    indexes = [idx['name'] for idx in inspector.get_indexes('apps')]

    # Drop old unique index if it exists (SAFE - only removes index structure, not data)
    if 'ix_apps_name' in indexes:
        op.drop_index('ix_apps_name', table_name='apps')

    # Create new non-unique index (SAFE - only creates performance structure)
    op.create_index(op.f('ix_apps_name'), 'apps', ['name'], unique=False)

    # Create composite unique index if it doesn't exist
    if 'idx_app_owner_name' not in indexes:
        op.create_index('idx_app_owner_name', 'apps', ['owner_id', 'name'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    from sqlalchemy import inspect

    # Check if table and indexes exist
    conn = op.get_bind()
    inspector = inspect(conn)

    # Only proceed if apps table exists
    if 'apps' not in inspector.get_table_names():
        return

    indexes = [idx['name'] for idx in inspector.get_indexes('apps')]

    # Drop composite unique index if it exists
    if 'idx_app_owner_name' in indexes:
        op.drop_index('idx_app_owner_name', table_name='apps')

    # Drop non-unique index if it exists
    if 'ix_apps_name' in indexes:
        op.drop_index(op.f('ix_apps_name'), table_name='apps')

    # Recreate unique index if it doesn't exist
    if 'ix_apps_name' not in indexes:
        op.create_index('ix_apps_name', 'apps', ['name'], unique=True)