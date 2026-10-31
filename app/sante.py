"""Sante des articles scannes : Nutri-Score, transformation (NOVA), additifs, labels, et mieux note a proposer.

On s'en tient aux notes officielles (le Nutri-Score est celui de Sante publique France) et aux faits (la liste des
additifs), sans juger nous-memes un produit. Les propositions « mieux note » viennent du meme rayon d'Open Food
Facts, la marque de l'enseigne de la personne d'abord, avec le prix quand on le connait (ses tickets, Open Prices).
"""

import logging
import re
from collections import Counter
from datetime import date
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from . import codebarres, config, rayons
from .models import ProductAlias, Receipt, ReceiptItem, Store, User

log = logging.getLogger("fairbasket.sante")
CHAMPS = "nutriscore_grade,nova_group,additives_tags,labels_tags,ecoscore_grade,categories_tags"
NOTES = "abcde"
A_AMELIORER = ("d", "e")  # on ne propose mieux que pour un D ou un E : pas de remarque sur ce qui est deja correct
FRAICHEUR_JOURS = 30
LABELS = {"en:organic": "Bio", "en:eu-organic": "Bio", "fr:ab-agriculture-biologique": "Bio",
          "fr:label-rouge": "Label Rouge", "en:fair-trade": "Commerce équitable", "en:fairtrade-international":
          "Commerce équitable", "en:max-havelaar": "Commerce équitable", "fr:bleu-blanc-coeur": "Bleu-Blanc-Cœur",
          "en:pdo": "AOP", "en:pgi": "IGP", "fr:aoc": "AOC", "en:msc": "Pêche durable MSC",
          "en:free-range": "Plein air", "en:vegan": "Vegan", "en:vegetarian": "Végétarien",
          "en:no-palm-oil": "Sans huile de palme", "en:no-added-sugar": "Sans sucres ajoutés",
          "en:french-agriculture": "Origine France", "en:made-in-france": "Fabriqué en France"}


def _note(v) -> Optional[str]:
    v = str(v or "").lower()
    return v if len(v) == 1 and v in NOTES else None


def _nova(v) -> Optional[int]:
    try:
        return int(v) if int(v) in (1, 2, 3, 4) else None
    except (TypeError, ValueError):
        return None


def extraire(p: dict) -> dict:
    """Les faits utiles d'une fiche Open Food Facts (rien d'invente : une donnee absente reste absente)."""
    labels = []
    for t in p.get("labels_tags") or []:
        if t in LABELS and LABELS[t] not in labels:
            labels.append(LABELS[t])
    return {"nutriscore": _note(p.get("nutriscore_grade")), "nova": _nova(p.get("nova_group")),
            "additifs": [t.split(":")[-1].upper() for t in p.get("additives_tags") or []][:20],
            "labels": labels, "ecoscore": _note(p.get("ecoscore_grade")),
            "categories": [t for t in p.get("categories_tags") or [] if t.startswith("en:")][-3:]}


def _proposition(h: dict) -> dict:
    return {**codebarres._fiche(h, h["code"]), "nutriscore": _note(h.get("nutriscore_grade")),
            "nova": _nova(h.get("nova_group"))}


def _chercher(get: Callable, q: str, limite: int) -> tuple[list, int]:
    """(produits trouves, nombre total de fiches qui repondent a la recherche)."""
    d = get(codebarres.RECHERCHE, {"q": q, "langs": "fr", "page_size": limite,
                                   "fields": codebarres.CHAMPS + ",nutriscore_grade,nova_group,categories_tags"})
    hits = [h for h in d.get("hits", []) if codebarres.valide(str(h.get("code", ""))) and h.get("product_name")]
    return hits, int(d.get("count") or len(hits))


RARE = 0.03  # mieux note que 3 % du rayon : sans doute des fiches mal remplies (un beurre « C »), pas une alternative


def mieux_notes(categories: list, enseigne: Optional[str], note: Optional[str], sauf: str = "",
                get: Optional[Callable] = None, limite: int = 3, notes: str = "a OR b OR c") -> list:
    """Le meme rayon, mieux note (A ou B, sinon C), vendu en France : la marque de l'enseigne d'abord, puis
    toutes marques ; les mieux notes et les moins transformes en premier. Seulement des fiches completes (marque,
    format) et quand le rayon compte vraiment des produits mieux notes."""
    get = get or (codebarres._get if config.OPEN_FOOD_FACTS_AUTO else None)
    if get is None or not categories or note not in A_AMELIORER:
        return []
    marque = enseigne.lower() if enseigne and enseigne != "Inconnue" else None
    trouves, vus = {}, set()
    try:
        for categorie in reversed(categories[-2:]):  # le rayon le plus precis, puis un peu plus large
            rayon = f'categories_tags:"{categorie}" AND countries_tags:"en:france"'
            mieux, nb_mieux = _chercher(get, f"{rayon} AND nutriscore_grade:({notes})", 12)
            _, nb_rayon = _chercher(get, rayon, 1)
            if nb_mieux < max(5, nb_rayon * RARE):
                continue
            de_l_enseigne = _chercher(get, f'{rayon} AND nutriscore_grade:({notes}) AND brands:"{marque}"', 12)[0] \
                if marque else []
            for h, avec_marque in [(h, True) for h in de_l_enseigne] + [(h, False) for h in mieux]:
                p = _proposition(h)
                double = (" ".join(re.sub(r"\W+", " ", p["nom"].casefold()).split()),
                          (p["marque"] or "").split(",")[0].casefold(), p["format"])
                if h["code"] == sauf or h["code"] in trouves or double in vus or not p["marque"] or not p["format"]:
                    continue
                vus.add(double)
                trouves[h["code"]] = {**p, "enseigne": avec_marque}
            if trouves:
                break
    except Exception as e:  # service indisponible : rien a proposer cette fois
        log.info("mieux notes indisponibles : %s", e)
    rang = sorted(trouves.values(), key=lambda p: (p["nutriscore"] or "z", not p["enseigne"], p["nova"] or 5))
    return rang[:limite]


def rayon_de(hits: list) -> Optional[str]:
    """Le rayon Open Food Facts commun aux produits trouves pour un mot (« cereales ») : le plus precis de ceux
    que partage au moins la moitie d'entre eux."""
    compte, position = Counter(), {}
    for h in hits:
        tags = [t for t in h.get("categories_tags") or [] if t.startswith("en:")]
        for i, t in enumerate(tags):
            compte[t] += 1
            position.setdefault(t, []).append((i + 1) / len(tags))
    communs = [t for t, n in compte.items() if n >= max(2, len(hits) // 2)]
    return max(communs, key=lambda t: sum(position[t]) / len(position[t])) if communs else None


def pour_produit(produit: str, enseigne: Optional[str], get: Optional[Callable] = None, limite: int = 5) -> list:
    """Sans article scanne : le rayon du produit d'apres Open Food Facts, puis ce qui y est note A ou B."""
    get = get or (codebarres._get if config.OPEN_FOOD_FACTS_AUTO else None)
    if get is None or len(produit) < 3:
        return []
    try:
        rayon = rayon_de(_chercher(get, f'{produit} AND countries_tags:"en:france"', 10)[0])
    except Exception as e:
        log.info("rayon de %s indisponible : %s", produit, e)
        return []
    return mieux_notes([rayon], enseigne, "e", get=get, limite=limite, notes="a OR b") if rayon else []


def completer(db: Session, alias: ProductAlias, get: Optional[Callable] = None) -> bool:
    """Ajoute (ou rafraichit) la sante d'un article scanne : ses notes et les mieux notes du meme rayon."""
    get = get or (codebarres._get if config.OPEN_FOOD_FACTS_AUTO else None)
    if get is None or not alias.code_barres:
        return False
    try:
        d = get(codebarres.FICHE.format(code=alias.code_barres), {"fields": CHAMPS})
    except Exception as e:
        log.info("sante %s indisponible : %s", alias.code_barres, e)
        return False
    s = extraire(d.get("product") or {}) if d.get("status") == 1 else {}
    s["mieux"] = mieux_notes(s.get("categories") or [], alias.enseigne, s.get("nutriscore"), alias.code_barres, get)
    s["le"] = date.today().isoformat()
    alias.sante = s
    exact = rayons.type_des_categories(s.get("categories") or [])
    if exact and alias.product is not None and not alias.product.type_off:  # le rayon exact de l'article scanne
        alias.product.type_off, alias.product.type_nom = exact[0], exact[1][:120]
    db.commit()
    return True


def a_rafraichir(alias: ProductAlias) -> bool:
    if not alias.code_barres:
        return False
    if not alias.sante or not alias.sante.get("le"):
        return True
    return (date.today() - date.fromisoformat(alias.sante["le"])).days > FRAICHEUR_JOURS


def prix_connu(db: Session, user: User, code: str, zone: Optional[dict]) -> Optional[dict]:
    """Le prix d'un article d'apres son code : le dernier paye par la personne, sinon le moins cher autour."""
    connus = db.execute(select(ProductAlias.enseigne, ProductAlias.libelle).where(ProductAlias.code_barres == code)).all()
    if connus:
        it = db.scalar(select(ReceiptItem).join(Receipt).join(Store).where(
            Receipt.user_id == user.id, tuple_(Store.enseigne, ReceiptItem.libelle).in_([tuple(c) for c in connus]))
            .order_by(Receipt.achete_le.desc()))
        if it is not None:
            prix = (it.montant / it.quantite).quantize(Decimal("0.01")) if it.quantite else it.montant
            return {"prix": prix, "ou": it.receipt.store.enseigne, "distance": None, "source": "tickets"}
    ailleurs = codebarres.ailleurs(db, code, zone, limite=1)
    if ailleurs:
        a = ailleurs[0]
        return {"prix": a["p"].prix, "ou": a["p"].magasin.title(), "distance": a["distance"], "source": "open_prices"}
    return None


def avec_prix(db: Session, user: User, propositions: list, zone: Optional[dict], format_actuel: Optional[str] = None,
              prix_actuel: Optional[tuple] = None) -> list:
    """Chaque proposition avec son prix connu et, quand les deux formats sont connus, l'ecart au kilo (ou au litre)."""
    resultat = []
    for p in propositions:
        p = dict(p)
        prix = prix_connu(db, user, p["code"], zone)
        p["prix"] = prix
        if prix and prix_actuel:
            unite = codebarres.prix_unite(prix["prix"], Decimal(1), p.get("format"))
            if unite and unite[1] == prix_actuel[1]:
                p["unite"], p["ecart_unite"] = unite, unite[0] - prix_actuel[0]
        resultat.append(p)
    return resultat


def bilan(lignes: list) -> Optional[dict]:
    """[(montant, nutriscore)] des articles scannes d'un ticket -> la part de la depense par note, de A a E."""
    notes = [(m, n) for m, n in lignes if n]
    if not notes:
        return None
    total = sum(m for m, _ in notes)
    par = Counter()
    for m, n in notes:
        par[n] += m
    parts = [{"note": n, "pct": round(float(par[n] / total * 100)) if total else 0} for n in NOTES if par[n]]
    bons = sum(par[n] for n in "ab")
    return {"nb": len(notes), "montant": total, "parts": parts,
            "pct_bons": round(float(bons / total * 100)) if total else 0}
