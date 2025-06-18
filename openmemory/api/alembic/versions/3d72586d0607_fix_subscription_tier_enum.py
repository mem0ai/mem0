"""fix subscription tier enum and add fields

Revision ID: 3d72586d0607
Revises: 2834f44d4d7d
Create Date: 2025-01-17 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3d72586d0607'
down_revision = '2834f44d4d7d'
branch_labels = None
depends_on = None

def upgrade():
    # First, check if the columns already exist (in case they were partially added)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('users')]
    
    # Create the subscription tier enum type
    subscription_tier_enum = postgresql.ENUM('FREE', 'PRO', 'ENTERPRISE', name='subscriptiontier', create_type=False)
    subscription_tier_enum.create(connection, checkfirst=True)
    
    # Add subscription columns if they don't exist
    if 'subscription_tier' not in existing_columns:
        op.add_column('users', sa.Column('subscription_tier', subscription_tier_enum, nullable=True, server_default='FREE'))
    else:
        # If column exists but has wrong type/values, fix it
        # First, update any lowercase values to uppercase
        op.execute("UPDATE users SET subscription_tier = 'FREE' WHERE subscription_tier = 'free'")
        op.execute("UPDATE users SET subscription_tier = 'PRO' WHERE subscription_tier = 'pro'")  
        op.execute("UPDATE users SET subscription_tier = 'ENTERPRISE' WHERE subscription_tier = 'enterprise'")
        
        # Change column type to enum if it's currently string
        op.alter_column('users', 'subscription_tier',
                       type_=subscription_tier_enum,
                       postgresql_using='subscription_tier::subscriptiontier')
    
    if 'stripe_customer_id' not in existing_columns:
        op.add_column('users', sa.Column('stripe_customer_id', sa.String(), nullable=True))
    
    if 'stripe_subscription_id' not in existing_columns:
        op.add_column('users', sa.Column('stripe_subscription_id', sa.String(), nullable=True))
    
    if 'subscription_status' not in existing_columns:
        op.add_column('users', sa.Column('subscription_status', sa.String(), nullable=True, server_default='active'))
    
    if 'subscription_current_period_end' not in existing_columns:
        op.add_column('users', sa.Column('subscription_current_period_end', sa.DateTime(), nullable=True))
    
    # Create indexes if they don't exist
    try:
        op.create_index('ix_users_subscription_tier', 'users', ['subscription_tier'], unique=False)
    except:
        pass  # Index might already exist
    
    try:
        op.create_index('ix_users_stripe_customer_id', 'users', ['stripe_customer_id'], unique=False)
    except:
        pass
    
    try:
        op.create_index('ix_users_stripe_subscription_id', 'users', ['stripe_subscription_id'], unique=False)
    except:
        pass

def downgrade():
    # Remove indexes
    try:
        op.drop_index('ix_users_stripe_subscription_id', table_name='users')
    except:
        pass
    
    try:
        op.drop_index('ix_users_stripe_customer_id', table_name='users')
    except:
        pass
    
    try:
        op.drop_index('ix_users_subscription_tier', table_name='users')
    except:
        pass
    
    # Remove columns
    op.drop_column('users', 'subscription_current_period_end')
    op.drop_column('users', 'subscription_status')
    op.drop_column('users', 'stripe_subscription_id')
    op.drop_column('users', 'stripe_customer_id')
    op.drop_column('users', 'subscription_tier')
    
    # Drop the enum type
    subscription_tier_enum = postgresql.ENUM('FREE', 'PRO', 'ENTERPRISE', name='subscriptiontier')
    subscription_tier_enum.drop(op.get_bind()) 