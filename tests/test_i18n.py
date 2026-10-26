import glob
import re

from app import i18n, lecture, main

MOTIF = re.compile(r'''_\(\s*("((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')''')


def cles_des_gabarits():
    cles = set()
    for f in glob.glob("app/templates/*.html"):
        for m in MOTIF.finditer(open(f, encoding="utf-8").read()):
            cles.add((m.group(2) if m.group(2) is not None else m.group(3)).replace("\\'", "'"))
    return cles


def test_tout_est_traduit():
    textes_python = {t for paire in main.SLIDES for t in paire} | set(lecture.CATEGORIES)
    manquants = sorted((cles_des_gabarits() | textes_python) - set(i18n.EN))
    assert manquants == []


def test_memes_valeurs_a_remplir():
    for fr, en in i18n.EN.items():
        assert set(re.findall(r"{(\w+)}", fr)) == set(re.findall(r"{(\w+)}", en)), fr


def test_pluriels():
    fr, en = i18n.traducteur("fr"), i18n.traducteur("en")
    assert fr("{n} achat(s)", n=1) == "1 achat" and fr("{n} achat(s)", n=3) == "3 achats"
    assert en("{n} achat(s)", n=2) == "2 purchases"


def test_page_en_anglais(client):
    r = client.get("/", headers={"accept-language": "en-GB,en;q=0.9"})
    assert "Pay the fair price for your basket." in r.text and '<html lang="en">' in r.text
    client.get("/langue/fr?retour=/")
    assert "Payez le juste prix" in client.get("/", headers={"accept-language": "en"}).text  # le choix l'emporte


def test_retour_seulement_local(client):
    r = client.get("/langue/en?retour=https://exemple.com", follow_redirects=False)
    assert r.headers["location"] == "/"
