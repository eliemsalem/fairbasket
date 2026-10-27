"""Adresse d'un magasin trouvee toute seule, pour que la personne n'ait rien a saisir.

1. OpenStreetMap (Nominatim) : « Carrefour Market Paris Jean Jaures » -> le magasin et son adresse.
2. Base Adresse Nationale (api-adresse.data.gouv.fr) : quand le nom du magasin contient l'adresse
   (« CITY PARIS CRIMÉE 96 » -> 96 rue de Crimée, 75019 Paris).
Sans resultat sur, on ne devine pas : l'adresse reste vide et la personne peut l'indiquer si elle le veut.
"""

import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
from typing import Callable, Optional

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Receipt, Store
from .openprices import AGENT
from .tickets import cle_magasin, cle_produit

log = logging.getLogger("fairbasket.adresses")
SANS_LIEU = {"Inconnue", "Marché", "Commerce"}
_verrou = threading.Lock()  # Nominatim demande au plus une requete par seconde
_derniere = [0.0]


def _get(url: str) -> object:
    with _verrou:
        attente = 1.1 - (time.monotonic() - _derniere[0])
        if attente > 0:
            time.sleep(attente)
        _derniere[0] = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=8) as rep:
            return json.loads(rep.read())


FORMATS = {"city", "market", "express", "contact", "hyper", "montagne", "les", "des", "sur"}


def _mots(texte: str) -> list:
    return re.sub(r"[^\w]+", " ", cle_produit(texte)).split()


def _osm(enseigne: str, nom: str, get: Callable) -> Optional[dict]:
    q = nom if cle_produit(enseigne) in cle_produit(nom) else f"{enseigne} {nom}"
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "addressdetails": 1, "countrycodes": "fr", "limit": 3})
    for r in get(url):
        a = r.get("address") or {}
        # un magasin de cette enseigne (pas une rue ou un opticien du meme nom)
        if not (r.get("category") == "shop" and cle_produit(enseigne).split()[0] in cle_produit(r.get("name") or "")
                and a.get("road") and a.get("postcode")):
            continue
        # et au bon endroit : un mot du nom (« Jaures », « Republique ») dans la rue ou le quartier trouves ;
        # sinon c'est un autre magasin de l'enseigne dans la meme ville
        ville = cle_produit(a.get("city") or a.get("town") or a.get("village") or "")
        distinctifs = [m for m in _mots(cle_magasin(enseigne, nom)) if len(m) >= 3 and not m.isdigit()
                       and m not in FORMATS and m not in ville]
        lieu = _mots(" ".join(a.get(k) or "" for k in ("road", "quarter", "suburb", "neighbourhood", "city_district")))
        if distinctifs and any(m in lieu for m in distinctifs):
            return {"adresse": " ".join(x for x in (a.get("house_number"), a["road"]) if x), "code_postal": a["postcode"],
                    "ville": a.get("city") or a.get("town") or a.get("village") or ""}
    return None


def _ban(enseigne: str, nom: str, get: Callable) -> Optional[dict]:
    mots = cle_magasin(enseigne, nom).upper().split()
    numeros = [m for m in mots if m.isdigit()]
    if not numeros:
        return None
    # « PARIS CRIMEE 96 » -> « 96 PARIS CRIMEE » ; les mots de format (city, market…) ne sont pas une adresse
    reste = [m for m in mots if not m.isdigit() and m.lower() not in FORMATS]
    url = "https://api-adresse.data.gouv.fr/search/?" + urllib.parse.urlencode(
        {"q": " ".join([numeros[-1], *reste]), "limit": 1, "type": "housenumber"})
    for f in get(url).get("features", []):
        p = f["properties"]
        if p.get("score", 0) >= 0.5 and p.get("type") == "housenumber":
            return {"adresse": p["name"], "code_postal": p["postcode"], "ville": p["city"]}
    return None


def trouver(enseigne: str, nom: str, get: Optional[Callable] = None) -> Optional[dict]:
    """{adresse, code_postal, ville} ou None. Un nom sans lieu (« AUCHAN » seul) ne suffit pas."""
    if enseigne in SANS_LIEU or cle_magasin(enseigne, nom) == cle_produit(enseigne):
        return None
    # un numero dans le nom (« CITY PARIS CRIMÉE 96 ») est l'adresse elle-meme : la base des adresses d'abord
    ordre = (_ban, _osm) if any(m.isdigit() for m in cle_magasin(enseigne, nom).split()) else (_osm, _ban)
    for chercher in ordre:
        try:
            trouve = chercher(enseigne, nom, get or _get)
        except Exception as e:  # service indisponible : on n'empeche jamais d'enregistrer un ticket
            log.warning("Adresse de %s %s : %s", enseigne, nom, e)
            continue
        if trouve:
            return trouve
    return None


def completer(db: Session, store: Store, get: Optional[Callable] = None) -> bool:
    """Complete l'adresse d'un magasin qui n'en a pas ; ses tickets sont alors valides. True si trouvee."""
    if store.adresse or store.code_postal:
        return False
    trouve = trouver(store.enseigne, store.nom, get)
    if not trouve:
        return False
    store.adresse, store.code_postal, store.ville = trouve["adresse"][:200], trouve["code_postal"][:10], trouve["ville"][:80]
    if store.id:
        db.execute(update(Receipt).where(Receipt.store_id == store.id).values(adresse_ok=True))
    log.info("Adresse trouvée pour %s %s : %s, %s %s", store.enseigne, store.nom, store.adresse, store.code_postal,
             store.ville)
    return True


def completer_tous(db: Session, get: Optional[Callable] = None) -> int:
    stores = db.scalars(select(Store).where(Store.adresse.is_(None), or_(Store.code_postal.is_(None),
                                                                           Store.code_postal == ""))).all()
    n = sum(completer(db, s, get) for s in stores)
    db.commit()
    return n


def demarrer_recherche() -> None:
    """Au demarrage, en tache de fond : les magasins deja enregistres sans adresse."""
    def tache():
        try:
            with SessionLocal() as db:
                log.info("Adresses des magasins : %s trouvée(s)", completer_tous(db))
        except Exception as e:
            log.error("Adresses des magasins : recherche impossible : %s", e)
    threading.Thread(target=tache, name="adresses", daemon=True).start()
