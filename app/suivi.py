"""Suivi pour l'administration : qui utilise l'app, ou, combien de tickets passent, et ou ca bloque.

On note seulement le modele de la page (« /tickets/{receipt_id} », sans recherche ni contenu de ticket),
les resultats d'ajout de ticket et les erreurs. Garde 180 jours ; supprime avec le compte.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Avis, Evenement, Receipt, User

log = logging.getLogger("fairbasket.suivi")
GARDE_JOURS = 180

PAGES = {"/": "Inscription", "/connexion": "Connexion", "/auth/{token}": "Lien de connexion",
         "/presentation": "Présentation", "/accueil": "Accueil", "/comparer": "Comparer", "/liste": "Liste",
         "/liste/comparer": "Où faire mes courses", "/profil": "Profil", "/tickets/ajouter": "Ajouter un ticket",
         "/tickets/{receipt_id}": "Voir un ticket", "/tickets": "Envoi d'un ticket", "/avis": "Donner son avis",
         "/admin": "Administration"}
# pages qui ne disent rien de l'usage (fichiers, sondes, administration)
IGNOREES = ("/static", "/sw.js", "/health", "/admin", "/favicon")


def nom_page(page: Optional[str]) -> str:
    return PAGES.get(page or "", page or "—")


def noter(user_id: Optional[int], type: str, page: Optional[str] = None, detail: Optional[str] = None) -> None:
    """Note un evenement dans sa propre session : ne fait jamais echouer la page qui l'appelle."""
    try:
        with SessionLocal() as db:
            db.add(Evenement(user_id=user_id, type=type[:20], page=(page or "")[:80] or None,
                             detail=(detail or "")[:300] or None))
            db.commit()
    except Exception as e:
        log.warning("Suivi impossible (%s) : %s", type, e)


def purger(db: Session) -> None:
    db.execute(delete(Evenement).where(Evenement.quand < datetime.now(timezone.utc) - timedelta(days=GARDE_JOURS)))
    db.commit()


def _aware(d: Optional[datetime]) -> Optional[datetime]:
    return d.replace(tzinfo=timezone.utc) if d is not None and d.tzinfo is None else d


def tableau(db: Session) -> dict:
    """Tout ce que la page d'administration affiche."""
    maintenant = datetime.now(timezone.utc)
    il_y_a_7j = maintenant - timedelta(days=7)
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()

    tickets = defaultdict(Counter)  # user -> statut -> nombre
    for uid, statut, n in db.execute(select(Receipt.user_id, Receipt.statut, func.count()).group_by(Receipt.user_id,
                                                                                                    Receipt.statut)):
        tickets[uid][statut] += n
    evenements = db.scalars(select(Evenement).order_by(Evenement.quand)).all()
    vus, jours, derniere_page, refuses = {}, defaultdict(set), {}, Counter()
    for e in evenements:
        quand = _aware(e.quand)
        if e.user_id is not None:
            vus[e.user_id] = quand
            jours[e.user_id].add(quand.date())
            if e.type == "page":
                derniere_page[e.user_id] = e.page
            if e.type == "ticket_refuse":
                refuses[e.user_id] += 1

    lignes = []
    for u in users:
        t = tickets[u.id]
        lignes.append({"u": u, "vu": vus.get(u.id), "jours": len(jours[u.id]), "page": nom_page(derniere_page.get(u.id)),
                       "tickets": sum(t.values()), "ok": t["ok"], "a_verifier": t["ecart"],
                       "illisibles": t["illisible"] + t["erreur"], "refuses": refuses[u.id]})

    acceptes = [l for l in lignes if l["u"].statut == "actif"]
    entonnoir = [("Inscrits", len(lignes)), ("Acceptés", len(acceptes)),
                 ("Venus dans l'app", sum(1 for l in acceptes if l["jours"])),
                 ("Au moins 1 ticket", sum(1 for l in acceptes if l["tickets"])),
                 ("5 tickets ou plus", sum(1 for l in acceptes if l["tickets"] >= 5)),
                 ("Revenus un autre jour", sum(1 for l in acceptes if l["jours"] >= 2))]

    recents = [e for e in evenements if _aware(e.quand) >= il_y_a_7j]
    pages = Counter(nom_page(e.page) for e in recents if e.type == "page").most_common(12)
    resultats = Counter(e.type for e in evenements if e.type.startswith("ticket_"))
    blocages = Counter((e.type, e.detail or "—") for e in evenements
                       if e.type in ("ticket_refuse", "erreur") or (e.type == "connexion" and e.detail != "lien envoyé"))
    lectures = Counter("Code (sans IA)" if (r or "").startswith("code") and "+" not in (r or "") else
                       "Code + IA pour les noms" if (r or "").startswith("code") else "IA" if r else "—"
                       for r in db.scalars(select(Receipt.modele)))
    prenoms = {u.id: u.prenom for u in users}
    return {
        "chiffres": {"inscrits": len(lignes), "attente": len(lignes) - len(acceptes),
                     "actifs_7j": len({e.user_id for e in recents if e.user_id}),
                     "tickets": sum(l["tickets"] for l in lignes),
                     "tickets_7j": sum(1 for e in recents if e.type in ("ticket_ok", "ticket_ecart", "ticket_illisible",
                                                                          "ticket_erreur")),
                     "avis": db.scalar(select(func.count()).select_from(Avis).where(Avis.traite.is_(False)))},
        "utilisateurs": lignes, "entonnoir": entonnoir, "pages": pages, "resultats": resultats,
        "blocages": blocages.most_common(15), "lectures": lectures.most_common(),
        "derniers_problemes": [(e, prenoms.get(e.user_id, "—")) for e in reversed(evenements)
                               if e.type in ("ticket_refuse", "ticket_illisible", "ticket_erreur", "erreur")
                               or (e.type == "connexion" and e.detail != "lien envoyé")][:20],
        "avis": [(a, prenoms.get(a.user_id, "—")) for a in db.scalars(select(Avis).order_by(Avis.traite,
                                                                                            Avis.quand.desc()).limit(50))],
    }


def parcours(db: Session, user: User, limite: int = 150) -> list:
    """Les derniers evenements d'une personne, du plus recent au plus ancien."""
    return db.scalars(select(Evenement).where(Evenement.user_id == user.id)
                      .order_by(Evenement.quand.desc()).limit(limite)).all()
