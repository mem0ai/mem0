"""add sms conversation table for conversation continuity

Revision ID: sms_conversation_manual  
Revises: f1074f6618e2
Create Date: 2025-07-01 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'sms_conversation_manual'
down_revision: Union[str, None] = 'f1074f6618e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create sms_conversations table for SMS conversation continuity."""
    
    # Check if the table already exists
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()
    
    if 'sms_conversations' not in existing_tables:
        # Create SMS role enum if it doesn't exist
        op.execute("CREATE TYPE IF NOT EXISTS smsrole AS ENUM ('USER', 'ASSISTANT')")
        
        # Create the sms_conversations table
        op.create_table('sms_conversations',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=False),
            sa.Column('role', sa.Enum('USER', 'ASSISTANT', name='smsrole'), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes for efficient conversation history retrieval
        op.create_index('idx_sms_conversation_user_created', 'sms_conversations', ['user_id', 'created_at'])
        op.create_index(op.f('ix_sms_conversations_user_id'), 'sms_conversations', ['user_id'])
        op.create_index(op.f('ix_sms_conversations_created_at'), 'sms_conversations', ['created_at'])
        
        # Table created successfully
    else:
        # Table already exists, skipping creation
        pass


def downgrade() -> None:
    """Remove sms_conversations table."""
    
    # Check if the table exists before trying to drop it
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()
    
    if 'sms_conversations' in existing_tables:
        # Drop indexes
        try:
            op.drop_index(op.f('ix_sms_conversations_created_at'), table_name='sms_conversations')
        except:
            pass
        try:
            op.drop_index(op.f('ix_sms_conversations_user_id'), table_name='sms_conversations')
        except:
            pass
        try:
            op.drop_index('idx_sms_conversation_user_created', table_name='sms_conversations')
        except:
            pass
        
        # Drop table
        op.drop_table('sms_conversations')
        
        # Drop enum type
        op.execute("DROP TYPE IF EXISTS smsrole")
        
        # Table removed successfully
    else:
        # Table doesn't exist, skipping removal
        pass 