import json

from app import auth, config
from app.models import User


class FausseReponse:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_envoi_brevo(monkeypatch):
    envoye = {}

    def faux_urlopen(req, timeout):
        envoye["url"], envoye["entetes"], envoye["corps"] = req.full_url, dict(req.header_items()), json.loads(req.data)
        return FausseReponse()

    monkeypatch.setattr(config, "EMAIL_BACKEND", "brevo")
    monkeypatch.setattr(config, "BREVO_API_KEY", "cle-test")
    monkeypatch.setattr(config, "EMAIL_FROM", "bonjour@fairbasket.app")
    monkeypatch.setattr(auth.urllib.request, "urlopen", faux_urlopen)
    u = User(email="marie@exemple.fr", prenom="Marie", lang="en")
    auth.send_login_email(u, "https://site/auth/abc")
    assert envoye["url"] == "https://api.brevo.com/v3/smtp/email"
    assert envoye["entetes"]["Api-key"] == "cle-test"
    c = envoye["corps"]
    assert c["to"][0]["email"] == "marie@exemple.fr" and c["subject"] == "Your FairBasket login link"
    assert "https://site/auth/abc" in c["textContent"] and 'href="https://site/auth/abc"' in c["htmlContent"]


def test_erreur_brevo_ne_casse_pas(monkeypatch, caplog):
    def panne(req, timeout):
        raise OSError("réseau")

    monkeypatch.setattr(config, "EMAIL_BACKEND", "brevo")
    monkeypatch.setattr(auth.urllib.request, "urlopen", panne)
    auth.send_login_email(User(email="a@b.fr", prenom="A", lang="fr"), "https://site/auth/secret")
    assert "Échec d'envoi" in caplog.text and "secret" not in caplog.text  # jamais le lien dans les logs
