"""add_write_queue_table

Revision ID: b1a2c3d4e5f6
Revises: afd00efbd06b
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, None] = 'afd00efbd06b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'write_queue',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project', sa.String(), nullable=False),
        sa.Column('hostname', sa.String(), nullable=False),
        sa.Column('client_name', sa.String(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('queued', 'processing', 'done', 'failed',
                    name='writequeuestatus'),
            nullable=False,
        ),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_write_queue_project'), 'write_queue', ['project'])
    op.create_index(op.f('ix_write_queue_hostname'), 'write_queue', ['hostname'])
    op.create_index(op.f('ix_write_queue_status'), 'write_queue', ['status'])
    op.create_index(op.f('ix_write_queue_created_at'), 'write_queue', ['created_at'])
    op.create_index(
        'idx_write_queue_status_created', 'write_queue', ['status', 'created_at']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_write_queue_status_created', table_name='write_queue')
    op.drop_index(op.f('ix_write_queue_created_at'), table_name='write_queue')
    op.drop_index(op.f('ix_write_queue_status'), table_name='write_queue')
    op.drop_index(op.f('ix_write_queue_hostname'), table_name='write_queue')
    op.drop_index(op.f('ix_write_queue_project'), table_name='write_queue')
    op.drop_table('write_queue')
