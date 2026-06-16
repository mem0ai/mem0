"""add write_queue.attempts and write_audit_logs

Revision ID: d3c4e5f6a7b8
Revises: c2b3d4e5f6a7
Create Date: 2026-06-15 00:00:00.000000

task_06: bounded retry needs a durable attempts counter on the queue rows.
task_04: durable write-attribution audit (write_audit_logs).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3c4e5f6a7b8'
down_revision: Union[str, None] = 'c2b3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # task_06: retry bookkeeping on the write queue.
    op.add_column(
        'write_queue',
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
    )

    # task_04: durable write-attribution audit trail.
    op.create_table(
        'write_audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=True),
        sa.Column('project', sa.String(), nullable=False),
        sa.Column('hostname', sa.String(), nullable=False),
        sa.Column('client_name', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_write_audit_logs_job_id'), 'write_audit_logs', ['job_id'])
    op.create_index(op.f('ix_write_audit_logs_project'), 'write_audit_logs', ['project'])
    op.create_index(op.f('ix_write_audit_logs_hostname'), 'write_audit_logs', ['hostname'])
    op.create_index(op.f('ix_write_audit_logs_action'), 'write_audit_logs', ['action'])
    op.create_index(op.f('ix_write_audit_logs_created_at'), 'write_audit_logs', ['created_at'])
    op.create_index('idx_write_audit_project_time', 'write_audit_logs', ['project', 'created_at'])
    op.create_index('idx_write_audit_hostname_time', 'write_audit_logs', ['hostname', 'created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_write_audit_hostname_time', table_name='write_audit_logs')
    op.drop_index('idx_write_audit_project_time', table_name='write_audit_logs')
    op.drop_index(op.f('ix_write_audit_logs_created_at'), table_name='write_audit_logs')
    op.drop_index(op.f('ix_write_audit_logs_action'), table_name='write_audit_logs')
    op.drop_index(op.f('ix_write_audit_logs_hostname'), table_name='write_audit_logs')
    op.drop_index(op.f('ix_write_audit_logs_project'), table_name='write_audit_logs')
    op.drop_index(op.f('ix_write_audit_logs_job_id'), table_name='write_audit_logs')
    op.drop_table('write_audit_logs')
    op.drop_column('write_queue', 'attempts')
