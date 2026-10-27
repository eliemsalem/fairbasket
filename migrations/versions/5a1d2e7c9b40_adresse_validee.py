"""adresse du magasin validee

Revision ID: 5a1d2e7c9b40
Revises: 2ce2591495bc
Create Date: 2026-10-27 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a1d2e7c9b40'
down_revision: Union[str, None] = '2ce2591495bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('receipts', sa.Column('adresse_ok', sa.Boolean(), server_default=sa.false(), nullable=False))
    # tickets deja enregistres : valides si l'adresse du magasin est connue
    op.execute("UPDATE receipts SET adresse_ok = TRUE WHERE store_id IN "
               "(SELECT id FROM stores WHERE adresse IS NOT NULL OR code_postal IS NOT NULL)")


def downgrade() -> None:
    op.drop_column('receipts', 'adresse_ok')
