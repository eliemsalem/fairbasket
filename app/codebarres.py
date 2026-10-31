"""Code-barres des produits : scanne une fois, retenu pour toujours pour « enseigne + libelle du ticket ».

Le nom imprime sur le ticket (« PAVE SAUM MONOPRIX ») ne suffit pas a retrouver l'article exact : les marques de
distributeur ont un code different dans chaque enseigne, et deviner par le nom se trompe souvent. Le code-barres
(EAN, le meme dans le monde entier) donne le produit exact : son nom complet, sa marque, son format (donc un vrai
prix au kilo) et les prix releves pour ce meme code dans Open Prices.

Fiches et propositions : Open Food Facts (licence ODbL), interroge seulement quand la personne scanne ou ouvre
la page du code-barres.
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, openprices
from .models import OpenPrice, ProductAlias, ReceiptItem, User

log = logging.getLogger("fairbasket.codebarres")
FICHE = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
RECHERCHE = "https://search.openfoodfacts.org/search"
CHAMPS = "code,product_name,brands,quantity,image_front_small_url"


def _get(url: str, params: Optional[dict] = None) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": openprices.AGENT})
    with urllib.request.urlopen(req, timeout=5) as rep:
        return json.loads(rep.read())


def nettoyer(code: str) -> str:
    return re.sub(r"\D", "", code or "")


def valide(code: str) -> bool:
    """EAN-13, EAN-8, UPC-A (12) ou GTIN-14 avec la bonne cle de controle : une faute de frappe est refusee."""
    if len(code) not in (8, 12, 13, 14) or not code.isdigit():
        return False
    chiffres = [int(c) for c in code[:-1]][::-1]
    somme = sum(c * (3 if i % 2 == 0 else 1) for i, c in enumerate(chiffres))
    return (10 - somme % 10) % 10 == int(code[-1])


def _fiche(p: dict, code: str) -> dict:
    marques = p.get("brands") or ""
    if isinstance(marques, list):
        marques = ", ".join(marques)
    return {"code": code, "nom": (p.get("product_name") or "").strip()[:200] or None,
            "marque": marques.strip()[:120] or None, "format": (p.get("quantity") or "").strip()[:40] or None,
            "image": (p.get("image_front_small_url") or "")[:300] or None}


def fiche(code: str, get: Optional[Callable] = None) -> dict:
    """Nom, marque, format et photo du produit chez Open Food Facts (seulement le code s'il est inconnu)."""
    get = get or (_get if config.OPEN_FOOD_FACTS_AUTO else None)
    try:
        d = get(FICHE.format(code=code), {"fields": "product_name,brands,quantity,image_front_small_url"}) if get else {}
        if d.get("status") == 1:
            return _fiche(d.get("product") or {}, code)
    except Exception as e:  # service indisponible : le code seul est deja utile
        log.info("fiche %s indisponible : %s", code, e)
    return {"code": code, "nom": None, "marque": None, "format": None, "image": None}


def propositions(nom: str, enseigne: str, get: Optional[Callable] = None, limite: int = 3,
                 type_off: Optional[str] = None) -> list:
    """Quelques produits qui ressemblent a la ligne du ticket, avec photo : la personne touche le bon.
    D'abord dans son produit type (rayon) et la marque de l'enseigne (Monoprix, Carrefour…), puis la marque de
    l'enseigne seule, sinon toutes marques."""
    get = get or (_get if config.OPEN_FOOD_FACTS_AUTO else None)
    nom = " ".join(nom.split())
    if len(nom) < 3 or get is None:
        return []
    marque = f' brands:"{enseigne.lower()}"' if enseigne and enseigne != "Inconnue" else ""
    essais = ([f'{nom} categories_tags:"{type_off}"{marque}'] if type_off else []) + ([nom + marque] if marque else [])
    for q in essais + [nom]:
        try:
            d = get(RECHERCHE, {"q": q, "langs": "fr", "page_size": limite, "fields": CHAMPS})
        except Exception as e:
            log.info("propositions indisponibles : %s", e)
            return []
        trouves = [_fiche(h, h["code"]) for h in d.get("hits", []) if valide(str(h.get("code", ""))) and h.get("product_name")]
        if trouves:
            return trouves[:limite]
    return []


def alias_de(db: Session, item: ReceiptItem) -> Optional[ProductAlias]:
    if item.receipt.store is None:
        return None
    return db.scalar(select(ProductAlias).where(ProductAlias.enseigne == item.receipt.store.enseigne,
                                                ProductAlias.libelle == item.libelle))


def enregistrer(db: Session, item: ReceiptItem, f: dict, user: Optional[User] = None) -> Optional[ProductAlias]:
    """Le scan compte comme un avis fort sur ce libelle dans cette enseigne (confiance.py) : retenu pour tous
    quand il est le mieux soutenu, et alors les prochains tickets le connaissent deja."""
    from .confiance import donner_avis

    if item.receipt.store is None:
        return None
    user = user or db.get(User, item.receipt.user_id)
    if item.product is None:  # ligne jamais nommee : le nom de la fiche (ou du ticket) devient le produit
        from .tickets import renommer_produit
        renommer_produit(db, item, f.get("nom") or item.libelle.capitalize(), user)
        db.refresh(item)
    alias = donner_avis(db, user, item, code=f["code"])
    if alias is not None and alias.code_barres == f["code"]:
        alias.nom_exact, alias.marque = f.get("nom") or alias.nom_exact, f.get("marque") or alias.marque
        alias.format, alias.image = f.get("format") or alias.format, f.get("image") or alias.image
    db.commit()
    return alias


UNITES = {"g": Decimal("0.001"), "kg": Decimal(1), "mg": Decimal("0.000001"),
          "ml": Decimal("0.001"), "cl": Decimal("0.01"), "dl": Decimal("0.1"), "l": Decimal(1)}


def quantite(format_: Optional[str]) -> Optional[tuple]:
    """« 240 g » -> (0.24, "kg") ; « 4 x 125 g » -> (0.5, "kg") ; « 1 L » -> (1, "L")."""
    if not format_:
        return None
    m = re.search(r"(?:(\d+)\s*[x×*]\s*)?(\d+(?:[.,]\d+)?)\s*(mg|kg|g|ml|cl|dl|l)\b", format_.lower())
    if not m:
        return None
    n = Decimal(m.group(1) or 1) * Decimal(m.group(2).replace(",", ".")) * UNITES[m.group(3)]
    return (n, "L" if m.group(3).endswith("l") else "kg") if n > 0 else None


def prix_unite(montant: Decimal, nb: Decimal, format_: Optional[str]) -> Optional[tuple]:
    """Le vrai prix au kilo (ou au litre) grace au format exact du paquet."""
    q = quantite(format_)
    if not q or not nb:
        return None
    return (montant / nb / q[0]).quantize(Decimal("0.01")), q[1]


def ailleurs(db: Session, code: str, zone: Optional[dict], prix: Optional[Decimal] = None, limite: int = 3) -> list:
    """Le meme produit exact (meme code) releve dans d'autres magasins autour : le moins cher d'abord."""
    vus, resultats = set(), []
    for p in openprices.proches(db.scalars(select(OpenPrice).where(OpenPrice.code_barres == code)
                                           .order_by(OpenPrice.jour.desc())).all(), zone, 12):
        if (p.magasin, p.ville) in vus:
            continue
        vus.add((p.magasin, p.ville))
        distance = round(openprices.distance_km(zone["lat"], zone["lon"], p.lat, p.lon), 1) \
            if zone and p.lat is not None and p.lon is not None else None
        resultats.append({"p": p, "distance": distance, "ecart": (p.prix - prix) if prix is not None else None})
    resultats.sort(key=lambda r: r["p"].prix)
    return resultats[:limite]
