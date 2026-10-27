"""Enseignes de supermarches et d'epiceries en France : nom, formats, et magasins 100 % bio.

Source unique pour reconnaitre l'enseigne d'un ticket ou d'un magasin Open Prices, et pour savoir si
ses produits doivent etre consideres comme bio (le ticket ne le precise pas). Liste a completer au besoin :
un motif est cherche dans le nom (sans accents ni majuscules), le plus long d'abord.
"""

import re
import unicodedata

# (motif dans le nom, enseigne, magasin 100 % bio)
FORMATS = [
    # magasins specialises bio
    ("biocoop", "Biocoop", True), ("naturalia", "Naturalia", True), ("la vie claire", "La Vie Claire", True),
    ("bio c bon", "Bio c' Bon", True), ("bio c' bon", "Bio c' Bon", True),
    ("comptoirs de la bio", "Les Comptoirs de la Bio", True), ("eau vive", "L'Eau Vive", True),
    ("satoriz", "Satoriz", True), ("biomonde", "Biomonde", True), ("natureo", "NaturéO", True),
    ("marcel & fils", "Marcel & Fils", True), ("marcel et fils", "Marcel & Fils", True),
    ("la recolte", "La Récolte", True), ("so.bio", "So.bio", True), ("so bio", "So.bio", True),
    ("carrefour bio", "Carrefour", True),
    # grandes enseignes et leurs formats
    ("carrefour", "Carrefour", False), ("promocash", "Carrefour", False),
    ("auchan", "Auchan", False), ("my auchan", "Auchan", False),
    ("e.leclerc", "E.Leclerc", False), ("leclerc", "E.Leclerc", False),
    ("intermarche", "Intermarché", False), ("netto", "Netto", False),
    ("hyper u", "Système U", False), ("super u", "Système U", False), ("u express", "Système U", False),
    ("systeme u", "Système U", False), ("utile", "Système U", False),
    ("monoprix", "Monoprix", False), ("monop", "Monoprix", False),
    ("franprix", "Franprix", False), ("casino", "Casino", False), ("spar", "Spar", False), ("vival", "Vival", False),
    ("sherpa", "Sherpa", False), ("lidl", "Lidl", False), ("aldi", "Aldi", False),
    ("leader price", "Leader Price", False), ("cora", "Cora", False), ("match", "Match", False),
    ("colruyt", "Colruyt", False), ("g20", "G20", False), ("diagonal", "Diagonal", False),
    ("coccinelle", "Coccinelle", False), ("proxi", "Proxi", False), ("8 a huit", "8 à Huit", False),
    ("picard", "Picard", False), ("grand frais", "Grand Frais", False), ("thiriet", "Thiriet", False),
    ("la grande epicerie", "La Grande Épicerie", False), ("lafayette gourmet", "Lafayette Gourmet", False),
    ("day by day", "Day by Day", False), ("biocash", "Biocash", False),
]


def _cle(texte: str) -> str:
    """Minuscules sans accents, ponctuation remplacee par des espaces (sauf « & » et « . » : E.Leclerc, So.bio)."""
    texte = texte.replace("œ", "oe").replace("Œ", "oe")
    texte = "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))
    texte = re.sub(r"[^\w&.]+", " ", texte.casefold())
    return f" {' '.join(texte.split())} "


_FORMATS = sorted(((_cle(m), e, b) for m, e, b in FORMATS), key=lambda f: -len(f[0]))


def reconnaitre(*noms: str) -> tuple:
    """(enseigne, bio) a partir du nom de l'enseigne et/ou du magasin ; (None, False) si inconnue."""
    for nom in noms:
        cle = _cle(nom or "")
        for motif, enseigne, bio in _FORMATS:
            if motif in cle:  # mots entiers grace aux espaces (« match » ne trouve pas « matcha »)
                return enseigne, bio
    return None, False


def est_bio(enseigne: str, magasin: str = "") -> bool:
    """Magasin 100 % bio (Naturalia, La Récolte, Carrefour Bio…) : ses produits sont consideres comme bio."""
    return reconnaitre(magasin, enseigne)[1] or reconnaitre(enseigne)[1]
