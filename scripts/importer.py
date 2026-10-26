"""Importe des tickets (PDF, photos) dans le compte d'un utilisateur existant.

Usage : .venv/bin/python -m scripts.importer EMAIL FICHIER [FICHIER ...]
Les lectures par l'IA sont faites en parallele (facturees), l'enregistrement ensuite, un par un.
"""

import mimetypes
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app import config, tickets
from app.db import SessionLocal, init_db
from app.lecture import lire_ticket
from app.models import User
from scripts.test_lecture import PRIX, totaux_connus


def _lire(p: Path):
    try:
        return p, lire_ticket(p.read_bytes(), mimetypes.guess_type(p.name)[0]), None
    except Exception as e:  # on continue avec les autres tickets
        return p, None, e


def main(email, fichiers):
    init_db()
    db = SessionLocal()
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        sys.exit(f"Aucun compte pour {email} : inscrivez-vous d'abord.")
    config.MAX_TICKETS_PAR_MOIS = 10_000  # import de l'historique : pas de quota
    connus = totaux_connus()
    with ThreadPoolExecutor(max_workers=4) as pool:
        lectures = list(pool.map(_lire, [Path(f) for f in fichiers]))

    bilan = {"ok": 0, "ecart": 0, "doublon": 0, "refus": 0, "erreur": 0}
    faux, cout = [], 0.0
    pe, ps = PRIX.get(config.CLAUDE_MODEL, (0, 0))
    for p, lecture, err in lectures:
        if err:
            bilan["erreur"] += 1
            print(f"ERREUR {p.name} : {err}")
            continue
        cout += lecture.tokens_entree / 1e6 * pe + lecture.tokens_sortie / 1e6 * ps
        media = mimetypes.guess_type(p.name)[0]
        try:
            res = tickets.enregistrer_ticket(db, user, p.read_bytes(), p.name, media, lire=lambda d, m: lecture)
        except tickets.TicketRefuse as e:
            bilan["refus"] += 1
            print(f"REFUS {p.name} : {e}")
            continue
        r = res.receipt
        bilan["doublon" if res.doublon else r.statut] += 1
        attendu = connus.get(p.name)
        if attendu and r.total != Decimal(attendu).quantize(Decimal("0.01")):
            faux.append(f"{p.name} : lu {r.total}, attendu {attendu}")
    print(f"\n{len(fichiers)} fichiers : {bilan}")
    print(f"Totaux différents du POC : {len(faux)}")
    for f in faux:
        print("  " + f)
    print(f"Coût de lecture : {cout:.3f} $")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
