"""add document chunks table for efficient retrieval

Revision ID: 2834f44d4d7d
Revises: f8c6e2d514fc
Create Date: 2025-05-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2834f44d4d7d'
down_revision = 'f8c6e2d514fc'
branch_labels = None
depends_on = None
disable_ddl_transaction = True


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')
    # Create document_chunks table
    op.create_table('document_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient retrieval
    op.create_index('idx_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('idx_document_chunks_chunk_index', 'document_chunks', ['chunk_index'])


def downgrade() -> None:
    op.drop_index('idx_document_chunks_chunk_index', table_name='document_chunks')
    op.drop_index('idx_document_chunks_document_id', table_name='document_chunks')
    op.drop_table('document_chunks')
    op.execute('DROP EXTENSION IF EXISTS pgcrypto;')
