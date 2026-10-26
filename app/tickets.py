"""Enregistrement d'un ticket : doublons, quota, lecture par l'IA, controle du total, prix partages."""

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .lecture import Lecture, LectureImpossible, image_compressee, lire_ticket
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


# formats de magasin ramenes a leur enseigne : « Carrefour City » est un magasin Carrefour
FORMATS = {"carrefour": "Carrefour", "monop": "Monoprix", "monoprix": "Monoprix", "franprix": "Franprix",
           "intermarche": "Intermarché", "intermarché": "Intermarché", "auchan": "Auchan", "naturalia": "Naturalia",
           "biocoop": "Biocoop", "lidl": "Lidl", "aldi": "Aldi", "leclerc": "E.Leclerc", "e.leclerc": "E.Leclerc"}


def enseigne_canonique(enseigne: str) -> str:
    enseigne = " ".join((enseigne or "").split())[:60]
    premier = enseigne.split(" ")[0].lower().rstrip("'’") if enseigne else ""
    if premier in FORMATS:
        return FORMATS[premier]
    if enseigne.isupper() or enseigne.islower():
        enseigne = enseigne.title()  # « MONOPRIX » et « Monoprix » sont la meme enseigne
    return enseigne


def _magasin(db: Session, d: dict) -> Optional[Store]:
    enseigne = enseigne_canonique(d.get("enseigne") or "")
    nom = (d.get("magasin") or enseigne).strip().upper()[:120]
    if not enseigne:
        return None
    store = db.scalar(select(Store).where(Store.enseigne == enseigne, Store.nom == nom))
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


def _produit(db: Session, enseigne: str, libelle: str, nom: str, categorie: Optional[str]) -> Optional[Product]:
    """Retrouve le produit : d'abord par un libelle deja vu dans cette enseigne, sinon par son nom lisible."""
    if enseigne:
        alias = db.scalar(select(ProductAlias).where(ProductAlias.enseigne == enseigne, ProductAlias.libelle == libelle))
        if alias:
            return alias.product
    nom = " ".join((nom or "").split())[:120]
    if not nom or nom.lower() == "article illisible":
        return None
    produit = db.scalar(select(Product).where(Product.cle == cle_produit(nom)))
    if produit is None:
        produit = Product(nom=nom[0].upper() + nom[1:], cle=cle_produit(nom), categorie=categorie)
        db.add(produit)
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
                       lire: Optional[Callable[[bytes, str], Lecture]] = None, importe: bool = False) -> Resultat:
    if media_type not in TYPES_ACCEPTES:
        raise TicketRefuse("Format non pris en charge : envoyez un PDF ou une photo (JPEG, PNG).")
    sha = hashlib.sha256(data).hexdigest()
    existant = db.scalar(select(Receipt).where(Receipt.user_id == user.id, Receipt.file_sha256 == sha))
    if existant:
        return Resultat(existant, doublon=True)
    if not importe and tickets_ce_mois(db, user) >= config.MAX_TICKETS_PAR_MOIS:
        raise TicketRefuse("Limite de {n} tickets par mois atteinte.", n=config.MAX_TICKETS_PAR_MOIS)

    try:
        lecture = (lire or lire_ticket)(data, media_type)
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
    items = [
        ReceiptItem(position=i, libelle=(a["libelle"] or "?")[:120], quantite=Decimal(str(a["quantite"] or 1)),
                    product=None if a.get("illisible") else _produit(db, enseigne, (a["libelle"] or "?")[:120],
                                                                      a.get("nom"), a.get("categorie")),
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
    receipt = Receipt(
        user_id=user.id, store=store, achete_le=achete_le, total=total, somme_articles=somme,
        remises_globales=remises, statut=statut, remarques=(d.get("remarques") or None) and d["remarques"][:500],
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
    db.commit()


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
