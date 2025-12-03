"""add_is_superuser_to_users

Revision ID: 8e4db04e7709
Revises: add_prompts_table
Create Date: 2025-12-02 20:54:48.513437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e4db04e7709'
down_revision: Union[str, None] = 'add_prompts_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    import os
    from app.config import USER_ID

    # Add is_superuser column to users table
    op.add_column('users', sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='0'))

    # Set default user as superuser
    op.execute(f"UPDATE users SET is_superuser = 1 WHERE user_id = '{USER_ID}'")


def downgrade() -> None:
    """Downgrade schema."""
    # Remove is_superuser column from users table
    op.drop_column('users', 'is_superuser')
