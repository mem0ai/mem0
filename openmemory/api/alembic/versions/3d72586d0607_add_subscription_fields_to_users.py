"""add_subscription_fields_to_users

Revision ID: 3d72586d0607
Revises: 2834f44d4d7d
Create Date: 2025-01-17 20:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3d72586d0607'
down_revision = '2834f44d4d7d'
branch_labels = None
depends_on = None

def upgrade():
    # Add subscription fields to users table
    op.add_column('users', sa.Column('subscription_tier', sa.String(), nullable=True, server_default='free'))
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(), nullable=True))
    op.add_column('users', sa.Column('stripe_subscription_id', sa.String(), nullable=True))
    op.add_column('users', sa.Column('subscription_status', sa.String(), nullable=True, server_default='active'))
    op.add_column('users', sa.Column('subscription_current_period_end', sa.DateTime(), nullable=True))
    
    # Add indexes
    op.create_index('ix_users_subscription_tier', 'users', ['subscription_tier'], unique=False)
    op.create_index('ix_users_stripe_customer_id', 'users', ['stripe_customer_id'], unique=False)
    op.create_index('ix_users_stripe_subscription_id', 'users', ['stripe_subscription_id'], unique=False)

def downgrade():
    # Remove indexes
    op.drop_index('ix_users_stripe_subscription_id', table_name='users')
    op.drop_index('ix_users_stripe_customer_id', table_name='users')
    op.drop_index('ix_users_subscription_tier', table_name='users')
    
    # Remove columns
    op.drop_column('users', 'subscription_current_period_end')
    op.drop_column('users', 'subscription_status')
    op.drop_column('users', 'stripe_subscription_id')
    op.drop_column('users', 'stripe_customer_id')
    op.drop_column('users', 'subscription_tier') 