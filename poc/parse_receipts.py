#!/usr/bin/env python3
"""
POC - Parsing de tickets de caisse (Carrefour, Monoprix, Naturalia)

Lit les PDF dans ../Carrefour, ../Monoprix, ../Naturalia (texte natif, pas de scan),
en extrait magasin / ville / date / produits / prix / categorie,
et ecrit deux CSV consolides dans data/ :
  - receipts.csv : un ticket par ligne
  - items.csv    : une ligne d'article par ligne (produit, prix, categorie...)
"""

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENSEIGNES = ["Carrefour", "Monoprix", "Naturalia"]
OUT_DIR = Path(__file__).resolve().parent / "data"


def pdf_to_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def to_float(s: str) -> float:
    return float(s.replace(",", ".").replace("€", "").strip())


# ---------------------------------------------------------------------------
# Parsing Carrefour
# ---------------------------------------------------------------------------
CARREFOUR_ITEM_RE = re.compile(
    r"^\s*(?P<tva>\d+[.,]\d+)%\s+(?P<name>.+?)\s+(?P<qte>\d+)\s*x\s*(?P<pu>[\d.,]+)\s+(?P<montant>[\d.,]+)\s*$"
)
CARREFOUR_DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s+à\s+(\d{2})h(\d{2})")
CARREFOUR_TOTAL_RE = re.compile(r"Total à payer\s+([\d.,]+)\s*€")
# ligne de pesee juste apres un article vendu au poids, ex: "0.196kg x 20.90€/kg"
WEIGHT_RE = re.compile(r"^\s*[\d.,]+\s*kg\s*x\s*([\d.,]+)\s*€\s*/\s*kg", re.IGNORECASE)


def parse_carrefour(text: str, filename: str):
    lines = text.split("\n")
    magasin = next((l.strip() for l in lines if l.strip()), "")

    m = CARREFOUR_DATE_RE.search(text)
    date = f"{m.group(1)} {m.group(2)}:{m.group(3)}" if m else None

    m = CARREFOUR_TOTAL_RE.search(text)
    total = to_float(m.group(1)) if m else None

    items = []
    for line in lines:
        m = CARREFOUR_ITEM_RE.match(line)
        if m:
            items.append({
                "categorie": None,
                "produit": m.group("name").strip(),
                "qte": int(m.group("qte")),
                "prix_unitaire": to_float(m.group("pu")),
                "montant": to_float(m.group("montant")),
                "tva": m.group("tva"),
                "prix_kg": None,
            })
            continue
        w = WEIGHT_RE.match(line)
        if w and items:
            items[-1]["prix_kg"] = to_float(w.group(1))

    return {"magasin": magasin, "ville": None, "date": date, "total": total}, items


# ---------------------------------------------------------------------------
# Parsing Monoprix / Naturalia (meme format de caisse)
# ---------------------------------------------------------------------------
CATEGORY_RE = re.compile(r"^([A-ZÀÉÈÀÙÂÊÎÔÛ][A-ZÀÉÈÀÙÂÊÎÔÛ/ .]+)\.{3,}\s*$")
# ligne d'article: [qte X] nom .... [pu€] montant€   (au moins 2 espaces avant le prix)
ITEM_RE = re.compile(
    r"^\s*(?:(?P<qte>\d+)X\s+)?(?P<name>[^\d].*?)\s{2,}(?:(?P<pu>[\d.,]+)€\s{2,})?(?P<montant>[\d.,]+)€\s*$"
)
SKIP_PATTERNS = re.compile(
    r"scanner X|€/kg|Le \d.*moins|TOTAL|NOMBRE ARTICLES|H\.T\.|T\.V\.A\.|Total TVA|MONTANT|^\d+[.,]\d+%"
)
# ligne de pesee juste apres un article vendu au poids, ex:
# "0.126kg scanner X 20.50 €/kg" ou "0.280kg manuelle X 24.99 €/kg"
MONOPRIX_WEIGHT_RE = re.compile(r"^\s*[\d.,]+\s*kg\s+\S+\s+X\s+([\d.,]+)\s*€\s*/\s*kg", re.IGNORECASE)
ADDRESS_RE = re.compile(r"^\s*\d{5}\s+(.+?)\s*$")
DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})")
TOTAL_HA_RE = re.compile(r"TOTAL HORS AVANTAGES\s+([\d.,]+)€")
RESTE_A_PAYER_RE = re.compile(r"RESTE A PAYER\s+([\d.,]+)€")
# depuis sept. 2026 les tickets Monoprix commencent par "Bonjour Mme, M." sans nom
# de magasin : on le deduit du code magasin en tete du numero de ticket
STORE_CODES = {
    "0292": ("MONOPRIX CRIMEE", "PARIS"),
    "0325": ("MONO BELVEDERE", "PARIS"),
}


def parse_monoprix_style(text: str, filename: str):
    lines = text.split("\n")
    magasin = next((l.strip() for l in lines if l.strip()), "")
    if magasin.startswith("Bonjour"):
        m = re.match(r"Ticket-(\d{4})", filename)
        magasin, ville = STORE_CODES.get(m.group(1) if m else "", ("INCONNU", None))
        header_ville = ville
    else:
        header_ville = None

    ville = header_ville
    for line in lines[:6]:
        m = ADDRESS_RE.match(line)
        if m:
            ville = m.group(1).strip()
            break

    m = DATE_RE.search(text)
    date = f"{m.group(1)} {m.group(2)}" if m else None

    m = RESTE_A_PAYER_RE.search(text)
    if m:
        total = to_float(m.group(1))
    else:
        m = TOTAL_HA_RE.search(text)
        total = to_float(m.group(1)) if m else None

    items = []
    current_cat = None
    for line in lines:
        if "TOTAL HORS AVANTAGES" in line:
            break
        cat_m = CATEGORY_RE.match(line)
        if cat_m:
            current_cat = cat_m.group(1).strip()
            continue
        w = MONOPRIX_WEIGHT_RE.match(line)
        if w and items:
            items[-1]["prix_kg"] = to_float(w.group(1))
            continue
        if SKIP_PATTERNS.search(line):
            continue
        m = ITEM_RE.match(line)
        if m:
            name = m.group("name").strip()
            if not name or name.isupper() is False and len(name) < 2:
                continue
            items.append({
                "categorie": current_cat,
                "produit": name,
                "qte": int(m.group("qte")) if m.group("qte") else 1,
                "prix_unitaire": to_float(m.group("pu")) if m.group("pu") else None,
                "montant": to_float(m.group("montant")),
                "tva": None,
                "prix_kg": None,
            })

    return {"magasin": magasin, "ville": ville, "date": date, "total": total}, items


def main():
    receipts_rows = []
    items_rows = []
    errors = []

    for enseigne in ENSEIGNES:
        folder = ROOT / enseigne
        if not folder.is_dir():
            continue
        for pdf_path in sorted(folder.glob("*.pdf")):
            try:
                text = pdf_to_text(pdf_path)
                if enseigne == "Carrefour":
                    header, items = parse_carrefour(text, pdf_path.name)
                else:
                    header, items = parse_monoprix_style(text, pdf_path.name)

                receipt_id = pdf_path.stem
                receipts_rows.append({
                    "receipt_id": receipt_id,
                    "enseigne": enseigne,
                    "magasin": header["magasin"],
                    "ville": header["ville"],
                    "date": header["date"],
                    "total": header["total"],
                    "nb_articles_extraits": len(items),
                    "fichier": pdf_path.name,
                })
                for it in items:
                    it["receipt_id"] = receipt_id
                    it["enseigne"] = enseigne
                    it["date"] = header["date"]
                    items_rows.append(it)

                if header["total"] is None:
                    errors.append(f"[{enseigne}] {pdf_path.name}: total non trouve")
                if not items:
                    errors.append(f"[{enseigne}] {pdf_path.name}: aucun article extrait")
            except Exception as e:
                errors.append(f"[{enseigne}] {pdf_path.name}: ERREUR {e}")

    OUT_DIR.mkdir(exist_ok=True)

    with open(OUT_DIR / "receipts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "receipt_id", "enseigne", "magasin", "ville", "date", "total",
            "nb_articles_extraits", "fichier",
        ])
        w.writeheader()
        w.writerows(receipts_rows)

    with open(OUT_DIR / "items.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "receipt_id", "enseigne", "date", "categorie", "produit", "qte",
            "prix_unitaire", "montant", "tva", "prix_kg",
        ])
        w.writeheader()
        w.writerows(items_rows)

    print(f"{len(receipts_rows)} tickets traites -> {OUT_DIR/'receipts.csv'}")
    print(f"{len(items_rows)} articles extraits -> {OUT_DIR/'items.csv'}")
    if errors:
        print(f"\n{len(errors)} avertissement(s):")
        for e in errors[:30]:
            print(" -", e)
        if len(errors) > 30:
            print(f"   ... et {len(errors) - 30} de plus")


if __name__ == "__main__":
    sys.exit(main())
