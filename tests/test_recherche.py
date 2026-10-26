from app.recherche import classer, score

PRODUITS = [
    ("Pavé de saumon", "poisson", "Viandes et poissons"),
    ("Limande meunière", "poisson", "Viandes et poissons"),
    ("Œufs bio ×6", "œufs", "Produits laitiers et œufs"),
    ("Chocolat noir 85 % 100 g", "chocolat", "Épicerie sucrée"),
    ("Morbier AOP lait cru", "fromage", "Fromages"),
    ("Bière blonde Chti 75 cl", "bière", "Boissons"),
    ("Red Bull 25 cl ×4", "boisson énergisante", "Boissons"),
]


def noms(q):
    return [p[0] for p in classer(q, PRODUITS, cle=lambda p: p)]


def test_debut_de_mot():
    assert noms("sau")[0] == "Pavé de saumon"


def test_sans_accent_ni_ligature():
    assert noms("oeuf")[0] == "Œufs bio ×6"


def test_faute_de_frappe():
    assert noms("choclat")[0] == "Chocolat noir 85 % 100 g"


def test_par_le_sens():
    assert set(noms("poisson")[:2]) == {"Pavé de saumon", "Limande meunière"}
    assert noms("fromage")[0] == "Morbier AOP lait cru"


def test_plusieurs_mots():
    assert noms("chocolat noir")[0] == "Chocolat noir 85 % 100 g"


def test_rien_de_pertinent():
    assert noms("dentifrice") == []


def test_score_borne():
    assert 0 <= score("saumon", "Pavé de saumon") <= 1


def test_mots_colles_et_pieges():
    assert noms("redbull")[0] == "Red Bull 25 cl ×4"
    assert "Pavé de saumon" not in noms("boisson")      # boisson n'est pas poisson
    assert noms("biere") == ["Bière blonde Chti 75 cl"]  # pas « meunière »
