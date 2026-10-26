import os
import tempfile

import pytest

# base de test jetable, configuree avant l'import de l'application
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["ADMIN_EMAILS"] = "admin@exemple.fr"
os.environ["BASE_URL"] = "http://testserver"

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
