from app import adresses, config
from app.adresses import trouver
from app.tickets import enregistrer_ticket
from tests.test_tickets import ALDI, db, fausse_lecture, nouvel_utilisateur  # noqa: F401

OSM = [{"category": "highway", "name": "Avenue Jean Jaurès", "address": {"road": "Avenue Jean Jaurès", "postcode": "75019"}},
       {"category": "shop", "name": "Carrefour Market", "address": {"house_number": "59", "road": "Avenue Jean Jaurès",
                                                                     "postcode": "75019", "city": "Paris"}}]
BAN = {"features": [{"properties": {"score": 0.62, "type": "housenumber", "name": "96 Rue de Crimée",
                                    "postcode": "75019", "city": "Paris"}}]}


def faux_get(osm, ban, urls=None):
    def get(url):
        if urls is not None:
            urls.append(url)
        return osm if "nominatim" in url else ban
    return get


def test_trouve_par_openstreetmap():
    urls = []
    a = trouver("Carrefour", "MARKET PARIS JEAN JAURES", faux_get(OSM, BAN, urls))
    assert a == {"adresse": "59 Avenue Jean Jaurès", "code_postal": "75019", "ville": "Paris"}
    assert len(urls) == 1 and "Carrefour+MARKET" in urls[0]


def test_trouve_par_le_nom_du_magasin():
    urls = []
    a = trouver("Carrefour", "CITY PARIS CRIMÉE 96", faux_get(OSM, BAN, urls))
    assert a["adresse"] == "96 Rue de Crimée" and "q=96+PARIS+CRIMEE" in urls[0]  # numero : adresse d'abord


def test_ne_devine_pas():
    assert trouver("Auchan", "AUCHAN", faux_get(OSM, BAN)) is None  # pas de lieu dans le nom
    assert trouver("Inconnue", "INCONNU", faux_get(OSM, BAN)) is None
    assert trouver("Carrefour", "MARKET PARIS ITALIE", faux_get([], {"features": []})) is None

    def panne(url):
        raise OSError("hors ligne")
    assert trouver("Carrefour", "MARKET PARIS JEAN JAURES", panne) is None


def test_ticket_sans_adresse_complete(db, monkeypatch):
    monkeypatch.setattr(config, "ADRESSES_AUTO", True)
    monkeypatch.setattr(adresses, "_get", faux_get(OSM, BAN))
    u = nouvel_utilisateur(db, "a@x.fr")
    d = {**ALDI, "enseigne": "Carrefour", "magasin": "MARKET PARIS JEAN JAURES", "adresse": None, "code_postal": None,
         "ville": None}
    r = enregistrer_ticket(db, u, b"1", "t.pdf", "application/pdf", lire=fausse_lecture(d)).receipt
    assert r.adresse_ok and r.store.adresse == "59 Avenue Jean Jaurès"  # rien a saisir


def test_autre_magasin_de_la_ville_refuse():
    # « CITY PARIS VAUGIRARD » : OSM renvoie un Carrefour City rue des Entrepreneurs, ce n'est pas lui
    autre = [{"category": "shop", "name": "Carrefour City", "address": {"road": "Rue des Entrepreneurs",
                                                                         "postcode": "75015", "city": "Paris"}}]
    assert trouver("Carrefour", "CITY PARIS VAUGIRARD", faux_get(autre, {"features": []})) is None
