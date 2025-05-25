"""Add Document table for storing full content

Revision ID: f8c6e2d514fc
Revises: 143338ceedf6
Create Date: 2025-05-24 22:55:36.838887

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8c6e2d514fc'
down_revision: Union[str, None] = '143338ceedf6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create documents table
    op.create_table('documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('app_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('source_url', sa.String(), nullable=True),
    sa.Column('document_type', sa.String(), nullable=False),
    sa.Column('content', sa.String(), nullable=False),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['app_id'], ['apps.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_documents_created', 'documents', ['created_at'], unique=False)
    op.create_index('idx_documents_type', 'documents', ['document_type'], unique=False)
    op.create_index('idx_documents_user_app', 'documents', ['user_id', 'app_id'], unique=False)
    op.create_index(op.f('ix_documents_app_id'), 'documents', ['app_id'], unique=False)
    op.create_index(op.f('ix_documents_created_at'), 'documents', ['created_at'], unique=False)
    op.create_index(op.f('ix_documents_user_id'), 'documents', ['user_id'], unique=False)
    
    # Create document_memories association table
    op.create_table('document_memories',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('memory_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['memory_id'], ['memories.id'], ),
    sa.PrimaryKeyConstraint('document_id', 'memory_id')
    )
    op.create_index('idx_document_memory', 'document_memories', ['document_id', 'memory_id'], unique=False)
    op.create_index(op.f('ix_document_memories_document_id'), 'document_memories', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_memories_memory_id'), 'document_memories', ['memory_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop document_memories table
    op.drop_index(op.f('ix_document_memories_memory_id'), table_name='document_memories')
    op.drop_index(op.f('ix_document_memories_document_id'), table_name='document_memories')
    op.drop_index('idx_document_memory', table_name='document_memories')
    op.drop_table('document_memories')
    
    # Drop documents table
    op.drop_index(op.f('ix_documents_user_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_created_at'), table_name='documents')
    op.drop_index(op.f('ix_documents_app_id'), table_name='documents')
    op.drop_index('idx_documents_user_app', table_name='documents')
    op.drop_index('idx_documents_type', table_name='documents')
    op.drop_index('idx_documents_created', table_name='documents')
    op.drop_table('documents')
