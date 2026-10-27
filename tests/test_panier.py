from datetime import date

from app import openprices
from app.liste import _tickets
from app.panier import comparer_panier, enseigne_du_magasin
from tests.test_openprices import faux_service, item
from tests.test_stats import ticket
from tests.test_tickets import _article, db, nouvel_utilisateur  # noqa: F401


def test_enseigne_du_magasin():
    assert enseigne_du_magasin("Centre Commercial E.Leclerc") == "E.Leclerc"
    assert enseigne_du_magasin("Carrefour Market") == "Carrefour"
    assert enseigne_du_magasin("Hal shop") == "Hal shop"


def test_panier_par_enseigne(db, monkeypatch):
    from app import panier
    monkeypatch.setattr(openprices.time, "sleep", lambda s: None)
    # Claude « garde » tous les candidats sauf la biere
    monkeypatch.setattr(panier, "verifier", lambda noms, cand: {i: {p.id for p in c if "Bière" not in p.nom}
                                                                  for i, c in cand.items()})
    u = nouvel_utilisateur(db, "a@x.fr")
    r = ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("X6", "Œufs bio ×6", 2.49), _article("K", "Kéfir 1 L", 2.85)])
    oeufs, kefir = (it.product_id for it in r.items)
    get, _ = faux_service([[item(1, "Œufs bio x6", 2.20, "Lidl"), item(2, "Kéfir 1 L", 2.40, "Lidl"),
                            item(3, "Œufs bio x6", 3.10, "Monoprix"), item(4, "Bière", 2.0, "Lidl")]])
    openprices.synchroniser(db, get=get)
    res = comparer_panier(db, u, [("Œufs bio ×6", oeufs), ("Kéfir 1 L", kefir)], _tickets(db, u))
    par = {e["enseigne"]: e for e in res["enseignes"]}
    assert par["Carrefour"]["trouves"] == 2 and str(par["Carrefour"]["total"]) == "5.34"  # ses propres prix
    assert par["Lidl"]["trouves"] == 2 and str(par["Lidl"]["total"]) == "4.60"           # prix releves
    assert par["Monoprix"]["trouves"] == 1
    assert res["enseignes"][0]["enseigne"] == "Lidl"  # panier complet le moins cher en premier
    assert str(res["total_malin"]) == "4.60" and res["trouves_malin"] == 2
    assert par["Carrefour"]["lignes"][0][1]["source"] == "moi"
    assert par["Lidl"]["ecart"] == -14 and par["Carrefour"]["ecart"] == 0  # 4,60 contre 5,34 payes
    assert par["Monoprix"]["ecart"] == 24 and res["conseil"]["enseigne"] == "Lidl"


def test_panier_pondere_et_juste(db, monkeypatch):
    """Une enseigne qui n'a qu'un produit bon marche ne passe pas devant ; le plus achete compte plus."""
    from app import panier
    monkeypatch.setattr(openprices.time, "sleep", lambda s: None)
    monkeypatch.setattr(panier, "verifier", lambda noms, cand: {i: {p.id for p in c} for i, c in cand.items()})
    u = nouvel_utilisateur(db, "a@x.fr")
    r = ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("L", "Lait 1 L", 1.20), _article("C", "Café 250 g", 4.00)])
    lait, cafe = (it.product_id for it in r.items)
    get, _ = faux_service([[item(1, "Lait 1 L", 1.00, "Lidl"), item(2, "Café 250 g", 4.40, "Lidl"),
                            item(3, "Lait 1 L", 0.50, "Aldi")]])
    openprices.synchroniser(db, get=get)
    articles = [("Lait 1 L", lait), ("Café 250 g", cafe)]
    res = comparer_panier(db, u, articles, _tickets(db, u), poids=[10, 1])  # 10 laits pour 1 café
    par = {e["enseigne"]: e for e in res["enseignes"]}
    assert par["Lidl"]["ecart"] == -10  # (10 + 4,40) / (12 + 4) - 1
    assert res["conseil"]["enseigne"] == "Lidl"  # Aldi n'a qu'un article sur deux : pas assez pour conseiller
    sans_poids = comparer_panier(db, u, articles, _tickets(db, u))  # un de chaque : Lidl plus cher (5,40 / 5,20)
    assert {e["enseigne"]: e["ecart"] for e in sans_poids["enseignes"]}["Lidl"] == 4 and sans_poids["conseil"] is None


def test_page_panier(client, links):
    from tests.test_auth import connecter_admin
    connecter_admin(client, links)
    assert "Calcul en cours" in client.get("/liste/comparer").text  # la page s'affiche tout de suite
    assert "Ajoutez des articles" in client.get("/liste/comparer?fragment=1").text
    client.post("/liste", data={"nom": "pain"})
    r = client.get("/liste/comparer?fragment=1")
    assert r.status_code == 200 and "<main" not in r.text
    assert "Calcul en cours" in client.get("/liste/comparer?habituel=1").text  # depuis Comparer, liste non vide


def test_repli_sans_claude(db, monkeypatch):
    from app import panier
    monkeypatch.setattr(openprices.time, "sleep", lambda s: None)

    def panne(noms, cand):
        raise RuntimeError("pas de réseau")
    monkeypatch.setattr(panier, "verifier", panne)
    u = nouvel_utilisateur(db, "a@x.fr")
    get, _ = faux_service([[item(1, "Lait demi-écrémé 1 L", 1.10, "Lidl"),
                            item(2, "Tartelette chocolat au lait", 1.15, "E.Leclerc")]])
    openprices.synchroniser(db, get=get)
    res = comparer_panier(db, u, [("Lait demi-écrémé 1 L", None)], _tickets(db, u))
    assert [e["enseigne"] for e in res["enseignes"]] == ["Lidl"]  # la tartelette n'est pas du lait
