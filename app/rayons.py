"""Le produit type d'un article : un rayon d'Open Food Facts (« Beurres demi-sel », « Bananes », « Œufs »).

C'est le dictionnaire commun qui permet de comparer d'une enseigne a l'autre : « 250G BEUR 1/2-SEL » chez
Carrefour et « Monoprix Beurre demi-sel 250g » sont tous deux des « Beurres demi-sel ». La liste vient de la
taxonomie d'Open Food Facts (licence ODbL) avec ses synonymes francais, limitee aux rayons qui ont des produits
vendus en France (scripts/rayons.py la refabrique). Rien n'est envoye nulle part : tout est dans le fichier.
"""

import json
import logging
import re
import threading
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

log = logging.getLogger("fairbasket.rayons")
FICHIER = Path(__file__).resolve().parent / "data" / "rayons_fr.json"
VIDES = {"de", "du", "des", "la", "le", "les", "à", "a", "au", "aux", "et", "en", "d", "l", "x", "avec", "pour", "sur",
         "un", "une", "pièce", "pièces", "pce"}


def mots(texte: str) -> list:
    """Les mots qui comptent, au singulier : « Œufs bio ×6 » -> ["oeuf", "bio"]. Les accents restent (pâte ≠ pâté)."""
    texte = (texte or "").lower().replace("œ", "oe").replace("½", " demi ").replace("1/2", " demi ")
    sortie = []
    for m in re.findall(r"[a-zà-ÿ]+", texte):
        if m in VIDES:
            continue
        sortie.append(m[:-1] if len(m) > 3 and m[-1] in "sx" and not m.endswith("ss") else m)
    return sortie


@lru_cache(maxsize=1)
def _dictionnaire() -> tuple:
    """(noms ranges par leur premier mot, id -> nom affiche)."""
    rayons = json.loads(FICHIER.read_text(encoding="utf-8"))["rayons"]
    par_premier, affiche = defaultdict(list), {}
    for ident, r in rayons.items():
        affiche[ident] = r["fr"][0][:1].upper() + r["fr"][0][1:]
        for nom in r["fr"]:
            m = tuple(mots(nom))
            if m:
                par_premier[m[0]].append((m, ident, r["n"]))
    return par_premier, affiche


def _dans(petite: tuple, grande: list) -> bool:
    """Les mots du rayon se suivent dans le nom (d'autres peuvent s'intercaler : « lait UHT demi-écrémé »)."""
    suite = iter(grande)
    return all(m in suite for m in petite)


def type_de(nom: str) -> Optional[tuple]:
    """(id, nom) du rayon le plus precis dont le nom se retrouve dans celui du produit. En francais le mot
    principal vient d'abord : « Tofu bio à l'ail » est du tofu, pas de l'ail."""
    m = mots(nom)
    if not m:
        return None
    par_premier, affiche = _dictionnaire()
    bons = [n for premier in set(m) for n in par_premier.get(premier, ()) if _dans(n[0], m)]
    if not bons:
        return None
    meilleur = max(bons, key=lambda n: (len(n[0]) + (1.5 if n[0][0] == m[0] else 0), n[0] == tuple(m), n[2]))
    return meilleur[1], affiche[meilleur[1]]


def type_des_categories(categories: list) -> Optional[tuple]:
    """Le rayon exact d'un article scanne (ses categories Open Food Facts), le plus precis connu."""
    _, affiche = _dictionnaire()
    for c in reversed(categories or []):
        if c in affiche:
            return c, affiche[c]
    return None


def classer(produit) -> bool:
    """Donne son produit type a un produit (vide quand aucun rayon ne correspond, pour ne pas rechercher)."""
    t = type_de(produit.nom)
    produit.type_off, produit.type_nom = (t[0], t[1][:120]) if t else ("", None)
    return t is not None


def completer(db: Session) -> int:
    """Les produits pas encore classes (anciens tickets, ou dictionnaire tout neuf)."""
    from .models import Product

    produits = db.scalars(select(Product).where(Product.type_off.is_(None))).all()
    trouves = sum(classer(p) for p in produits)
    db.commit()
    if produits:
        log.info("Produits types : %s classes sur %s", trouves, len(produits))
    return trouves


def completer_en_fond() -> None:
    from .db import SessionLocal

    def tache():
        try:
            with SessionLocal() as db:
                completer(db)
        except Exception as e:
            log.error("Produits types impossibles a completer : %s", e)
    threading.Thread(target=tache, name="produits-types", daemon=True).start()
