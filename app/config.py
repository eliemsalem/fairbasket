"""Reglages lus dans les variables d'environnement (fichier .env en local, onglet Environment sur Render)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    # mini-lecteur de .env pour le developpement local, sans dependance en plus
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{ROOT / 'fairbasket.db'}")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-a-changer")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
# "console" : le lien de connexion s'affiche dans le terminal (developpement)
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "console")
# adresses qui ont acces a l'administration et passent la liste d'attente
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
# cookie "Secure" en production (HTTPS)
COOKIE_SECURE = BASE_URL.startswith("https://")

LOGIN_TOKEN_MINUTES = 15
SESSION_DAYS = 30
MAX_LINKS_PER_HOUR = 5
CGU_VERSION = "2026-10-26"

# Lecture des tickets par l'IA (modele et niveau d'effort reglables sans toucher au code)
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
CLAUDE_EFFORT = os.environ.get("CLAUDE_EFFORT", "medium")
MAX_TICKETS_PAR_MOIS = 60
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", ROOT / "uploads"))
