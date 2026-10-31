"""Fabrique app/data/rayons_fr.json : les rayons d'Open Food Facts (taxonomie des categories, licence ODbL) qui
comptent au moins 5 produits vendus en France, avec leurs noms et synonymes francais.

    python -m scripts.rayons                    # telecharge la taxonomie et l'export France (~1,5 Go lu en flux)
    python -m scripts.rayons produits_fr.tsv    # ou un export deja filtre (colonne categories_tags)

A relancer de temps en temps (quelques fois par an) : les rayons changent peu.
"""

import csv
import gzip
import io
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

from app.openprices import AGENT

TAXONOMIE = "https://raw.githubusercontent.com/openfoodfacts/openfoodfacts-server/main/taxonomies/food/categories.txt"
EXPORT = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
SORTIE = Path(__file__).resolve().parent.parent / "app" / "data" / "rayons_fr.json"
MINIMUM = 5


def _ouvrir(url: str):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=120)


def _slug(t: str) -> str:
    t = t.strip().lower().replace("œ", "oe").replace("æ", "ae")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def taxonomie(texte: str) -> dict:
    """id -> {"fr": [nom, synonymes...], "parents": [...]} pour les rayons qui ont un nom francais."""
    rayons = {}
    for bloc in re.split(r"\n\s*\n", texte):
        ident, parents, fr, commun = None, [], [], []
        for ligne in bloc.splitlines():
            if ligne.startswith("#"):
                continue
            m = re.match(r"<\s*([a-z]{2}):\s*(.+)", ligne)
            if m:
                parents.append(f"{m.group(1)}:{_slug(m.group(2))}")
                continue
            m = re.match(r"([a-z]{2}):\s*(.+)", ligne)
            if m:
                noms = [v.strip() for v in m.group(2).split(",") if v.strip()]
                if m.group(1) == "xx":  # meme nom dans toutes les langues (« Tofu »)
                    commun += noms
                    continue
                if ident is None and noms:
                    ident = f"{m.group(1)}:{_slug(noms[0])}"
                if m.group(1) == "fr":
                    fr = noms
        if ident and (fr or commun):
            rayons[ident] = {"fr": fr + [n for n in commun if n not in fr], "parents": parents}
    return rayons


def compter(lignes) -> Counter:
    """Nombre de produits vendus en France par rayon."""
    csv.field_size_limit(10**9)
    lecteur = csv.reader((l.replace("\0", "") for l in lignes), delimiter="\t", quoting=csv.QUOTE_NONE)
    entete = next(lecteur)
    cats, pays = entete.index("categories_tags"), entete.index("countries_tags") if "countries_tags" in entete else None
    compte = Counter()
    for l in lecteur:
        if len(l) == len(entete) and (pays is None or "en:france" in l[pays]):
            compte.update(c for c in l[cats].split(",") if c)
    return compte


def main():
    with _ouvrir(TAXONOMIE) as rep:
        rayons = taxonomie(rep.read().decode("utf-8"))
    if len(sys.argv) > 1:
        with open(sys.argv[1], newline="", encoding="utf-8") as f:
            compte = compter(f)
    else:
        with _ouvrir(EXPORT) as rep:
            compte = compter(io.TextIOWrapper(gzip.GzipFile(fileobj=rep), encoding="utf-8", errors="replace"))
    gardes = {k: {"fr": v["fr"], "parents": v["parents"], "n": compte[k]}
              for k, v in sorted(rayons.items()) if compte[k] >= MINIMUM}
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({"source": "Open Food Facts, taxonomie des catégories (ODbL)",
                                  "le": date.today().isoformat(), "rayons": gardes},
                                 ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(gardes)} rayons sur {len(rayons)} -> {SORTIE}")


if __name__ == "__main__":
    main()
