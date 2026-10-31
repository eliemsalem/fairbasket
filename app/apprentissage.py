"""Bases d'apprentissage : tout ce qu'il faut garder pour ameliorer l'assistant et la lecture des tickets.

Lectures : chaque ticket lu (reussi ou non), avec son fichier, ce que le code ou Claude a lu, et ce que la
personne a corrige ensuite. La difference entre « lu » et « corrige » est exactement ce qu'il faut apprendre.
Questions : chaque question posee a l'assistant, aboutie ou non (voir app/assistant.py).

Tout part avec le compte (et une lecture avec son ticket) ; rien n'est garde plus de APPRENTISSAGE_JOURS.
"""

import io
import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import config
from .db import SessionLocal
from .models import LectureTicket, Question, Receipt, now

log = logging.getLogger("fairbasket.apprentissage")


def cout_usd(modele: Optional[str], entree: int, sortie: int, recherches_web: int = 0) -> float:
    prix = next((p for nom, p in config.PRIX_MODELES.items() if nom in (modele or "")), (0.0, 0.0))
    return round(entree / 1e6 * prix[0] + sortie / 1e6 * prix[1] + recherches_web * config.PRIX_RECHERCHE_WEB, 6)


def en_json(valeur):
    """Decimal, dates… -> types JSON (les lectures du code contiennent des Decimal)."""
    return json.loads(json.dumps(valeur, default=str)) if valeur is not None else None


def methode(modele: Optional[str]) -> Optional[str]:
    if not modele:
        return None
    if modele == "code":
        return "code"
    return "code+IA" if modele.startswith("code") else "IA"


def _dimensions(data: bytes) -> tuple[Optional[int], Optional[int]]:
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            return img.width, img.height
    except Exception:
        return None, None


def _garder_fichier(user_id: int, sha: str, data: bytes, media_type: str) -> Optional[str]:
    """Le fichier d'une lecture ratee : c'est l'exemple le plus utile pour ameliorer la lecture."""
    try:
        dossier = config.UPLOAD_DIR / str(user_id) / "apprentissage"
        dossier.mkdir(parents=True, exist_ok=True)
        ext = "pdf" if media_type == "application/pdf" else (media_type.split("/")[-1] or "bin")
        chemin = dossier / f"{sha}.{ext}"
        chemin.write_bytes(data)
        return str(chemin.relative_to(config.UPLOAD_DIR))
    except Exception as e:
        log.warning("Fichier d'apprentissage non garde : %s", e)
        return None


def instantane(receipt: Receipt) -> dict:
    """Le ticket tel qu'il est maintenant (apres les corrections de la personne)."""
    return en_json({
        "enseigne": receipt.store.enseigne if receipt.store else None,
        "magasin": receipt.store.nom if receipt.store else None,
        "adresse": receipt.store.adresse if receipt.store else None,
        "code_postal": receipt.store.code_postal if receipt.store else None,
        "date": receipt.achete_le.isoformat() if receipt.achete_le else None,
        "total": receipt.total, "remises_globales": receipt.remises_globales, "statut": receipt.statut,
        "articles": [{"libelle": it.libelle, "nom": it.product.nom if it.product else None,
                      "categorie": it.product.categorie if it.product else None,
                      "famille": it.product.famille if it.product else None, "quantite": it.quantite,
                      "prix_unitaire": it.prix_unitaire, "montant": it.montant, "remise": it.remise,
                      "poids_kg": it.poids_kg, "prix_kg": it.prix_kg, "illisible": it.illisible}
                     for it in receipt.items],
    })


def noter_lecture(user_id: int, sha: str, data: bytes, suite: Sequence[bytes], media_type: str, resultat: str,
                  lu: Optional[dict] = None, modele: Optional[str] = None, tokens: tuple = (0, 0),
                  duree_ms: int = 0, message: Optional[str] = None, receipt_id: Optional[int] = None) -> None:
    """Garde une lecture, dans sa propre session : ne fait jamais echouer l'ajout du ticket."""
    try:
        with SessionLocal() as db:
            receipt = db.get(Receipt, receipt_id) if receipt_id else None
            largeur, hauteur = (None, None) if media_type == "application/pdf" else _dimensions(data)
            articles = (lu or {}).get("articles") or []
            ecart = None
            if receipt is not None and receipt.total is not None and receipt.somme_articles is not None:
                ecart = float(receipt.total - (receipt.somme_articles + receipt.frais - receipt.remises_globales))
            db.add(LectureTicket(
                user_id=user_id, receipt_id=receipt_id, source="pdf" if media_type == "application/pdf" else "photo",
                media_type=media_type[:40], nb_fichiers=1 + len(suite), taille_octets=len(data) + sum(map(len, suite)),
                largeur=largeur, hauteur=hauteur,
                # le fichier d'un ticket enregistre est deja garde avec lui ; celui d'un echec est garde ici
                fichier_chemin=receipt.fichier_chemin if receipt is not None else
                _garder_fichier(user_id, sha, data, media_type) if resultat in ("illisible", "erreur") else None,
                methode=methode(modele), modele=(modele or "")[:40] or None, resultat=resultat,
                message=(message or "")[:300] or None, duree_ms=duree_ms, tokens_entree=tokens[0],
                tokens_sortie=tokens[1], cout_usd=cout_usd(modele, *tokens), enseigne=((lu or {}).get("enseigne") or "")[:60] or None,
                nb_articles=len(articles), nb_illisibles=sum(1 for a in articles if a.get("illisible")),
                ecart=ecart, lu=en_json(lu), corrige=instantane(receipt) if receipt is not None else None))
            db.commit()
    except Exception as e:
        log.warning("Lecture non gardee pour l'apprentissage : %s", e)


def figer(db: Session, receipt: Receipt) -> None:
    """Apres une correction : le ticket corrige est garde a cote de ce qui avait ete lu."""
    try:
        for lecture in db.scalars(select(LectureTicket).where(LectureTicket.receipt_id == receipt.id)):
            lecture.corrige = instantane(receipt)
            lecture.nb_corrections += 1
            lecture.corrige_le = now()
        db.commit()
    except Exception as e:
        db.rollback()
        log.warning("Correction non gardee pour l'apprentissage : %s", e)


def purger(db: Session) -> None:
    limite = datetime.now(timezone.utc) - timedelta(days=config.APPRENTISSAGE_JOURS)
    for chemin in db.scalars(select(LectureTicket.fichier_chemin).where(
            LectureTicket.quand < limite, LectureTicket.receipt_id.is_(None), LectureTicket.fichier_chemin.is_not(None))):
        (config.UPLOAD_DIR / chemin).unlink(missing_ok=True)
    db.execute(delete(LectureTicket).where(LectureTicket.quand < limite))
    db.execute(delete(Question).where(Question.quand < limite))
    db.commit()


def _debut_du_mois() -> datetime:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def tableau_lectures(db: Session) -> dict:
    lectures = db.scalars(select(LectureTicket).order_by(LectureTicket.quand.desc())).all()
    mois = _debut_du_mois()
    par_methode = Counter((l.methode or "—", l.resultat) for l in lectures)
    methodes = sorted({m for m, _ in par_methode})
    corrigees = [l for l in lectures if l.nb_corrections]
    lues = [l for l in lectures if l.resultat in ("ok", "ecart")]
    return {
        "chiffres": {"lectures": len(lectures), "reussies": sum(1 for l in lectures if l.resultat == "ok"),
                     "a_verifier": sum(1 for l in lectures if l.resultat == "ecart"),
                     "ratees": sum(1 for l in lectures if l.resultat in ("illisible", "erreur")),
                     "corrigees": len(corrigees),
                     "sans_ia": round(100 * sum(1 for l in lues if l.methode == "code") / len(lues)) if lues else None,
                     "cout_mois": sum(l.cout_usd for l in lectures if _aware(l.quand) >= mois),
                     "duree": round(sum(l.duree_ms for l in lues) / len(lues) / 1000, 1) if lues else None},
        "methodes": [(m, {r: par_methode[(m, r)] for r in ("ok", "ecart", "illisible", "erreur", "doublon")})
                     for m in methodes],
        "enseignes": Counter((l.enseigne or "—", l.resultat) for l in lectures),
        "a_etudier": [l for l in lectures if l.resultat in ("illisible", "erreur", "ecart") or l.nb_corrections][:40],
    }


def _aware(d: datetime) -> datetime:
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def tableau_questions(db: Session) -> dict:
    questions = db.scalars(select(Question).order_by(Question.quand.desc())).all()
    mois = _debut_du_mois()
    n = len(questions) or 1
    return {
        "chiffres": {"questions": len(questions),
                     "trouvees": round(100 * sum(q.trouve for q in questions) / n) if questions else None,
                     "sans_claude": round(100 * sum(q.moteur != "claude" for q in questions) / n) if questions else None,
                     "utiles": sum(1 for q in questions if q.note == 1),
                     "pas_utiles": sum(1 for q in questions if q.note == -1),
                     "cout_mois": sum(q.cout_usd for q in questions if _aware(q.quand) >= mois),
                     "web": sum(q.recherches_web for q in questions),
                     "duree": round(sum(q.duree_ms for q in questions) / n / 1000, 1) if questions else None},
        "moteurs": Counter(q.moteur for q in questions).most_common(),
        "intentions": Counter(q.intention or "non comprise" for q in questions).most_common(),
        "sans_reponse": [q for q in questions if not q.trouve][:30],
        "pas_utiles": [q for q in questions if q.note == -1][:30],
        "frequentes": Counter(q.cle for q in questions).most_common(15),
        "dernieres": questions[:30],
    }


def _ligne(objet, colonnes) -> str:
    return json.dumps({c: en_json(getattr(objet, c)) if not isinstance(getattr(objet, c), datetime)
                       else getattr(objet, c).isoformat() for c in colonnes}, ensure_ascii=False)


def exporter(db: Session, modele) -> Iterator[str]:
    """Une ligne JSON par enregistrement (JSONL), sans l'identite des personnes : pret pour un jeu de test."""
    colonnes = [c.name for c in modele.__table__.columns if c.name != "user_id"]
    for objet in db.scalars(select(modele).order_by(modele.id)).yield_per(200):
        yield _ligne(objet, colonnes) + "\n"
