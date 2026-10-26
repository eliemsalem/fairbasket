"""Enregistrement d'un ticket : doublons, quota, lecture par l'IA, controle du total, prix partages."""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .lecture import Lecture, LectureImpossible, lire_ticket
from .models import Receipt, ReceiptItem, SharedPrice, Store, User, now

TOLERANCE = Decimal("0.02")
TYPES_ACCEPTES = {"application/pdf": "pdf", "image/jpeg": "photo", "image/png": "photo", "image/webp": "photo",
                  "image/heic": "photo"}


class TicketRefuse(Exception):
    """Ticket non enregistre, avec un message a montrer a l'utilisateur."""


@dataclass
class Resultat:
    receipt: Receipt
    doublon: bool = False


def _dec(v) -> Optional[Decimal]:
    return None if v is None else Decimal(str(v)).quantize(Decimal("0.01"))


def tickets_ce_mois(db: Session, user: User) -> int:
    debut = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(select(func.count()).select_from(Receipt).where(Receipt.user_id == user.id,
                                                                      Receipt.created_at >= debut))


def _magasin(db: Session, d: dict) -> Optional[Store]:
    enseigne = (d.get("enseigne") or "").strip()[:60]
    if enseigne.isupper():
        enseigne = enseigne.title()  # « MONOPRIX » et « Monoprix » sont la meme enseigne
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


def _date_achat(d: dict) -> Optional[datetime]:
    try:
        return datetime.strptime(f"{d.get('date')} {d.get('heure') or '00:00'}", "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


def enregistrer_ticket(db: Session, user: User, data: bytes, fichier_nom: str, media_type: str,
                       lire: Callable[[bytes, str], Lecture] = lire_ticket) -> Resultat:
    if media_type not in TYPES_ACCEPTES:
        raise TicketRefuse("Format non pris en charge : envoyez un PDF ou une photo (JPEG, PNG).")
    sha = hashlib.sha256(data).hexdigest()
    existant = db.scalar(select(Receipt).where(Receipt.user_id == user.id, Receipt.file_sha256 == sha))
    if existant:
        return Resultat(existant, doublon=True)
    if tickets_ce_mois(db, user) >= config.MAX_TICKETS_PAR_MOIS:
        raise TicketRefuse(f"Limite de {config.MAX_TICKETS_PAR_MOIS} tickets par mois atteinte.")

    try:
        lecture = lire(data, media_type)
    except LectureImpossible as e:
        raise TicketRefuse(str(e))
    d = lecture.donnees
    if not d.get("lisible"):
        raise TicketRefuse("Ce ticket n'a pas pu être lu. Reprenez la photo à plat, bien éclairée.")

    store = _magasin(db, d)
    achete_le = _date_achat(d)
    total = _dec(d.get("total"))
    remises = _dec(d.get("remises_globales")) or Decimal("0")
    items = [
        ReceiptItem(position=i, libelle=(a["libelle"] or "?")[:120], quantite=Decimal(str(a["quantite"] or 1)),
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
        remises_globales=remises, statut=statut, remarques=(d.get("remarques") or None),
        source=TYPES_ACCEPTES[media_type], fichier_nom=fichier_nom[:200], file_sha256=sha,
        modele=lecture.modele, tokens_entree=lecture.tokens_entree, tokens_sortie=lecture.tokens_sortie,
        items=items,
    )
    db.add(receipt)
    db.flush()

    # garde l'original (C9) : utile pour relire un ticket ou prouver un achat
    dossier = config.UPLOAD_DIR / str(user.id)
    dossier.mkdir(parents=True, exist_ok=True)
    ext = "pdf" if media_type == "application/pdf" else media_type.split("/")[1]
    chemin = dossier / f"{sha}.{ext}"
    chemin.write_bytes(data)
    receipt.fichier_chemin = str(chemin.relative_to(config.UPLOAD_DIR))

    # prix anonymes : seulement avec l'accord, seulement si le ticket est juste, sans lien vers la personne
    if user.partage_consent and statut == "ok" and store is not None and achete_le:
        for it in items:
            if it.illisible or it.montant <= 0:
                continue
            prix = it.prix_unitaire or (it.montant / it.quantite if it.quantite else it.montant)
            db.add(SharedPrice(store=store, libelle=it.libelle, prix_unitaire=_dec(prix), prix_kg=it.prix_kg,
                               jour=achete_le.date()))
    db.commit()
    return Resultat(receipt)
