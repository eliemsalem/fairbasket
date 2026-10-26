#!/usr/bin/env python3
"""
Ajoute au dataset les 7 tickets photographies (dossier "Appareil photo") :
- un ticket de marche primeur (produits non identifiables : COMPTAGE LIBRE / PRIX LIBRE)
- deux tickets Biocoop Canal Bio (detailles)
- trois tickets Auchan (detailles)
- un ticket Aldi rue de Meaux (detaille)
Ces tickets sont lus manuellement (photos, pas de texte extractible) et ajoutes
aux CSV existants generes par parse_receipts.py.
"""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

NEW_RECEIPTS = [
    {
        "receipt_id": "Photo-20260901-Marche",
        "enseigne": "Marche (non identifie)",
        "magasin": "Marche primeur (nom illisible sur photo)",
        "ville": None,
        "date": "01/09/2026 10:09",
        "total": 46.46,
        "nb_articles_extraits": 0,
        "fichier": "IMG20260903105019.jpg (produits non identifiables)",
    },
    {
        "receipt_id": "Photo-20260904-Biocoop",
        "enseigne": "Biocoop",
        "magasin": "BIOCOOP CANAL BIO",
        "ville": "46bis Quai de la Loire, 75019 Paris",
        "date": "04/09/2026 12:21",
        "total": 53.07,
        "nb_articles_extraits": 12,
        "fichier": "IMG20260904123402.jpg",
    },
    {
        "receipt_id": "Photo-20260908-Auchan",
        "enseigne": "Auchan",
        "magasin": "AUCHAN (adresse non visible sur le ticket)",
        "ville": None,
        "date": "08/09/2026 16:21",
        "total": 13.03,
        "nb_articles_extraits": 5,
        "fichier": "IMG20260908163356.jpg",
    },
    {
        "receipt_id": "Photo-20260925-Aldi",
        "enseigne": "Aldi",
        "magasin": "ALDI RUE DE MEAUX",
        "ville": "85/87 Rue de Meaux, 75019 Paris",
        "date": "25/09/2026 18:11",
        "total": 14.97,
        "nb_articles_extraits": 9,
        "fichier": "IMG20261026093326.jpg",
    },
    {
        "receipt_id": "Photo-20260928-Auchan",
        "enseigne": "Auchan",
        "magasin": "AUCHAN (adresse non visible sur le ticket)",
        "ville": None,
        "date": "28/09/2026 16:42",
        "total": 13.78,
        "nb_articles_extraits": 3,
        "fichier": "IMG20261026093330.jpg",
    },
    {
        "receipt_id": "Photo-20261015-Biocoop",
        "enseigne": "Biocoop",
        "magasin": "BIOCOOP CANAL BIO",
        "ville": "46bis Quai de la Loire, 75019 Paris",
        "date": "15/10/2026 11:31",
        "total": 69.76,
        "nb_articles_extraits": 14,
        "fichier": "IMG20261026093257.jpg",
    },
    {
        "receipt_id": "Photo-20261023-Auchan",
        "enseigne": "Auchan",
        "magasin": "AUCHAN (adresse non visible sur le ticket)",
        "ville": None,
        "date": "23/10/2026 16:26",
        "total": 9.60,
        "nb_articles_extraits": 5,
        "fichier": "IMG20261026093304.jpg",
    },
]

NEW_ITEMS = [
    # Biocoop
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "Miel clementinier 400g", "qte": 1, "prix_unitaire": None, "montant": 9.05, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "KEFIR 1L CC", "qte": 1, "prix_unitaire": None, "montant": 2.65, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "Ravioli aubergines huile olive", "qte": 1, "prix_unitaire": None, "montant": 5.10, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "TOFU FUME AMANDE SESAME 200G", "qte": 1, "prix_unitaire": None, "montant": 3.60, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "TOFU ROSSO OLIVES ET TOMATES", "qte": 1, "prix_unitaire": None, "montant": 3.40, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "FILET TOFU AIL DES OURS 2X80G", "qte": 1, "prix_unitaire": None, "montant": 2.60, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "KEFIR CITRON 75CL", "qte": 1, "prix_unitaire": None, "montant": 4.08, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "OEUFS BIOCOOP (6) CAL 53/63", "qte": 1, "prix_unitaire": None, "montant": 2.82, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "OEUFS BIOCOOP (6) CAL 53/63", "qte": 1, "prix_unitaire": None, "montant": 2.82, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "Cafe melange Exception grains", "qte": 1, "prix_unitaire": None, "montant": 12.30, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "RUBAN SPIRULINE AUX OEUFS 250G", "qte": 1, "prix_unitaire": None, "montant": 3.35, "tva": None},
    {"receipt_id": "Photo-20260904-Biocoop", "enseigne": "Biocoop", "date": "04/09/2026 12:21",
     "categorie": None, "produit": "BANANES", "qte": 1, "prix_unitaire": 2.05, "montant": 1.30, "tva": None},
    # Auchan
    {"receipt_id": "Photo-20260908-Auchan", "enseigne": "Auchan", "date": "08/09/2026 16:21",
     "categorie": None, "produit": "SPECK", "qte": 1, "prix_unitaire": None, "montant": 4.29, "tva": None},
    {"receipt_id": "Photo-20260908-Auchan", "enseigne": "Auchan", "date": "08/09/2026 16:21",
     "categorie": None, "produit": "BIO PAIN CEREALES", "qte": 1, "prix_unitaire": None, "montant": 2.19, "tva": None},
    {"receipt_id": "Photo-20260908-Auchan", "enseigne": "Auchan", "date": "08/09/2026 16:21",
     "categorie": None, "produit": "FE PARMIG REGG AOP", "qte": 1, "prix_unitaire": None, "montant": 2.99, "tva": None},
    {"receipt_id": "Photo-20260908-Auchan", "enseigne": "Auchan", "date": "08/09/2026 16:21",
     "categorie": None, "produit": "AUCHAN TORTELLINI", "qte": 1, "prix_unitaire": None, "montant": 2.47, "tva": None},
    {"receipt_id": "Photo-20260908-Auchan", "enseigne": "Auchan", "date": "08/09/2026 16:21",
     "categorie": None, "produit": "ANANAS CROWNLESS P", "qte": 1, "prix_unitaire": None, "montant": 1.09, "tva": None},
    # Aldi 25/09/2026
    {"receipt_id": "Photo-20260925-Aldi", "enseigne": "Aldi", "date": "25/09/2026 18:11",
     "categorie": None, "produit": "OIGNONS ROUGE 500G", "qte": 1, "prix_unitaire": None, "montant": 0.95, "tva": None},
    {"receipt_id": "Photo-20260925-Aldi", "enseigne": "Aldi", "date": "25/09/2026 18:11",
     "categorie": None, "produit": "VINAIGRE BLANC 1L", "qte": 1, "prix_unitaire": None, "montant": 0.39, "tva": None},
    {"receipt_id": "Photo-20260925-Aldi", "enseigne": "Aldi", "date": "25/09/2026 18:11",
     "categorie": None, "produit": "POIS CHICHES ORIENTAUX", "qte": 1, "prix_unitaire": None, "montant": 1.09, "tva": None},
    {"receipt_id": "Photo-20260925-Aldi", "enseigne": "Aldi", "date": "25/09/2026 18:11",
     "categorie": None, "produit": "CITRONS JAUNE 500G", "qte": 1, "prix_unitaire": None, "montant": 0.99, "tva": None},
    {"receipt_id": "Photo-20260925-Aldi", "enseigne": "Aldi", "date": "25/09/2026 18:11",
     "categorie": None, "produit": "PDT CONSO CHAIR .. 1K", "qte": 1, "prix_unitaire": None, "montant": 0.99, "tva": None},
    {"receipt_id": "Photo-20260925-Aldi", "enseigne": "Aldi", "date": "25/09/2026 18:11",
     "categorie": None, "produit": "CAROTTES BIO ..", "qte": 1, "prix_unitaire": None, "montant": 1.99, "tva": None},
    {"receipt_id": "Photo-20260925-Aldi", "enseigne": "Aldi", "date": "25/09/2026 18:11",
     "categorie": None, "produit": "COTES DE PORC .. 700", "qte": 1, "prix_unitaire": None, "montant": 5.29, "tva": None},
    {"receipt_id": "Photo-20260925-Aldi", "enseigne": "Aldi", "date": "25/09/2026 18:11",
     "categorie": None, "produit": "AUBERGINE 500G", "qte": 1, "prix_unitaire": None, "montant": 0.99, "tva": None},
    {"receipt_id": "Photo-20260925-Aldi", "enseigne": "Aldi", "date": "25/09/2026 18:11",
     "categorie": None, "produit": "CELERI BRANCHE", "qte": 1, "prix_unitaire": None, "montant": 2.29, "tva": None},
    # Auchan 28/09/2026
    {"receipt_id": "Photo-20260928-Auchan", "enseigne": "Auchan", "date": "28/09/2026 16:42",
     "categorie": None, "produit": "AUCH BIOD CAFE GRA..", "qte": 1, "prix_unitaire": None, "montant": 9.60, "tva": None},
    {"receipt_id": "Photo-20260928-Auchan", "enseigne": "Auchan", "date": "28/09/2026 16:42",
     "categorie": None, "produit": "BIO BANANE FAIRTRA..", "qte": 1, "prix_unitaire": None, "montant": 1.99, "tva": None},
    {"receipt_id": "Photo-20260928-Auchan", "enseigne": "Auchan", "date": "28/09/2026 16:42",
     "categorie": None, "produit": "BIO PAIN CEREALES", "qte": 1, "prix_unitaire": None, "montant": 2.19, "tva": None},
    # Biocoop 15/10/2026
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "boule aux graines 400gr (remise 30%)", "qte": 1, "prix_unitaire": None, "montant": 2.90, "tva": None, "prix_kg": 10.37},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "OEUFS BIOCOOP(10) CAL 53/63", "qte": 1, "prix_unitaire": None, "montant": 4.65, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "BLEU CREMEUX 30%MG 150G", "qte": 1, "prix_unitaire": None, "montant": 4.70, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "SPIRALE COMPLET 500G", "qte": 1, "prix_unitaire": None, "montant": 1.55, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "MANGUE", "qte": 1, "prix_unitaire": 2.5, "montant": 2.50, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "PATE A TARTINER MIEL SPIRULINE", "qte": 1, "prix_unitaire": None, "montant": 9.95, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "Cafe Altura Mexique en vrac", "qte": 1, "prix_unitaire": None, "montant": 14.33, "tva": None, "prix_kg": 31.5},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "BEURRE DEMI-SEL DE BARATTE 250", "qte": 1, "prix_unitaire": None, "montant": 3.50, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "KEFIR 1L CC", "qte": 1, "prix_unitaire": None, "montant": 2.65, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "Miel clementinier 400g", "qte": 1, "prix_unitaire": None, "montant": 9.05, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "KEFIR CITRON 75CL", "qte": 1, "prix_unitaire": None, "montant": 4.08, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "TOFU FUME AMANDE SESAME 200G", "qte": 1, "prix_unitaire": None, "montant": 3.60, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "SUPREME TOFU TOMATE SECHEE BAS", "qte": 1, "prix_unitaire": None, "montant": 3.05, "tva": None},
    {"receipt_id": "Photo-20261015-Biocoop", "enseigne": "Biocoop", "date": "15/10/2026 11:31",
     "categorie": None, "produit": "Tofu grille a l'Orientale 2x70", "qte": 1, "prix_unitaire": None, "montant": 3.25, "tva": None},
    # Auchan 23/10/2026
    {"receipt_id": "Photo-20261023-Auchan", "enseigne": "Auchan", "date": "23/10/2026 16:26",
     "categorie": None, "produit": "POUCE VINAIGRE ALC..", "qte": 1, "prix_unitaire": None, "montant": 0.43, "tva": None},
    {"receipt_id": "Photo-20261023-Auchan", "enseigne": "Auchan", "date": "23/10/2026 16:26",
     "categorie": None, "produit": "MYRTILLE 125G", "qte": 1, "prix_unitaire": None, "montant": 2.99, "tva": None},
    {"receipt_id": "Photo-20261023-Auchan", "enseigne": "Auchan", "date": "23/10/2026 16:26",
     "categorie": None, "produit": "FRAMBOISE 125G", "qte": 1, "prix_unitaire": None, "montant": 2.49, "tva": None},
    {"receipt_id": "Photo-20261023-Auchan", "enseigne": "Auchan", "date": "23/10/2026 16:26",
     "categorie": None, "produit": "AUC OEUFS DJP SOL X6", "qte": 1, "prix_unitaire": None, "montant": 1.50, "tva": None},
    {"receipt_id": "Photo-20261023-Auchan", "enseigne": "Auchan", "date": "23/10/2026 16:26",
     "categorie": None, "produit": "BIO PAIN CEREALES", "qte": 1, "prix_unitaire": None, "montant": 2.19, "tva": None},
]


def main():
    receipts_path = DATA_DIR / "receipts.csv"
    items_path = DATA_DIR / "items.csv"

    with open(receipts_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    existing_ids = {r["receipt_id"] for r in rows}
    added = [r for r in NEW_RECEIPTS if r["receipt_id"] not in existing_ids]
    rows.extend(added)
    with open(receipts_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with open(items_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    existing_ids = {r["receipt_id"] for r in rows}
    added_items = [r for r in NEW_ITEMS if r["receipt_id"] not in existing_ids]
    rows.extend(added_items)
    with open(items_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"{len(added)} nouveaux tickets ajoutes a receipts.csv")
    print(f"{len(added_items)} nouveaux articles ajoutes a items.csv")


if __name__ == "__main__":
    main()
