#!/usr/bin/env python3
"""
POC - Analyse des courses a partir des CSV produits par parse_receipts.py
Calcule les KPI cles et les affiche / les sauvegarde dans data/kpis_summary.txt
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"


def load():
    receipts = pd.read_csv(DATA_DIR / "receipts.csv", parse_dates=["date"], dayfirst=True)
    items = pd.read_csv(DATA_DIR / "items.csv", parse_dates=["date"], dayfirst=True)
    receipts["mois"] = receipts["date"].dt.to_period("M")
    items["mois"] = items["date"].dt.to_period("M")
    return receipts, items


def section(title):
    return f"\n{'=' * 60}\n{title}\n{'=' * 60}"


def main():
    receipts, items = load()
    out = []

    # --- Vue d'ensemble ---------------------------------------------------
    out.append(section("VUE D'ENSEMBLE"))
    out.append(f"Periode couverte      : {receipts['date'].min().date()} -> {receipts['date'].max().date()}")
    out.append(f"Nombre de tickets     : {len(receipts)}")
    out.append(f"Depense totale        : {receipts['total'].sum():.2f} EUR")
    out.append(f"Panier moyen          : {receipts['total'].mean():.2f} EUR")
    out.append(f"Panier median         : {receipts['total'].median():.2f} EUR")

    # --- Depense par enseigne ----------------------------------------------
    out.append(section("DEPENSE PAR ENSEIGNE"))
    par_enseigne = receipts.groupby("enseigne").agg(
        nb_tickets=("receipt_id", "count"),
        total=("total", "sum"),
        panier_moyen=("total", "mean"),
    ).sort_values("total", ascending=False)
    par_enseigne["part_%"] = (par_enseigne["total"] / par_enseigne["total"].sum() * 100).round(1)
    out.append(par_enseigne.round(2).to_string())

    # --- Tendance mensuelle -------------------------------------------------
    out.append(section("DEPENSE PAR MOIS"))
    par_mois = receipts.groupby("mois").agg(
        nb_tickets=("receipt_id", "count"),
        total=("total", "sum"),
    )
    out.append(par_mois.round(2).to_string())

    # --- Depense par magasin (proxy "pres de chez vous") --------------------
    out.append(section("DEPENSE PAR MAGASIN"))
    par_magasin = receipts.groupby(["enseigne", "magasin"]).agg(
        nb_tickets=("receipt_id", "count"),
        total=("total", "sum"),
        panier_moyen=("total", "mean"),
    ).sort_values("total", ascending=False)
    out.append(par_magasin.round(2).to_string())

    # --- Depense par categorie (Monoprix/Naturalia uniquement) --------------
    out.append(section("DEPENSE PAR CATEGORIE (Monoprix/Naturalia - Carrefour ne detaille pas la categorie)"))
    cat_items = items[items["categorie"].notna()]
    par_cat = cat_items.groupby("categorie").agg(
        nb_articles=("produit", "count"),
        total=("montant", "sum"),
    ).sort_values("total", ascending=False)
    out.append(par_cat.round(2).to_string())

    # --- Top produits par depense cumulee ------------------------------------
    out.append(section("TOP 15 PRODUITS PAR DEPENSE CUMULEE"))
    top_depense = items.groupby("produit").agg(
        nb_achats=("montant", "count"),
        depense_totale=("montant", "sum"),
        prix_moyen=("montant", "mean"),
    ).sort_values("depense_totale", ascending=False).head(15)
    out.append(top_depense.round(2).to_string())

    # --- Top produits par frequence d'achat -----------------------------------
    out.append(section("TOP 15 PRODUITS PAR FREQUENCE D'ACHAT"))
    top_freq = items.groupby("produit").agg(
        nb_achats=("montant", "count"),
        depense_totale=("montant", "sum"),
    ).sort_values("nb_achats", ascending=False).head(15)
    out.append(top_freq.round(2).to_string())

    # --- Produits achetes plusieurs fois avec variation de prix ---------------
    out.append(section("PRODUITS RECURRENTS : VARIATION DE PRIX OBSERVEE (detection inflation perso)"))
    recurrents = items.groupby("produit").agg(
        nb_achats=("montant", "count"),
        prix_min=("montant", "min"),
        prix_max=("montant", "max"),
    )
    recurrents = recurrents[recurrents["nb_achats"] >= 3].copy()
    recurrents["ecart_%"] = ((recurrents["prix_max"] - recurrents["prix_min"]) / recurrents["prix_min"] * 100).round(1)
    recurrents = recurrents.sort_values("ecart_%", ascending=False).head(15)
    out.append(recurrents.round(2).to_string())

    # --- Frequence de visite ---------------------------------------------------
    out.append(section("FREQUENCE DE VISITE PAR ENSEIGNE"))
    nb_mois = receipts["mois"].nunique()
    freq = receipts.groupby("enseigne")["receipt_id"].count() / nb_mois
    out.append((freq.round(2).rename("visites_par_mois")).to_string())

    report = "\n".join(str(x) for x in out)
    print(report)

    with open(DATA_DIR / "kpis_summary.txt", "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n\nRapport sauvegarde -> {DATA_DIR / 'kpis_summary.txt'}")


if __name__ == "__main__":
    main()
