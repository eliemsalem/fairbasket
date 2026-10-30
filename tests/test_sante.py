from datetime import date
from decimal import Decimal

import pytest

from app import assistant, codebarres, config, sante, tickets
from app.lecture import Lecture
from app.models import OpenPrice, ProductAlias, ReceiptItem
from tests.test_auth import connecter_admin
from tests.test_stats import ticket
from tests.test_tickets import ALDI, _article, db, nouvel_utilisateur  # noqa: F401

PDF = ("ticket.pdf", b"%PDF-1.4 faux", "application/pdf")
CEREALES = "4061458000123"
AVOINE = "3560071199494"
MUESLI = "3560030410004"

FICHE_CEREALES = {"status": 1, "product": {
    "product_name": "Céréales chocolat", "brands": "Aldi", "quantity": "500 g", "nutriscore_grade": "d",
    "nova_group": 4, "additives_tags": ["en:e322", "en:e471"], "labels_tags": ["en:organic", "en:eu-organic"],
    "categories_tags": ["en:breakfasts", "en:cereals-and-potatoes", "en:breakfast-cereals",
                        "en:chocolate-cereals"]}}
OFF_MIEUX = [{"code": AVOINE, "product_name": "Flocons d'avoine", "brands": ["Aldi"], "quantity": "500 g",
              "nutriscore_grade": "a", "nova_group": 1},
             {"code": MUESLI, "product_name": "Muesli", "brands": ["Aldi"], "quantity": "750 g",
              "nutriscore_grade": "b", "nova_group": 3}]


class FauxOFF:
    """Open Food Facts sans reseau : note chaque recherche."""

    def __init__(self):
        self.recherches = []

    def __call__(self, url, params):
        if url == codebarres.RECHERCHE:
            q = params["q"]
            self.recherches.append(q)
            if "nutriscore_grade" in q:
                return {"hits": OFF_MIEUX, "count": 40}
            if "categories_tags" in q:
                return {"hits": [], "count": 100}  # tout le rayon : 40 % mieux notes
            return {"hits": [{"code": CEREALES, "product_name": "Céréales",
                              "categories_tags": FICHE_CEREALES["product"]["categories_tags"]},
                             {"code": AVOINE, "product_name": "Avoine",
                              "categories_tags": ["en:breakfasts", "en:breakfast-cereals"]}]}
        if CEREALES in url:
            return FICHE_CEREALES
        return {"status": 0}


def test_faits_sans_jugement():
    s = sante.extraire(FICHE_CEREALES["product"])
    assert s["nutriscore"] == "d" and s["nova"] == 4 and s["additifs"] == ["E322", "E471"]
    assert s["labels"] == ["Bio"]  # deux etiquettes bio : une seule fois
    assert s["categories"][-1] == "en:chocolate-cereals"
    assert sante.extraire({"nutriscore_grade": "not-applicable", "nova_group": "x"})["nutriscore"] is None


def test_mieux_notes_meme_rayon_marque_de_l_enseigne_d_abord():
    off = FauxOFF()
    mieux = sante.mieux_notes(["en:breakfast-cereals", "en:chocolate-cereals"], "Aldi", "d", CEREALES, off)
    assert [m["code"] for m in mieux] == [AVOINE, MUESLI]  # A avant B
    assert all('categories_tags:"en:chocolate-cereals"' in q for q in off.recherches)
    assert 'brands:"aldi"' in off.recherches[-1]
    assert sante.mieux_notes(["en:breakfast-cereals"], "Aldi", "b", get=off) == []  # deja bien note : rien


def test_quelques_fiches_mieux_notees_ne_suffisent_pas():
    def beurres(url, params):  # 3 beurres « C » sur 400 : des fiches mal remplies
        if "nutriscore_grade" in params["q"]:
            return {"hits": [{"code": AVOINE, "product_name": "Beurre", "brands": "X", "quantity": "250 g",
                              "nutriscore_grade": "c"}], "count": 3}
        return {"hits": [], "count": 400}
    assert sante.mieux_notes(["en:butters", "en:half-salted-butter"], "Carrefour", "e", get=beurres) == []


def test_doublons_et_fiches_incompletes_ecartes():
    def recherche(url, params):
        if "nutriscore_grade" not in params["q"]:
            return {"hits": [], "count": 10}
        return {"count": 10, "hits": [
            {**OFF_MIEUX[0]}, {**OFF_MIEUX[0], "code": "3560071469573"},  # meme produit, autre code
            {"code": MUESLI, "product_name": "Muesli sans marque", "quantity": "500 g", "nutriscore_grade": "a"}]}
    assert [m["code"] for m in sante.mieux_notes(["en:breakfast-cereals"], None, "d", get=recherche)] == [AVOINE]


def test_rayon_commun():
    assert sante.rayon_de([{"categories_tags": ["en:breakfasts", "en:breakfast-cereals", "en:chocolate-cereals"]},
                           {"categories_tags": ["en:breakfasts", "en:breakfast-cereals"]},
                           {"categories_tags": ["en:snacks"]}]) == "en:breakfast-cereals"
    assert sante.rayon_de([]) is None


def test_bilan_par_note():
    b = sante.bilan([(Decimal(6), "a"), (Decimal(2), "b"), (Decimal(2), "e"), (Decimal(5), None)])
    assert b["nb"] == 3 and b["pct_bons"] == 80 and [p["note"] for p in b["parts"]] == ["a", "b", "e"]
    assert sante.bilan([(Decimal(5), None)]) is None


@pytest.fixture
def off(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(config, "OPEN_FOOD_FACTS_AUTO", True)
    faux = FauxOFF()
    monkeypatch.setattr(codebarres, "_get", faux)
    donnees = {**ALDI, "articles": [
        {**ALDI["articles"][0], "libelle": "CEREALES CHOCO", "nom": "Céréales chocolat"}, *ALDI["articles"][1:]]}
    monkeypatch.setattr(tickets, "lire_ticket",
                        lambda data, mt: Lecture(donnees=donnees, modele="test", tokens_entree=1, tokens_sortie=1))
    return faux


def test_scan_puis_sante_sur_le_ticket(client, links, off):
    from app.db import SessionLocal

    connecter_admin(client, links)
    rid = int(client.post("/tickets", files={"fichier": PDF}, follow_redirects=False).headers["location"].split("/")[-1])
    with SessionLocal() as s:
        iid = s.query(ReceiptItem).filter_by(libelle="CEREALES CHOCO").one().id
        s.add(OpenPrice(id=1, nom="Flocons d'avoine", code_barres=AVOINE, prix=Decimal("0.79"), jour=date(2026, 10, 20),
                        magasin="ALDI MEAUX", ville="Paris", lat=48.885, lon=2.38))
        s.commit()
    client.post(f"/tickets/{rid}/code/{iid}", data={"code": CEREALES})

    page = client.get(f"/tickets/{rid}").text
    assert "nutri-d" in page and "NOVA 4" in page and "E322" in page and "Bio" in page
    assert "Mieux noté" in page and "Flocons d&#39;avoine" in page and "0,79" in page
    assert "en A ou B" in page  # bilan sante du ticket : 0 % ici
    code = client.get(f"/tickets/{rid}/code/{iid}").text
    assert "Mieux noté dans le même rayon" in code and "Muesli" in code and "Ajouter à ma liste" in code


def test_assistant_comprend_plus_sain():
    assert assistant.comprendre("Une alternative plus saine aux céréales que j'achète ?") == ("sante", {"produit": "cereales"})
    assert assistant.comprendre("chips plus saines")[0] == "sante"


def test_assistant_part_de_l_article_scanne(db):
    u = nouvel_utilisateur(db, "sain@x.fr")
    ticket(db, u, 1, "Aldi", "2026-10-03", [_article("CEREALES CHOCO", "Céréales chocolat", 3.10)])
    alias = db.query(ProductAlias).filter_by(enseigne="Aldi", libelle="CEREALES CHOCO").one()
    alias.code_barres, alias.nom_exact = CEREALES, "Céréales chocolat"
    alias.sante = {**sante.extraire(FICHE_CEREALES["product"]), "le": date.today().isoformat(),
                   "mieux": [sante._proposition(h) for h in OFF_MIEUX]}
    db.commit()
    res = assistant.plus_sain(db, u, None, "cereales")
    assert res["actuel"]["nutriscore"] == "d" and [m["code"] for m in res["sains"]] == [AVOINE, MUESLI]
    texte = assistant.rediger("sante", {"produit": "cereales"}, res, "fr")
    assert "Nutri-Score D" in texte and "Flocons d'avoine" in texte and "Nutri-Score A" in texte


def test_assistant_sans_scan_ni_reseau(db):
    u = nouvel_utilisateur(db, "rien@x.fr")
    res = assistant.plus_sain(db, u, None, "chips")
    assert not res["trouve"]
    assert "Scannez le code-barres" in assistant.rediger("sante", {"produit": "chips"}, res, "fr")
