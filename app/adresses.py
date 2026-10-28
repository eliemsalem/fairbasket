"""Adresse d'un magasin trouvee toute seule, pour que la personne n'ait rien a saisir.

1. OpenStreetMap (Nominatim) : « Carrefour Market Paris Jean Jaures » -> le magasin et son adresse.
2. Base Adresse Nationale (api-adresse.data.gouv.fr) : quand le nom du magasin contient l'adresse
   (« CITY PARIS CRIMÉE 96 » -> 96 rue de Crimée, 75019 Paris).
Sans resultat sur, on ne devine pas : l'adresse reste vide et la personne peut l'indiquer si elle le veut.
La position du magasin (latitude, longitude) est gardee aussi : elle situe la zone de prix de la personne.
Une adresse imprimee sur le ticket ou saisie est situee par la Base Adresse Nationale.
"""

import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
from typing import Callable, Optional

from sqlalchemy import select, update
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
                    "ville": a.get("city") or a.get("town") or a.get("village") or "", **_position(r.get("lat"), r.get("lon"))}
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
            return {"adresse": p["name"], "code_postal": p["postcode"], "ville": p["city"], **_position_ban(f)}
    return None


def _position(lat, lon) -> dict:
    try:
        return {"lat": float(lat), "lon": float(lon)}
    except (TypeError, ValueError):
        return {}


def _position_ban(feature: dict) -> dict:
    coords = (feature.get("geometry") or {}).get("coordinates") or [None, None]
    return _position(coords[1], coords[0])


def localiser(adresse: Optional[str], code_postal: Optional[str], ville: Optional[str],
              get: Optional[Callable] = None) -> Optional[dict]:
    """Position d'une adresse connue (imprimee sur le ticket ou saisie) : {lat, lon} ou None."""
    q = " ".join(x for x in (adresse, code_postal, ville) if x)
    if len(q) < 4:
        return None
    url = "https://api-adresse.data.gouv.fr/search/?" + urllib.parse.urlencode({"q": q, "limit": 1})
    try:
        for f in (get or _get)(url).get("features", []):
            p = f["properties"]
            # dans le bon departement (un code postal voisin mal saisi passe), pas une rue homonyme ailleurs
            if p.get("score", 0) >= 0.4 and (not code_postal or (p.get("postcode") or "")[:2] == code_postal[:2]):
                return _position_ban(f) or None
    except Exception as e:
        log.warning("Position de %s : %s", q, e)
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
    """Complete l'adresse d'un magasin qui n'en a pas (ses tickets sont alors valides), et sa position.
    True si l'adresse a ete trouvee."""
    from .openprices import ajouter_zone

    trouvee = False
    if not (store.adresse or store.code_postal):
        trouve = trouver(store.enseigne, store.nom, get)
        if trouve:
            store.adresse, store.code_postal = trouve["adresse"][:200], trouve["code_postal"][:10]
            store.ville, store.lat, store.lon = trouve["ville"][:80], trouve.get("lat"), trouve.get("lon")
            if store.id:
                db.execute(update(Receipt).where(Receipt.store_id == store.id).values(adresse_ok=True))
            log.info("Adresse trouvée pour %s %s : %s, %s %s", store.enseigne, store.nom, store.adresse,
                     store.code_postal, store.ville)
            trouvee = True
    if store.lat is None and (store.adresse or store.code_postal):
        position = localiser(store.adresse, store.code_postal, store.ville, get)
        if position:
            store.lat, store.lon = position["lat"], position["lon"]
    if store.lat is not None:
        ajouter_zone(db, store.lat, store.lon)  # ses prix du quartier seront copies
    return trouvee


def completer_tous(db: Session, get: Optional[Callable] = None) -> int:
    stores = db.scalars(select(Store).where(Store.lat.is_(None))).all()
    n = sum(completer(db, s, get) for s in stores)
    db.commit()
    return n


def demarrer_recherche() -> None:
    """Au demarrage, en tache de fond : les magasins deja enregistres sans adresse ou sans position."""
    def tache():
        try:
            with SessionLocal() as db:
                log.info("Adresses des magasins : %s trouvée(s)", completer_tous(db))
        except Exception as e:
            log.error("Adresses des magasins : recherche impossible : %s", e)
    threading.Thread(target=tache, name="adresses", daemon=True).start()


_proches: dict = {}  # (enseigne, lat, lon) -> magasin le plus proche (ou None), pour ne pas redemander


def magasin_proche(enseigne: str, lat: float, lon: float, get: Optional[Callable] = None) -> Optional[dict]:
    """Le magasin de cette enseigne le plus proche d'un point (OpenStreetMap, dans un rayon d'environ 5 km) :
    {nom, adresse, code_postal, ville, lat, lon, distance_km}, ou None."""
    from .openprices import distance_km

    cle = (cle_produit(enseigne), round(lat, 2), round(lon, 2))
    if cle in _proches:
        return _proches[cle]
    mot = (cle_produit(enseigne).split() or [""])[0]
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": enseigne, "format": "jsonv2", "addressdetails": 1, "countrycodes": "fr", "limit": 15, "bounded": 1,
         "viewbox": f"{lon - 0.07},{lat + 0.045},{lon + 0.07},{lat - 0.045}"})
    trouve = None
    try:
        candidats = []
        for r in (get or _get)(url):
            a = r.get("address") or {}
            if r.get("category") != "shop" or not mot or mot not in cle_produit(r.get("name") or ""):
                continue
            p = _position(r.get("lat"), r.get("lon"))
            if p:
                candidats.append((distance_km(lat, lon, p["lat"], p["lon"]), r, a, p))
        if candidats:
            d, r, a, p = min(candidats, key=lambda c: c[0])
            trouve = {"nom": r.get("name") or enseigne,
                      "adresse": " ".join(x for x in (a.get("house_number"), a.get("road")) if x) or None,
                      "code_postal": a.get("postcode"), "ville": a.get("city") or a.get("town") or a.get("village"),
                      **p, "distance_km": round(d, 1)}
    except Exception as e:
        log.warning("Magasin %s le plus proche : %s", enseigne, e)
        return None  # pas garde : on reessaiera
    _proches[cle] = trouve
    return trouve


def situer(texte: str, get: Optional[Callable] = None) -> Optional[dict]:
    """Un code postal, une ville ou une adresse tapes par la personne -> {lat, lon, quartier} (« 75019 Paris »)."""
    texte = " ".join((texte or "").split())[:120]
    if len(texte) < 2:
        return None
    url = "https://api-adresse.data.gouv.fr/search/?" + urllib.parse.urlencode({"q": texte, "limit": 1})
    try:
        for f in (get or _get)(url).get("features", []):
            p = f["properties"]
            if p.get("score", 0) >= 0.3:
                return {**_position_ban(f), "quartier": " ".join(x for x in (p.get("postcode"), p.get("city")) if x)}
    except Exception as e:
        log.warning("Quartier %s : %s", texte, e)
    return None


def nommer_lieu(lat: float, lon: float, get: Optional[Callable] = None) -> Optional[str]:
    """Le code postal et la ville d'une position (« 75019 Paris »), sans l'adresse exacte."""
    url = "https://api-adresse.data.gouv.fr/reverse/?" + urllib.parse.urlencode({"lat": lat, "lon": lon, "limit": 1})
    try:
        for f in (get or _get)(url).get("features", []):
            p = f["properties"]
            return " ".join(x for x in (p.get("postcode"), p.get("city")) if x) or None
    except Exception as e:
        log.warning("Nom du lieu %s, %s : %s", lat, lon, e)
    return None


_supermarches: dict = {}  # (lat, lon) arrondis -> magasins a cote


def supermarches_proches(lat: float, lon: float, get: Optional[Callable] = None) -> list:
    """Les supermarches autour d'un point (OpenStreetMap, environ 1,5 km), le plus proche de chaque enseigne
    connue d'abord : [{enseigne, nom, adresse, ville, lat, lon, distance_km}], du plus proche au plus loin."""
    from .enseignes import reconnaitre
    from .openprices import distance_km

    cle = (round(lat, 2), round(lon, 2))
    if cle in _supermarches:
        return _supermarches[cle]
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": "supermarket", "format": "jsonv2", "addressdetails": 1, "limit": 40, "bounded": 1,
         "viewbox": f"{lon - 0.021},{lat + 0.0135},{lon + 0.021},{lat - 0.0135}"})
    try:
        resultats = (get or _get)(url)
    except Exception as e:
        log.warning("Supermarchés autour de %s, %s : %s", lat, lon, e)
        return []  # pas garde : on reessaiera
    par_enseigne = {}
    for r in resultats:
        enseigne = reconnaitre(r.get("name") or "")[0]
        p = _position(r.get("lat"), r.get("lon"))
        if r.get("category") != "shop" or not enseigne or not p:
            continue
        a = r.get("address") or {}
        m = {"enseigne": enseigne, "nom": r.get("name"),
             "adresse": " ".join(x for x in (a.get("house_number"), a.get("road"), a.get("postcode")) if x) or None,
             "ville": a.get("city") or a.get("town") or a.get("village"), **p,
             "distance_km": round(distance_km(lat, lon, p["lat"], p["lon"]), 1)}
        if enseigne not in par_enseigne or m["distance_km"] < par_enseigne[enseigne]["distance_km"]:
            par_enseigne[enseigne] = m
    magasins = sorted(par_enseigne.values(), key=lambda m: m["distance_km"])
    _supermarches[cle] = magasins
    return magasins
