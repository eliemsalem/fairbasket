import os
import tempfile

import pytest

# base de test jetable, configuree avant l'import de l'application
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ADMIN_EMAILS"] = "admin@exemple.fr"
os.environ["BASE_URL"] = "http://testserver"

from fastapi.testclient import TestClient  # noqa: E402

from app import auth, main  # noqa: E402
from app.db import Base, engine  # noqa: E402


@pytest.fixture
def links(monkeypatch):
    """Liens de connexion « envoyés », par adresse."""
    sent = {}
    monkeypatch.setattr(auth, "send_login_email", lambda user, link: sent.setdefault(user.email, []).append(link))
    return sent


@pytest.fixture
def client(links):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(main.app) as c:
        yield c
