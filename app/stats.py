"""Calculs du tableau de bord, a partir des tickets d'un seul utilisateur."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Receipt, ReceiptItem, User
from .unites import format_produit, prix_par_unite

ZERO = Decimal("0")


def _ajoute_mois(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


@dataclass
class Tableau:
    periode: str
    debut: date
    fin: date  # premier jour du dernier mois de la periode
    debut_prec: date
    total: Decimal = ZERO
    nb_tickets: int = 0
    panier_moyen: Optional[Decimal] = None
    evolution: Optional[int] = None  # en %, par rapport a la periode precedente
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
    else:
        periode = "an"
        debut, fin = _ajoute_mois(mois_courant, -11), _ajoute_mois(mois_courant, 1)
        debut_prec = _ajoute_mois(debut, -12)

    tickets = db.scalars(
        select(Receipt).where(Receipt.user_id == user.id, Receipt.achete_le.is_not(None))
        .options(selectinload(Receipt.items).selectinload(ReceiptItem.product), selectinload(Receipt.store))
    ).all()
    dans = [r for r in tickets if debut <= r.achete_le.date() < fin]
    avant = [r for r in tickets if debut_prec <= r.achete_le.date() < debut]

    t = Tableau(periode=periode, debut=debut, fin=mois_courant, debut_prec=debut_prec)
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
    t.mois = [{"date": m, "valeur": par_mois[m], "hauteur": max(2, int(par_mois[m] / maxi * 120)), "courant": m == mois_courant}
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


def _derniers_prix(tickets, ticket_de: Optional[dict] = None, unites: Optional[dict] = None) -> tuple[dict, dict, dict]:
    """produit -> enseigne -> (date, prix unitaire) ; produit -> nom ; produit -> nombre d'achats.
    Si `ticket_de` est fourni, il recoit (produit, enseigne) -> ticket ou ce dernier prix a ete paye.
    Si `unites` est fourni : prix paye ramene a la piece, au kilo ou au litre, et un meme produit en formats
    differents regroupe (« Avocat bio » et « Avocats bio ×2 ») ; le produit est alors une cle (produit, unite),
    et `unites` recoit cle -> (unite, paquets)."""
    derniers, noms, achats = defaultdict(dict), {}, defaultdict(int)
    groupes = {}  # (nom sans format, unite) -> premier produit vu, qui represente le groupe
    for r in sorted(tickets, key=lambda r: r.achete_le):
        if not r.store or r.store.enseigne in ("Inconnue", "Marché", "Commerce"):
            continue
        for it in r.items:
            if not it.product_id:
                continue
            pid, nom = it.product_id, it.product.nom
            if unites is None:
                prix = _prix_unitaire(it)
            else:
                fmt = format_produit(nom, it.product.categorie)
                prix, unite = prix_par_unite(it, fmt)
                # cle : (premier produit vu du groupe, unite) ; un meme produit vendu au kilo et en barquette
                # sans poids connu fait deux groupes
                pid = (groupes.setdefault((fmt.cle, unite), pid), unite)
                nom = noms.get(pid, fmt.nom)
                deja = unites.get(pid, (unite, False))
                unites[pid] = (unite, deja[1] or fmt.paquet or it.quantite != 1)
            if prix:
                derniers[pid][r.store.enseigne] = (r.achete_le, prix)
                if ticket_de is not None:
                    ticket_de[(pid, r.store.enseigne)] = r.id
                noms[pid] = nom
                achats[pid] += 1
    return derniers, noms, achats


def comparaisons(db: Session, user: User, recherche: str = "") -> dict:
    """Sans recherche : produits achetes dans au moins deux enseignes, les plus achetes d'abord.
    Avec recherche : tous les produits pertinents (fautes et sens toleres), meme achetes dans une seule enseigne."""
    from .models import Product
    from .recherche import classer

    tickets = db.scalars(
        select(Receipt).where(Receipt.user_id == user.id, Receipt.achete_le.is_not(None))
        .options(selectinload(Receipt.items).selectinload(ReceiptItem.product), selectinload(Receipt.store))
    ).all()
    ticket_de, unites = {}, {}
    # prix paye ramene a la piece, au kilo ou au litre : un lot de 2 avocats se compare a un avocat seul
    derniers, noms, achats = _derniers_prix(tickets, ticket_de, unites)
    produits = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_([k[0] for k in derniers])))}
    produit = lambda k: produits[k[0]]  # cle : (produit, unite)

    def fiche(pid):
        lignes = sorted(({"enseigne": e, "prix": p, "date": d, "ticket": ticket_de.get((pid, e))}
                         for e, (d, p) in derniers[pid].items()), key=lambda l: l["prix"])
        unite, paquets = unites.get(pid, ("pièce", False))
        # « / pièce » seulement si des lots ou des quantites ont ete ramenes a l'unite
        return {"id": pid[0], "nom": noms[pid], "achats": achats[pid], "lignes": lignes, "seul": len(lignes) == 1,
                "unite": None if unite == "article" or (unite == "pièce" and not paquets) else unite}

    if recherche.strip():
        # a pertinence egale : d'abord ce qui se compare (plusieurs enseignes), puis le plus achete
        ids = classer(recherche, list(derniers), cle=lambda pid: (noms[pid], produit(pid).famille or "",
                                                                  produit(pid).categorie or ""),
                      ensuite=lambda pid: (len(derniers[pid]) >= 2) * 1000 + achats[pid])
        resultat = [fiche(pid) for pid in ids[:30]]
    else:
        multi = [pid for pid in derniers if len(derniers[pid]) >= 2]
        resultat = sorted((fiche(pid) for pid in multi), key=lambda p: -p["achats"])[:30]

    gagnantes = defaultdict(int)
    for pid in derniers:
        if len(derniers[pid]) >= 2:
            gagnantes[min(derniers[pid].items(), key=lambda kv: kv[1][1])[0]] += 1
    # suggestions : les familles que la personne achete le plus (« saumon », « œufs »…)
    par_famille = defaultdict(int)
    for pid, n in achats.items():
        if produits.get(pid[0]) and produits[pid[0]].famille:
            par_famille[produits[pid[0]].famille] += n
    suggestions = [f for f, _ in sorted(par_famille.items(), key=lambda kv: -kv[1])[:8]]
    meilleure = max(gagnantes.items(), key=lambda kv: kv[1]) if gagnantes else None
    return {"produits": resultat, "meilleure": meilleure, "nb_compares": sum(gagnantes.values()),
            "suggestions": suggestions}


def communaute(db: Session, user: User, recherche: str = "", jours: int = 90) -> list:
    """Prix partages par tous les utilisateurs (anonymes) pour les produits que cette personne achete."""
    from datetime import timedelta

    from .models import SharedPrice, Store

    mes_produits = set(db.scalars(select(ReceiptItem.product_id).join(Receipt)
                                  .where(Receipt.user_id == user.id, ReceiptItem.product_id.is_not(None))))
    if not mes_produits:
        return []
    depuis = date.today() - timedelta(days=jours)
    rangs = db.execute(select(SharedPrice, Store).join(Store)
                       .where(SharedPrice.product_id.in_(mes_produits), SharedPrice.jour >= depuis)).all()
    from .models import Product
    from .recherche import classer
    fiches = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(mes_produits)))}
    noms = {pid: p.nom for pid, p in fiches.items()}
    gardes = set(classer(recherche, list(fiches), cle=lambda pid: (fiches[pid].nom, fiches[pid].famille or "",
                                                                   fiches[pid].categorie or ""))) \
        if recherche.strip() else set(fiches)
    groupes = defaultdict(lambda: defaultdict(list))
    for sp, store in rangs:
        if sp.product_id not in gardes:
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
