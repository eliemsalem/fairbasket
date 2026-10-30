"""sante des articles scannes : Nutri-Score, NOVA, additifs, labels, mieux note

Revision ID: e2b8c4d6a9f3
Revises: d7e3a9c5f1b2
Create Date: 2026-10-30 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b8c4d6a9f3'
down_revision: Union[str, None] = 'd7e3a9c5f1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_aliases', sa.Column('sante', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('product_aliases', 'sante')
