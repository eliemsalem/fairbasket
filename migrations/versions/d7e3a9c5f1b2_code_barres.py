"""code-barres scanne pour un libelle d'enseigne : l'article exact

Revision ID: d7e3a9c5f1b2
Revises: c4f9e2a7b1d3
Create Date: 2026-10-30 09:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e3a9c5f1b2'
down_revision: Union[str, None] = 'c4f9e2a7b1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_aliases', sa.Column('code_barres', sa.String(32), nullable=True))
    op.add_column('product_aliases', sa.Column('nom_exact', sa.String(200), nullable=True))
    op.add_column('product_aliases', sa.Column('marque', sa.String(120), nullable=True))
    op.add_column('product_aliases', sa.Column('format', sa.String(40), nullable=True))
    op.add_column('product_aliases', sa.Column('image', sa.String(300), nullable=True))
    op.create_index('ix_product_aliases_code_barres', 'product_aliases', ['code_barres'])


def downgrade() -> None:
    op.drop_index('ix_product_aliases_code_barres', 'product_aliases')
    for c in ('image', 'format', 'marque', 'nom_exact', 'code_barres'):
        op.drop_column('product_aliases', c)
