from app import liste
from app.models import ShoppingItem
from tests.test_stats import ticket
from tests.test_tickets import _article, db, nouvel_utilisateur  # noqa: F401


def test_liste_prix_et_magasin(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    # Monoprix (et pas Biocoop, ou tout est bio : le kefir y serait un autre produit)
    ticket(db, u, 1, "Monoprix", "2026-10-03", [_article("O", "Œufs bio ×6", 2.82), _article("K", "Kéfir 1 L", 2.65)])
    ticket(db, u, 2, "Carrefour", "2026-10-15", [_article("X", "Œufs bio ×6", 2.49), _article("K2", "Kéfir 1 L", 2.85)])
    liste.ajouter(db, u, "oeufs")          # retrouve « Œufs bio ×6 »
    liste.ajouter(db, u, "kéfir 1 l")
    liste.ajouter(db, u, "dentifrice")     # jamais acheté : sans prix
    db.refresh(u)
    v = liste.vue(db, u)
    assert [l["item"].nom for l in v["lignes"]] == ["Œufs bio ×6", "Kéfir 1 L", "Dentifrice"]
    assert v["lignes"][0]["enseigne"] == "Carrefour" and v["lignes"][1]["enseigne"] == "Monoprix"
    assert str(v["total"]) == "5.14"
    assert dict(v["magasins"]) == {"Carrefour": 1, "Monoprix": 1}
    assert v["suggestions"] == []  # les deux produits achetés 2 fois sont déjà dans la liste


def test_suggestions(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("A", "Avocat bio", 1.69)])
    ticket(db, u, 2, "Carrefour", "2026-10-10", [_article("A", "Avocat bio", 1.69)])
    db.refresh(u)
    assert [s["nom"] for s in liste.vue(db, u)["suggestions"]] == ["Avocat bio"]


def test_pages_liste(client, links):
    from tests.test_auth import connecter_admin
    connecter_admin(client, links)
    client.post("/liste", data={"nom": "pain"})
    page = client.get("/liste").text
    assert "Pain" in page
    from app.db import SessionLocal
    item = SessionLocal().query(ShoppingItem).one()
    client.post(f"/liste/{item.id}/cocher")
    client.post("/liste/vider")
    assert SessionLocal().query(ShoppingItem).count() == 0
