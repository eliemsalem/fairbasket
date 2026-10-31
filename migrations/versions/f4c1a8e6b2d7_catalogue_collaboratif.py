"""catalogue collaboratif : avis de chacun sur les libelles, etat de confiance des correspondances, produit type

Revision ID: f4c1a8e6b2d7
Revises: e2b8c4d6a9f3
Create Date: 2026-10-31 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4c1a8e6b2d7'
down_revision: Union[str, None] = 'e2b8c4d6a9f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('type_off', sa.String(length=80), nullable=True))
    op.add_column('products', sa.Column('type_nom', sa.String(length=120), nullable=True))
    op.create_index('ix_products_type_off', 'products', ['type_off'])
    op.add_column('product_aliases', sa.Column('etat', sa.String(length=10), server_default='probable',
                                               nullable=False))
    op.create_table(
        'contributions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('enseigne', sa.String(length=60), nullable=False),
        sa.Column('libelle', sa.String(length=120), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('code_barres', sa.String(length=32), nullable=True),
        sa.Column('quand', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'enseigne', 'libelle'),
    )
    op.create_index('ix_contributions_user_id', 'contributions', ['user_id'])
    op.create_index('ix_contributions_enseigne', 'contributions', ['enseigne'])


def downgrade() -> None:
    op.drop_index('ix_contributions_enseigne', table_name='contributions')
    op.drop_index('ix_contributions_user_id', table_name='contributions')
    op.drop_table('contributions')
    op.drop_column('product_aliases', 'etat')
    op.drop_index('ix_products_type_off', table_name='products')
    op.drop_column('products', 'type_nom')
    op.drop_column('products', 'type_off')
