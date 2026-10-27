"""prix du quartier propres a chaque utilisateur

Revision ID: 7c3e9a1f2b55
Revises: 5a1d2e7c9b40
Create Date: 2026-10-27 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c3e9a1f2b55'
down_revision: Union[str, None] = '5a1d2e7c9b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('stores', sa.Column('lon', sa.Float(), nullable=True))
    op.add_column('open_prices', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('open_prices', sa.Column('lon', sa.Float(), nullable=True))
    op.create_table('zones_prix',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('lat', sa.Float(), nullable=False),
                    sa.Column('lon', sa.Float(), nullable=False),
                    sa.Column('copie_le', sa.DateTime(timezone=True), nullable=True),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('lat', 'lon'))
    # copie sans position : recopiee au demarrage, avec la position de chaque magasin
    op.execute("DELETE FROM open_prices")


def downgrade() -> None:
    op.drop_table('zones_prix')
    op.drop_column('open_prices', 'lon')
    op.drop_column('open_prices', 'lat')
    op.drop_column('stores', 'lon')
    op.drop_column('stores', 'lat')
