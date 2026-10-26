"""FairBasket - serveur web : inscription, connexion par lien magique, liste d'attente."""

import re
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import auth, config
from .db import get_db, init_db
from .models import User, now

APP_DIR = config.ROOT / "app"


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="FairBasket", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    return auth.user_from_session(db, request.cookies.get(auth.SESSION_COOKIE))


def require_user(user: Optional[User] = Depends(current_user)) -> User:
    if user is None:
        # pas connecte : retour a l'accueil public
        raise HTTPException(status_code=303, headers={"Location": "/connexion"})
    return user


def page(request: Request, name: str, status_code: int = 200, **ctx):
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


@app.get("/health")
def health():
    # utilise par Render pour verifier que le service repond
    return {"ok": True}


# --- Inscription -----------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def accueil_public(request: Request, user: Optional[User] = Depends(current_user)):
    if user:
        return RedirectResponse("/accueil", status_code=303)
    return page(request, "inscription.html", form={})


@app.post("/inscription", response_class=HTMLResponse)
def inscription(
    request: Request,
    prenom: str = Form(""),
    email: str = Form(""),
    age: Optional[str] = Form(None),
    cgu: Optional[str] = Form(None),
    ia: Optional[str] = Form(None),
    partage: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    prenom, email = prenom.strip(), email.strip().lower()
    form = {"prenom": prenom, "email": email, "age": bool(age), "cgu": bool(cgu), "ia": bool(ia), "partage": bool(partage)}
    erreurs = []
    if not prenom or len(prenom) > 50:
        erreurs.append("Indiquez votre prénom (50 caractères maximum).")
    if not EMAIL_RE.match(email) or len(email) > 254:
        erreurs.append("Indiquez une adresse e-mail valide.")
    if not (age and cgu and ia):
        erreurs.append("Les trois premières cases sont nécessaires pour créer un compte.")
    if erreurs:
        return page(request, "inscription.html", status_code=400, form=form, erreurs=erreurs)

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        t = now()
        actif = email in config.ADMIN_EMAILS
        user = User(
            email=email, prenom=prenom, statut="actif" if actif else "attente", activated_at=t if actif else None,
            age_ok_at=t, cgu_at=t, cgu_version=config.CGU_VERSION, ia_consent_at=t,
            partage_consent=bool(partage), partage_consent_at=t if partage else None,
        )
        db.add(user)
        db.commit()
    if user.statut != "actif":
        return page(request, "attente.html", user=user)
    return _envoyer_lien(request, db, user)


def _envoyer_lien(request: Request, db: Session, user: User):
    link = auth.create_login_link(db, user)
    if link:
        auth.send_login_email(user, link)
    # meme page dans tous les cas : on ne revele pas si un compte existe
    return page(request, "lien_envoye.html", email=user.email)


# --- Connexion --------------------------------------------------------------

@app.get("/connexion", response_class=HTMLResponse)
def connexion_form(request: Request):
    return page(request, "connexion.html")


@app.post("/connexion", response_class=HTMLResponse)
def connexion(request: Request, email: str = Form(""), db: Session = Depends(get_db)):
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user and user.statut == "actif":
        return _envoyer_lien(request, db, user)
    return page(request, "lien_envoye.html", email=email)


@app.get("/auth/{token}")
def auth_lien(request: Request, token: str, db: Session = Depends(get_db)):
    user = auth.use_login_token(db, token)
    if user is None:
        return page(request, "lien_invalide.html", status_code=400)
    sid = auth.create_session(db, user)
    resp = RedirectResponse("/accueil" if user.onboarded else "/presentation", status_code=303)
    resp.set_cookie(auth.SESSION_COOKIE, sid, max_age=config.SESSION_DAYS * 86400,
                    httponly=True, samesite="lax", secure=config.COOKIE_SECURE)
    return resp


@app.post("/deconnexion")
def deconnexion(request: Request, db: Session = Depends(get_db)):
    auth.delete_session(db, request.cookies.get(auth.SESSION_COOKIE))
    resp = RedirectResponse("/connexion", status_code=303)
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


# --- Pages connectees ---------------------------------------------------------

SLIDES = [
    ("Ajoutez vos tickets", "Prenez le ticket en photo à la sortie du magasin, ou déposez le PDF reçu par e-mail. Toutes les enseignes fonctionnent."),
    ("Voyez où part votre argent", "Dépenses par mois, par magasin, par rayon et par produit, calculées automatiquement. Rien à saisir à la main."),
    ("Payez le juste prix", "FairBasket compare les prix de vos produits habituels et vous dit où faire vos courses pour payer moins cher."),
]


@app.get("/presentation", response_class=HTMLResponse)
def presentation(request: Request, etape: int = 1, user: User = Depends(require_user)):
    etape = min(max(etape, 1), len(SLIDES))
    titre, texte = SLIDES[etape - 1]
    return page(request, "presentation.html", etape=etape, total=len(SLIDES), titre=titre, texte=texte)


@app.post("/presentation/fin")
def presentation_fin(user: User = Depends(require_user), db: Session = Depends(get_db)):
    user.onboarded = True
    db.commit()
    return RedirectResponse("/accueil", status_code=303)


@app.get("/accueil", response_class=HTMLResponse)
def accueil(request: Request, user: User = Depends(require_user)):
    return page(request, "accueil.html", user=user, admin=auth.is_admin(user))


# --- Administration : liste d'attente --------------------------------------

def require_admin(user: User = Depends(require_user)) -> User:
    if not auth.is_admin(user):
        raise HTTPException(status_code=404)
    return user


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    attente = db.scalars(select(User).where(User.statut == "attente").order_by(User.created_at)).all()
    actifs = db.scalars(select(User).where(User.statut == "actif").order_by(User.created_at)).all()
    return page(request, "admin.html", attente=attente, actifs=actifs)


@app.post("/admin/activer/{user_id}")
def admin_activer(user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    if user.statut != "actif":
        user.statut, user.activated_at = "actif", now()
        db.commit()
        link = auth.create_login_link(db, user)
        if link:
            auth.send_login_email(user, link)
    return RedirectResponse("/admin", status_code=303)
