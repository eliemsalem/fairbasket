"""Teste la lecture par l'IA sur quelques vrais tickets dont on connait deja le total (POC).

Usage : .venv/bin/python -m scripts.test_lecture FICHIER [FICHIER ...]
Chaque appel est facture sur le compte Anthropic.
"""

import csv
import mimetypes
import sys
import time
from decimal import Decimal
from pathlib import Path

from app import config
from app.lecture import lire_ticket

# prix publics par million de jetons (entree, sortie), en dollars
PRIX = {"claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0)}
PHOTOS = {"IMG20261026093257.jpg": "69.76", "IMG20261026093326.jpg": "14.97", "IMG20261026093330.jpg": "13.78",
          "IMG20261026093304.jpg": "9.60", "IMG20260904123402.jpg": "53.07", "IMG20260908163356.jpg": "13.03"}


def totaux_connus():
    with open(config.ROOT / "poc/data/receipts.csv", encoding="utf-8") as f:
        connus = {r["fichier"]: r["total"] for r in csv.DictReader(f) if r["total"]}
    connus.update(PHOTOS)
    return connus


def main(fichiers):
    connus = totaux_connus()
    cout_total = 0.0
    print(f"Modèle : {config.CLAUDE_MODEL} · effort : {config.CLAUDE_EFFORT}\n")
    for f in fichiers:
        p = Path(f)
        media = mimetypes.guess_type(p.name)[0]
        t0 = time.time()
        lecture = lire_ticket(p.read_bytes(), media)
        d = lecture.donnees
        attendu = Decimal(connus[p.name]) if p.name in connus else None
        total = Decimal(str(d["total"])) if d["total"] is not None else None
        somme = sum(Decimal(str(a["montant"])) for a in d["articles"]) - Decimal(str(d["remises_globales"]))
        pe, ps = PRIX.get(config.CLAUDE_MODEL, (0, 0))
        cout = lecture.tokens_entree / 1e6 * pe + lecture.tokens_sortie / 1e6 * ps
        cout_total += cout
        ok_total = "✓" if attendu is not None and total == attendu else "✗"
        ok_somme = "✓" if total is not None and abs(somme - total) <= Decimal("0.02") else "✗"
        illisibles = sum(a["illisible"] for a in d["articles"])
        print(f"{p.name[:46]:46} {d['enseigne'][:10]:10} {d['date']} total {total} (attendu {attendu}) {ok_total} "
              f"| somme {somme:.2f} {ok_somme} | {len(d['articles'])} art."
              f"{f', {illisibles} illisible(s)' if illisibles else ''} | {time.time() - t0:.0f} s | {cout:.4f} $")
        if d.get("remarques"):
            print(f"    remarque : {d['remarques']}")
    print(f"\nCoût total : {cout_total:.3f} $ · moyenne {cout_total / len(fichiers):.4f} $ par ticket")


if __name__ == "__main__":
    main(sys.argv[1:])
