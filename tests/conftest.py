import os
import tempfile

import pytest

# base de test jetable, configuree avant l'import de l'application
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["ADMIN_EMAILS"] = "admin@exemple.fr"
os.environ["BASE_URL"] = "http://testserver"
os.environ["OPEN_PRICES_AUTO"] = "0"  # pas d'appel reseau pendant les tests
os.environ["ADRESSES_AUTO"] = "0"
os.environ["OPEN_FOOD_FACTS_AUTO"] = "0"
os.environ["ANTHROPIC_API_KEY"] = ""  # jamais d'appel reel a Claude (la cle du .env local ne passe pas)
os.environ["INSCRIPTION_LIBRE"] = "0"  # les tests de la liste d'attente ; l'inscription libre a son propre test

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import close_all_sessions  # noqa: E402

from app import auth, main  # noqa: E402
from app.db import Base, engine  # noqa: E402


@pytest.fixture
def links(monkeypatch):
    """Liens de connexion « envoyés », par adresse."""
    sent = {}
    monkeypatch.setattr(auth, "send_login_email",
                        lambda user, link: sent.setdefault(user.email, []).append(link) or True)
    return sent


def base_vide():
    # PostgreSQL : une session restee ouverte bloquerait la suppression des tables
    close_all_sessions()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture
def client(links):
    base_vide()
    with TestClient(main.app) as c:
        yield c
