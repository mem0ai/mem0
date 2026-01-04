"""Change app name uniqueness from global to per-user

This migration:
1. Drops the global unique constraint on apps.name
2. Adds a composite unique index on (owner_id, name)

This allows different users to have apps with the same name,
while preventing duplicate app names for the same user.

Revision ID: change_app_name_per_user
Revises: 8e4db04e7709
Create Date: 2025-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'change_app_name_per_user'
down_revision: Union[str, None] = '8e4db04e7709'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection to check what indexes exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Get existing indexes on apps table
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('apps')}
    existing_constraints = {c['name'] for c in inspector.get_unique_constraints('apps')}

    # Drop the global unique constraint on name if it exists
    # SQLite doesn't support dropping constraints directly, so we check first
    if conn.dialect.name == 'sqlite':
        # For SQLite, we need to recreate the table without the unique constraint
        # But first check if our new index already exists
        if 'idx_app_owner_name' not in existing_indexes:
            # Create a new table with the correct schema
            op.execute('''
                CREATE TABLE apps_new (
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    owner_id VARCHAR(36) NOT NULL REFERENCES users(id),
                    name VARCHAR NOT NULL,
                    description VARCHAR,
                    metadata JSON DEFAULT '{}',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            ''')

            # Copy data
            op.execute('''
                INSERT INTO apps_new (id, owner_id, name, description, metadata, is_active, created_at, updated_at)
                SELECT id, owner_id, name, description, metadata, is_active, created_at, updated_at
                FROM apps
            ''')

            # Drop old table and rename new
            op.execute('DROP TABLE apps')
            op.execute('ALTER TABLE apps_new RENAME TO apps')

            # Create indexes
            op.create_index('ix_apps_owner_id', 'apps', ['owner_id'])
            op.create_index('ix_apps_name', 'apps', ['name'])
            op.create_index('ix_apps_is_active', 'apps', ['is_active'])
            op.create_index('ix_apps_created_at', 'apps', ['created_at'])
            op.create_index('idx_app_owner_name', 'apps', ['owner_id', 'name'], unique=True)
    else:
        # For PostgreSQL/MySQL
        # Drop unique constraint on name if it exists
        if 'apps_name_key' in existing_constraints:
            op.drop_constraint('apps_name_key', 'apps', type_='unique')

        # Create composite unique index if it doesn't exist
        if 'idx_app_owner_name' not in existing_indexes:
            op.create_index('idx_app_owner_name', 'apps', ['owner_id', 'name'], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('apps')}

    # Drop the composite unique index if it exists
    if 'idx_app_owner_name' in existing_indexes:
        op.drop_index('idx_app_owner_name', table_name='apps')

    # Re-add global unique constraint on name
    if conn.dialect.name != 'sqlite':
        op.create_unique_constraint('apps_name_key', 'apps', ['name'])
