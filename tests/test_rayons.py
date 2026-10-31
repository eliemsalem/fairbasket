from app import codebarres, rayons, sante
from app.models import Product, ProductAlias
from tests.test_stats import ticket
from tests.test_tickets import _article, db, nouvel_utilisateur  # noqa: F401


def test_produit_type_d_apres_le_nom():
    assert rayons.type_de("Beurre demi-sel 250 g") == ("en:half-salted-butter", "Beurres demi-sel")
    assert rayons.type_de("Œufs bio ×6")[0] == "en:eggs"
    assert rayons.type_de("Bananes vrac")[0] == rayons.type_de("Banane bio Fairtrade")[0] == "en:bananas"
    assert rayons.type_de("Lait UHT demi-écrémé bio")[0] == "en:semi-skimmed-milks"  # « UHT » intercale
    assert rayons.type_de("Tofu bio aux tomates séchées")[0] == "en:tofu"  # le mot principal d'abord
    assert rayons.type_de("Pâtes bio spirales complètes 500 g")[0] != "en:pate"  # pâtes ≠ pâté
    assert rayons.type_de("Liquide vaisselle") is None and rayons.type_de("") is None


def test_rayon_exact_d_un_article_scanne():
    assert rayons.type_des_categories(["en:butters", "en:half-salted-butter", "en:inconnu"])[0] == "en:half-salted-butter"
    assert rayons.type_des_categories([]) is None


def test_chaque_nouveau_produit_a_son_type_et_les_anciens_sont_completes(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("250G BEUR 1/2-SEL", "Beurre demi-sel 250 g", 2.65),
                                                 _article("LIQ VAISSELLE", "Liquide vaisselle", 1.95)])
    beurre = db.query(Product).filter_by(nom="Beurre demi-sel 250 g").one()
    assert beurre.type_nom == "Beurres demi-sel"
    assert db.query(Product).filter_by(nom="Liquide vaisselle").one().type_off == ""  # cherche, rien : pas a refaire
    beurre.type_off = beurre.type_nom = None
    db.commit()
    assert rayons.completer(db) == 1 and beurre.type_off == "en:half-salted-butter"


def test_le_scan_donne_le_rayon_exact_quand_le_nom_n_a_rien_donne(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    r = ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("PLQ BRETONNE", "Plaquette bretonne", 2.65)])
    produit = r.items[0].product
    assert produit.type_off == ""
    alias = db.query(ProductAlias).one()
    alias.code_barres = "3560071599362"
    db.commit()
    fiche = {"status": 1, "product": {"nutriscore_grade": "e", "categories_tags": ["en:butters",
                                                                                  "en:half-salted-butter"]}}
    sante.completer(db, alias, lambda url, params: fiche if "product" in url else {"hits": [], "count": 0})
    assert produit.type_nom == "Beurres demi-sel"


def test_propositions_d_abord_dans_le_produit_type():
    demandes = []

    def recherche(url, p):
        demandes.append(p["q"])
        return {"hits": [{"code": "3560071599362", "product_name": "Beurre demi-sel", "brands": "Carrefour"}]}
    codebarres.propositions("Beurre demi-sel", "Carrefour", recherche, type_off="en:half-salted-butter")
    assert demandes == ['Beurre demi-sel categories_tags:"en:half-salted-butter" brands:"carrefour"']


def test_comparer_le_meme_produit_type_d_une_enseigne_a_l_autre(db):
    from app import assistant, stats

    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("250G BEUR 1/2-SEL", "Beurre demi-sel 250 g", 2.65),
                                                 _article("6 OEUFS BIO", "Œufs bio ×6", 3.10)])
    ticket(db, u, 2, "Monoprix", "2026-10-10", [_article("PAYSAN BRETON BEUR", "Beurre demi-sel Paysan Breton 250 g",
                                                         2.99),
                                                _article("6 OEUFS", "Œufs ×6", 2.10)])
    c = stats.comparaisons(db, u)
    beurre = next(p for p in c["produits"] if p["nom"] == "Beurres demi-sel")
    assert beurre["melange"] and beurre["unite"] == "kg" and len(beurre["ids"]) == 2
    assert [(l["enseigne"], str(l["prix"]), l["nom"]) for l in beurre["lignes"]] == [
        ("Carrefour", "10.60", "Beurre demi-sel"), ("Monoprix", "11.96", "Beurre demi-sel Paysan Breton")]
    assert not any(p["nom"].startswith("Œufs") for p in c["produits"])  # bio et pas bio : pas comparables
    assert stats.comparaisons(db, u, "paysan breton")["produits"][0]["nom"] == "Beurres demi-sel"
    offres = assistant.chercher_prix(db, u, None, "beurre demi-sel")["offres"]
    assert {o["produit"] for o in offres if o["source"] == "tickets"} == {"Beurre demi-sel",
                                                                          "Beurre demi-sel Paysan Breton"}


def test_bilan_moins_cher_ailleurs_avec_un_article_semblable(db):
    from app import stats

    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("250G BEUR 1/2-SEL", "Beurre demi-sel 250 g", 2.65)])
    r = ticket(db, u, 2, "Monoprix", "2026-10-10", [_article("PAYSAN BRETON BEUR",
                                                             "Beurre demi-sel Paysan Breton 250 g", 2.99)])
    b = stats.bilan_ticket(db, u, r)
    assert b["compares"] == 0  # pas le meme article : pas de « payé plus que la dernière fois »
    assert b["ailleurs"][0]["ailleurs_enseigne"] == "Carrefour"
    assert b["ailleurs"][0]["ailleurs_produit"] == "Beurre demi-sel" and str(b["ailleurs_total"]) == "0.34"


def test_page_comparer_dit_quel_article_est_compare(client, links):
    from app.db import SessionLocal
    from app.models import User
    from tests.test_auth import connecter_admin

    connecter_admin(client, links)
    with SessionLocal() as s:
        u = s.query(User).first()
        ticket(s, u, 1, "Carrefour", "2026-10-03", [_article("250G BEUR 1/2-SEL", "Beurre demi-sel 250 g", 2.65)])
        r = ticket(s, u, 2, "Monoprix", "2026-10-10", [_article("PAYSAN BRETON BEUR",
                                                                "Beurre demi-sel Paysan Breton 250 g", 2.99)])
        rid, pid = r.id, r.items[0].product_id
    page = client.get("/comparer?onglet=moi").text
    assert "Beurres demi-sel" in page and "Articles semblables" in page and "Beurre demi-sel Paysan Breton" in page
    assert f"#p{pid}" in page  # chaque prix mene a la bonne ligne de son ticket
    assert "(Beurre demi-sel)" in client.get(f"/tickets/{rid}").text  # bilan : moins cher ailleurs, et lequel


def test_un_rayon_trop_large_ne_melange_pas_des_articles_differents(db):
    from app import stats

    assert rayons.precis("en:eggs") and not rayons.precis("en:beers") and not rayons.precis("en:fruits")
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("50CL HEINEKEN", "Bière Heineken 50 cl", 1.45)])
    ticket(db, u, 2, "Monoprix", "2026-10-10", [_article("50C GOUDALE BTE", "Bière Goudale 50 cl", 1.85)])
    assert all(p["seul"] for p in stats.comparaisons(db, u, "bière")["produits"])
