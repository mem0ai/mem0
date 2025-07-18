"""add project and org columns

Revision ID: 770db1036d83
Revises: afd00efbd06b
Create Date: 2025-07-17 22:53:41.863468

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '770db1036d83'
down_revision: Union[str, None] = 'afd00efbd06b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('memories', sa.Column('metadata', postgresql.JSONB, nullable=True, server_default=sa.text("'{}'::JSONB")))
    op.add_column('memories', sa.Column('project_id', sa.Text(), nullable=True))
    op.add_column('memories', sa.Column('org_id', sa.Text(), nullable=True))
    op.create_index('idx_memories_metadata', 'memories', ['metadata'], postgresql_using='gin')
    op.create_index('idx_memories_project_id', 'memories', ['project_id'])
    op.create_index('idx_memories_org_id', 'memories', ['org_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_memories_org_id', table_name='memories')
    op.drop_index('idx_memories_project_id', table_name='memories')
    op.drop_index('idx_memories_metadata', table_name='memories')
    op.drop_column('memories', 'org_id')
    op.drop_column('memories', 'project_id')
    op.drop_column('memories', 'metadata')
