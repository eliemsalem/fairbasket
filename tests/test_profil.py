from app.models import Receipt, SharedPrice, User
from tests.test_auth import connecter_admin
from tests.test_tickets_pages import PDF, sans_ia  # noqa: F401


def test_export_csv(client, links):
    connecter_admin(client, links)
    client.post("/tickets", files={"fichier": PDF})
    r = client.get("/profil/export.csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    lignes = r.content.decode("utf-8-sig").splitlines()
    assert lignes[0].startswith("date;heure;enseigne") and len(lignes) == 4  # en-tete + 3 articles
    assert "OIGNONS ROUGE 500G" in lignes[1] and "0,95" in lignes[1]


def test_retirer_le_partage(client, links):
    from app.db import SessionLocal
    connecter_admin(client, links)
    client.post("/profil/partage", data={"partage": "1"})
    client.post("/profil/partage", data={})
    s = SessionLocal()
    assert s.query(User).one().partage_consent is False


def test_suppression_du_compte(client, links, tmp_path):
    from app.db import SessionLocal
    connecter_admin(client, links)
    client.post("/profil/partage", data={"partage": "1"})
    client.post("/tickets", files={"fichier": PDF})
    assert client.post("/profil/supprimer", data={"confirmation": "non"}, follow_redirects=False).headers["location"] == "/profil?erreur=confirmation"
    r = client.post("/profil/supprimer", data={"confirmation": "SUPPRIMER"}, follow_redirects=False)
    assert r.headers["location"] == "/?supprime=1"
    s = SessionLocal()
    assert s.query(User).count() == 0 and s.query(Receipt).count() == 0
    assert s.query(SharedPrice).count() == 3  # prix anonymes conserves
    assert not any(tmp_path.rglob("*.pdf"))
    assert client.get("/accueil", follow_redirects=False).status_code == 303  # session terminee
