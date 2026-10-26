from datetime import date

from app.stats import tableau_de_bord
from app.tickets import enregistrer_ticket
from tests.test_tickets import ALDI, _article, db, fausse_lecture, nouvel_utilisateur  # noqa: F401

AUJ = date(2026, 10, 26)


def ticket(db, u, n, enseigne, jour, articles):
    d = {**ALDI, "enseigne": enseigne, "magasin": enseigne.upper(), "date": jour, "heure": "12:00",
         "total": sum(a["montant"] for a in articles), "articles": articles}
    return enregistrer_ticket(db, u, str(n).encode(), "t.pdf", "application/pdf", lire=fausse_lecture(d)).receipt


def test_totaux_et_evolution(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("A", "Œufs bio ×6", 10.0)])
    ticket(db, u, 2, "Monoprix", "2026-10-12", [_article("B", "Kéfir 1 L", 30.0)])
    ticket(db, u, 3, "Carrefour", "2026-09-20", [_article("C", "Kéfir 1 L", 20.0)])
    ticket(db, u, 4, "Carrefour", "2025-01-10", [_article("D", "Pain", 5.0)])  # hors des 12 mois

    mois = tableau_de_bord(db, u, "mois", AUJ)
    assert float(mois.total) == 40.0 and mois.nb_tickets == 2 and float(mois.panier_moyen) == 20.0
    assert mois.evolution == 100  # 40 € contre 20 € en septembre

    an = tableau_de_bord(db, u, "an", AUJ)
    assert float(an.total) == 60.0 and an.nb_tickets == 3
    assert len(an.mois) == 12 and an.mois[-1]["courant"] and float(an.mois[-1]["valeur"]) == 40.0
    assert an.enseignes[0]["nom"] == "Carrefour" and an.enseignes[0]["part"] == 50
    assert an.produits[0]["nom"] == "Kéfir 1 L" and an.produits[0]["achats"] == 2


def test_alerte_moins_cher_ailleurs(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("X6 OEUFS CRF BIO", "Œufs bio ×6", 2.49)])
    ticket(db, u, 2, "Biocoop", "2026-10-15", [_article("OEUFS BIOCOOP 6", "Œufs bio ×6", 2.82)])
    a = tableau_de_bord(db, u, "an", AUJ).alertes
    assert len(a) == 1 and a[0]["enseigne"] == "Carrefour" and a[0]["habituelle"] == "Biocoop"


def test_pas_d_alerte_si_deja_le_moins_cher(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Biocoop", "2026-10-03", [_article("O", "Œufs bio ×6", 2.82)])
    ticket(db, u, 2, "Carrefour", "2026-10-15", [_article("X", "Œufs bio ×6", 2.49)])
    assert tableau_de_bord(db, u, "an", AUJ).alertes == []


def test_seulement_ses_tickets(db):
    a, b = nouvel_utilisateur(db, "a@x.fr"), nouvel_utilisateur(db, "b@x.fr")
    ticket(db, a, 1, "Carrefour", "2026-10-03", [_article("A", "Pain", 10.0)])
    assert tableau_de_bord(db, b, "an", AUJ).nb_tickets == 0


def test_comparaisons(db):
    from app.stats import comparaisons
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Biocoop", "2026-10-03", [_article("O", "Œufs bio ×6", 2.82), _article("K", "Kéfir 1 L", 2.65)])
    ticket(db, u, 2, "Carrefour", "2026-10-15", [_article("X", "Œufs bio ×6", 2.49)])
    c = comparaisons(db, u)
    assert [p["nom"] for p in c["produits"]] == ["Œufs bio ×6"]  # le kéfir n'est que chez Biocoop
    assert c["produits"][0]["lignes"][0]["enseigne"] == "Carrefour" and c["meilleure"] == ("Carrefour", 1)
    assert comparaisons(db, u, "oeufs")["produits"] and not comparaisons(db, u, "saumon")["produits"]


def test_communaute_anonyme(db):
    from app.stats import communaute
    a = nouvel_utilisateur(db, "a@x.fr", partage=True)
    b = nouvel_utilisateur(db, "b@x.fr", partage=True)
    ticket(db, a, 1, "Biocoop", date.today().isoformat(), [_article("O", "Œufs bio ×6", 2.82)])
    ticket(db, a, 2, "Carrefour", date.today().isoformat(), [_article("X", "Œufs bio ×6", 2.49)])
    ticket(db, b, 3, "Biocoop", date.today().isoformat(), [_article("O", "Œufs bio ×6", 2.90)])
    res = communaute(db, b, "")
    assert res and res[0]["lignes"][0]["enseigne"] == "Carrefour"  # b voit le prix partagé par a
