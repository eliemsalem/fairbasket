"""Enregistrement d'un ticket : doublons, quota, lecture par l'IA, controle du total, prix partages."""

import hashlib
import re
from collections import defaultdict
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from . import config
from .enseignes import est_bio, reconnaitre
from .lecture import Lecture, LectureImpossible, image_compressee, lire_ticket, photos_assemblees
from .lecture_code import lire_pdf
from .models import Product, ProductAlias, Receipt, ReceiptItem, SharedPrice, Store, User, now

TOLERANCE = Decimal("0.02")
TYPES_ACCEPTES = {"application/pdf": "pdf", "image/jpeg": "photo", "image/png": "photo", "image/webp": "photo",
                  "image/heic": "photo"}


class TicketRefuse(Exception):
    """Ticket non enregistre, avec un message a montrer a l'utilisateur (cle de traduction + valeurs)."""

    def __init__(self, cle: str, **valeurs):
        super().__init__(cle.format(**valeurs))
        self.cle, self.valeurs = cle, valeurs


@dataclass
class Resultat:
    receipt: Receipt
    doublon: bool = False


def _dec(v) -> Optional[Decimal]:
    return None if v is None else Decimal(str(v)).quantize(Decimal("0.01"))


def tickets_ce_mois(db: Session, user: User) -> int:
    debut = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(select(func.count()).select_from(Receipt).where(Receipt.user_id == user.id,
                                                                      Receipt.created_at >= debut,
                                                                      Receipt.importe.is_(False)))


def enseigne_canonique(enseigne: str) -> str:
    """« Carrefour City » -> « Carrefour », « Monop' » -> « Monoprix » ; une enseigne inconnue garde son nom."""
    enseigne = " ".join((enseigne or "").split())[:60]
    connue, _ = reconnaitre(enseigne)
    if connue:
        return connue
    if enseigne.isupper() or enseigne.islower():
        enseigne = enseigne.title()  # « MONOPRIX » et « Monoprix » sont la meme enseigne
    return enseigne


def cle_magasin(enseigne: str, nom: str) -> str:
    """« CARREFOUR MARKET PARIS JEAN JAURÈS » et « MARKET PARIS JEAN JAURES » chez Carrefour -> la meme cle."""
    mots_enseigne = set(re.sub(r"[^\w&]+", " ", cle_produit(enseigne)).split())
    mots = [m for m in re.sub(r"[^\w&]+", " ", cle_produit(nom)).split() if m not in mots_enseigne]
    return " ".join(mots) or cle_produit(enseigne)


def _magasin(db: Session, d: dict) -> Optional[Store]:
    enseigne = enseigne_canonique(d.get("enseigne") or "")
    nom = (d.get("magasin") or enseigne).strip().upper()[:120]
    if not enseigne:
        return None
    # meme magasin ecrit autrement (accents, enseigne en tete) : on reprend celui qu'on connait
    cle = cle_magasin(enseigne, nom)
    store = next((s for s in db.scalars(select(Store).where(Store.enseigne == enseigne).order_by(Store.id))
                  if cle_magasin(enseigne, s.nom) == cle), None)
    if store is None:
        store = Store(enseigne=enseigne, nom=nom)
        db.add(store)
    # complete l'adresse si ce ticket la donne et qu'on ne l'avait pas
    for champ, taille in (("adresse", 200), ("code_postal", 10), ("ville", 80)):
        if not getattr(store, champ) and d.get(champ):
            setattr(store, champ, d[champ][:taille])
    return store


def cle_produit(nom: str) -> str:
    nom = nom.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae").replace("×", "x")
    nom = "".join(c for c in unicodedata.normalize("NFKD", nom) if not unicodedata.combining(c))
    return " ".join(nom.casefold().split())[:120]


def avec_bio(nom: str) -> str:
    """« Œufs ×6 » -> « Œufs bio ×6 » ; inchange si « bio » y est deja (meme forme que les autres produits bio)."""
    if not nom or "bio" in cle_produit(nom).split():
        return nom
    premier, _, reste = nom.partition(" ")
    return f"{premier} bio {reste}".strip()


def _produit(db: Session, enseigne: str, libelle: str, nom: str, categorie: Optional[str],
             famille: Optional[str] = None) -> Optional[Product]:
    """Retrouve le produit : d'abord par un libelle deja vu dans cette enseigne, sinon par son nom lisible."""
    if enseigne:
        alias = db.scalar(select(ProductAlias).where(ProductAlias.enseigne == enseigne, ProductAlias.libelle == libelle))
        if alias:
            if famille and not alias.product.famille:
                alias.product.famille = famille.strip().lower()[:60]
            return alias.product
    nom = " ".join((nom or "").split())[:120]
    if not nom or nom.lower() == "article illisible":
        return None
    produit = db.scalar(select(Product).where(Product.cle == cle_produit(nom)))
    if produit is None:
        produit = Product(nom=nom[0].upper() + nom[1:], cle=cle_produit(nom), categorie=categorie)
        db.add(produit)
    if famille and not produit.famille:
        produit.famille = famille.strip().lower()[:60]
    if enseigne:
        db.add(ProductAlias(enseigne=enseigne, libelle=libelle, product=produit))
        db.flush()
    return produit


def _date_achat(d: dict) -> Optional[datetime]:
    try:
        return datetime.strptime(f"{d.get('date')} {d.get('heure') or '00:00'}", "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


def enregistrer_ticket(db: Session, user: User, data: bytes, fichier_nom: str, media_type: str,
                       lire: Optional[Callable[..., Lecture]] = None, importe: bool = False,
                       suite: Sequence[bytes] = ()) -> Resultat:
    """suite : les photos suivantes du meme ticket, quand il ne tient pas sur une seule photo."""
    if media_type not in TYPES_ACCEPTES:
        raise TicketRefuse("Format non pris en charge : envoyez un PDF ou une photo (JPEG, PNG).")
    if suite and media_type == "application/pdf":
        raise TicketRefuse("Plusieurs morceaux d'un même ticket : seulement des photos.")
    sha = hashlib.sha256(data + b"".join(suite)).hexdigest()
    existant = db.scalar(select(Receipt).where(Receipt.user_id == user.id, Receipt.file_sha256 == sha))
    if existant:
        return Resultat(existant, doublon=True)
    if not importe and tickets_ce_mois(db, user) >= config.MAX_TICKETS_PAR_MOIS:
        raise TicketRefuse("Limite de {n} tickets par mois atteinte.", n=config.MAX_TICKETS_PAR_MOIS)

    try:
        # un PDF d'un format connu est lu par le code (gratuit, exact) ; sinon, ou si le total ne tombe pas juste,
        # Claude lit le ticket
        lecture = None if lire else media_type == "application/pdf" and lire_pdf(db, data)
        if not lecture:
            lire = lire or lire_ticket
            lecture = lire(data, media_type, suite=suite) if suite else lire(data, media_type)
    except LectureImpossible as e:
        raise TicketRefuse(str(e))
    d = lecture.donnees
    if not d.get("lisible"):
        raise TicketRefuse("Ce ticket n'a pas pu être lu. Reprenez la photo à plat, bien éclairée.")

    store = _magasin(db, d)
    achete_le = _date_achat(d)
    total = _dec(d.get("total"))
    remises = _dec(d.get("remises_globales")) or Decimal("0")
    enseigne = store.enseigne if store else ""
    if store is not None and est_bio(d.get("enseigne") or "", d.get("magasin") or ""):
        # magasin 100 % bio : le ticket ne le dit pas, mais le produit l'est
        d = {**d, "articles": [{**a, "nom": avec_bio(a.get("nom") or "")} for a in d.get("articles") or []]}
    items = [
        ReceiptItem(position=i, libelle=(a["libelle"] or "?")[:120], quantite=Decimal(str(a["quantite"] or 1)),
                    product=None if a.get("illisible") else _produit(db, enseigne, (a["libelle"] or "?")[:120],
                                                                      a.get("nom"), a.get("categorie"),
                                                                      a.get("famille")),
                    prix_unitaire=_dec(a["prix_unitaire"]), montant=_dec(a["montant"]), remise=_dec(a["remise"]),
                    poids_kg=None if a["poids_kg"] is None else Decimal(str(a["poids_kg"])),
                    prix_kg=_dec(a["prix_kg"]), illisible=bool(a["illisible"]))
        for i, a in enumerate(d.get("articles") or [])
    ]
    somme = sum((it.montant for it in items), Decimal("0"))

    # meme ticket deja ajoute sous un autre fichier (ex. photo + PDF) : meme magasin, heure et total
    if store is not None and store.id and achete_le and total is not None:
        meme = db.scalar(select(Receipt).where(Receipt.user_id == user.id, Receipt.store_id == store.id,
                                               Receipt.achete_le == achete_le, Receipt.total == total))
        if meme:
            db.rollback()
            return Resultat(meme, doublon=True)

    statut = "ok" if total is not None and abs(somme - remises - total) <= TOLERANCE else "ecart"
    # adresse absente du ticket : l'app la cherche elle-meme, la personne n'a rien a saisir
    trouvee = False
    if store is not None and config.ADRESSES_AUTO and not (store.adresse or store.code_postal):
        from .adresses import completer
        trouvee = completer(db, store)
    receipt = Receipt(
        user_id=user.id, store=store, achete_le=achete_le, total=total, somme_articles=somme,
        remises_globales=remises, statut=statut, remarques=(d.get("remarques") or None) and d["remarques"][:500],
        adresse_ok=bool(d.get("adresse") or d.get("code_postal")) or trouvee or _adresse_deja_confirmee(db, user, store),
        source=TYPES_ACCEPTES[media_type], importe=importe, fichier_nom=fichier_nom[:200], file_sha256=sha,
        modele=lecture.modele, tokens_entree=lecture.tokens_entree, tokens_sortie=lecture.tokens_sortie,
        items=items,
    )
    db.add(receipt)
    db.flush()

    # garde l'original (C9) : utile pour relire un ticket ou prouver un achat
    dossier = config.UPLOAD_DIR / str(user.id)
    dossier.mkdir(parents=True, exist_ok=True)
    if media_type == "application/pdf":
        ext, contenu = "pdf", data
    elif suite:
        ext, contenu = "jpg", photos_assemblees([data, *suite])
    elif len(data) > 3 * 1024 * 1024:
        # une photo de telephone pese 12 a 18 Mo : on garde une version compressee, lisible
        ext, contenu = "jpg", image_compressee(data)
    else:
        ext, contenu = media_type.split("/")[1], data
    chemin = dossier / f"{sha}.{ext}"
    chemin.write_bytes(contenu)
    receipt.fichier_chemin = str(chemin.relative_to(config.UPLOAD_DIR))

    if statut == "ok":
        partager_prix(db, user, receipt)
    db.commit()
    return Resultat(receipt)


def partager_prix(db: Session, user: User, receipt: Receipt) -> None:
    """Prix anonymes : seulement avec l'accord, seulement pour un ticket juste, sans lien vers la personne."""
    if not (user.partage_consent and receipt.store is not None and receipt.achete_le):
        return
    for it in receipt.items:
        if it.illisible or it.montant <= 0:
            continue
        prix = it.prix_unitaire or (it.montant / it.quantite if it.quantite else it.montant)
        db.add(SharedPrice(store=receipt.store, libelle=it.libelle, product_id=it.product_id,
                           prix_unitaire=_dec(prix), prix_kg=it.prix_kg, jour=receipt.achete_le.date()))


def montant_saisi(texte: str) -> Optional[Decimal]:
    """« 5,29 », « 5.29 € » -> Decimal ; None si vide ou invalide."""
    texte = (texte or "").replace("€", "").replace(",", ".").strip()
    try:
        return _dec(texte) if texte else None
    except ArithmeticError:
        return None


def changer_magasin(db: Session, receipt: Receipt, enseigne: str, nom: str) -> None:
    if not enseigne_canonique(enseigne):
        return
    receipt.store = _magasin(db, {"enseigne": enseigne, "magasin": nom or enseigne})
    receipt.adresse_ok = False  # autre magasin : son adresse est a confirmer
    db.commit()


def confirmer_adresse(db: Session, receipt: Receipt, adresse: str, code_postal: str, ville: str) -> None:
    """La personne confirme (ou indique) l'adresse du magasin : le ticket est valide, le magasin la garde."""
    if receipt.store is not None:
        for champ, valeur, taille in (("adresse", adresse, 200), ("code_postal", code_postal, 10), ("ville", ville, 80)):
            valeur = " ".join((valeur or "").split())[:taille]
            if valeur:
                setattr(receipt.store, champ, valeur)
    # une seule confirmation par magasin : ses autres tickets sont valides aussi
    for r in db.scalars(select(Receipt).where(Receipt.user_id == receipt.user_id, Receipt.store_id == receipt.store_id)):
        r.adresse_ok = True
    receipt.adresse_ok = True
    db.commit()


def _adresse_deja_confirmee(db: Session, user: User, store: Optional[Store]) -> bool:
    if store is None or store.id is None:
        return False
    return db.scalar(select(func.count()).select_from(Receipt).where(
        Receipt.user_id == user.id, Receipt.store_id == store.id, Receipt.adresse_ok.is_(True))) > 0


def corriger_ticket(db: Session, user: User, receipt: Receipt, lignes: dict, nouvelle: Optional[tuple]) -> None:
    """lignes : {item_id: (libelle, montant)} ; nouvelle : (libelle, montant) a ajouter, ou None."""
    for it in receipt.items:
        if it.id in lignes:
            libelle, montant = lignes[it.id]
            if libelle:
                it.libelle = libelle[:120]
            if montant is not None:
                it.montant = montant
                it.illisible = False
    if nouvelle and nouvelle[0] and nouvelle[1] is not None:
        receipt.items.append(ReceiptItem(position=len(receipt.items), libelle=nouvelle[0][:120],
                                         quantite=Decimal("1"), montant=nouvelle[1]))
    receipt.somme_articles = sum((it.montant for it in receipt.items), Decimal("0"))
    etait_ok = receipt.statut == "ok"
    juste = receipt.total is not None and abs(receipt.somme_articles - receipt.remises_globales - receipt.total) <= TOLERANCE
    receipt.statut = "ok" if juste else "ecart"
    if juste and not etait_ok:
        partager_prix(db, user, receipt)
    db.commit()


def corriger_bio(db: Session) -> int:
    """Tickets deja enregistres : rattache les achats faits dans une enseigne bio au produit bio correspondant."""
    deplaces = 0
    items = db.scalars(select(ReceiptItem).join(Receipt).join(Store)
                       .where(ReceiptItem.product_id.is_not(None))).all()
    for it in items:
        if not est_bio(it.receipt.store.enseigne, it.receipt.store.nom):
            continue
        nom_bio = avec_bio(it.product.nom)
        if nom_bio == it.product.nom:
            continue
        cible = db.scalar(select(Product).where(Product.cle == cle_produit(nom_bio)))
        if cible is None:
            cible = Product(nom=nom_bio, cle=cle_produit(nom_bio), categorie=it.product.categorie,
                            famille=it.product.famille)
            db.add(cible)
            db.flush()
        enseigne = it.receipt.store.enseigne
        ancien = it.product_id
        it.product = cible
        # le meme libelle dans cette enseigne designe desormais le produit bio
        alias = db.scalar(select(ProductAlias).where(ProductAlias.enseigne == enseigne, ProductAlias.libelle == it.libelle))
        if alias:
            alias.product = cible
        for sp in db.scalars(select(SharedPrice).where(SharedPrice.store_id == it.receipt.store_id,
                                                       SharedPrice.libelle == it.libelle,
                                                       SharedPrice.product_id == ancien)):
            sp.product_id = cible.id
        deplaces += 1
    db.commit()
    return deplaces


def fusionner_magasins(db: Session) -> int:
    """Magasins deja enregistres en double (« MARKET PARIS JEAN JAURES » et « CARREFOUR MARKET PARIS JEAN JAURÈS ») :
    un seul magasin garde les tickets, les prix partages et l'adresse. Renvoie le nombre de doublons retires."""
    groupes = defaultdict(list)
    for store in db.scalars(select(Store).order_by(Store.id)):
        enseigne = enseigne_canonique(store.enseigne)
        groupes[(enseigne, cle_magasin(enseigne, store.nom))].append(store)
    retires = 0
    for (enseigne, _), stores in groupes.items():
        garde = max(stores, key=lambda st: (bool(st.adresse or st.code_postal), -st.id))  # celui qui a l'adresse
        for st in stores:
            if st is garde:
                continue
            for champ in ("adresse", "code_postal", "ville"):
                if not getattr(garde, champ) and getattr(st, champ):
                    setattr(garde, champ, getattr(st, champ))
            db.execute(update(Receipt).where(Receipt.store_id == st.id).values(store_id=garde.id))
            db.execute(update(SharedPrice).where(SharedPrice.store_id == st.id).values(store_id=garde.id))
            db.delete(st)
            retires += 1
        db.flush()
        garde.enseigne = enseigne
    db.flush()
    # une adresse confirmee pour un ticket vaut pour tous les tickets de ce magasin
    for store_id, user_id in db.execute(select(Receipt.store_id, Receipt.user_id)
                                        .where(Receipt.adresse_ok.is_(True)).distinct()).all():
        db.execute(update(Receipt).where(Receipt.store_id == store_id, Receipt.user_id == user_id)
                   .values(adresse_ok=True))
    db.commit()
    return retires
