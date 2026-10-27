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
# Render donne « postgresql://… » : on precise le pilote psycopg 3
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-a-changer")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
# Envoi des e-mails par Brevo des que la cle est presente ; sinon le lien s'affiche dans les logs (developpement)
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
# (une ancienne variable EMAIL_BACKEND=console restee sur Render ne doit pas bloquer l'envoi)
EMAIL_BACKEND = "brevo" if BREVO_API_KEY else "console"
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")  # adresse d'expediteur verifiee dans Brevo
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "FairBasket")
# adresses qui ont acces a l'administration et passent la liste d'attente
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
# cookie "Secure" en production (HTTPS)
COOKIE_SECURE = BASE_URL.startswith("https://")

LOGIN_TOKEN_MINUTES = 15
SESSION_DAYS = 30
MAX_LINKS_PER_HOUR = 5
CGU_VERSION = "2026-10-26"

# Lecture des tickets par l'IA (modele et niveau d'effort reglables sans toucher au code)
# Haiku : 8/8 sur le test de reference du 26/10/2026, ~0,0015 $ par ticket (Opus : 8/8, ~0,045 $)
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")
CLAUDE_EFFORT = os.environ.get("CLAUDE_EFFORT", "medium")
MAX_TICKETS_PAR_MOIS = 60
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", ROOT / "uploads"))

# Open Prices : zone dont on copie les prix (par defaut Paris 19e, rayon 10 km), 90 derniers jours
OPEN_PRICES_LAT = float(os.environ.get("OPEN_PRICES_LAT", "48.8897"))
OPEN_PRICES_LON = float(os.environ.get("OPEN_PRICES_LON", "2.3820"))
OPEN_PRICES_RAYON_KM = int(os.environ.get("OPEN_PRICES_RAYON_KM", "10"))
OPEN_PRICES_JOURS = 90
ADRESSES_AUTO = os.environ.get("ADRESSES_AUTO", "1") == "1"  # adresse des magasins cherchee toute seule (OSM, BAN)
OPEN_PRICES_AUTO = os.environ.get("OPEN_PRICES_AUTO", "1") == "1"  # synchronisation quotidienne en tache de fond
