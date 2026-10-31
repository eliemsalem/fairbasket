from app import confiance, config, tickets
from app.models import Contribution, ProductAlias, ReceiptItem, User
from tests.test_auth import connecter_admin
from tests.test_stats import ticket
from tests.test_tickets import _article, db, nouvel_utilisateur  # noqa: F401

BEURRE = "250G BEUR 1/2-SEL"


def _nom(db, receipt):
    db.expire_all()
    return db.get(ReceiptItem, receipt.items[0].id).product.nom


def _alias(db):
    db.expire_all()
    return db.query(ProductAlias).filter_by(enseigne="Carrefour", libelle=BEURRE).one()


def _quatre(db):
    gens = [nouvel_utilisateur(db, f"{n}@x.fr") for n in "abcd"]
    recus = [ticket(db, u, i, "Carrefour", "2026-10-03", [_article(BEURRE, "Beurre 250 g", 2.65)])
             for i, u in enumerate(gens)]
    return gens, recus


def test_une_correction_s_applique_a_soi_et_l_emporte_sur_la_lecture(db):
    (a, b, c, d), (ra, rb, rc, rd) = _quatre(db)
    assert _alias(db).etat == "probable"
    tickets.renommer_produit(db, ra.items[0], "Beurre demi-sel 250 g", a)
    assert _nom(db, ra) == "Beurre demi-sel 250 g"
    assert _nom(db, rb) == "Beurre demi-sel 250 g"  # une personne (2) contre la lecture (1) : suivi par tous
    assert _alias(db).etat == "confirme"


def test_une_personne_seule_ne_defait_pas_ce_que_d_autres_ont_confirme(db):
    (a, b, c, d), (ra, rb, rc, rd) = _quatre(db)
    tickets.renommer_produit(db, ra.items[0], "Beurre demi-sel 250 g", a)
    tickets.renommer_produit(db, rb.items[0], "Margarine 250 g", b)
    assert _nom(db, rb) == "Margarine 250 g"  # son avis, pour ses tickets
    assert _nom(db, rc) == "Beurre demi-sel 250 g"  # les autres gardent la correspondance en place
    confiance.donner_avis(db, c, rc.items[0], produit=rc.items[0].product)
    db.commit()
    assert _alias(db).etat == "sur"  # deux personnes d'accord

    tickets.renommer_produit(db, rd.items[0], "Margarine 250 g", d)  # deux contre deux, l'en place garde 1 de plus
    assert _nom(db, ra) == "Beurre demi-sel 250 g" and _alias(db).product.nom == "Beurre demi-sel 250 g"


def test_deux_avis_l_emportent_et_chacun_garde_le_sien(db):
    (a, b, c, d), (ra, rb, rc, rd) = _quatre(db)
    tickets.renommer_produit(db, ra.items[0], "Beurre demi-sel 250 g", a)
    tickets.renommer_produit(db, rb.items[0], "Beurre doux 250 g", b)
    tickets.renommer_produit(db, rc.items[0], "Beurre doux 250 g", c)
    assert _alias(db).product.nom == "Beurre doux 250 g"
    assert _nom(db, rd) == "Beurre doux 250 g"  # sans avis : suit la correspondance commune
    assert _nom(db, ra) == "Beurre demi-sel 250 g"  # a garde le sien
    nouveau = ticket(db, a, 9, "Carrefour", "2026-10-10", [_article(BEURRE, "Beurre 250 g", 2.65)])
    assert _nom(db, nouveau) == "Beurre demi-sel 250 g"  # ses prochains tickets aussi


def test_qui_contredit_souvent_compte_moitie_moins(db):
    a, b = nouvel_utilisateur(db, "a@x.fr"), nouvel_utilisateur(db, "b@x.fr")
    for i in range(3):
        libelle = f"ARTICLE {i}"
        ra = ticket(db, a, 10 + i, "Carrefour", f"2026-10-0{i + 1}", [_article(libelle, f"Article {i}", 1.0)])
        rb = ticket(db, b, 20 + i, "Carrefour", f"2026-10-0{i + 1}", [_article(libelle, f"Article {i}", 1.0)])
        tickets.renommer_produit(db, ra.items[0], f"Bon article {i}", a)
        tickets.renommer_produit(db, rb.items[0], f"Mauvais article {i}", b)  # 2 contre 2 + 1 : perd
    assert confiance.fiabilite(db, a.id) == 1.0 and confiance.fiabilite(db, b.id) == 0.5


def test_l_administrateur_tranche(db, monkeypatch):
    (a, b, c, d), (ra, rb, rc, rd) = _quatre(db)
    tickets.renommer_produit(db, ra.items[0], "Beurre demi-sel 250 g", a)
    tickets.renommer_produit(db, rb.items[0], "Beurre demi-sel 250 g", b)
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"d@x.fr"})
    tickets.renommer_produit(db, rd.items[0], "Beurre doux 250 g", d)
    assert _alias(db).product.nom == "Beurre doux 250 g" and _alias(db).etat == "sur"


def test_scans_differents(db):
    (a, b, c, d), (ra, rb, rc, rd) = _quatre(db)
    alias = confiance.donner_avis(db, a, ra.items[0], code="3560071599362")
    alias.nom_exact = "Beurre demi-sel Carrefour"
    db.commit()
    assert _alias(db).code_barres == "3560071599362"
    confiance.donner_avis(db, b, rb.items[0], code="3270190025801")  # 5 contre 5 + 1 : le premier reste
    assert _alias(db).code_barres == "3560071599362" and _alias(db).nom_exact == "Beurre demi-sel Carrefour"
    confiance.donner_avis(db, c, rc.items[0], code="3270190025801")
    db.commit()
    assert _alias(db).code_barres == "3270190025801" and _alias(db).nom_exact is None  # fiche a reprendre


def test_une_question_par_ticket_puis_merci(client, links):
    from app.db import SessionLocal

    connecter_admin(client, links)
    with SessionLocal() as s:
        u = s.query(User).first()
        r = ticket(s, u, 1, "Carrefour", "2026-10-03", [_article("LAIT 1L", "Lait 1 L", 1.10),
                                                        _article(BEURRE, "Beurre demi-sel 250 g", 2.65)])
        rid, iid, lait = r.id, r.items[1].id, r.items[0].id
    page = client.get(f"/tickets/{rid}").text
    assert "Une petite vérification" in page and f"/tickets/{rid}/confirmer/{iid}" in page  # la plus chere d'abord
    assert f"?corriger={iid}" in page
    assert '<details class="renommer" open>' in client.get(f"/tickets/{rid}?corriger={iid}").text

    r = client.post(f"/tickets/{rid}/confirmer/{iid}", follow_redirects=False)
    assert r.headers["location"].startswith(f"/tickets/{rid}?merci=1")
    page = client.get(r.headers["location"]).text
    assert "Merci !" in page and f"/tickets/{rid}/confirmer/{lait}" in page  # puis la suivante
    with SessionLocal() as s:
        assert s.query(ProductAlias).filter_by(libelle=BEURRE).one().etat == "sur"  # avis de l'administrateur
        assert s.query(Contribution).count() == 1
    assert "Merci pour votre correction" in client.get("/profil").text


def test_corrections_utiles_aux_autres_et_effacees_avec_le_compte(db):
    (a, b, c, d), (ra, rb, rc, rd) = _quatre(db)
    tickets.renommer_produit(db, ra.items[0], "Beurre demi-sel 250 g", a)
    assert confiance.aides(db, a) == {"avis": 1, "personnes": 3}
    assert confiance.aides(db, b) == {"avis": 0, "personnes": 0}
    db.delete(db.get(User, a.id))
    db.commit()
    assert db.query(Contribution).count() == 0
    assert _alias(db).product.nom == "Beurre demi-sel 250 g"  # la correspondance commune reste, sans lien avec a
