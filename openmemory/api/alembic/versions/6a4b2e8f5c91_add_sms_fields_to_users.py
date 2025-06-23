"""add sms fields to users table

Revision ID: 6a4b2e8f5c91
Revises: 3d72586d0607
Create Date: 2025-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6a4b2e8f5c91'
down_revision = '3d72586d0607'
branch_labels = None
depends_on = None

def upgrade():
    # First, check if the columns already exist (in case they were partially added)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('users')]
    
    # Add SMS fields to users table
    if 'phone_number' not in existing_columns:
        op.add_column('users', sa.Column('phone_number', sa.String(20), nullable=True, unique=True))
    
    if 'phone_verified' not in existing_columns:
        op.add_column('users', sa.Column('phone_verified', sa.Boolean(), nullable=True, server_default='false'))
    
    if 'phone_verification_attempts' not in existing_columns:
        op.add_column('users', sa.Column('phone_verification_attempts', sa.Integer(), nullable=True, server_default='0'))
    
    if 'phone_verified_at' not in existing_columns:
        op.add_column('users', sa.Column('phone_verified_at', sa.DateTime(), nullable=True))
    
    if 'sms_enabled' not in existing_columns:
        op.add_column('users', sa.Column('sms_enabled', sa.Boolean(), nullable=True, server_default='true'))
    
    # Create indexes if they don't exist
    try:
        op.create_index('ix_users_phone_number', 'users', ['phone_number'], unique=True)
    except:
        pass  # Index might already exist
    
    try:
        op.create_index('ix_users_phone_verified', 'users', ['phone_verified'], unique=False)
    except:
        pass

def downgrade():
    # Remove indexes
    try:
        op.drop_index('ix_users_phone_verified', table_name='users')
    except:
        pass
    
    try:
        op.drop_index('ix_users_phone_number', table_name='users')
    except:
        pass
    
    # Remove columns
    op.drop_column('users', 'sms_enabled')
    op.drop_column('users', 'phone_verified_at')
    op.drop_column('users', 'phone_verification_attempts')
    op.drop_column('users', 'phone_verified')
    op.drop_column('users', 'phone_number') 