"""Ramener un achat a l'unite pour comparer : prix par piece, par kilo ou par litre.

« Avocats bio ×2 » a 3,99 € et « Avocat bio » a 1,69 € deviennent le meme produit, « Avocat bio »,
a 2,00 € et 1,69 € la piece. « Tomates cerises bio 200 g » et « 250 g » se comparent au kilo.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .rayons import mots, precis, type_de
from .tickets import cle_produit, nom_bio

NOMBRE = re.compile(r"(?:^|\s)[×x]\s?(\d+)(?=\s|$)", re.IGNORECASE)
MESURE = re.compile(r"(?:^|\s)(\d+(?:[.,]\d+)?)\s?(kg|g|cl|ml|l)(?=\s|$)", re.IGNORECASE)
VERS_KILO = {"kg": (Decimal(1), "kg"), "g": (Decimal("0.001"), "kg"), "l": (Decimal(1), "L"),
             "cl": (Decimal("0.01"), "L"), "ml": (Decimal("0.001"), "L")}


@dataclass
class Format:
    nom: str          # nom sans le format : « Avocat bio »
    cle: str          # pour regrouper, au singulier : « avocat bio »
    unite: str        # « pièce », « kg », « L », ou « article » (format inconnu)
    quantite: Decimal  # dans un article : 2 pieces, 0,2 kg…
    paquet: bool      # le nom precisait un nombre ou un poids


def _singulier(mot: str) -> str:
    return mot[:-1] if len(mot) > 3 and mot[-1] in "sS" and mot[-2] not in "sS" else mot


def format_produit(nom: str, categorie: Optional[str] = None) -> Format:
    """Sans nombre ni poids dans le nom, un fruit ou un legume est vendu a la piece ; pour le reste on ne sait
    pas (une boite d'oeufs ? un paquet ?), alors il reste a part (« article ») plutot que d'etre mal compare."""
    nombre = NOMBRE.search(nom)
    mesure = MESURE.search(nom)
    reste = MESURE.sub(" ", NOMBRE.sub(" ", nom))
    base = " ".join(reste.split()) or nom
    cle = cle_produit(" ".join(_singulier(m) for m in base.split()))
    n = Decimal(nombre.group(1)) if nombre else Decimal(1)
    if mesure:
        facteur, unite = VERS_KILO[mesure.group(2).lower()]
        quantite = Decimal(mesure.group(1).replace(",", ".")) * facteur * n
    elif nombre or categorie == "Fruits et légumes":
        unite, quantite = "pièce", n
    else:
        unite, quantite = "article", n
    return Format(nom=base, cle=cle, unite=unite, quantite=quantite,
                  paquet=bool(nombre or mesure))


def prix_par_unite(item, fmt: Format, arrondi: bool = True) -> tuple[Optional[Decimal], str]:
    """Prix reellement paye (remises deduites) pour une piece, un kilo ou un litre."""
    if item.poids_kg or item.prix_kg:  # vendu au poids : le prix au kilo imprime sur le ticket, sinon calcule
        if item.prix_kg:
            return item.prix_kg, "kg"
        prix = item.montant / item.poids_kg if item.poids_kg > 0 else None
    elif not item.quantite or item.quantite <= 0 or not fmt.quantite or item.montant <= 0:
        return None, fmt.unite
    else:
        prix = item.montant / item.quantite / fmt.quantite
    if prix is not None and arrondi:
        prix = prix.quantize(Decimal("0.01"))
    return prix, "kg" if item.poids_kg else fmt.unite


def cle_comparaison(nom: str, fmt: Format, type_off: Optional[str] = None) -> tuple:
    """Ce qui se compare d'une enseigne a l'autre : le meme produit type (rayon Open Food Facts, rayons.py) quand
    il est assez precis, le bio a part ; sinon le meme nom sans son format (« Avocat bio »). type_off : celui du
    produit ; None quand il n'est pas encore classe (alors d'apres le nom), "" quand aucun rayon ne correspond."""
    if type_off is None:
        t = type_de(nom)
        type_off = t[0] if t else ""
    return ("type", type_off, nom_bio(nom)) if type_off and precis(type_off) else ("nom", fmt.cle)


def nom_du_type(type_nom: str, nom: str) -> str:
    """« Œufs » pour des œufs bio -> « Œufs bio »."""
    return f"{type_nom} bio" if nom_bio(nom) and "bio" not in mots(type_nom) else type_nom
