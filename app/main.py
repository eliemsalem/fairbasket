"""FairBasket - serveur web : inscription, connexion par lien magique, liste d'attente."""

import re
from contextlib import asynccontextmanager
from typing import Optional

import csv
import io
import mimetypes
import shutil
from decimal import Decimal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import auth, config, stats, tickets
from .db import get_db, init_db
from .models import Receipt, ReceiptItem, Store, User, now

APP_DIR = config.ROOT / "app"


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="FairBasket", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

COULEURS = {"Carrefour": "#1F5FBF", "Monoprix": "#C2410C", "Naturalia": "#15803D", "Biocoop": "#A16207",
            "Auchan": "#BE185D", "Aldi": "#1E3A8A", "Lidl": "#0050AA"}


def _euros(v) -> str:
    return "—" if v is None else f"{v:,.2f}".replace(",", "\u202f").replace(".", ",") + "\u00a0€"


templates.env.filters["euros"] = _euros
templates.env.filters["couleur"] = lambda enseigne: COULEURS.get(enseigne or "", "#9A9A9A")

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
def accueil_public(request: Request, supprime: int = 0, user: Optional[User] = Depends(current_user)):
    if user:
        return RedirectResponse("/accueil", status_code=303)
    return page(request, "inscription.html", form={}, supprime=bool(supprime))


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
    return _envoyer_lien(request, db, user, inscription=True)


def _envoyer_lien(request: Request, db: Session, user: User, inscription: bool = False):
    link = auth.create_login_link(db, user)
    if link:
        auth.send_login_email(user, link)
    # a la connexion, meme page dans tous les cas : on ne revele pas si un compte existe
    return page(request, "lien_envoye.html", email=user.email, inscription=inscription)


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
    return RedirectResponse("/tickets/ajouter", status_code=303)


@app.get("/accueil", response_class=HTMLResponse)
def accueil(request: Request, periode: str = "an", user: User = Depends(require_user), db: Session = Depends(get_db)):
    recents = db.scalars(select(Receipt).where(Receipt.user_id == user.id)
                         .order_by(Receipt.achete_le.desc(), Receipt.id.desc()).limit(10)).all()
    a_corriger = db.scalars(select(Receipt).where(Receipt.user_id == user.id, Receipt.statut == "ecart")).all()
    return page(request, "accueil.html", user=user, admin=auth.is_admin(user), recents=recents,
                a_corriger=a_corriger, t=stats.tableau_de_bord(db, user, periode))


@app.get("/comparer", response_class=HTMLResponse)
def comparer(request: Request, onglet: str = "moi", q: str = "", user: User = Depends(require_user),
             db: Session = Depends(get_db)):
    q = q.strip()[:60]
    if onglet == "communaute":
        return page(request, "comparer.html", onglet=onglet, q=q, commu=stats.communaute(db, user, q))
    return page(request, "comparer.html", onglet="moi", q=q, c=stats.comparaisons(db, user, q))


# --- Profil et donnees personnelles -------------------------------------------

@app.get("/profil", response_class=HTMLResponse)
def profil(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return page(request, "profil.html", user=user, utilises=tickets.tickets_ce_mois(db, user),
                maximum=config.MAX_TICKETS_PAR_MOIS, nb_tickets=len(user.receipts))


@app.post("/profil/partage")
def profil_partage(partage: Optional[str] = Form(None), user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    user.partage_consent = bool(partage)
    user.partage_consent_at = now() if partage else None
    db.commit()
    return RedirectResponse("/profil", status_code=303)


@app.get("/profil/export.csv")
def profil_export(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Toutes les donnees de la personne, lisibles dans Excel (point-virgule, UTF-8 avec BOM)."""
    rows = db.scalars(select(Receipt).where(Receipt.user_id == user.id).order_by(Receipt.achete_le)
                      .options(selectinload(Receipt.items).selectinload(ReceiptItem.product),
                               selectinload(Receipt.store))).all()
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["date", "heure", "enseigne", "magasin", "total_ticket", "statut", "produit", "libelle_ticket",
                "categorie", "quantite", "montant", "prix_kg", "fichier"])
    virg = lambda v: "" if v is None else str(v).replace(".", ",")  # noqa: E731
    for r in rows:
        for it in r.items or [None]:
            w.writerow([r.achete_le.strftime("%d/%m/%Y") if r.achete_le else "",
                        r.achete_le.strftime("%H:%M") if r.achete_le else "",
                        r.store.enseigne if r.store else "", r.store.nom if r.store else "", virg(r.total), r.statut,
                        it.product.nom if it and it.product else "", it.libelle if it else "",
                        it.product.categorie if it and it.product else "", virg(it.quantite) if it else "",
                        virg(it.montant) if it else "", virg(it.prix_kg) if it else "", r.fichier_nom])
    return Response("\ufeff" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="fairbasket-mes-tickets.csv"'})


@app.post("/profil/supprimer")
def profil_supprimer(confirmation: str = Form(""), user: User = Depends(require_user),
                     db: Session = Depends(get_db)):
    if confirmation != "SUPPRIMER":
        return RedirectResponse("/profil?erreur=confirmation", status_code=303)
    # tickets, articles, sessions et liens partent avec le compte ; les prix partages restent, sans lien avec lui
    shutil.rmtree(config.UPLOAD_DIR / str(user.id), ignore_errors=True)
    db.delete(user)
    db.commit()
    resp = RedirectResponse("/?supprime=1", status_code=303)
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


# --- Tickets ----------------------------------------------------------------

TAILLE_MAX = 30 * 1024 * 1024


def _ticket_de(db: Session, user: User, receipt_id: int) -> Receipt:
    r = db.get(Receipt, receipt_id)
    if r is None or r.user_id != user.id:
        # un utilisateur ne voit jamais le ticket d'un autre (404, pas 403 : on ne revele rien)
        raise HTTPException(status_code=404)
    return r


@app.get("/tickets/ajouter", response_class=HTMLResponse)
def ticket_ajout(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return page(request, "ticket_ajout.html", utilises=tickets.tickets_ce_mois(db, user),
                maximum=config.MAX_TICKETS_PAR_MOIS)


@app.post("/tickets")
def ticket_envoi(request: Request, fichier: UploadFile = File(...), user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    data = fichier.file.read(TAILLE_MAX + 1)
    media_type = fichier.content_type
    if not media_type or media_type == "application/octet-stream":
        media_type = mimetypes.guess_type(fichier.filename or "")[0] or ""
    erreur = None
    if not data:
        erreur = "Le fichier est vide."
    elif len(data) > TAILLE_MAX:
        erreur = "Fichier trop lourd (30 Mo maximum)."
    else:
        try:
            res = tickets.enregistrer_ticket(db, user, data, fichier.filename or "ticket", media_type)
            suffixe = "?doublon=1" if res.doublon else ""
            return RedirectResponse(f"/tickets/{res.receipt.id}{suffixe}", status_code=303)
        except tickets.TicketRefuse as e:
            erreur = str(e)
    return page(request, "ticket_ajout.html", status_code=400, erreur=erreur,
                utilises=tickets.tickets_ce_mois(db, user), maximum=config.MAX_TICKETS_PAR_MOIS)


@app.get("/tickets/{receipt_id}", response_class=HTMLResponse)
def ticket_detail(request: Request, receipt_id: int, doublon: int = 0, user: User = Depends(require_user),
                  db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    ecart = (r.total - (r.somme_articles - r.remises_globales)) if r.total is not None else None
    enseignes = sorted({e for e in db.scalars(select(Store.enseigne).join(Receipt).where(Receipt.user_id == user.id))
                        if e != "Inconnue"} | set(COULEURS))
    return page(request, "ticket.html", r=r, doublon=bool(doublon), ecart=ecart, enseignes=enseignes)


@app.post("/tickets/{receipt_id}/corriger")
async def ticket_corriger(request: Request, receipt_id: int, user: User = Depends(require_user),
                          db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    form = await request.form()
    lignes = {it.id: (str(form.get(f"libelle_{it.id}", "")).strip(), tickets.montant_saisi(str(form.get(f"montant_{it.id}", ""))))
              for it in r.items}
    nouvelle = (str(form.get("libelle_new", "")).strip(), tickets.montant_saisi(str(form.get("montant_new", ""))))
    tickets.corriger_ticket(db, user, r, lignes, nouvelle)
    return RedirectResponse(f"/tickets/{r.id}", status_code=303)


@app.post("/tickets/{receipt_id}/magasin")
def ticket_magasin(receipt_id: int, enseigne: str = Form(""), magasin: str = Form(""),
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    tickets.changer_magasin(db, r, enseigne, magasin)
    return RedirectResponse(f"/tickets/{r.id}", status_code=303)


@app.post("/tickets/{receipt_id}/supprimer")
def ticket_supprimer(receipt_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    if r.fichier_chemin:
        (config.UPLOAD_DIR / r.fichier_chemin).unlink(missing_ok=True)
    db.delete(r)
    db.commit()
    return RedirectResponse("/accueil", status_code=303)


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
