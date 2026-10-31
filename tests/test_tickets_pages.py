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


def test_page_adresse_et_photos(client, links, monkeypatch):
    from app import tickets
    from app.lecture import Lecture
    from tests.test_tickets import ALDI
    from tests.test_auth import connecter_admin
    connecter_admin(client, links)
    sans = {**ALDI, "adresse": None, "code_postal": None, "ville": None}
    vus = []

    def lire(data, media_type, suite=()):
        vus.append(1 + len(suite))
        return Lecture(donnees=sans, modele="t", tokens_entree=1, tokens_sortie=1)
    monkeypatch.setattr(tickets, "lire_ticket", lire)
    monkeypatch.setattr(tickets, "photos_assemblees", lambda photos: b"assemblees")
    r = client.post("/tickets", files=[("fichier", ("a.jpg", b"haut", "image/jpeg")),
                                       ("fichier", ("b.jpg", b"bas", "image/jpeg"))], data={"meme_ticket": "1"})
    assert vus == [2] and "Adresse du magasin inconnue" in r.text
    numero = r.url.path.rsplit("/", 1)[1]
    r = client.post(f"/tickets/{numero}/adresse", data={"adresse": "85 rue de Meaux", "code_postal": "75019",
                                                         "ville": "Paris"})
    assert "85 rue de Meaux, 75019 Paris" in r.text


def test_renommer_un_produit(client, links, monkeypatch, tmp_path):
    """« Ce n'est pas le meme produit » : la ligne, ses semblables et les prochains tickets changent de nom."""
    from app import tickets
    from app.db import SessionLocal
    from app.models import ProductAlias, ReceiptItem
    from tests.test_auth import connecter_admin
    from tests.test_stats import ticket
    from tests.test_tickets import _article
    connecter_admin(client, links)
    with SessionLocal() as db:
        from app.models import User
        u = db.query(User).first()
        r1 = ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("BQ P SAUM AP FQC", "Pavé de saumon", 6.59)])
        r2 = ticket(db, u, 2, "Carrefour", "2026-10-04", [_article("BQ P SAUM AP FQC", "Pavé de saumon", 6.59),
                                                          _article("PAVE SAUMON", "Pavé de saumon", 9.99)])
        item, rid, rid2 = r1.items[0].id, r1.id, r2.id
    assert "Corriger" in client.get(f"/tickets/{rid}").text
    r = client.post(f"/tickets/{rid}/produit/{item}", data={"nom": "Pavé de saumon Filière Qualité",
                                                            "retour": "/comparer?q=saumon"}, follow_redirects=False)
    assert r.headers["location"].startswith(f"/tickets/{rid}?retour=/comparer%3Fq%3Dsaumon#p")
    with SessionLocal() as db:
        noms = {(i.libelle, i.product.nom) for i in db.query(ReceiptItem).filter(ReceiptItem.receipt_id.in_([rid, rid2]))}
        assert noms == {("BQ P SAUM AP FQC", "Pavé de saumon Filière Qualité"), ("PAVE SAUMON", "Pavé de saumon")}
        alias = db.query(ProductAlias).filter_by(enseigne="Carrefour", libelle="BQ P SAUM AP FQC").one()
        assert alias.product.nom == "Pavé de saumon Filière Qualité"  # retenu pour les prochains tickets


def test_bio_en_un_geste(client, links):
    from app.db import SessionLocal
    from app.models import ReceiptItem, User
    from tests.test_auth import connecter_admin
    from tests.test_stats import ticket
    from tests.test_tickets import _article
    connecter_admin(client, links)
    with SessionLocal() as db:
        u = db.query(User).first()
        r = ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("PAVE SAUMON", "Pavé de saumon", 9.99)])
        rid, item = r.id, r.items[0].id
    assert 'aria-pressed="false"' in client.get(f"/tickets/{rid}").text
    client.post(f"/tickets/{rid}/bio/{item}")
    page = client.get(f"/tickets/{rid}").text
    assert 'class="row bio"' in page and 'aria-pressed="true"' in page and "Pavé de saumon bio" in page
    client.post(f"/tickets/{rid}/bio/{item}")  # et retour en arriere
    with SessionLocal() as db:
        assert db.get(ReceiptItem, item).product.nom == "Pavé de saumon"


def test_changer_le_rayon(client, links):
    from app.db import SessionLocal
    from app.models import ReceiptItem, User
    from tests.test_auth import connecter_admin
    from tests.test_stats import ticket
    from tests.test_tickets import _article
    connecter_admin(client, links)
    with SessionLocal() as db:
        u = db.query(User).first()
        r = ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("PAVE SAUMON", "Pavé de saumon", 9.99)])
        rid, item = r.id, r.items[0].id
    client.post(f"/tickets/{rid}/rayon/{item}", data={"categorie": "Viandes et poissons"})
    client.post(f"/tickets/{rid}/rayon/{item}", data={"categorie": "n'importe quoi"})  # ignore
    with SessionLocal() as db:
        assert db.get(ReceiptItem, item).product.categorie == "Viandes et poissons"
    page = client.get("/rayon?nom=Viandes%20et%20poissons").text
    assert "Pavé de saumon" in page and "9,99" in page
    assert client.get("/rayon?nom=inconnu", follow_redirects=False).status_code == 303
    assert "/rayon?nom=Viandes%20et%20poissons" in client.get("/accueil").text
