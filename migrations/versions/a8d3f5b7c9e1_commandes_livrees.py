"""commandes livrees : canal (magasin, livraison, drive), plateforme, frais ; les tickets Uber Eats deja lus

Revision ID: a8d3f5b7c9e1
Revises: f4c1a8e6b2d7
Create Date: 2026-10-31 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d3f5b7c9e1'
down_revision: Union[str, None] = 'f4c1a8e6b2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLATEFORMES = {"uber eats": "Uber Eats", "deliveroo": "Deliveroo", "getir": "Getir", "flink": "Flink"}


def upgrade() -> None:
    op.add_column('receipts', sa.Column('frais', sa.Numeric(10, 2), server_default='0', nullable=False))
    op.add_column('receipts', sa.Column('canal', sa.String(length=10), server_default='magasin', nullable=False))
    op.add_column('receipts', sa.Column('plateforme', sa.String(length=40), nullable=True))

    # commandes livrees deja lues : la note de lecture le disait ; l'ecart restant, ce sont les frais
    for motif, nom in PLATEFORMES.items():
        op.execute(sa.text("UPDATE receipts SET canal = 'livraison', plateforme = :nom "
                           "WHERE lower(remarques) LIKE :motif").bindparams(nom=nom, motif=f"%{motif}%"))
    op.execute("UPDATE receipts SET canal = 'livraison' WHERE lower(remarques) LIKE '%livraison à domicile%'")
    op.execute("UPDATE receipts SET frais = total - (somme_articles - remises_globales), statut = 'ok' "
               "WHERE canal = 'livraison' AND statut = 'ecart' AND total IS NOT NULL AND somme_articles IS NOT NULL "
               "AND total - (somme_articles - remises_globales) > 0 "
               "AND total - (somme_articles - remises_globales) <= 30")
    # leurs prix ne sont pas ceux du magasin : retires des prix partages
    jour = "date(r.achete_le)" if op.get_bind().dialect.name == "sqlite" else "CAST(r.achete_le AS DATE)"
    op.execute("DELETE FROM shared_prices WHERE EXISTS (SELECT 1 FROM receipts r JOIN receipt_items i "
               "ON i.receipt_id = r.id WHERE r.canal = 'livraison' AND r.store_id = shared_prices.store_id "
               f"AND i.libelle = shared_prices.libelle AND shared_prices.jour = {jour})")


def downgrade() -> None:
    op.drop_column('receipts', 'plateforme')
    op.drop_column('receipts', 'canal')
    op.drop_column('receipts', 'frais')
