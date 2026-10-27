from app import adresses, config, openprices
from app.models import OpenPrice, ZonePrix
from tests.test_adresses import BAN, OSM, faux_get
from tests.test_openprices import faux_service, item
from tests.test_stats import ticket
from tests.test_tickets import _article, db, nouvel_utilisateur  # noqa: F401

JAURES = (48.8845, 2.3762)   # Paris 19e
BASTILLE = (48.8532, 2.3691)  # 3,5 km
LYON = (45.7640, 4.8357)


def situe(i, nom, prix, magasin, pos):
    it = item(i, nom, prix, magasin)
    it["location"].update(osm_lat=pos[0], osm_lon=pos[1])
    return it


def test_zone_deduite_des_tickets(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    assert openprices.zone_de(db, u)["source"] == "defaut"  # pas encore de ticket
    for n, (enseigne, pos) in enumerate([("Carrefour", JAURES), ("Monoprix", JAURES), ("Lidl", LYON)]):
        r = ticket(db, u, n, enseigne, "2026-10-03", [_article("A", "Pain", 1.0)])
        r.store.lat, r.store.lon, r.store.ville = pos[0], pos[1], "Paris" if pos == JAURES else "Lyon"
    db.commit()
    zone = openprices.zone_de(db, u)
    # un ticket a Lyon (vacances) ne deplace pas la zone
    assert zone["source"] == "tickets" and (zone["lat"], zone["lon"]) == JAURES and zone["ville"] == "Paris"
    assert openprices.zone_de(db, u, position=LYON)["source"] == "position"  # « Autour de moi » d'abord


def test_seulement_les_magasins_proches(db, monkeypatch):
    monkeypatch.setattr(openprices.time, "sleep", lambda s: None)
    get, appels = faux_service([[situe(1, "Pain de mie", 1.5, "Monoprix", BASTILLE),
                                 situe(2, "Pain de mie", 1.2, "Lidl", LYON)]])
    openprices.synchroniser(db, get=get)
    pres_de_jaures = {"lat": JAURES[0], "lon": JAURES[1]}
    assert [r["p"].magasin for r in openprices.chercher(db, "pain", zone=pres_de_jaures)] == ["Monoprix"]
    assert db.get(OpenPrice, 2).lat == LYON[0]


def test_zones_copiees_et_panne(db, monkeypatch):
    monkeypatch.setattr(openprices.time, "sleep", lambda s: None)
    openprices.ajouter_zone(db, *LYON)
    openprices.ajouter_zone(db, 45.7612, 4.8301)  # meme carre : pas de doublon
    get, appels = faux_service([[item(1, "Pain", 1.0)]])
    openprices.synchroniser(db, get=get)
    assert {(a["lat"], a["lon"]) for a in appels} == {(45.8, 4.8), (48.9, 2.4)}  # Lyon et la zone par defaut
    assert all(z.copie_le for z in db.query(ZonePrix))

    def panne(params):
        raise OSError("hors ligne")
    openprices.synchroniser(db, get=panne)
    assert db.query(OpenPrice).count() == 1  # en panne : l'ancienne copie est gardee


def test_position_du_magasin(db, monkeypatch):
    osm = [{**OSM[1], "lat": "48.8845", "lon": "2.3762"}]
    u = nouvel_utilisateur(db, "a@x.fr")
    r = ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("A", "Pain", 1.0)])
    r.store.nom, r.store.adresse, r.store.code_postal = "MARKET PARIS JEAN JAURES", None, None
    assert adresses.completer(db, r.store, faux_get(osm, BAN))
    assert (r.store.lat, r.store.lon) == JAURES
    assert db.query(ZonePrix).filter_by(lat=48.9, lon=2.4).count() == 1  # ses prix du quartier seront copies
    # adresse imprimee sur le ticket : situee par la Base Adresse Nationale
    ban = {"features": [{"geometry": {"coordinates": [2.3691, 48.8532]},
                         "properties": {"score": 0.9, "postcode": "75011"}}]}
    assert adresses.localiser("3 rue de la Roquette", "75011", "Paris", faux_get([], ban)) == \
        {"lat": BASTILLE[0], "lon": BASTILLE[1]}
    assert adresses.localiser("3 rue de la Roquette", "13001", "Marseille", faux_get([], ban)) is None


def test_autour_de_moi(client, links, monkeypatch):
    from tests.test_auth import connecter_admin
    monkeypatch.setattr(config, "OPEN_PRICES_AUTO", False)
    connecter_admin(client, links)
    assert "zone par défaut" in client.get("/comparer?q=pain").text
    r = client.post("/position", data={"lat": "45.764", "lon": "4.836", "retour": "/comparer?q=pain"},
                    follow_redirects=False)
    assert r.headers["location"] == "/comparer?q=pain" and "45.76:4.84" in r.headers["set-cookie"]
    page = client.get("/comparer?q=pain").text
    assert "de votre position" in page and "Chargement des prix" in page and "Revenir à mes magasins" in page
    client.post("/position", data={"retour": "/comparer"})  # « Revenir à mes magasins »
    assert "zone par défaut" in client.get("/comparer?q=pain").text
    r = client.post("/position", data={"lat": "1", "lon": "2", "retour": "https://ailleurs.com"}, follow_redirects=False)
    assert r.headers["location"] == "/comparer"
