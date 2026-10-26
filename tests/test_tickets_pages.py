import pytest

from app import config, tickets
from app.lecture import Lecture
from tests.test_auth import chemin, connecter_admin, inscrire
from tests.test_tickets import ALDI

PDF = ("ticket.pdf", b"%PDF-1.4 faux", "application/pdf")


@pytest.fixture(autouse=True)
def sans_ia(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    lu = {"donnees": ALDI}
    monkeypatch.setattr(tickets, "lire_ticket",
                        lambda data, mt: Lecture(donnees=lu["donnees"], modele="test", tokens_entree=1, tokens_sortie=1))
    return lu


def test_ajout_puis_affichage(client, links):
    connecter_admin(client, links)
    r = client.post("/tickets", files={"fichier": PDF}, follow_redirects=False)
    assert r.status_code == 303
    page = client.get(r.headers["location"])
    assert "Total vérifié" in page.text and "OIGNONS ROUGE 500G" in page.text
    assert "Aldi" in client.get("/accueil").text


def test_doublon_signale(client, links):
    connecter_admin(client, links)
    client.post("/tickets", files={"fichier": PDF})
    r = client.post("/tickets", files={"fichier": PDF})
    assert "déjà enregistré" in r.text


def test_correction_d_un_ecart(client, links, sans_ia):
    sans_ia["donnees"] = {**ALDI, "articles": ALDI["articles"][:2]}  # il manque 8,73 €
    connecter_admin(client, links)
    loc = client.post("/tickets", files={"fichier": PDF}, follow_redirects=False).headers["location"]
    page = client.get(loc)
    assert "Écart" in page.text and 'value="8,73"' in page.text  # montant manquant pre-rempli
    client.post(loc + "/corriger", data={"libelle_new": "CELERI BRANCHE", "montant_new": "8,73"})
    assert "Total vérifié" in client.get(loc).text


def test_format_refuse(client, links):
    connecter_admin(client, links)
    r = client.post("/tickets", files={"fichier": ("a.txt", b"bonjour", "text/plain")})
    assert r.status_code == 400 and "Format non pris en charge" in r.text


def test_ticket_d_un_autre_invisible(client, links):
    connecter_admin(client, links)
    loc = client.post("/tickets", files={"fichier": PDF}, follow_redirects=False).headers["location"]
    client.post("/deconnexion")
    # deuxieme compte, accepte par l'admin puis connecte
    inscrire(client, "marie@exemple.fr")
    connecter_admin(client, links)
    client.post("/admin/activer/2")
    client.post("/deconnexion")
    client.get(chemin(links["marie@exemple.fr"][-1]))
    assert client.get(loc).status_code == 404
    assert client.post(loc + "/supprimer").status_code == 404


def test_suppression(client, links, tmp_path):
    connecter_admin(client, links)
    loc = client.post("/tickets", files={"fichier": PDF}, follow_redirects=False).headers["location"]
    assert any(tmp_path.rglob("*.pdf"))
    client.post(loc + "/supprimer")
    assert client.get(loc).status_code == 404
    assert not any(tmp_path.rglob("*.pdf"))  # l'original est supprime aussi


def test_ajout_sans_connexion(client):
    r = client.post("/tickets", files={"fichier": PDF}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"


def test_changer_de_magasin(client, links, sans_ia):
    sans_ia["donnees"] = {**ALDI, "enseigne": "Inconnue", "magasin": "Inconnue"}
    connecter_admin(client, links)
    loc = client.post("/tickets", files={"fichier": PDF}, follow_redirects=False).headers["location"]
    assert "Magasin inconnu" in client.get(loc).text
    client.post(loc + "/magasin", data={"enseigne": "monoprix", "magasin": "Crimée"})
    page = client.get(loc).text
    assert "Monoprix" in page and "Magasin inconnu" not in page
    assert "Changer de magasin" in page


def test_import_reserve_a_l_admin(client, links):
    from app.db import SessionLocal
    from app.models import Receipt
    connecter_admin(client, links)
    assert client.get("/tickets/importer").status_code == 200
    client.post("/tickets", files={"fichier": PDF}, data={"importe": "1"})
    assert SessionLocal().query(Receipt).one().importe is True
    client.post("/deconnexion")
    inscrire(client, "marie@exemple.fr")
    connecter_admin(client, links)
    client.post("/admin/activer/2")
    client.post("/deconnexion")
    client.get(chemin(links["marie@exemple.fr"][-1]))
    assert client.get("/tickets/importer").status_code == 404
    client.post("/tickets", files={"fichier": ("b.pdf", b"autre", "application/pdf")}, data={"importe": "1"})
    s = SessionLocal()
    assert s.query(Receipt).filter(Receipt.importe.is_(False)).count() == 1  # marie ne peut pas contourner le quota
