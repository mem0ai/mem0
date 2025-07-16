"""Create openmemory schema and tables

Revision ID: 7a2521026e06
Revises: afd00efbd06b
Create Date: 2025-07-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a2521026e06'
down_revision = 'afd00efbd06b'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS openmemory")
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('user_id'),
        schema='openmemory'
    )
    op.create_table(
        'apps',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['openmemory.users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_id', 'name', name='idx_app_owner_name'),
        schema='openmemory'
    )
    op.create_table(
        'memories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('app_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('vector', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('state', sa.Enum('active', 'paused', 'archived', 'deleted', name='memorystate'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['app_id'], ['openmemory.apps.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['openmemory.users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='openmemory'
    )
    op.create_table(
        'memory_access_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('memory_id', sa.UUID(), nullable=False),
        sa.Column('app_id', sa.UUID(), nullable=False),
        sa.Column('accessed_at', sa.DateTime(), nullable=True),
        sa.Column('access_type', sa.String(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['app_id'], ['openmemory.apps.id'], ),
        sa.ForeignKeyConstraint(['memory_id'], ['openmemory.memories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='openmemory'
    )
    op.create_table(
        'memory_status_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('memory_id', sa.UUID(), nullable=False),
        sa.Column('changed_by', sa.UUID(), nullable=False),
        sa.Column('old_state', sa.Enum('active', 'paused', 'archived', 'deleted', name='memorystate'), nullable=False),
        sa.Column('new_state', sa.Enum('active', 'paused', 'archived', 'deleted', name='memorystate'), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['changed_by'], ['openmemory.users.id'], ),
        sa.ForeignKeyConstraint(['memory_id'], ['openmemory.memories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='openmemory'
    )


def downgrade():
    op.drop_table('memory_status_history', schema='openmemory')
    op.drop_table('memory_access_logs', schema='openmemory')
    op.drop_table('memories', schema='openmemory')
    op.drop_table('apps', schema='openmemory')
    op.drop_table('users', schema='openmemory')
    op.execute("DROP SCHEMA IF EXISTS openmemory")