from datetime import date, timedelta

from app import openprices
from app.models import OpenPrice
from tests.test_tickets import db  # noqa: F401

AUJ = date.today().isoformat()


def item(i, nom, prix, magasin="Monoprix", qte=None, unite=None, par=None, devise="EUR", jour=AUJ):
    return {"id": i, "price": prix, "currency": devise, "date": jour, "price_per": par,
            "product": {"product_name": nom, "brands": "Marque", "product_quantity": qte,
                        "product_quantity_unit": unite} if nom else None,
            "category_tag": None if nom else "en:lemons",
            "location": {"osm_name": magasin, "osm_address_city": "Paris"}}


def faux_service(pages):
    appels = []

    def get(params):
        appels.append(params)
        return {"items": pages[params["page"] - 1], "pages": len(pages)}
    return get, appels


def test_synchronisation_paginee(db, monkeypatch):
    monkeypatch.setattr(openprices.time, "sleep", lambda s: None)
    get, appels = faux_service([[item(1, "Pavé de saumon", 9.5, qte=250, unite="g")],
                                [item(2, None, 3.99, par="KILOGRAM"), item(3, "Bière", 2, devise="USD")]])
    assert openprices.synchroniser(db, get=get) == 2  # le prix en dollars est ignore
    assert [a["page"] for a in appels] == [1, 2] and appels[0]["radius_km"] > 0
    assert db.get(OpenPrice, 2).nom == "lemons"  # produit sans code-barres : nom tire de la categorie
    assert str(openprices.prix_au_kilo(db.get(OpenPrice, 1))) == "38.00"
    # nouvelle synchronisation : la copie est remplacee, pas dupliquee
    get2, _ = faux_service([[item(1, "Pavé de saumon", 9.9, qte=250, unite="g")]])
    openprices.synchroniser(db, get=get2)
    assert db.query(OpenPrice).count() == 1 and str(db.get(OpenPrice, 1).prix) == "9.90"


def test_recherche_autour(db, monkeypatch):
    monkeypatch.setattr(openprices.time, "sleep", lambda s: None)
    hier = (date.today() - timedelta(days=1)).isoformat()
    get, _ = faux_service([[item(1, "Pavé de saumon", 9.5, "Monoprix", 250, "g"),
                            item(2, "Saumon fumé", 6.0, "Carrefour Market", 100, "g"),
                            item(3, "Pavé de saumon", 9.9, "Monoprix", 250, "g", jour=hier),
                            item(4, "Bière blonde", 2.0, "Franprix")]])
    openprices.synchroniser(db, get=get)
    r = openprices.chercher(db, "saumon")
    # le nom qui commence par le mot cherche d'abord, puis le moins cher au kilo
    assert [x["p"].nom for x in r] == ["Saumon fumé", "Pavé de saumon"]
    assert str(r[1]["p"].prix) == "9.50"  # un seul prix par produit et magasin : le plus recent
    assert openprices.chercher(db, "") == []
