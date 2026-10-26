"""FairBasket - serveur web (squelette pour le premier deploiement sur Render)."""

from fastapi import FastAPI

app = FastAPI(title="FairBasket")


@app.get("/")
def accueil():
    return {"application": "FairBasket", "statut": "en construction"}


@app.get("/health")
def health():
    # utilise par Render pour verifier que le service repond
    return {"ok": True}
