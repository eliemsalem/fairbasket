"""Liste de courses : prix estime d'apres les achats passes, et ou acheter chaque article le moins cher."""

from collections import defaultdict
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import Product, Receipt, ReceiptItem, ShoppingItem, User
from .stats import _derniers_prix
from .tickets import cle_produit


def _tickets(db: Session, user: User):
    return db.scalars(
        select(Receipt).where(Receipt.user_id == user.id, Receipt.achete_le.is_not(None))
        .options(selectinload(Receipt.items).selectinload(ReceiptItem.product), selectinload(Receipt.store))
    ).all()


def trouver_produit(db: Session, user: User, nom: str) -> Optional[Product]:
    """Le produit deja achete qui correspond le mieux a ce que la personne a tape (« oeufs » -> « Œufs bio ×6 »)."""
    cle = cle_produit(nom)
    if not cle:
        return None
    achats = db.execute(
        select(Product, func.count(ReceiptItem.id)).join(ReceiptItem, ReceiptItem.product_id == Product.id)
        .join(Receipt).where(Receipt.user_id == user.id).group_by(Product.id)
    ).all()
    exact = [p for p, _ in achats if p.cle == cle]
    if exact:
        return exact[0]
    proches = sorted(((n, p) for p, n in achats if cle in p.cle), key=lambda x: -x[0])
    return proches[0][1] if proches else None


def ajouter(db: Session, user: User, nom: str, product: Optional[Product] = None) -> None:
    nom = " ".join((nom or "").split())[:120]
    if not nom:
        return
    product = product or trouver_produit(db, user, nom)
    db.add(ShoppingItem(user_id=user.id, nom=product.nom if product else nom[0].upper() + nom[1:], product=product))
    db.commit()


def vue(db: Session, user: User) -> dict:
    derniers, noms, achats = _derniers_prix(_tickets(db, user))
    lignes, par_magasin, total = [], defaultdict(int), Decimal("0")
    for item in user.liste:
        prix = derniers.get(item.product_id, {})
        meilleur = min(prix.items(), key=lambda kv: kv[1][1]) if prix else None
        ligne = {"item": item, "enseigne": meilleur[0] if meilleur else None,
                 "prix": meilleur[1][1] if meilleur else None}
        lignes.append(ligne)
        if not item.coche and meilleur:
            total += meilleur[1][1]
            par_magasin[meilleur[0]] += 1
    dans_liste = {i.product_id for i in user.liste if i.product_id}
    # suggestions : ce que la personne achete le plus souvent et qui n'est pas deja dans la liste
    suggestions = [{"id": pid, "nom": noms[pid]} for pid, n in sorted(achats.items(), key=lambda kv: -kv[1])
                   if n >= 2 and pid not in dans_liste][:6]
    return {"lignes": lignes, "total": total, "suggestions": suggestions,
            "magasins": sorted(par_magasin.items(), key=lambda kv: -kv[1]),
            "restants": sum(not i.coche for i in user.liste)}
