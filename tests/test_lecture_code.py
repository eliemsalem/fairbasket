"""Lecture sans IA des tickets PDF connus : tickets inventes, au format des caisses Carrefour et Monoprix."""

from decimal import Decimal

from app import lecture_code
from app.lecture_code import analyser, lire_pdf
from app.tickets import enregistrer_ticket
from tests.test_tickets import ALDI, db, fausse_lecture, nouvel_utilisateur  # noqa: F401

CARREFOUR = """                     MARKET PARIS TEST

20/03/2025 à 12h35

TVA      Produit                                    QTE x P.U.           Montant €
5.5%     PAVE SAUMON                                       1 x 9.99                9.99
5.5%     1L BLE LAIT 1/2 EC                                2 x 1.21                2.42
                                                             Remise immédiate -0.25
5.5%     1L BLE LAIT 1/2 EC                               -1 x 1.21               -1.21
5.5%     TOMATE GRAPPE                                     1 x 2.10                2.10
          0.420kg x 5.00€/kg
5.5%     COUPON FIDELITE                                   1 x -5.00              -5.00
Total à payer                                                                 8.05€
"""

MONOPRIX = """                                    MONOPRIX TEST
                                  1 RUE DE LA PAIX
                                         75002 PARIS

FRUITS/LEGUMES......................
               BIO BANANE M.HAV                                                               2.07€
               1.040kg manuelle X 1.99 €/kg
               -10% Monopflix                                                        -0.21€
EPICERIE/BOISSONS...................
   2X          345G HAR.VERT XF                                     2.99€               5.98€
               Le 2ème à moins 50%                                                -1.50€
                                                                                      =========
TOTAL HORS AVANTAGES                                                                          8.05€
NOMBRE ARTICLES                                                                                    3
TOTAL DES REMISES                                                                           -1.71€
RESTE A PAYER                                                                                6.34€
                                09/09/2026 12:05 292 80 9311 800
"""


def test_carrefour():
    d = analyser(CARREFOUR)
    assert d["enseigne"] == "Carrefour" and d["date"] == "2025-03-20" and d["heure"] == "12:35"
    lait = d["articles"][1]
    assert lait["montant"] == Decimal("2.17") and lait["remise"] == Decimal("0.25")  # remise sous l'article
    assert d["articles"][2]["montant"] == Decimal("-1.21")  # article rendu : reste une ligne
    assert d["articles"][3]["prix_kg"] == Decimal("5.00")
    assert d["remises_globales"] == Decimal("5.00") and len(d["articles"]) == 4  # le coupon est une remise


def test_monoprix():
    d = analyser(MONOPRIX)
    assert d["enseigne"] == "Monoprix" and d["adresse"] == "1 Rue De La Paix" and d["code_postal"] == "75002"
    assert [a["libelle"] for a in d["articles"]] == ["BIO BANANE M.HAV", "345G HAR.VERT XF"]
    assert d["articles"][1]["quantite"] == 2 and d["articles"][1]["montant"] == Decimal("4.48")
    assert d["remises_globales"] == 0 and d["total"] == Decimal("6.34")  # remises deja deduites des articles


def test_total_faux_ou_format_inconnu():
    assert analyser(CARREFOUR.replace("8.05€", "9.05€")) is None  # Claude reprendra le ticket
    assert analyser("TICKET LIDL\nTOTAL 12,00") is None


def test_noms_connus_sans_claude(db, monkeypatch):
    u = nouvel_utilisateur(db, "a@x.fr")
    # un premier ticket lu par Claude fait connaitre le libelle « PAVE SAUMON » chez Carrefour
    vu = {**ALDI, "enseigne": "Carrefour", "magasin": "Market test", "total": 9.99, "articles": [
        {**ALDI["articles"][0], "libelle": "PAVE SAUMON", "nom": "Pavé de saumon", "categorie": "Viandes et poissons",
         "famille": "poisson", "montant": 9.99}]}
    enregistrer_ticket(db, u, b"1", "1.pdf", "application/pdf", lire=fausse_lecture(vu))
    monkeypatch.setattr(lecture_code, "texte_pdf", lambda data: CARREFOUR)
    demandes = []

    def nommer(enseigne, libelles):
        demandes.append(libelles)
        return {l: {"nom": l.title(), "categorie": "Autre", "famille": "x"} for l in libelles}, "haiku", 50, 20
    lu = lire_pdf(db, b"%PDF", nommer=nommer)
    assert demandes == [["1L BLE LAIT 1/2 EC", "TOMATE GRAPPE"]]  # seuls les libelles nouveaux
    assert lu.donnees["articles"][0]["nom"] == "Pavé de saumon" and lu.modele == "code + haiku"
    demandes.clear()

    def panne(enseigne, libelles):
        raise RuntimeError("pas de réseau")
    assert lire_pdf(db, b"%PDF", nommer=panne) is None  # sans les noms, Claude lit le ticket entier


def test_pdf_enregistre_par_le_code(db, monkeypatch):
    from app import tickets
    u = nouvel_utilisateur(db, "a@x.fr")
    monkeypatch.setattr(lecture_code, "texte_pdf", lambda data: MONOPRIX)
    monkeypatch.setattr(lecture_code, "nommer", lambda e, ls: ({}, "haiku", 1, 1))
    monkeypatch.setattr(tickets, "lire_pdf", lambda db, data: lire_pdf(db, data, nommer=lambda e, ls: ({}, "h", 1, 1)))
    monkeypatch.setattr(tickets, "lire_ticket", lambda d, m: (_ for _ in ()).throw(AssertionError("Claude appelé")))
    r = enregistrer_ticket(db, u, b"%PDF mono", "m.pdf", "application/pdf").receipt
    assert r.statut == "ok" and r.total == Decimal("6.34") and r.adresse_ok and r.store.code_postal == "75002"
