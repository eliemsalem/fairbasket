from app.db import SessionLocal
from app.models import Avis, Evenement
from tests.test_auth import connecter_admin


def evenements():
    with SessionLocal() as db:
        return [(e.type, e.page, e.detail) for e in db.query(Evenement).order_by(Evenement.id)]


def test_pages_et_tickets_suivis(client, links):
    connecter_admin(client, links)
    client.get("/accueil")
    client.get("/comparer?q=saumon&fragment=1")  # recherche pendant la frappe : pas notee
    client.get("/static/style.css")
    client.post("/tickets", files={"fichier": ("t.txt", b"bonjour", "text/plain")})  # format refuse
    ev = evenements()
    pages = [p for t, p, _ in ev if t == "page"]
    assert "/accueil" in pages and "/comparer" not in pages and not any("static" in p for p in pages)
    assert ("connexion", "/connexion", "lien envoyé") in ev
    assert any(t == "ticket_refuse" and "Format non pris en charge" in d for t, _, d in ev)
    assert not any("saumon" in (d or "") or "saumon" in (p or "") for _, p, d in ev)  # jamais la recherche

    r = client.get("/admin")
    assert r.status_code == 200 and "Où les gens s'arrêtent" in r.text and "Format non pris en charge" in r.text
    assert "Accueil" in r.text  # derniere page, en clair


def test_avis(client, links):
    assert "Écrivez" in client.post("/avis", data={"message": " ", "de": "/connexion"}).text
    client.post("/avis", data={"message": "Je ne reçois pas le lien", "de": "/connexion", "email": "x@y.fr",
                               "retour": "https://ailleurs.com"})
    connecter_admin(client, links)
    r = client.post("/avis", data={"message": "La liste est top", "de": "/liste", "retour": "/liste"},
                    follow_redirects=False)
    assert r.headers["location"] == "/avis?merci=1&retour=/liste"
    page = client.get("/admin").text
    assert "[x@y.fr] Je ne reçois pas le lien" in page and "La liste est top" in page and "non connecté" in page
    with SessionLocal() as db:
        a = db.query(Avis).first()
    client.post(f"/admin/avis/{a.id}/traite")
    with SessionLocal() as db:
        assert db.get(Avis, a.id).traite


def test_fiche_et_suppression(client, links):
    connecter_admin(client, links)
    client.get("/liste")
    with SessionLocal() as db:
        uid = db.query(Evenement).filter(Evenement.user_id.isnot(None)).first().user_id
    r = client.get(f"/admin/utilisateurs/{uid}")
    assert r.status_code == 200 and "Son parcours" in r.text and "Liste" in r.text
    client.post("/profil/supprimer", data={"confirmation": "SUPPRIMER"})
    with SessionLocal() as db:
        assert db.query(Evenement).filter(Evenement.user_id == uid).count() == 0  # parti avec le compte


def test_admin_reserve(client, links):
    from tests.test_auth import inscrire
    assert client.get("/admin", follow_redirects=False).status_code in (303, 401, 403)
