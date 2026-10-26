"""Prix ouverts d'Open Prices (Open Food Facts) autour de la zone choisie.

API publique : https://prices.openfoodfacts.org (licence ODbL : citer la source, partager a l'identique
une base qui en serait derivee). On copie une fois par jour les prix des 90 derniers jours dans la zone,
pour ne pas interroger leur service a chaque recherche.
"""

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import config
from .db import SessionLocal
from .models import OpenPrice

log = logging.getLogger("fairbasket.openprices")
API = "https://prices.openfoodfacts.org/api/v1/prices"
AGENT = "FairBasket/0.1 (https://fairbasket-jhiu.onrender.com)"  # demande par Open Food Facts : s'identifier
PAR_PAGE = 100


def _get(params: dict) -> dict:
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as rep:
        return json.loads(rep.read())


def _dec(v) -> Optional[Decimal]:
    try:
        return None if v in (None, "") else Decimal(str(v))
    except ArithmeticError:
        return None


def _ligne(item: dict) -> Optional[OpenPrice]:
    produit = item.get("product") or {}
    lieu = item.get("location") or {}
    nom = produit.get("product_name") or (item.get("category_tag") or "").split(":")[-1].replace("-", " ")
    prix = _dec(item.get("price"))
    if not nom or prix is None or item.get("currency") != "EUR" or not item.get("date"):
        return None
    return OpenPrice(
        id=item["id"], nom=nom[:200], marque=(produit.get("brands") or "")[:120] or None,
        code_barres=(item.get("product_code") or "")[:32] or None,
        quantite=_dec(produit.get("product_quantity")), unite=(produit.get("product_quantity_unit") or "")[:8] or None,
        prix=prix, prix_par=item.get("price_per"), promo=bool(item.get("price_is_discounted")),
        jour=date.fromisoformat(item["date"]), magasin=(lieu.get("osm_name") or "Magasin")[:120],
        ville=(lieu.get("osm_address_city") or "")[:80] or None)


def synchroniser(db: Session, get: Callable[[dict], dict] = _get) -> int:
    """Copie les prix des 90 derniers jours dans la zone ; renvoie le nombre de prix gardes."""
    depuis = date.today() - timedelta(days=config.OPEN_PRICES_JOURS)
    params = {"lat": config.OPEN_PRICES_LAT, "lon": config.OPEN_PRICES_LON, "radius_km": config.OPEN_PRICES_RAYON_KM,
              "date__gte": depuis.isoformat(), "size": PAR_PAGE, "order_by": "-date"}
    lignes, page = {}, 1
    while True:
        d = get({**params, "page": page})
        for item in d.get("items", []):
            ligne = _ligne(item)
            if ligne:
                lignes[ligne.id] = ligne
        if page >= (d.get("pages") or 1) or not d.get("items"):
            break
        page += 1
        time.sleep(0.5)  # rester leger pour leur service
    db.execute(delete(OpenPrice))
    db.add_all(lignes.values())
    db.commit()
    log.info("Open Prices : %s prix copiés (%s pages)", len(lignes), page)
    return len(lignes)


def derniere_synchro(db: Session) -> Optional[datetime]:
    d = db.scalar(select(func.max(OpenPrice.synchronise_le)))
    return d.replace(tzinfo=timezone.utc) if d and d.tzinfo is None else d


def prix_au_kilo(p: OpenPrice) -> Optional[Decimal]:
    """Prix au kilo (ou au litre) quand le format est connu, pour comparer des formats differents."""
    if p.prix_par == "KILOGRAM":
        return p.prix
    facteurs = {"g": 1000, "ml": 1000, "cl": 100, "kg": 1, "l": 1}
    if p.quantite and p.quantite > 0 and (p.unite or "").lower() in facteurs:
        return (p.prix / p.quantite * facteurs[p.unite.lower()]).quantize(Decimal("0.01"))
    return None


def unite_kilo(p: OpenPrice) -> str:
    return "L" if (p.unite or "").lower() in ("ml", "cl", "l") else "kg"


def demarrer_synchro_quotidienne() -> None:
    """Tache de fond : synchronise si la copie a plus de 20 heures, puis verifie toutes les heures."""
    def boucle():
        while True:
            try:
                with SessionLocal() as db:
                    derniere = derniere_synchro(db)
                    if derniere is None or datetime.now(timezone.utc) - derniere > timedelta(hours=20):
                        synchroniser(db)
            except Exception as e:  # le site continue de marcher sans Open Prices
                log.error("Open Prices : synchronisation impossible : %s", e)
            time.sleep(3600)

    threading.Thread(target=boucle, name="open-prices", daemon=True).start()


def chercher(db: Session, requete: str, limite: int = 8) -> list:
    """Prix releves autour de la zone pour ce que la personne cherche. Ordre : les plus pertinents, puis
    ceux dont le nom commence par le mot cherche (« saumon fume » avant « tagliatelles au saumon »),
    puis les moins chers au kilo. Un seul prix par produit et par magasin (le plus recent)."""
    from .recherche import SEUIL, score
    from .tickets import cle_produit

    premier = (cle_produit(requete).split() or [""])[0]
    if not premier:
        return []
    vus, resultats = set(), []
    for p in db.scalars(select(OpenPrice).order_by(OpenPrice.jour.desc())):
        s = score(requete, p.nom, p.marque or "")
        cle = (p.nom.lower(), p.magasin, p.ville)
        if s < SEUIL or cle in vus:
            continue
        vus.add(cle)
        commence = cle_produit(p.nom).startswith(premier[:max(3, len(premier) - 1)])
        kilo = prix_au_kilo(p)
        resultats.append({"p": p, "score": s, "kilo": kilo, "unite": unite_kilo(p), "commence": commence})
    resultats.sort(key=lambda r: (-round(r["score"], 1), not r["commence"],
                                  r["kilo"] if r["kilo"] is not None else r["p"].prix))
    return resultats[:limite]
