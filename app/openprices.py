"""Prix ouverts d'Open Prices (Open Food Facts) pres de chez chaque utilisateur.

API publique : https://prices.openfoodfacts.org (licence ODbL : citer la source, partager a l'identique
une base qui en serait derivee). On copie une fois par jour les prix des 90 derniers jours dans chaque zone
(autour des magasins des tickets, ou d'une position « Autour de moi »), pour ne pas interroger leur service
a chaque recherche. Chaque personne ne voit ensuite que les magasins proches de chez elle : sa zone est
deduite des magasins ou elle fait ses courses, sans adresse a saisir.
"""

import json
import logging
import math
import statistics
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
from .models import OpenPrice, Receipt, Store, User, ZonePrix

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
        ville=(lieu.get("osm_address_city") or "")[:80] or None,
        lat=lieu.get("osm_lat"), lon=lieu.get("osm_lon"))


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(a))


def ajouter_zone(db: Session, lat: float, lon: float) -> ZonePrix:
    """La zone (carre d'un dixieme de degre) qui contient ce point ; creee si besoin, copiee ensuite."""
    lat, lon = round(lat, 1), round(lon, 1)
    zone = db.scalar(select(ZonePrix).where(ZonePrix.lat == lat, ZonePrix.lon == lon))
    if zone is None:
        zone = ZonePrix(lat=lat, lon=lon)
        db.add(zone)
        db.flush()
    return zone


def _copier_zone(zone: ZonePrix, get: Callable[[dict], dict]) -> dict:
    depuis = date.today() - timedelta(days=config.OPEN_PRICES_JOURS)
    # rayon de copie plus grand que le carre : tout point du carre a ses magasins proches dans la copie
    params = {"lat": zone.lat, "lon": zone.lon, "radius_km": config.OPEN_PRICES_RAYON_KM,
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
    return lignes


def synchroniser(db: Session, get: Callable[[dict], dict] = _get, zones: Optional[list] = None) -> int:
    """Copie les prix des 90 derniers jours de chaque zone ; renvoie le nombre de prix gardes.
    Sans zones precisees : toutes les zones, et la copie remplace l'ancienne (si aucune zone n'a echoue)."""
    tout = zones is None
    if tout:
        ajouter_zone(db, config.OPEN_PRICES_LAT, config.OPEN_PRICES_LON)  # zone par defaut, avant tout ticket
        zones = db.scalars(select(ZonePrix)).all()
    lignes, echec = {}, False
    for zone in zones:
        try:
            lignes.update(_copier_zone(zone, get))
            zone.copie_le = datetime.now(timezone.utc)
        except Exception as e:  # une zone en panne n'empeche pas les autres
            echec = True
            log.error("Open Prices : zone %s, %s impossible : %s", zone.lat, zone.lon, e)
    if tout and not echec:
        db.execute(delete(OpenPrice))
    else:
        db.execute(delete(OpenPrice).where(OpenPrice.id.in_(list(lignes))))
    db.add_all(lignes.values())
    db.commit()
    log.info("Open Prices : %s prix copiés (%s zone(s))", len(lignes), len(zones))
    return len(lignes)


def zone_de(db: Session, user: User, position: Optional[tuple] = None) -> dict:
    """Ou chercher les prix pour cette personne : sa position « Autour de moi » si elle l'a donnee,
    sinon la ou elle fait ses courses (magasins de ses tickets), sinon la zone par defaut."""
    if position:
        return {"lat": position[0], "lon": position[1], "source": "position", "ville": None}
    lieux = db.execute(select(Store.lat, Store.lon, Store.ville).join(Receipt, Receipt.store_id == Store.id)
                       .where(Receipt.user_id == user.id, Store.lat.is_not(None))).all()
    if lieux:
        # la mediane : un ticket pris en vacances ne deplace pas la zone
        villes = [v for _, _, v in lieux if v]
        return {"lat": statistics.median(l[0] for l in lieux), "lon": statistics.median(l[1] for l in lieux),
                "source": "tickets", "ville": max(set(villes), key=villes.count) if villes else None}
    return {"lat": config.OPEN_PRICES_LAT, "lon": config.OPEN_PRICES_LON, "source": "defaut",
            "ville": config.OPEN_PRICES_VILLE}


def proches(prix: list, zone: Optional[dict], km: Optional[float] = None) -> list:
    """Les prix des magasins a moins de PRES_KM (ou km) de la zone (un prix sans position est garde)."""
    if not zone:
        return list(prix)
    km = km or config.OPEN_PRICES_PRES_KM
    return [p for p in prix if p.lat is None or p.lon is None
            or distance_km(zone["lat"], zone["lon"], p.lat, p.lon) <= km]


def zone_en_copie(db: Session, zone: dict) -> bool:
    """La zone vient d'etre demandee et ses prix ne sont pas encore copies."""
    z = db.scalar(select(ZonePrix).where(ZonePrix.lat == round(zone["lat"], 1), ZonePrix.lon == round(zone["lon"], 1)))
    return z is not None and z.copie_le is None


def copier_en_fond(zone_id: int) -> None:
    """Copie tout de suite une nouvelle zone (« Autour de moi »), sans faire attendre la page."""
    def tache():
        try:
            with SessionLocal() as db:
                zone = db.get(ZonePrix, zone_id)
                if zone is not None and zone.copie_le is None:
                    synchroniser(db, zones=[zone])
        except Exception as e:
            log.error("Open Prices : copie de la zone impossible : %s", e)
    threading.Thread(target=tache, name="open-prices-zone", daemon=True).start()


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
    """Tache de fond : synchronise si la copie a plus de 20 heures, puis verifie toutes les heures
    (et copie entre-temps les nouvelles zones, nees d'un nouveau magasin)."""
    def boucle():
        while True:
            try:
                with SessionLocal() as db:
                    derniere = derniere_synchro(db)
                    if derniere is None or datetime.now(timezone.utc) - derniere > timedelta(hours=20):
                        synchroniser(db)
                    else:
                        nouvelles = db.scalars(select(ZonePrix).where(ZonePrix.copie_le.is_(None))).all()
                        if nouvelles:
                            synchroniser(db, zones=nouvelles)
            except Exception as e:  # le site continue de marcher sans Open Prices
                log.error("Open Prices : synchronisation impossible : %s", e)
            time.sleep(3600)

    threading.Thread(target=boucle, name="open-prices", daemon=True).start()


def chercher(db: Session, requete: str, limite: int = 8, zone: Optional[dict] = None,
             km: Optional[float] = None) -> list:
    """Prix releves pres de la zone de la personne pour ce qu'elle cherche. Ordre : les plus pertinents, puis
    ceux dont le nom commence par le mot cherche (« saumon fume » avant « tagliatelles au saumon »),
    puis les moins chers au kilo. Un seul prix par produit et par magasin (le plus recent)."""
    from .recherche import SEUIL, score
    from .tickets import cle_produit

    premier = (cle_produit(requete).split() or [""])[0]
    if not premier:
        return []
    vus, resultats = set(), []
    for p in proches(db.scalars(select(OpenPrice).order_by(OpenPrice.jour.desc())).all(), zone, km):
        s = score(requete, p.nom, p.marque or "")
        cle = (p.nom.lower(), p.magasin, p.ville)
        if s < SEUIL or cle in vus:
            continue
        vus.add(cle)
        commence = cle_produit(p.nom).startswith(premier[:max(3, len(premier) - 1)])
        kilo = prix_au_kilo(p)
        distance = distance_km(zone["lat"], zone["lon"], p.lat, p.lon) if zone and p.lat is not None \
            and p.lon is not None else None
        resultats.append({"p": p, "score": s, "kilo": kilo, "unite": unite_kilo(p), "commence": commence,
                          "distance": distance})
    resultats.sort(key=lambda r: (-round(r["score"], 1), not r["commence"],
                                  r["kilo"] if r["kilo"] is not None else r["p"].prix))
    return resultats[:limite]
