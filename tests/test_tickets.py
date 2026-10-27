from datetime import datetime, timezone

import pytest

from app import config
from app.db import SessionLocal
from tests.conftest import base_vide
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
    base_vide()
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


def test_magasin_bio_produit_bio(db):
    from app.models import Product
    from app.tickets import avec_bio
    assert avec_bio("Œufs ×6") == "Œufs bio ×6" and avec_bio("Banane") == "Banane bio"
    assert avec_bio("Kéfir bio 1 L") == "Kéfir bio 1 L"
    u = nouvel_utilisateur(db, "a@x.fr")
    oeufs = {**_article("OEUF PT X6", "Œufs ×6", 2.89)}
    d = {**ALDI, "enseigne": "Naturalia", "magasin": "QUAI DE LA LOIRE", "total": 2.89, "articles": [oeufs]}
    r = enregistrer_ticket(db, u, b"n", "n.pdf", "application/pdf", lire=fausse_lecture(d)).receipt
    assert r.items[0].product.nom == "Œufs bio ×6"
    # chez Aldi, le meme nom reste non bio
    d2 = {**ALDI, "total": 1.65, "articles": [_article("OEUFS", "Œufs ×6", 1.65)]}
    r2 = enregistrer_ticket(db, u, b"a", "a.pdf", "application/pdf", lire=fausse_lecture(d2)).receipt
    assert r2.items[0].product.nom == "Œufs ×6" and db.query(Product).count() == 2


def test_corriger_bio_historique(db, monkeypatch):
    from app import tickets as module_tickets
    from app.tickets import corriger_bio
    u = nouvel_utilisateur(db, "a@x.fr", partage=True)
    # ticket enregistre avant la regle : on la desactive le temps de l'import
    monkeypatch.setattr(module_tickets, "est_bio", lambda *a: False)
    d = {**ALDI, "enseigne": "Naturalia", "magasin": "X", "total": 2.89, "articles": [_article("OEUF", "Œufs ×6", 2.89)]}
    r = enregistrer_ticket(db, u, b"n", "n.pdf", "application/pdf", lire=fausse_lecture(d)).receipt
    assert r.items[0].product.nom == "Œufs ×6"
    monkeypatch.undo()
    assert corriger_bio(db) == 1 and corriger_bio(db) == 0  # une seule fois
    db.refresh(r)
    assert r.items[0].product.nom == "Œufs bio ×6"
    assert {sp.product_id for sp in db.query(SharedPrice)} == {r.items[0].product_id}


def test_liste_des_enseignes():
    from app.enseignes import est_bio, reconnaitre
    from app.tickets import enseigne_canonique
    assert enseigne_canonique("Carrefour City") == "Carrefour" and enseigne_canonique("Monop'") == "Monoprix"
    assert enseigne_canonique("HYPER U") == "Système U" and enseigne_canonique("Intermarché Express") == "Intermarché"
    assert reconnaitre("Centre Commercial E.Leclerc") == ("E.Leclerc", False)
    assert est_bio("La Récolte") and est_bio("Naturalia") and est_bio("Carrefour", "CARREFOUR BIO PARIS")
    assert not est_bio("Carrefour", "MARKET PARIS JEAN JAURES") and not est_bio("Monoprix")
    assert reconnaitre("Matcha & Co") == (None, False)  # « match » seulement comme mot entier
    assert enseigne_canonique("Épicerie du coin") == "Épicerie du coin"


def test_plusieurs_photos_un_ticket(db, tmp_path):
    import io
    from PIL import Image

    def photo(couleur):
        out = io.BytesIO()
        Image.new("RGB", (300, 400), couleur).save(out, format="JPEG")
        return out.getvalue()
    u = nouvel_utilisateur(db, "a@x.fr")
    recu = {}

    def lire(data, media_type, suite=()):
        recu["photos"] = 1 + len(suite)
        return Lecture(donnees=ALDI, modele="test", tokens_entree=1, tokens_sortie=1)
    r = enregistrer_ticket(db, u, photo("white"), "t.jpg", "image/jpeg", lire=lire,
                           suite=[photo("gray"), photo("black")]).receipt
    assert recu["photos"] == 3 and r.statut == "ok"
    from PIL import Image as I
    assert I.open(tmp_path / r.fichier_chemin).size == (300, 1200)  # gardees l'une sous l'autre
    with pytest.raises(TicketRefuse):
        enregistrer_ticket(db, u, b"%PDF", "t.pdf", "application/pdf", lire=lire, suite=[b"x"])


def test_adresse_a_confirmer(db):
    from app.tickets import confirmer_adresse
    u = nouvel_utilisateur(db, "a@x.fr")
    assert enregistrer_ticket(db, u, b"1", "t.pdf", "application/pdf", lire=fausse_lecture(ALDI)).receipt.adresse_ok
    sans = {**ALDI, "magasin": "Aldi autre", "adresse": None, "code_postal": None, "ville": None, "total": 0.95,
            "articles": ALDI["articles"][:1]}
    r = enregistrer_ticket(db, u, b"2", "t.pdf", "application/pdf", lire=fausse_lecture(sans)).receipt
    assert not r.adresse_ok  # pas d'adresse sur le ticket : la personne doit la confirmer
    confirmer_adresse(db, r, " 3 rue  du Test ", "75019", "Paris")
    assert r.adresse_ok and r.store.adresse == "3 rue du Test" and r.store.ville == "Paris"
    sans2 = {**sans, "heure": "19:00"}
    assert enregistrer_ticket(db, u, b"3", "t.pdf", "application/pdf", lire=fausse_lecture(sans2)).receipt.adresse_ok


def test_magasins_en_double(db):
    from app.models import Store
    from app.tickets import cle_magasin, fusionner_magasins
    assert cle_magasin("Carrefour", "CARREFOUR MARKET PARIS JEAN JAURÈS") == cle_magasin("Carrefour", "MARKET PARIS JEAN JAURES")
    assert cle_magasin("Carrefour", "CITY LYON PART-DIEU") == cle_magasin("Carrefour", "City Lyon Part Dieu")
    assert cle_magasin("Carrefour", "CITY PARIS CRIMÉE 96") != cle_magasin("Carrefour", "CITY PARIS FLANDRE 110")
    u = nouvel_utilisateur(db, "a@x.fr")
    d = {**ALDI, "enseigne": "Carrefour", "magasin": "MARKET PARIS JEAN JAURES", "adresse": None, "code_postal": None}
    r1 = enregistrer_ticket(db, u, b"1", "t.pdf", "application/pdf", lire=fausse_lecture(d)).receipt
    d2 = {**d, "magasin": "Carrefour Market Paris Jean Jaurès", "heure": "19:00"}
    r2 = enregistrer_ticket(db, u, b"2", "t.pdf", "application/pdf", lire=fausse_lecture(d2)).receipt
    assert r1.store_id == r2.store_id  # reconnu a l'enregistrement
    # doublons deja en base (enregistres avant) : fusionnes, l'adresse et la confirmation sont gardees
    ancien = Store(enseigne="Carrefour City", nom="CARREFOUR MARKET PARIS JEAN JAURÈS", adresse="1 av. Jean Jaurès")
    db.add(ancien)
    db.flush()
    r2.store_id, r2.adresse_ok = ancien.id, True
    db.commit()
    assert fusionner_magasins(db) == 1
    db.refresh(r1)
    db.refresh(r2)
    assert r1.store_id == r2.store_id and r1.store.adresse == "1 av. Jean Jaurès" and r1.store.enseigne == "Carrefour"
    assert r1.adresse_ok
