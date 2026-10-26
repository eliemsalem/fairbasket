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


def test_recherche_intelligente(db):
    from app.stats import comparaisons
    u = nouvel_utilisateur(db, "a@x.fr")
    art = lambda lib, nom, fam, prix: {**_article(lib, nom, prix), "famille": fam}  # noqa: E731
    ticket(db, u, 1, "Carrefour", "2026-10-03", [art("PAVE SAUM", "Pavé de saumon", "poisson", 9.99)])
    ticket(db, u, 2, "Monoprix", "2026-10-10", [art("PAVE SAUM MPX", "Pavé de saumon", "poisson", 10.47),
                                                art("LIMANDE", "Limande meunière", "poisson", 3.79)])
    assert [p["nom"] for p in comparaisons(db, u, "saumo")["produits"]] == ["Pavé de saumon"]
    poisson = comparaisons(db, u, "poisson")["produits"]
    assert {p["nom"] for p in poisson} == {"Pavé de saumon", "Limande meunière"}
    assert next(p for p in poisson if p["nom"] == "Limande meunière")["seul"]  # une seule enseigne : montrée
    assert comparaisons(db, u, "")["suggestions"] == ["poisson"]


def test_recherche_pendant_la_frappe(client, links):
    from tests.test_auth import connecter_admin
    connecter_admin(client, links)
    r = client.get("/comparer?onglet=moi&q=saumon&fragment=1")
    assert r.status_code == 200 and "<main" not in r.text  # seulement les resultats


def test_lien_vers_le_ticket(db):
    from app.stats import comparaisons
    u = nouvel_utilisateur(db, "a@x.fr")
    t1 = ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("X", "Œufs bio ×6", 2.49)])
    t2 = ticket(db, u, 2, "Biocoop", "2026-10-10", [_article("O", "Œufs bio ×6", 2.82)])
    lignes = comparaisons(db, u, "oeufs")["produits"][0]["lignes"]
    assert {l["enseigne"]: l["ticket"] for l in lignes} == {"Carrefour": t1.id, "Biocoop": t2.id}


def test_retour_depuis_le_ticket(client, links):
    from tests.test_auth import connecter_admin
    from tests.test_tickets_pages import PDF
    from app import config, tickets
    from app.lecture import Lecture
    from tests.test_tickets import ALDI
    import pytest
    mp = pytest.MonkeyPatch()
    mp.setattr(tickets, "lire_ticket", lambda d, m: Lecture(donnees=ALDI, modele="t", tokens_entree=1, tokens_sortie=1))
    connecter_admin(client, links)
    loc = client.post("/tickets", files={"fichier": PDF}, follow_redirects=False).headers["location"]
    page = client.get(loc + "?retour=/comparer%3Fonglet%3Dmoi%26q%3Doeuf").text
    assert 'href="/comparer?onglet=moi&amp;q=oeuf"' in page
    assert 'href="/accueil"' in client.get(loc + "?retour=https://exemple.com").text  # jamais une autre adresse
    mp.undo()
