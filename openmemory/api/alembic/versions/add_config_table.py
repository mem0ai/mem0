"""add_config_table

Revision ID: add_config_table
Revises: 0b53c747049a
Create Date: 2023-06-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = 'add_config_table'
down_revision = '0b53c747049a'
branch_labels = None
depends_on = None


def upgrade():
    # Create configs table if it doesn't exist
    op.create_table(
        'configs',
        sa.Column('id', sa.UUID(), nullable=False, default=lambda: uuid.uuid4()),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    
    # Create index for key lookups
    op.create_index('idx_configs_key', 'configs', ['key'])


def downgrade():
    # Drop the configs table
    op.drop_index('idx_configs_key', 'configs')
    op.drop_table('configs') 