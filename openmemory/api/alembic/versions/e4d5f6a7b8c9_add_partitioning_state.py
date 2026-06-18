"""add partitioning state: migration_state table + projects.partition_tier/shard_key

Revision ID: e4d5f6a7b8c9
Revises: d3c4e5f6a7b8
Create Date: 2026-06-17 00:00:00.000000

task_01 / ADR-002 / ADR-003: foundation for Qdrant partitioning (Fase 2).
Adds the global blue-green migration state and per-project partition columns.

Enum handling is dialect-aware: PostgreSQL gets native ENUM types (created once,
columns reference them with ``create_type=False`` to avoid double creation);
SQLite stores the values as plain strings, which is exactly what SQLAlchemy's
``Enum`` compiles to on that backend.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4d5f6a7b8c9'
down_revision: Union[str, None] = 'd3c4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIER_VALUES = ('shared', 'dedicated')
_STATUS_VALUES = ('planned', 'copying', 'validating', 'flipped', 'rolled_back', 'done')


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    is_pg = bind.dialect.name == 'postgresql'

    if is_pg:
        postgresql.ENUM(*_TIER_VALUES, name='partitiontier').create(bind, checkfirst=True)
        postgresql.ENUM(*_STATUS_VALUES, name='migrationstatus').create(bind, checkfirst=True)
        tier_type = postgresql.ENUM(*_TIER_VALUES, name='partitiontier', create_type=False)
        status_type = postgresql.ENUM(*_STATUS_VALUES, name='migrationstatus', create_type=False)
    else:
        # SQLite (and other non-native-enum backends): Enum -> VARCHAR.
        tier_type = sa.String()
        status_type = sa.String()

    # Per-project partition state (ADR-002).
    op.add_column(
        'projects',
        sa.Column('partition_tier', tier_type, nullable=False, server_default='shared'),
    )
    op.add_column('projects', sa.Column('shard_key', sa.String(), nullable=True))

    # Global blue-green migration state (ADR-003).
    op.create_table(
        'migration_state',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_collection', sa.String(), nullable=False),
        sa.Column('target_collection', sa.String(), nullable=False),
        sa.Column('active_collection', sa.String(), nullable=False),
        sa.Column('dual_write_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('scroll_cursor', sa.String(), nullable=True),
        sa.Column('status', status_type, nullable=False, server_default='planned'),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    is_pg = bind.dialect.name == 'postgresql'

    op.drop_table('migration_state')
    op.drop_column('projects', 'shard_key')
    op.drop_column('projects', 'partition_tier')

    if is_pg:
        postgresql.ENUM(name='migrationstatus').drop(bind, checkfirst=True)
        postgresql.ENUM(name='partitiontier').drop(bind, checkfirst=True)
