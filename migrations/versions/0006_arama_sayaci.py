"""gunluk kullanim: mekan arama sayaci

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-17 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('daily_usage', sa.Column('searches', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('daily_usage', 'searches')
