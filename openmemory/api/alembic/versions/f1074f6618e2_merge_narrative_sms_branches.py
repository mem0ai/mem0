"""merge migrations - resolve narrative and sms branches

Revision ID: f1074f6618e2
Revises: 0d81e543af1a, 6a4b2e8f5c91
Create Date: 2025-06-27 17:46:59.995313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1074f6618e2'
down_revision: Union[str, None] = ('0d81e543af1a', '6a4b2e8f5c91')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
