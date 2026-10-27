"""noms de produits corriges : pave de saumon bio (Carrefour, Monoprix) et barquette Filiere Qualite

Deux produits differents de Carrefour etaient ranges sous « Pavé de saumon » (signale par l'utilisateur).
Sans effet sur une base qui n'a pas ces libelles.

Revision ID: a1f7c3d9e2b4
Revises: 9d4b2c6e8f10
Create Date: 2026-10-27 20:00:00

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import select
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision: str = 'a1f7c3d9e2b4'
down_revision: Union[str, None] = '9d4b2c6e8f10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CORRECTIONS = [("Carrefour", "PAVE SAUMON", "Pavé de saumon bio"),
               ("Monoprix", "PAVE SAUM MONOPRIX", "Pavé de saumon bio"),
               ("Monoprix", "2X PAVE SAUM MONOPRIX", "Pavé de saumon bio"),
               ("Carrefour", "BQ P SAUM AP FQC", "Pavé de saumon Filière Qualité Carrefour")]


def upgrade() -> None:
    from app.models import Receipt, ReceiptItem, Store
    from app.tickets import renommer_produit

    db = Session(bind=op.get_bind())
    for enseigne, libelle, nom in CORRECTIONS:
        item = db.scalar(select(ReceiptItem).join(Receipt).join(Store)
                         .where(Store.enseigne == enseigne, ReceiptItem.libelle == libelle).limit(1))
        if item is not None:
            renommer_produit(db, item, nom)
    db.flush()


def downgrade() -> None:
    pass
