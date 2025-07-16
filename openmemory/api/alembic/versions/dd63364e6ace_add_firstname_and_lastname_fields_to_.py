"""add firstname and lastname fields to users table

Revision ID: dd63364e6ace
Revises: 4970823f31ba
Create Date: 2025-07-15 19:29:59.002388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd63364e6ace'
down_revision: Union[str, None] = '4970823f31ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add firstname and lastname fields to users table."""
    # Check if the columns already exist (in case they were partially added)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('users')]
    
    # Add firstname field
    if 'firstname' not in existing_columns:
        op.add_column('users', sa.Column('firstname', sa.String(100), nullable=True))
    
    # Add lastname field
    if 'lastname' not in existing_columns:
        op.add_column('users', sa.Column('lastname', sa.String(100), nullable=True))
    
    # Create indexes for better query performance
    try:
        op.create_index('ix_users_firstname', 'users', ['firstname'], unique=False)
    except:
        pass  # Index might already exist
    
    try:
        op.create_index('ix_users_lastname', 'users', ['lastname'], unique=False)
    except:
        pass  # Index might already exist


def downgrade() -> None:
    """Remove firstname and lastname fields from users table."""
    # Remove indexes
    try:
        op.drop_index('ix_users_firstname', table_name='users')
    except:
        pass
    
    try:
        op.drop_index('ix_users_lastname', table_name='users')
    except:
        pass
    
    # Remove columns
    op.drop_column('users', 'lastname')
    op.drop_column('users', 'firstname')
