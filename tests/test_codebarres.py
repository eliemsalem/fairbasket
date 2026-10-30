from datetime import date
from decimal import Decimal

import pytest

from app import codebarres, config, tickets
from app.lecture import Lecture
from app.models import OpenPrice, ProductAlias, ReceiptItem
from tests.test_auth import connecter_admin
from tests.test_tickets import ALDI

PDF = ("ticket.pdf", b"%PDF-1.4 faux", "application/pdf")
OIGNONS = "4061458000123"  # code inventé, cle de controle juste


@pytest.fixture(autouse=True)
def sans_ia(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(tickets, "lire_ticket",
                        lambda data, mt: Lecture(donnees=ALDI, modele="test", tokens_entree=1, tokens_sortie=1))


def test_cle_de_controle():
    assert codebarres.valide("3350030224462") and codebarres.valide(OIGNONS)
    assert not codebarres.valide("3350030224463")  # un chiffre faux
    assert not codebarres.valide("12345") and not codebarres.valide("")
    assert codebarres.nettoyer(" 3 350030 224462 ") == "3350030224462"


def test_format_du_paquet():
    assert codebarres.quantite("240 g") == (Decimal("0.240"), "kg")
    assert codebarres.quantite("4 x 125 g") == (Decimal("0.500"), "kg")
    assert codebarres.quantite("1 L") == (Decimal(1), "L")
    assert codebarres.quantite("25 cl")[1] == "L"
    assert codebarres.quantite("6 œufs") is None
    assert codebarres.prix_unite(Decimal("5.40"), Decimal(1), "240 g") == (Decimal("22.50"), "kg")


def test_fiche_et_propositions_sans_reseau():
    fiche = codebarres.fiche("3350030224462", lambda url, p: {"status": 1, "product": {
        "product_name": "Pavés de saumon bio", "brands": "Monoprix, Monoprix Bio", "quantity": "240 g"}})
    assert fiche["nom"] == "Pavés de saumon bio" and fiche["format"] == "240 g"
    assert codebarres.fiche("3350030224462", lambda url, p: {"status": 0})["nom"] is None

    def panne(url, p):
        raise OSError("hors ligne")
    assert codebarres.fiche("3350030224462", panne) == {"code": "3350030224462", "nom": None, "marque": None,
                                                        "format": None, "image": None}
    demandes = []

    def recherche(url, p):
        demandes.append(p["q"])
        return {"hits": [{"code": "3350030224462", "product_name": "Pavés de saumon bio", "brands": ["Monoprix"]},
                         {"code": "123", "product_name": "code faux"}]} if "brands" not in p["q"] else {"hits": []}
    trouves = codebarres.propositions("Pavé de saumon", "Monoprix", recherche)
    assert [t["code"] for t in trouves] == ["3350030224462"]
    assert demandes == ['Pavé de saumon brands:"monoprix"', "Pavé de saumon"]  # la marque de l'enseigne d'abord
    assert codebarres.propositions("Pavé de saumon", "Monoprix") == []  # reseau coupe pendant les tests


def test_scanner_une_ligne_puis_le_meme_moins_cher_ailleurs(client, links):
    from app.db import SessionLocal

    connecter_admin(client, links)
    loc = client.post("/tickets", files={"fichier": PDF}, follow_redirects=False).headers["location"]
    rid = int(loc.split("/")[-1].split("?")[0])
    with SessionLocal() as s:
        item = s.query(ReceiptItem).filter_by(libelle="OIGNONS ROUGE 500G").one()
        iid = item.id
        s.add(OpenPrice(id=1, nom="Oignons rouges", code_barres=OIGNONS, prix=Decimal("0.79"), jour=date(2026, 10, 20),
                        magasin="LIDL", ville="Paris", lat=48.885, lon=2.38))
        s.add(OpenPrice(id=2, nom="Oignons rouges", code_barres=OIGNONS, prix=Decimal("1.20"), jour=date(2026, 10, 20),
                        magasin="FRANPRIX", ville="Paris", lat=48.885, lon=2.38))
        s.commit()

    page = client.get(f"/tickets/{rid}")
    assert f"/tickets/{rid}/code/{iid}" in page.text and "Le même" not in page.text
    assert "Scanner le code-barres du paquet" in client.get(f"/tickets/{rid}/code/{iid}").text

    r = client.post(f"/tickets/{rid}/code/{iid}", data={"code": "4061458000124"}, follow_redirects=False)
    assert "erreur=1" in r.headers["location"]  # faute de frappe : refuse
    r = client.post(f"/tickets/{rid}/code/{iid}", data={"code": OIGNONS}, follow_redirects=False)
    assert r.status_code == 303
    with SessionLocal() as s:
        alias = s.query(ProductAlias).filter_by(enseigne="Aldi", libelle="OIGNONS ROUGE 500G").one()
        assert alias.code_barres == OIGNONS

    page = client.get(f"/tickets/{rid}").text
    assert "Le même : 0,79" in page and "Lidl" in page and "Franprix" not in page  # seulement moins cher
    assert "Déjà connu" in client.get(f"/tickets/{rid}/code/{iid}").text


def test_ligne_d_un_autre_compte_introuvable(client, links):
    connecter_admin(client, links)
    assert client.get("/tickets/999/code/1").status_code == 404
