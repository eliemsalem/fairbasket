"""Recherche de produits tolerante aux fautes, et par le sens grace a la famille du produit.

Meme idee que le TF-IDF sur caracteres du projet Rakuten (cours Hugging Face) : on compare des morceaux
de 2 a 4 lettres plutot que des mots entiers, ce qui absorbe fautes de frappe, accents et abreviations
(« saumo », « oeuf », « choclat »). La famille donnee par l'IA a la lecture (« poisson », « fromage »)
permet de trouver un produit par ce qu'il est, meme si son nom ne contient pas le mot cherche.
"""

import math
import re
from collections import Counter

from .tickets import cle_produit

SEUIL = 0.45


def _ngrammes(texte: str) -> Counter:
    texte = f" {cle_produit(texte)} "
    return Counter(texte[i:i + n] for n in (2, 3, 4) for i in range(len(texte) - n + 1))


def _cosinus(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    commun = sum(a[k] * b[k] for k in a.keys() & b.keys())
    return commun / math.sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))


MOTS_VIDES = {"de", "du", "des", "la", "le", "les", "au", "aux", "et", "en", "a", "l", "d", "un", "une", "avec", "sans",
              "pour", "sur", "the", "of", "and", "with"}


def _mots(texte: str) -> list:
    """Mots utiles : decoupes aussi sur les traits d'union et apostrophes, sans les petits mots (de, au…)."""
    brut = re.sub(r"[^0-9a-z%]+", " ", cle_produit(texte))
    return [m for m in brut.split() if len(m) > 1 and m not in MOTS_VIDES]


def _ressemblance(mot_tape: str, mot: str) -> float:
    """Deux mots se ressemblent s'ils commencent pareil : une faute touche rarement la premiere lettre
    (« choclat » ~ « chocolat »), alors que « poisson » et « boisson » different justement par elle."""
    if not mot_tape or not mot or mot_tape[0] != mot[0]:
        return 0.0
    if mot == mot_tape:
        return 1.0
    if mot.startswith(mot_tape):  # debut de mot tape (« sau » -> « saumon ») : juste sous le mot exact
        return 0.94
    return _cosinus(_ngrammes(mot_tape), _ngrammes(mot))


def _correspondance(mots_q: list, texte: str) -> float:
    """Moyenne, pour chaque mot tape, de sa ressemblance avec le mot le plus proche du texte."""
    mots = _mots(texte)
    if not mots_q or not mots:
        return 0.0
    return sum(max(_ressemblance(mq, m) for m in mots) for mq in mots_q) / len(mots_q)


def score(requete: str, nom: str, famille: str = "", categorie: str = "") -> float:
    """Pertinence entre 0 et 1 d'un produit pour une requete."""
    mots_q = _mots(requete)
    if not mots_q:
        return 0.0
    par_nom = _correspondance(mots_q, nom)
    colle = cle_produit(requete).replace(" ", "")
    # mots colles (« redbull » -> « Red Bull ») : seulement si la requete chevauche plusieurs mots du nom
    if (len(colle) >= 4 and colle in cle_produit(nom).replace(" ", "")
            and not any(colle in m for m in _mots(nom))):
        par_nom = max(par_nom, 1.0)
    par_sens = max(_correspondance(mots_q, famille or ""), 0.8 * _correspondance(mots_q, categorie or ""))
    return max(par_nom, 0.9 * par_sens)


def classer(requete: str, produits: list, cle=lambda p: p, ensuite=lambda p: 0) -> list:
    """Produits pertinents pour la requete, du plus au moins pertinent. `cle(p)` -> (nom, famille, categorie).
    A pertinence proche (meme dixieme), `ensuite(p)` departage : le plus grand d'abord."""
    notes = [(score(requete, *cle(p)), p) for p in produits]
    gardes = [(s, p) for s, p in notes if s >= SEUIL]
    return [p for s, p in sorted(gardes, key=lambda x: (-round(x[0], 1), -ensuite(x[1])))]
