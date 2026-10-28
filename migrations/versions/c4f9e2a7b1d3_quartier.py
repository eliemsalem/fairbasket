"""quartier de la personne (ou elle fait ses courses), arrondi a ~1 km

Revision ID: c4f9e2a7b1d3
Revises: b3e8d1f4a6c2
Create Date: 2026-10-28 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f9e2a7b1d3'
down_revision: Union[str, None] = 'b3e8d1f4a6c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('quartier', sa.String(120), nullable=True))
    op.add_column('users', sa.Column('quartier_lat', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('quartier_lon', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'quartier_lon')
    op.drop_column('users', 'quartier_lat')
    op.drop_column('users', 'quartier')
