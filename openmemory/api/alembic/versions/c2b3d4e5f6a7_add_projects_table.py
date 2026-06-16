"""add_projects_table

Revision ID: c2b3d4e5f6a7
Revises: b1a2c3d4e5f6
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2b3d4e5f6a7'
down_revision: Union[str, None] = 'b1a2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'projects',
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('first_seen_hostname', sa.String(), nullable=True),
        sa.Column('memory_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('name'),
    )
    op.create_index(op.f('ix_projects_created_at'), 'projects', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_projects_created_at'), table_name='projects')
    op.drop_table('projects')
