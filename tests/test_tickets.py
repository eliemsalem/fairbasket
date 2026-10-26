from datetime import datetime, timezone

import pytest

from app import config
from app.db import Base, SessionLocal, engine
from app.lecture import Lecture
from app.models import Receipt, SharedPrice, User
from app.tickets import TicketRefuse, enregistrer_ticket

ALDI = {
    "lisible": True, "enseigne": "Aldi", "magasin": "Aldi rue de Meaux", "adresse": "85/87 rue de Meaux",
    "code_postal": "75019", "ville": "Paris", "date": "2026-09-25", "heure": "18:11", "total": 14.97,
    "remises_globales": 0, "nombre_articles_imprime": 3, "remarques": None,
    "articles": [
        {"libelle": "OIGNONS ROUGE 500G", "quantite": 1, "prix_unitaire": 0.95, "montant": 0.95, "remise": None,
         "poids_kg": None, "prix_kg": None, "illisible": False},
        {"libelle": "COTES DE PORC 700", "quantite": 1, "prix_unitaire": 5.29, "montant": 5.29, "remise": None,
         "poids_kg": None, "prix_kg": None, "illisible": False},
        {"libelle": "CELERI BRANCHE", "quantite": 1, "prix_unitaire": None, "montant": 8.73, "remise": None,
         "poids_kg": None, "prix_kg": None, "illisible": False},
    ],
}


def fausse_lecture(donnees):
    return lambda data, media_type: Lecture(donnees=donnees, modele="test", tokens_entree=1000, tokens_sortie=200)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    yield s
    s.close()


def nouvel_utilisateur(db, email, partage=False):
    t = datetime.now(timezone.utc)
    u = User(email=email, prenom="X", statut="actif", age_ok_at=t, cgu_at=t, cgu_version="v", ia_consent_at=t,
             partage_consent=partage)
    db.add(u)
    db.commit()
    return u


def test_ticket_juste(db, tmp_path):
    u = nouvel_utilisateur(db, "a@x.fr")
    r = enregistrer_ticket(db, u, b"pdf1", "t.pdf", "application/pdf", lire=fausse_lecture(ALDI)).receipt
    assert r.statut == "ok" and r.total == r.somme_articles
    assert r.store.enseigne == "Aldi" and r.store.code_postal == "75019"
    assert [i.libelle for i in r.items][0] == "OIGNONS ROUGE 500G"
    assert (tmp_path / r.fichier_chemin).read_bytes() == b"pdf1"  # original conserve


def test_ecart_detecte(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    d = {**ALDI, "articles": ALDI["articles"][:2]}  # une ligne manque
    r = enregistrer_ticket(db, u, b"photo", "t.jpg", "application/pdf", lire=fausse_lecture(d)).receipt
    assert r.statut == "ecart"


def test_meme_fichier_deux_fois(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    appels = []

    def lire(data, mt):
        appels.append(1)
        return fausse_lecture(ALDI)(data, mt)

    enregistrer_ticket(db, u, b"pdf1", "t.pdf", "application/pdf", lire=lire)
    res = enregistrer_ticket(db, u, b"pdf1", "t.pdf", "application/pdf", lire=lire)
    assert res.doublon and len(appels) == 1  # pas de deuxieme lecture payee


def test_meme_ticket_autre_fichier(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    enregistrer_ticket(db, u, b"pdf1", "t.pdf", "application/pdf", lire=fausse_lecture(ALDI))
    res = enregistrer_ticket(db, u, b"photo-du-meme", "t.jpg", "application/pdf", lire=fausse_lecture(ALDI))
    assert res.doublon
    assert db.query(Receipt).count() == 1


def test_illisible_refuse(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    with pytest.raises(TicketRefuse):
        enregistrer_ticket(db, u, b"flou", "t.jpg", "application/pdf", lire=fausse_lecture({"lisible": False}))


def test_format_refuse(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    with pytest.raises(TicketRefuse):
        enregistrer_ticket(db, u, b"x", "t.docx", "application/msword", lire=fausse_lecture(ALDI))


def test_quota_mensuel(db, monkeypatch):
    monkeypatch.setattr(config, "MAX_TICKETS_PAR_MOIS", 2)
    u = nouvel_utilisateur(db, "a@x.fr")
    for i in range(2):
        d = {**ALDI, "heure": f"1{i}:00"}
        enregistrer_ticket(db, u, f"f{i}".encode(), "t.pdf", "application/pdf", lire=fausse_lecture(d))
    with pytest.raises(TicketRefuse):
        enregistrer_ticket(db, u, b"f3", "t.pdf", "application/pdf", lire=fausse_lecture(ALDI))


def test_tickets_separes_entre_utilisateurs(db):
    a, b = nouvel_utilisateur(db, "a@x.fr"), nouvel_utilisateur(db, "b@x.fr")
    enregistrer_ticket(db, a, b"pdf1", "t.pdf", "application/pdf", lire=fausse_lecture(ALDI))
    res = enregistrer_ticket(db, b, b"pdf1", "t.pdf", "application/pdf", lire=fausse_lecture(ALDI))
    assert not res.doublon and res.receipt.user_id == b.id


def test_prix_partages_seulement_avec_accord(db):
    sans = nouvel_utilisateur(db, "a@x.fr")
    enregistrer_ticket(db, sans, b"pdf1", "t.pdf", "application/pdf", lire=fausse_lecture(ALDI))
    assert db.query(SharedPrice).count() == 0

    avec = nouvel_utilisateur(db, "b@x.fr", partage=True)
    enregistrer_ticket(db, avec, b"pdf2", "t.pdf", "application/pdf", lire=fausse_lecture(ALDI))
    prix = db.query(SharedPrice).all()
    assert len(prix) == 3
    # anonyme : ni utilisateur, ni ticket, ni heure
    assert not hasattr(SharedPrice, "user_id") and not hasattr(SharedPrice, "receipt_id")
    assert str(prix[0].jour) == "2026-09-25"


def test_enseigne_meme_ecriture(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    r1 = enregistrer_ticket(db, u, b"a", "a.pdf", "application/pdf", lire=fausse_lecture(ALDI)).receipt
    d = {**ALDI, "enseigne": "ALDI", "heure": "19:00"}
    r2 = enregistrer_ticket(db, u, b"b", "b.pdf", "application/pdf", lire=fausse_lecture(d)).receipt
    assert r1.store_id == r2.store_id


def _article(libelle, nom, montant):
    return {"libelle": libelle, "nom": nom, "categorie": "Produits laitiers et œufs", "quantite": 1,
            "prix_unitaire": montant, "montant": montant, "remise": None, "poids_kg": None, "prix_kg": None,
            "illisible": False}


def test_meme_produit_entre_enseignes(db):
    from app.models import Product, ProductAlias
    u = nouvel_utilisateur(db, "a@x.fr", partage=True)
    carrefour = {**ALDI, "enseigne": "Carrefour", "magasin": "MARKET", "total": 2.49,
                 "articles": [_article("X6 OEUFS CRF BIO", "Œufs bio ×6", 2.49)]}
    biocoop = {**ALDI, "enseigne": "Biocoop", "magasin": "CANAL BIO", "total": 2.82,
               "articles": [_article("OEUFS BIOCOOP (6)", "œufs bio ×6", 2.82)]}
    r1 = enregistrer_ticket(db, u, b"c", "c.pdf", "application/pdf", lire=fausse_lecture(carrefour)).receipt
    r2 = enregistrer_ticket(db, u, b"b", "b.pdf", "application/pdf", lire=fausse_lecture(biocoop)).receipt
    assert r1.items[0].product_id == r2.items[0].product_id  # meme produit malgre la casse
    assert db.query(Product).one().nom == "Œufs bio ×6"
    assert db.query(ProductAlias).count() == 2
    assert {p.product_id for p in db.query(SharedPrice)} == {r1.items[0].product_id}


def test_libelle_deja_vu_reutilise(db):
    from app.models import Product
    u = nouvel_utilisateur(db, "a@x.fr")
    d1 = {**ALDI, "total": 2.49, "articles": [_article("X6 OEUFS", "Œufs bio ×6", 2.49)]}
    # la deuxieme fois l'IA propose un autre nom : le libelle connu l'emporte
    d2 = {**ALDI, "heure": "20:00", "total": 2.49, "articles": [_article("X6 OEUFS", "Oeufs biologiques", 2.49)]}
    enregistrer_ticket(db, u, b"1", "1.pdf", "application/pdf", lire=fausse_lecture(d1))
    enregistrer_ticket(db, u, b"2", "2.pdf", "application/pdf", lire=fausse_lecture(d2))
    assert db.query(Product).count() == 1


def test_ligne_illisible_sans_produit(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    art = {**_article("COTES DE POR..", "Côtes de porc", 5.29), "illisible": True}
    d = {**ALDI, "total": 5.29, "articles": [art]}
    r = enregistrer_ticket(db, u, b"1", "1.pdf", "application/pdf", lire=fausse_lecture(d)).receipt
    assert r.items[0].product_id is None


def test_formats_ramenes_a_l_enseigne():
    from app.tickets import enseigne_canonique
    assert enseigne_canonique("Carrefour City") == "Carrefour"
    assert enseigne_canonique("Monop'") == "Monoprix"
    assert enseigne_canonique("MONOPRIX") == "Monoprix"
    assert enseigne_canonique("picard") == "Picard"
    assert enseigne_canonique("Grand Frais") == "Grand Frais"


def test_import_hors_quota(db, monkeypatch):
    from app.tickets import tickets_ce_mois
    monkeypatch.setattr(config, "MAX_TICKETS_PAR_MOIS", 1)
    u = nouvel_utilisateur(db, "a@x.fr")
    for i in range(3):
        d = {**ALDI, "heure": f"1{i}:00"}
        enregistrer_ticket(db, u, f"h{i}".encode(), "t.pdf", "application/pdf", lire=fausse_lecture(d), importe=True)
    assert tickets_ce_mois(db, u) == 0
    enregistrer_ticket(db, u, b"nouveau", "t.pdf", "application/pdf", lire=fausse_lecture({**ALDI, "heure": "20:00"}))
