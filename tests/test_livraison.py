from app import stats
from app.lecture import SCHEMA
from app.models import SharedPrice
from app.tickets import enregistrer_ticket
from tests.test_stats import ticket
from tests.test_tickets import ALDI, _article, db, fausse_lecture, nouvel_utilisateur  # noqa: F401

# facture Uber Eats : 27,51 € d'articles + 9,48 € de frais - 5,29 € de remises = 31,70 € payes
UBER = {**ALDI, "enseigne": "La Belle Vie", "magasin": "La Belle Vie (Paris)", "adresse": None, "code_postal": None,
        "date": "2026-10-30", "heure": "18:40", "total": 31.70, "remises_globales": 5.29, "frais": 9.48,
        "canal": "livraison", "plateforme": "Uber Eats",
        "articles": [_article("Heineken - Bière blonde, original (500ml)", "Bière Heineken 50 cl ×2", 3.44),
                     _article("Melitta - Filtres à café (40)", "Filtres à café ×40", 1.59),
                     _article("Eléphant - Infusion bio thé détox (34g)", "Infusion bio thé détox 34 g", 2.68),
                     _article("Avril - Huile démaquillante bio (200ml)", "Huile démaquillante bio 200 ml", 13.20),
                     _article("Avril cosmétique - Gant nettoyant en coton bio", "Gant nettoyant coton bio", 6.60)]}


def test_la_lecture_demande_frais_et_canal():
    assert {"frais", "canal", "plateforme"} <= set(SCHEMA["required"])


def test_commande_livree_juste_avec_ses_frais_et_jamais_partagee(db):
    u = nouvel_utilisateur(db, "a@x.fr", partage=True)
    r = enregistrer_ticket(db, u, b"uber", "facture.pdf", "application/pdf", lire=fausse_lecture(UBER)).receipt
    assert r.statut == "ok" and str(r.frais) == "9.48" and r.canal == "livraison" and r.plateforme == "Uber Eats"
    assert db.query(SharedPrice).count() == 0  # prix de la plateforme : pas ceux du magasin


def test_une_livraison_ne_sert_pas_de_prix_en_magasin(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Monoprix", "2026-10-03", [_article("PAYSAN BRETON BEUR", "Beurre demi-sel 250 g", 2.65)])
    livre = {**UBER, "enseigne": "Monoprix", "magasin": "Monoprix", "total": 3.99 + 9.48 - 5.29,
             "articles": [_article("Paysan Breton - Beurre demi-sel (250g)", "Beurre demi-sel 250 g", 3.99)]}
    r = enregistrer_ticket(db, u, b"uber2", "f.pdf", "application/pdf", lire=fausse_lecture(livre)).receipt
    ticket(db, u, 3, "Carrefour", "2026-10-20", [_article("250G BEUR 1/2-SEL", "Beurre demi-sel 250 g", 2.79)])

    lignes = stats.comparaisons(db, u)["produits"][0]["lignes"]
    assert [(l["enseigne"], str(l["prix"])) for l in lignes] == [("Monoprix", "10.60"), ("Carrefour", "11.16")]
    b = stats.bilan_ticket(db, u, r)
    assert b["livraison"] and b["ailleurs"][0]["ailleurs_enseigne"] == "Monoprix"  # meme enseigne, en magasin


def test_page_du_ticket_livre(client, links):
    from app.db import SessionLocal
    from app.models import User
    from tests.test_auth import connecter_admin

    connecter_admin(client, links)
    with SessionLocal() as s:
        u = s.query(User).first()
        rid = enregistrer_ticket(s, u, b"uber", "f.pdf", "application/pdf", lire=fausse_lecture(UBER)).receipt.id
    page = client.get(f"/tickets/{rid}").text
    assert "Commande livrée · Uber Eats" in page and "Frais (livraison, service…)" in page and "9,48" in page
    assert "Écart" not in page
