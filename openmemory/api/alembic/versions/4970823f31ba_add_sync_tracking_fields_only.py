"""add_sync_tracking_fields_only

Revision ID: 4970823f31ba
Revises: 3a1b2c3d4e5f
Create Date: 2025-07-07 02:20:39.893830

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4970823f31ba'
down_revision: Union[str, None] = '3a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add sync tracking fields to apps table."""
    # Add the sync tracking columns to the apps table
    op.add_column('apps', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.add_column('apps', sa.Column('sync_status', sa.String(), nullable=True))
    op.add_column('apps', sa.Column('sync_error', sa.Text(), nullable=True))
    op.add_column('apps', sa.Column('total_memories_created', sa.Integer(), nullable=True))
    op.add_column('apps', sa.Column('total_memories_accessed', sa.Integer(), nullable=True))
    
    # Add indexes for performance
    op.create_index('ix_apps_last_synced_at', 'apps', ['last_synced_at'])
    op.create_index('ix_apps_sync_status', 'apps', ['sync_status'])
    op.create_index('ix_apps_total_memories_created', 'apps', ['total_memories_created'])
    op.create_index('ix_apps_total_memories_accessed', 'apps', ['total_memories_accessed'])
    
    # Set default values for existing records
    op.execute("UPDATE apps SET sync_status = 'idle' WHERE sync_status IS NULL")
    op.execute("UPDATE apps SET total_memories_created = 0 WHERE total_memories_created IS NULL")
    op.execute("UPDATE apps SET total_memories_accessed = 0 WHERE total_memories_accessed IS NULL")


def downgrade() -> None:
    """Remove sync tracking fields from apps table."""
    # Drop indexes
    op.drop_index('ix_apps_total_memories_accessed', 'apps')
    op.drop_index('ix_apps_total_memories_created', 'apps')
    op.drop_index('ix_apps_sync_status', 'apps')
    op.drop_index('ix_apps_last_synced_at', 'apps')
    
    # Drop columns
    op.drop_column('apps', 'total_memories_accessed')
    op.drop_column('apps', 'total_memories_created')
    op.drop_column('apps', 'sync_error')
    op.drop_column('apps', 'sync_status')
    op.drop_column('apps', 'last_synced_at')
