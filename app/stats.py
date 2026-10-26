"""Calculs du tableau de bord, a partir des tickets d'un seul utilisateur."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Receipt, ReceiptItem, User

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
ZERO = Decimal("0")


def _ajoute_mois(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


@dataclass
class Tableau:
    periode: str
    libelle_periode: str
    total: Decimal = ZERO
    nb_tickets: int = 0
    panier_moyen: Optional[Decimal] = None
    evolution: Optional[int] = None  # en %, par rapport a la periode precedente
    libelle_comparaison: str = ""
    mois: list = field(default_factory=list)
    enseignes: list = field(default_factory=list)
    categories: list = field(default_factory=list)
    produits: list = field(default_factory=list)
    alertes: list = field(default_factory=list)


def _prix_unitaire(it: ReceiptItem) -> Optional[Decimal]:
    if it.poids_kg:  # vendu au poids : pas comparable a l'unite
        return None
    if it.prix_unitaire:
        return it.prix_unitaire
    return (it.montant / it.quantite).quantize(Decimal("0.01")) if it.quantite else None


def tableau_de_bord(db: Session, user: User, periode: str = "an", aujourd_hui: Optional[date] = None) -> Tableau:
    aujourd_hui = aujourd_hui or date.today()
    mois_courant = aujourd_hui.replace(day=1)
    if periode == "mois":
        debut, fin = mois_courant, _ajoute_mois(mois_courant, 1)
        debut_prec = _ajoute_mois(mois_courant, -1)
        libelle = f"{MOIS[debut.month - 1].capitalize()} {debut.year}"
        comparaison = f"par rapport à {MOIS[debut_prec.month - 1]}"
    else:
        periode = "an"
        debut, fin = _ajoute_mois(mois_courant, -11), _ajoute_mois(mois_courant, 1)
        debut_prec = _ajoute_mois(debut, -12)
        libelle = f"{MOIS[debut.month - 1].capitalize()} {debut.year} – {MOIS[mois_courant.month - 1]} {mois_courant.year}"
        comparaison = "par rapport aux 12 mois précédents"

    tickets = db.scalars(
        select(Receipt).where(Receipt.user_id == user.id, Receipt.achete_le.is_not(None))
        .options(selectinload(Receipt.items).selectinload(ReceiptItem.product), selectinload(Receipt.store))
    ).all()
    dans = [r for r in tickets if debut <= r.achete_le.date() < fin]
    avant = [r for r in tickets if debut_prec <= r.achete_le.date() < debut]

    t = Tableau(periode=periode, libelle_periode=libelle, libelle_comparaison=comparaison)
    t.total = sum((r.total or ZERO for r in dans), ZERO)
    t.nb_tickets = len(dans)
    t.panier_moyen = (t.total / t.nb_tickets).quantize(Decimal("0.01")) if dans else None
    total_avant = sum((r.total or ZERO for r in avant), ZERO)
    if total_avant:
        t.evolution = round((t.total - total_avant) / total_avant * 100)

    # 12 derniers mois, toujours, pour le graphique
    par_mois = defaultdict(lambda: ZERO)
    for r in tickets:
        par_mois[r.achete_le.date().replace(day=1)] += r.total or ZERO
    mois12 = [_ajoute_mois(mois_courant, -i) for i in range(11, -1, -1)]
    maxi = max([par_mois[m] for m in mois12] + [Decimal("1")])
    t.mois = [{"lettre": MOIS[m.month - 1][0].upper(), "titre": f"{MOIS[m.month - 1]} {m.year}",
               "valeur": par_mois[m], "hauteur": max(2, int(par_mois[m] / maxi * 120)), "courant": m == mois_courant}
              for m in mois12]

    par_enseigne = defaultdict(lambda: ZERO)
    par_categorie = defaultdict(lambda: ZERO)
    par_produit = {}
    for r in dans:
        par_enseigne[r.store.enseigne if r.store else "Autre"] += r.total or ZERO
        for it in r.items:
            par_categorie[(it.product.categorie if it.product else None) or "Autre"] += it.montant
            if it.product:
                p = par_produit.setdefault(it.product_id, {"nom": it.product.nom, "total": ZERO, "achats": 0})
                p["total"] += it.montant
                p["achats"] += 1
    somme = sum(par_enseigne.values(), ZERO) or Decimal("1")
    t.enseignes = [{"nom": k, "total": v, "part": round(v / somme * 100)}
                   for k, v in sorted(par_enseigne.items(), key=lambda kv: -kv[1])]
    somme_cat = sum(par_categorie.values(), ZERO) or Decimal("1")
    t.categories = [{"nom": k, "total": v, "part": round(v / somme_cat * 100)}
                    for k, v in sorted(par_categorie.items(), key=lambda kv: -kv[1])[:6]]
    t.produits = sorted(par_produit.values(), key=lambda p: -p["total"])[:5]

    # alerte « moins cher ailleurs » : dernier prix paye pour le meme produit dans chaque enseigne
    derniers = defaultdict(dict)  # produit -> enseigne -> (date, prix)
    noms = {}
    for r in sorted(tickets, key=lambda r: r.achete_le):
        if not r.store:
            continue
        for it in r.items:
            prix = _prix_unitaire(it)
            if it.product_id and prix:
                derniers[it.product_id][r.store.enseigne] = (r.achete_le, prix)
                noms[it.product_id] = it.product.nom
    for pid, par_ens in derniers.items():
        if len(par_ens) < 2:
            continue
        habituelle = max(par_ens.items(), key=lambda kv: kv[1][0])[0]  # ou il l'a achete en dernier
        moins_chere = min(par_ens.items(), key=lambda kv: kv[1][1])
        if moins_chere[0] != habituelle and moins_chere[1][1] < par_ens[habituelle][1]:
            t.alertes.append({"produit": noms[pid], "enseigne": moins_chere[0], "prix": moins_chere[1][1],
                              "habituelle": habituelle, "prix_habituel": par_ens[habituelle][1],
                              "gain": par_ens[habituelle][1] - moins_chere[1][1]})
    t.alertes = sorted(t.alertes, key=lambda a: -a["gain"])[:3]
    return t


def _derniers_prix(tickets) -> tuple[dict, dict, dict]:
    """produit -> enseigne -> (date, prix unitaire) ; produit -> nom ; produit -> nombre d'achats."""
    derniers, noms, achats = defaultdict(dict), {}, defaultdict(int)
    for r in sorted(tickets, key=lambda r: r.achete_le):
        if not r.store or r.store.enseigne in ("Inconnue", "Marché", "Commerce"):
            continue
        for it in r.items:
            prix = _prix_unitaire(it)
            if it.product_id and prix:
                derniers[it.product_id][r.store.enseigne] = (r.achete_le, prix)
                noms[it.product_id] = it.product.nom
                achats[it.product_id] += 1
    return derniers, noms, achats


def comparaisons(db: Session, user: User, recherche: str = "") -> dict:
    """Produits achetes dans au moins deux enseignes, dernier prix dans chacune, la moins chere en premier."""
    from .tickets import cle_produit

    tickets = db.scalars(
        select(Receipt).where(Receipt.user_id == user.id, Receipt.achete_le.is_not(None))
        .options(selectinload(Receipt.items).selectinload(ReceiptItem.product), selectinload(Receipt.store))
    ).all()
    derniers, noms, achats = _derniers_prix(tickets)
    cle = cle_produit(recherche) if recherche else ""
    produits, gagnantes = [], defaultdict(int)
    for pid, par_ens in derniers.items():
        if len(par_ens) < 2 or (cle and cle not in cle_produit(noms[pid])):
            continue
        lignes = sorted(({"enseigne": e, "prix": p, "date": d} for e, (d, p) in par_ens.items()),
                        key=lambda l: l["prix"])
        produits.append({"nom": noms[pid], "achats": achats[pid], "lignes": lignes})
        gagnantes[lignes[0]["enseigne"]] += 1
    produits.sort(key=lambda p: -p["achats"])
    meilleure = max(gagnantes.items(), key=lambda kv: kv[1]) if gagnantes else None
    return {"produits": produits[:30], "meilleure": meilleure, "nb_compares": len(produits)}


def communaute(db: Session, user: User, recherche: str = "", jours: int = 90) -> list:
    """Prix partages par tous les utilisateurs (anonymes) pour les produits que cette personne achete."""
    from datetime import timedelta

    from .models import SharedPrice, Store
    from .tickets import cle_produit

    mes_produits = set(db.scalars(select(ReceiptItem.product_id).join(Receipt)
                                  .where(Receipt.user_id == user.id, ReceiptItem.product_id.is_not(None))))
    if not mes_produits:
        return []
    depuis = date.today() - timedelta(days=jours)
    rangs = db.execute(select(SharedPrice, Store).join(Store)
                       .where(SharedPrice.product_id.in_(mes_produits), SharedPrice.jour >= depuis)).all()
    from .models import Product
    noms = {p.id: p.nom for p in db.scalars(select(Product).where(Product.id.in_(mes_produits)))}
    cle = cle_produit(recherche) if recherche else ""
    groupes = defaultdict(lambda: defaultdict(list))
    for sp, store in rangs:
        if cle and cle not in cle_produit(noms.get(sp.product_id, "")):
            continue
        groupes[sp.product_id][(store.enseigne, store.nom)].append(sp.prix_unitaire)
    resultat = []
    for pid, par_mag in groupes.items():
        lignes = []
        for (enseigne, nom), prix in par_mag.items():
            prix = sorted(prix)
            lignes.append({"enseigne": enseigne, "magasin": nom.title(), "prix": prix[len(prix) // 2],
                           "releves": len(prix)})
        if len(lignes) >= 2:
            resultat.append({"nom": noms[pid], "lignes": sorted(lignes, key=lambda l: l["prix"])})
    return sorted(resultat, key=lambda p: -sum(l["releves"] for l in p["lignes"]))[:30]
