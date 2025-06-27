"""add_user_narratives_table

Revision ID: 0d81e543af1a
Revises: 3d72586d0607
Create Date: 2025-06-27 14:04:34.293827

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d81e543af1a'
down_revision: Union[str, None] = '3d72586d0607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create user_narratives table
    op.create_table('user_narratives',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('narrative_content', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create indexes
    op.create_index('ix_user_narratives_user_id', 'user_narratives', ['user_id'], unique=False)
    op.create_index('ix_user_narratives_generated_at', 'user_narratives', ['generated_at'], unique=False)
    op.create_index('idx_narrative_user_generated', 'user_narratives', ['user_id', 'generated_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_narrative_user_generated', table_name='user_narratives')
    op.drop_index('ix_user_narratives_generated_at', table_name='user_narratives')
    op.drop_index('ix_user_narratives_user_id', table_name='user_narratives')
    
    # Drop table
    op.drop_table('user_narratives')
