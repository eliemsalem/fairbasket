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
