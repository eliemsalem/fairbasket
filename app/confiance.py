"""Catalogue collaboratif : la correspondance « libelle d'une enseigne -> produit » est commune a tous.

« 250G BEUR 1/2-SEL » chez Carrefour est le meme article pour tout le monde : une personne qui le corrige, le
confirme ou le scanne aide toutes les autres. Mais une erreur (ou une mauvaise blague) ne doit pas tout fausser.
Alors chacun donne un avis :
- ses propres tickets suivent son avis tout de suite ;
- la correspondance commune suit l'avis le mieux soutenu : la lecture de Claude compte 1, chaque personne 2,
  chaque scan 5, l'administrateur 10, et la correspondance en place garde 1 de plus a egalite. Une personne
  seule ne defait donc pas ce que d'autres ont confirme ;
- celle qui contredit souvent les autres compte moitie moins.
Une correspondance est « confirmee » quand une personne est d'accord, « sure » a partir de deux.
"""

from collections import Counter
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from . import auth
from .models import Contribution, Product, ProductAlias, Receipt, ReceiptItem, SharedPrice, Store, User, now

POIDS_LECTURE = 1  # en place : devinee a la lecture, ou deja retenue
POIDS_AVIS = 2
POIDS_SCAN = 5
POIDS_ADMIN = 10
SUR = 2  # personnes differentes d'accord


def _magasins(enseigne: str):
    return select(Store.id).where(Store.enseigne == enseigne)


def fiabilite(db: Session, user_id: int) -> float:
    """1, ou 0,5 pour qui contredit souvent la correspondance retenue la ou d'autres ont aussi donne leur avis."""
    d_accord = contre = 0
    for c, alias in db.execute(select(Contribution, ProductAlias).join(ProductAlias, (
            ProductAlias.enseigne == Contribution.enseigne) & (ProductAlias.libelle == Contribution.libelle))
            .where(Contribution.user_id == user_id, Contribution.product_id.is_not(None))):
        autres = db.scalar(select(func.count()).select_from(Contribution).where(
            Contribution.enseigne == c.enseigne, Contribution.libelle == c.libelle, Contribution.user_id != user_id,
            Contribution.product_id.is_not(None)))
        if autres:
            if c.product_id == alias.product_id:
                d_accord += 1
            else:
                contre += 1
    return 0.5 if contre >= 3 and contre > d_accord else 1.0


def _poids(db: Session, user_id: int, base: int, cache: dict) -> float:
    if user_id not in cache:
        u = db.get(User, user_id)
        cache[user_id] = POIDS_ADMIN if auth.is_admin(u) else fiabilite(db, user_id)
    return cache[user_id] if cache[user_id] == POIDS_ADMIN else base * cache[user_id]


def recalculer(db: Session, enseigne: str, libelle: str) -> Optional[ProductAlias]:
    """Retient pour tous le produit et le code-barres les mieux soutenus ; les tickets des personnes qui n'ont pas
    donne d'avis (et les prix partages) suivent."""
    alias = db.scalar(select(ProductAlias).where(ProductAlias.enseigne == enseigne, ProductAlias.libelle == libelle))
    avis = db.scalars(select(Contribution).where(Contribution.enseigne == enseigne,
                                                 Contribution.libelle == libelle)).all()
    cache: dict = {}
    produits, codes = Counter(), Counter()
    if alias is not None:
        produits[alias.product_id] += POIDS_LECTURE
        if alias.code_barres:
            codes[alias.code_barres] += POIDS_LECTURE
    for c in avis:
        if c.product_id:
            produits[c.product_id] += _poids(db, c.user_id, POIDS_AVIS, cache)
        if c.code_barres:
            codes[c.code_barres] += _poids(db, c.user_id, POIDS_SCAN, cache)
    if not produits:
        return alias
    actuel = alias.product_id if alias else None
    gagnant = max(produits, key=lambda p: (produits[p], p == actuel))
    if alias is None:
        alias = ProductAlias(enseigne=enseigne, libelle=libelle, product_id=gagnant)
        db.add(alias)
    if gagnant != actuel:
        alias.product_id = gagnant
        a_leur_avis = select(Contribution.user_id).where(Contribution.enseigne == enseigne,
                                                         Contribution.libelle == libelle,
                                                         Contribution.product_id.is_not(None))
        db.execute(update(ReceiptItem).where(ReceiptItem.libelle == libelle, ReceiptItem.receipt_id.in_(
            select(Receipt.id).where(Receipt.store_id.in_(_magasins(enseigne)), Receipt.user_id.not_in(a_leur_avis))))
            .values(product_id=gagnant))
        db.execute(update(SharedPrice).where(SharedPrice.libelle == libelle,
                                             SharedPrice.store_id.in_(_magasins(enseigne))).values(product_id=gagnant))
    if codes:
        code = max(codes, key=lambda k: (codes[k], k == alias.code_barres))
        if code != alias.code_barres:
            alias.code_barres = code
            alias.nom_exact = alias.marque = alias.format = alias.image = alias.sante = None  # fiche a reprendre
    d_accord = {c.user_id for c in avis if c.product_id == gagnant}
    admin = any(cache.get(u) == POIDS_ADMIN for u in d_accord)
    alias.etat = "sur" if admin or len(d_accord) >= SUR else "confirme" if d_accord else "probable"
    db.flush()
    return alias


def donner_avis(db: Session, user: User, item: ReceiptItem, produit: Optional[Product] = None,
                code: Optional[str] = None) -> Optional[ProductAlias]:
    """L'avis d'une personne sur une ligne de ses tickets : ses lignes semblables le suivent tout de suite, puis
    la correspondance commune est recalculee."""
    if item.receipt.store is None:
        return None
    enseigne, libelle = item.receipt.store.enseigne, item.libelle
    c = db.scalar(select(Contribution).where(Contribution.user_id == user.id, Contribution.enseigne == enseigne,
                                             Contribution.libelle == libelle))
    if c is None:
        c = Contribution(user_id=user.id, enseigne=enseigne, libelle=libelle)
        db.add(c)
    if produit is not None:
        c.product_id = produit.id
        db.execute(update(ReceiptItem).where(ReceiptItem.libelle == libelle, ReceiptItem.receipt_id.in_(
            select(Receipt.id).where(Receipt.user_id == user.id, Receipt.store_id.in_(_magasins(enseigne)))))
            .values(product_id=produit.id))
    if code:
        c.code_barres = code
    c.quand = now()
    db.flush()
    return recalculer(db, enseigne, libelle)


def produit_de(db: Session, user_id: int, enseigne: str, libelle: str) -> Optional[Product]:
    """Le produit choisi par la personne elle-meme pour ce libelle, si elle a donne son avis."""
    return db.scalar(select(Product).join(Contribution, Contribution.product_id == Product.id).where(
        Contribution.user_id == user_id, Contribution.enseigne == enseigne, Contribution.libelle == libelle))


def a_confirmer(db: Session, user: User, receipt: Receipt) -> Optional[ReceiptItem]:
    """Au plus une question par ticket : la ligne la plus chere dont le nom n'a ete que devine, sans avis de la
    personne."""
    if receipt.store is None or receipt.store.enseigne == "Inconnue":
        return None
    enseigne = receipt.store.enseigne
    devines = set(db.scalars(select(ProductAlias.libelle).where(
        ProductAlias.enseigne == enseigne, ProductAlias.etat == "probable",
        ProductAlias.libelle.in_([it.libelle for it in receipt.items]))))
    deja = set(db.scalars(select(Contribution.libelle).where(Contribution.user_id == user.id,
                                                              Contribution.enseigne == enseigne)))
    lignes = [it for it in receipt.items if it.product_id and it.libelle in devines and it.libelle not in deja]
    return max(lignes, key=lambda it: it.montant, default=None)


def aides(db: Session, user: User) -> dict:
    """Combien d'articles la personne a corriges ou confirmes, et a combien d'autres personnes ils ont servi."""
    avis = db.scalar(select(func.count()).select_from(Contribution).where(Contribution.user_id == user.id)) or 0
    if not avis:
        return {"avis": 0, "personnes": 0}
    personnes = db.scalar(
        select(func.count(func.distinct(Receipt.user_id))).select_from(ReceiptItem)
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id).join(Store, Receipt.store_id == Store.id)
        .join(Contribution, (Contribution.enseigne == Store.enseigne) & (Contribution.libelle == ReceiptItem.libelle))
        .join(ProductAlias, (ProductAlias.enseigne == Store.enseigne) & (ProductAlias.libelle == ReceiptItem.libelle))
        .where(Contribution.user_id == user.id, Receipt.user_id != user.id,
               ((Contribution.product_id.is_not(None)) & (Contribution.product_id == ProductAlias.product_id))
               | ((Contribution.code_barres.is_not(None)) & (Contribution.code_barres == ProductAlias.code_barres))))
    return {"avis": avis, "personnes": personnes or 0}
