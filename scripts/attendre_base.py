"""Attend que la base accepte les connexions (une base tout juste creee peut mettre quelques minutes).

Lance avant les migrations : python -m scripts.attendre_base && alembic upgrade head
"""

import sys
import time

from sqlalchemy import text

from app.db import engine

ESSAIS, PAUSE = 36, 5  # jusqu'a 3 minutes

for essai in range(1, ESSAIS + 1):
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        print(f"Base disponible (essai {essai}).")
        sys.exit(0)
    except Exception as e:  # base pas encore prete
        print(f"Base pas encore prête (essai {essai}/{ESSAIS}) : {type(e).__name__}", flush=True)
        time.sleep(PAUSE)
print("La base ne répond toujours pas.")
sys.exit(1)
