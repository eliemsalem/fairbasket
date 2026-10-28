"""FairBasket - serveur web : inscription, connexion par lien magique, liste d'attente."""

import re
from contextlib import asynccontextmanager
from typing import Optional

import csv
import io
import logging
import mimetypes
import shutil
import threading
from urllib.parse import quote
from decimal import Decimal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from . import adresses, apprentissage, assistant, auth, config, i18n, liste, openprices, panier, stats, suivi, tickets
from .db import SessionLocal, get_db, init_db
from .lecture import CATEGORIES
from .models import Avis, LectureTicket, OpenPrice, Question, Product, Receipt, ReceiptItem, ShoppingItem, Store, User, now

APP_DIR = config.ROOT / "app"


# messages de l'application visibles dans les logs Render (niveau INFO), en plus de ceux d'uvicorn
_journal = logging.getLogger("fairbasket")
if not _journal.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s fairbasket: %(message)s"))
    _journal.addHandler(_h)
_journal.setLevel(logging.INFO)
log = logging.getLogger("fairbasket.pages")


def _accepter_la_liste_d_attente() -> None:
    """Inscription libre : les personnes encore en liste d'attente sont acceptees et recoivent leur lien."""
    try:
        with SessionLocal() as db:
            for user in db.scalars(select(User).where(User.statut == "attente")).all():
                _activer(db, user)
                log.info("Liste d'attente : compte %s accepté automatiquement", user.id)
    except Exception as e:
        log.error("Liste d'attente : acceptation automatique impossible : %s", e)


@asynccontextmanager
async def lifespan(_app):
    init_db()
    log.info("Démarrage : base %s, e-mails %s", config.DATABASE_URL.split(":", 1)[0], config.EMAIL_BACKEND)
    if config.OPEN_PRICES_AUTO:
        openprices.demarrer_synchro_quotidienne()
    if config.ADRESSES_AUTO:
        adresses.demarrer_recherche()
    with SessionLocal() as db:
        suivi.purger(db)
        apprentissage.purger(db)
    if config.INSCRIPTION_LIBRE:
        threading.Thread(target=_accepter_la_liste_d_attente, name="liste-attente", daemon=True).start()
    yield


app = FastAPI(title="FairBasket", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


def _noter_requete(request: Request, type: str, detail: Optional[str] = None) -> None:
    route = request.scope.get("route")
    page_ = getattr(route, "path", None) or request.url.path
    with SessionLocal() as db:
        user = auth.user_from_session(db, request.cookies.get(auth.SESSION_COOKIE))
        uid = user.id if user else None
    suivi.noter(uid, type, page_, detail)


@app.middleware("http")
async def suivre(request: Request, call_next):
    """Pages vues et erreurs, pour le suivi de l'administration (jamais la recherche ni un contenu)."""
    try:
        resp = await call_next(request)
    except Exception as e:
        await run_in_threadpool(_noter_requete, request, "erreur", f"{type(e).__name__} : {e}")
        raise
    chemin = request.url.path
    if resp.status_code >= 500:
        await run_in_threadpool(_noter_requete, request, "erreur", f"HTTP {resp.status_code}")
    elif (request.method == "GET" and resp.status_code < 400 and not chemin.startswith(suivi.IGNOREES)
          and "fragment" not in request.query_params):
        await run_in_threadpool(_noter_requete, request, "page")
    return resp

COULEURS = {"Carrefour": "#1F5FBF", "Monoprix": "#C2410C", "Naturalia": "#15803D", "Biocoop": "#A16207",
            "Auchan": "#BE185D", "Aldi": "#1E3A8A", "Lidl": "#0050AA"}


def _euros(v) -> str:
    return "—" if v is None else f"{v:,.2f}".replace(",", "\u202f").replace(".", ",") + "\u00a0€"


templates.env.filters["euros"] = _euros
templates.env.globals["est_bio"] = tickets.nom_bio
templates.env.globals["rayons"] = CATEGORIES
templates.env.globals["pres_km"] = f"{config.OPEN_PRICES_PRES_KM:g}"
templates.env.filters["couleur"] = lambda enseigne: COULEURS.get(enseigne or "", "#9A9A9A")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    return auth.user_from_session(db, request.cookies.get(auth.SESSION_COOKIE))


def require_user(user: Optional[User] = Depends(current_user)) -> User:
    if user is None:
        # pas connecte : retour a l'accueil public
        raise HTTPException(status_code=303, headers={"Location": "/connexion"})
    return user


def langue(request: Request) -> str:
    return i18n.langue_demandee(request.cookies.get("lang", ""), request.headers.get("accept-language", ""))


def require_admin(user: User = Depends(require_user)) -> User:
    if not auth.is_admin(user):
        raise HTTPException(status_code=404)
    return user


def page(request: Request, name: str, status_code: int = 200, **ctx):
    lang = langue(request)
    ctx.update(lang=lang, _=i18n.traducteur(lang), mois=i18n.nom_mois(lang))
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


@app.get("/langue/{code}")
def changer_langue(code: str, retour: str = "/", user: Optional[User] = Depends(current_user),
                   db: Session = Depends(get_db)):
    code = code if code in i18n.LANGUES else "fr"
    if user:
        user.lang = code
        db.commit()
    # seulement un chemin local, jamais une autre adresse
    resp = RedirectResponse(retour if retour.startswith("/") and not retour.startswith("//") else "/", status_code=303)
    resp.set_cookie("lang", code, max_age=365 * 86400, samesite="lax", secure=config.COOKIE_SECURE)
    return resp


@app.get("/sw.js")
def service_worker():
    # servi a la racine pour couvrir tout le site (condition pour installer l'application)
    return Response((APP_DIR / "static" / "sw.js").read_text(), media_type="application/javascript",
                    headers={"Cache-Control": "no-cache"})


@app.get("/health")
def health():
    # utilise par Render pour verifier que le service repond ; le type de base aide au diagnostic
    return {"ok": True, "base": config.DATABASE_URL.split(":", 1)[0].split("+")[0], "email": config.EMAIL_BACKEND,
            "cle_brevo": bool(config.BREVO_API_KEY), "expediteur": bool(config.EMAIL_FROM)}


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
        erreurs.append("Cochez les cases encadrées en rouge pour créer votre compte.")
    if erreurs:
        return page(request, "inscription.html", status_code=400, form=form, erreurs=erreurs)

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        t = now()
        actif = email in config.ADMIN_EMAILS or config.INSCRIPTION_LIBRE
        user = User(
            email=email, prenom=prenom, statut="actif" if actif else "attente", activated_at=t if actif else None,
            lang=langue(request),
            age_ok_at=t, cgu_at=t, cgu_version=config.CGU_VERSION, ia_consent_at=t,
            partage_consent=bool(partage), partage_consent_at=t if partage else None,
        )
        db.add(user)
        db.commit()
    if user.statut != "actif" and config.INSCRIPTION_LIBRE:  # inscrit avant l'ouverture : accepte maintenant
        user.statut, user.activated_at = "actif", now()
        db.commit()
    if user.statut != "actif":
        log.info("Inscription en liste d'attente (compte %s) : pas de lien envoyé", user.id)
        return page(request, "attente.html", user=user)
    return _envoyer_lien(request, db, user, inscription=True)


def _envoyer_lien(request: Request, db: Session, user: User, inscription: bool = False):
    link = auth.create_login_link(db, user)
    if link:
        envoye = auth.send_login_email(user, link)
        if not envoye:
            auth.annuler_lien(db, link)
        suivi.noter(user.id, "connexion", "/connexion", "lien envoyé" if envoye else "e-mail non envoyé")
    else:
        log.info("Lien non envoyé au compte %s : limite de liens par heure atteinte", user.id)
        suivi.noter(user.id, "connexion", "/connexion", "limite de liens par heure atteinte")
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
    if user and user.statut != "actif" and config.INSCRIPTION_LIBRE:
        user.statut, user.activated_at = "actif", now()
        db.commit()
    if user and user.statut == "actif":
        return _envoyer_lien(request, db, user)
    log.info("Demande de lien pour un compte %s : rien envoyé", "en liste d'attente" if user else "inexistant")
    suivi.noter(user.id if user else None, "connexion", "/connexion",
                "compte en liste d'attente" if user else "e-mail inconnu")
    return page(request, "lien_envoye.html", email=email)


@app.get("/auth/{token}")
def auth_lien(request: Request, token: str, db: Session = Depends(get_db)):
    user = auth.use_login_token(db, token)
    if user is None:
        suivi.noter(None, "connexion", "/auth/{token}", "lien expiré ou déjà utilisé")
        return page(request, "lien_invalide.html", status_code=400)
    sid = auth.create_session(db, user)
    resp = RedirectResponse("/accueil" if user.onboarded else "/presentation", status_code=303)
    resp.set_cookie(auth.SESSION_COOKIE, sid, max_age=config.SESSION_DAYS * 86400,
                    httponly=True, samesite="lax", secure=config.COOKIE_SECURE)
    resp.set_cookie("lang", user.lang, max_age=365 * 86400, samesite="lax", secure=config.COOKIE_SECURE)
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
                a_corriger=a_corriger, t=stats.tableau_de_bord(db, user, periode),
                assistant_ok=assistant.peut_utiliser(user))


@app.get("/rayon", response_class=HTMLResponse)
def rayon(request: Request, nom: str = "", user: User = Depends(require_user), db: Session = Depends(get_db)):
    if nom not in CATEGORIES:
        return RedirectResponse("/accueil", status_code=303)
    return page(request, "rayon.html", user=user, ry=stats.rayon(db, user, nom))


POSITION_COOKIE = "position"


def _position(request: Request) -> Optional[tuple]:
    """Position « Autour de moi », gardee seulement sur le telephone (cookie), arrondie a ~1 km."""
    try:
        lat, lon = (float(x) for x in request.cookies.get(POSITION_COOKIE, "").split(":"))
    except ValueError:
        return None
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def _zone(request: Request, db: Session, user: User) -> dict:
    return openprices.zone_de(db, user, _position(request))


@app.post("/position")
def position(lat: Optional[float] = Form(None), lon: Optional[float] = Form(None), retour: str = Form("/comparer"),
             _: User = Depends(require_user), db: Session = Depends(get_db)):
    """« Autour de moi » (une position) ou « Mes magasins » (sans position : la zone vient des tickets)."""
    resp = RedirectResponse(retour if retour.startswith("/") and not retour.startswith("//") else "/comparer",
                            status_code=303)
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        resp.delete_cookie(POSITION_COOKIE)
        return resp
    zone = openprices.ajouter_zone(db, lat, lon)
    db.commit()
    if zone.copie_le is None and config.OPEN_PRICES_AUTO:
        openprices.copier_en_fond(zone.id)
    resp.set_cookie(POSITION_COOKIE, f"{lat:.2f}:{lon:.2f}", max_age=30 * 86400, httponly=True, samesite="lax",
                    secure=config.COOKIE_SECURE)
    return resp


@app.get("/comparer", response_class=HTMLResponse)
def comparer(request: Request, onglet: str = "moi", q: str = "", fragment: int = 0,
             user: User = Depends(require_user), db: Session = Depends(get_db)):
    q = q.strip()[:60]
    # fragment=1 : seulement la liste des resultats (recherche pendant la frappe)
    gabarit = "_comparer_resultats.html" if fragment else "comparer.html"
    zone = _zone(request, db, user)
    # prix Open Prices releves dans les magasins proches de chez la personne
    ctx = dict(q=q, zone=zone, autour=openprices.chercher(db, q, zone=zone),
               zone_en_copie=openprices.zone_en_copie(db, zone))
    if onglet == "communaute":
        return page(request, gabarit, onglet=onglet, commu=stats.communaute(db, user, q), **ctx)
    return page(request, gabarit, onglet="moi", c=stats.comparaisons(db, user, q), **ctx)


# --- Liste de courses ----------------------------------------------------------

@app.get("/liste", response_class=HTMLResponse)
def liste_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return page(request, "liste.html", v=liste.vue(db, user))


PANIER_HABITUEL = 20


@app.get("/liste/comparer", response_class=HTMLResponse)
def liste_comparer(request: Request, fragment: int = 0, direct: int = 0, habituel: int = 0,
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Combien coute la liste (ou le panier habituel : demande, ou liste vide) dans chaque enseigne.
    La page s'affiche d'abord vide, puis le calcul arrive (fragment=1) : il peut prendre quelques secondes."""
    habituel = bool(habituel) or not [i for i in user.liste if not i.coche]
    if not fragment and not direct:
        return page(request, "panier.html", habituel=habituel, calcul_differe=True)
    tickets_user = liste._tickets(db, user)
    articles, poids = [(i.nom, i.product_id) for i in user.liste if not i.coche], None
    if habituel:
        # les produits les plus achetes, chacun compte autant de fois qu'il est achete
        _, noms, achats = stats._derniers_prix(tickets_user)
        plus_achetes = sorted(achats.items(), key=lambda kv: -kv[1])[:PANIER_HABITUEL]
        articles, poids = [(noms[pid], pid) for pid, _ in plus_achetes], [n for _, n in plus_achetes]
    zone = _zone(request, db, user)
    return page(request, "_panier_resultats.html" if fragment else "panier.html", habituel=habituel, zone=zone,
                r=panier.comparer_panier(db, user, articles, tickets_user, poids, zone) if articles else None)


@app.post("/liste")
def liste_ajout(nom: str = Form(""), product_id: Optional[int] = Form(None), user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    liste.ajouter(db, user, nom, db.get(Product, product_id) if product_id else None)
    return RedirectResponse("/liste", status_code=303)


def _ligne_de(db: Session, user: User, item_id: int) -> ShoppingItem:
    item = db.get(ShoppingItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404)
    return item


@app.post("/liste/{item_id}/cocher")
def liste_cocher(item_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    item = _ligne_de(db, user, item_id)
    item.coche = not item.coche
    db.commit()
    return RedirectResponse("/liste", status_code=303)


@app.post("/liste/vider")
def liste_vider(user: User = Depends(require_user), db: Session = Depends(get_db)):
    for item in [i for i in user.liste if i.coche]:
        db.delete(item)
    db.commit()
    return RedirectResponse("/liste", status_code=303)


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
MAX_PHOTOS = 6  # morceaux d'un meme ticket long


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


@app.get("/tickets/importer", response_class=HTMLResponse)
def tickets_importer(request: Request, _: User = Depends(require_admin)):
    return page(request, "importer.html")


@app.post("/tickets")
def ticket_envoi(request: Request, fichier: list[UploadFile] = File(...), importe: Optional[str] = Form(None),
                 meme_ticket: Optional[str] = Form(None), user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    # un fichier = un ticket ; avec meme_ticket, les fichiers sont les photos successives d'un ticket long
    fichiers = fichier[:MAX_PHOTOS] if meme_ticket else fichier[:1]
    contenus = [f.file.read(TAILLE_MAX + 1) for f in fichiers]
    media_type = fichiers[0].content_type
    if not media_type or media_type == "application/octet-stream":
        media_type = mimetypes.guess_type(fichiers[0].filename or "")[0] or ""
    erreur = None
    if not all(contenus):
        erreur = ("Le fichier est vide.", {})
    elif sum(len(c) for c in contenus) > TAILLE_MAX:
        erreur = ("Fichier trop lourd (30 Mo maximum).", {})
    else:
        try:
            # import d'historique (hors quota) : reserve a l'administration pour l'instant
            res = tickets.enregistrer_ticket(db, user, contenus[0], fichiers[0].filename or "ticket", media_type,
                                             importe=bool(importe) and auth.is_admin(user), suite=contenus[1:])
            suivi.noter(user.id, "ticket_doublon" if res.doublon else f"ticket_{res.receipt.statut}", "/tickets",
                        f"{'PDF' if media_type == 'application/pdf' else 'photo'}"
                        f"{f' en {len(contenus)} morceaux' if len(contenus) > 1 else ''} · {res.receipt.modele or ''}")
            suffixe = "?doublon=1" if res.doublon else ""
            return RedirectResponse(f"/tickets/{res.receipt.id}{suffixe}", status_code=303)
        except tickets.TicketRefuse as e:
            erreur = (e.cle, e.valeurs)
    if erreur:
        suivi.noter(user.id, "ticket_refuse", "/tickets", erreur[0].format(**erreur[1]))
    return page(request, "ticket_ajout.html", status_code=400, erreur=erreur,
                utilises=tickets.tickets_ce_mois(db, user), maximum=config.MAX_TICKETS_PAR_MOIS)


@app.get("/tickets/{receipt_id}", response_class=HTMLResponse)
def ticket_detail(request: Request, receipt_id: int, doublon: int = 0, retour: str = "/accueil",
                  user: User = Depends(require_user), db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    retour = retour if retour.startswith("/") and not retour.startswith("//") else "/accueil"  # page du site seulement
    ecart = (r.total - (r.somme_articles - r.remises_globales)) if r.total is not None else None
    enseignes = sorted({e for e in db.scalars(select(Store.enseigne).join(Receipt).where(Receipt.user_id == user.id))
                        if e != "Inconnue"} | set(COULEURS))
    return page(request, "ticket.html", r=r, doublon=bool(doublon), ecart=ecart, enseignes=enseignes, retour=retour)


@app.post("/tickets/{receipt_id}/corriger")
async def ticket_corriger(request: Request, receipt_id: int, user: User = Depends(require_user),
                          db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    form = await request.form()
    lignes = {it.id: (str(form.get(f"libelle_{it.id}", "")).strip(), tickets.montant_saisi(str(form.get(f"montant_{it.id}", ""))))
              for it in r.items}
    nouvelle = (str(form.get("libelle_new", "")).strip(), tickets.montant_saisi(str(form.get("montant_new", ""))))
    tickets.corriger_ticket(db, user, r, lignes, nouvelle)
    apprentissage.figer(db, r)
    return RedirectResponse(f"/tickets/{r.id}", status_code=303)


@app.post("/tickets/{receipt_id}/magasin")
def ticket_magasin(receipt_id: int, enseigne: str = Form(""), magasin: str = Form(""),
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    tickets.changer_magasin(db, r, enseigne, magasin)
    apprentissage.figer(db, r)
    return RedirectResponse(f"/tickets/{r.id}", status_code=303)


@app.post("/tickets/{receipt_id}/produit/{item_id}")
def ticket_produit(receipt_id: int, item_id: int, nom: str = Form(""), retour: str = Form(""),
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    item = next((it for it in r.items if it.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404)
    produit = tickets.renommer_produit(db, item, nom)
    apprentissage.figer(db, r)
    suivi.noter(user.id, "produit_renomme", "/tickets/{receipt_id}", f"{item.libelle} → {nom[:80]}")
    suite = f"?retour={quote(retour)}" if retour.startswith("/") and not retour.startswith("//") else ""
    return RedirectResponse(f"/tickets/{r.id}{suite}#p{produit.id if produit else ''}", status_code=303)


@app.post("/tickets/{receipt_id}/bio/{item_id}")
def ticket_bio(receipt_id: int, item_id: int, retour: str = Form(""), user: User = Depends(require_user),
               db: Session = Depends(get_db)):
    """Un geste : l'article est bio, ou ne l'est pas (meme effet que corriger son nom)."""
    r = _ticket_de(db, user, receipt_id)
    item = next((it for it in r.items if it.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404)
    nom = item.product.nom if item.product else item.libelle.capitalize()
    nom = tickets.sans_bio(nom) if tickets.nom_bio(nom) else tickets.avec_bio(nom)
    produit = tickets.renommer_produit(db, item, nom)
    apprentissage.figer(db, r)
    suivi.noter(user.id, "produit_renomme", "/tickets/{receipt_id}", f"{item.libelle} → {nom[:80]}")
    suite = f"?retour={quote(retour)}" if retour.startswith("/") and not retour.startswith("//") else ""
    return RedirectResponse(f"/tickets/{r.id}{suite}#p{produit.id if produit else ''}", status_code=303)


@app.post("/tickets/{receipt_id}/rayon/{item_id}")
def ticket_rayon(receipt_id: int, item_id: int, categorie: str = Form(""), retour: str = Form(""),
                 user: User = Depends(require_user), db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    item = next((it for it in r.items if it.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404)
    if tickets.changer_rayon(db, item, categorie):
        apprentissage.figer(db, r)
        suivi.noter(user.id, "rayon_change", "/tickets/{receipt_id}", f"{item.libelle} → {categorie}")
    suite = f"?retour={quote(retour)}" if retour.startswith("/") and not retour.startswith("//") else ""
    return RedirectResponse(f"/tickets/{r.id}{suite}#p{item.product_id or ''}", status_code=303)


@app.post("/tickets/{receipt_id}/adresse")
def ticket_adresse(receipt_id: int, adresse: str = Form(""), code_postal: str = Form(""), ville: str = Form(""),
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    r = _ticket_de(db, user, receipt_id)
    tickets.confirmer_adresse(db, r, adresse, code_postal, ville)
    apprentissage.figer(db, r)
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

# --- Avis ---------------------------------------------------------------------

def _retour_sur(chemin: str) -> str:
    return chemin if chemin.startswith("/") and not chemin.startswith("//") else "/accueil"


@app.get("/avis", response_class=HTMLResponse)
def avis_form(request: Request, de: str = "", retour: str = "/accueil", merci: int = 0,
              user: Optional[User] = Depends(current_user)):
    return page(request, "avis.html", de=de[:80], retour=_retour_sur(retour), merci=merci, user=user)


@app.post("/avis")
def avis_envoi(request: Request, message: str = Form(""), de: str = Form(""), retour: str = Form("/accueil"),
               email: str = Form(""), user: Optional[User] = Depends(current_user), db: Session = Depends(get_db)):
    message = message.strip()[:1800]
    if not message:
        return page(request, "avis.html", de=de[:80], retour=_retour_sur(retour), merci=0, user=user,
                    erreur="Écrivez quelques mots.", status_code=400)
    if user is None and email.strip():  # pas connecte (bloque a la connexion) : de quoi lui repondre
        message = f"[{email.strip()[:120]}] {message}"
    db.add(Avis(user_id=user.id if user else None, page=de[:80] or None, message=message))
    db.commit()
    log.info("Nouvel avis reçu (page %s)", de or "—")
    return RedirectResponse(f"/avis?merci=1&retour={_retour_sur(retour)}", status_code=303)


# --- Assistant « Demandez-moi » -------------------------------------------------

EXEMPLES_QUESTIONS = ("Où trouver des pastilles lave-vaisselle moins chères ?",
                      "Combien j'ai dépensé en fromage ce mois-ci ?", "Ajoute du lait à ma liste")


def _assistant_pour(user: User) -> User:
    if not assistant.peut_utiliser(user):
        raise HTTPException(status_code=404)
    return user


@app.get("/assistant", response_class=HTMLResponse)
def assistant_page(request: Request, q: Optional[int] = None, user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    _assistant_pour(user)
    historique = db.scalars(select(Question).where(Question.user_id == user.id)
                            .order_by(Question.id.desc()).limit(10)).all()
    return page(request, "assistant.html", user=user, historique=historique, derniere=q,
                exemples=EXEMPLES_QUESTIONS, reste=None if auth.is_admin(user) else max(
                    0, config.ASSISTANT_QUESTIONS_PAR_MOIS - assistant.questions_claude_du_mois(db, user)))


@app.post("/assistant")
def assistant_question(request: Request, question: str = Form(""), user: User = Depends(require_user),
                       db: Session = Depends(get_db)):
    _assistant_pour(user)
    if not question.strip():
        return RedirectResponse("/assistant", status_code=303)
    q = assistant.demander(db, user, question, _zone(request, db, user), langue(request))
    suivi.noter(user.id, "question", "/assistant", f"{q.moteur} · {q.intention or '—'} · "
                                                   f"{'trouvé' if q.trouve else 'rien'}")
    return RedirectResponse(f"/assistant?q={q.id}#q{q.id}", status_code=303)


@app.post("/assistant/{question_id}/avis")
def assistant_avis(question_id: int, note: int = Form(0), commentaire: str = Form(""),
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if q is None or q.user_id != user.id:
        raise HTTPException(status_code=404)
    assistant.noter_avis(db, q, note, commentaire)
    return RedirectResponse(f"/assistant?q={q.id}#q{q.id}", status_code=303)


# --- Administration --------------------------------------------------------------

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    attente = db.scalars(select(User).where(User.statut == "attente").order_by(User.created_at)).all()
    return page(request, "admin.html", attente=attente, s=suivi.tableau(db), nom_page=suivi.nom_page,
                inscription_libre=config.INSCRIPTION_LIBRE,
                open_prices=(db.scalar(select(func.count()).select_from(OpenPrice)), openprices.derniere_synchro(db)))


@app.get("/admin/utilisateurs/{user_id}", response_class=HTMLResponse)
def admin_utilisateur(request: Request, user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404)
    recus = db.scalars(select(Receipt).where(Receipt.user_id == u.id).order_by(Receipt.created_at.desc()).limit(30)).all()
    return page(request, "admin_utilisateur.html", u=u, evenements=suivi.parcours(db, u), recus=recus,
                nom_page=suivi.nom_page, avis=db.scalars(select(Avis).where(Avis.user_id == u.id)
                                                         .order_by(Avis.quand.desc())).all())


@app.get("/admin/assistant", response_class=HTMLResponse)
def admin_assistant(request: Request, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return page(request, "admin_assistant.html", s=apprentissage.tableau_questions(db),
                depense=assistant.depense_du_mois(db), budget=config.ASSISTANT_BUDGET_USD, moteur=config.ASSISTANT_MOTEUR,
                pour=config.ASSISTANT_POUR, appris=db.scalar(select(func.count()).select_from(assistant.ExpressionApprise)))


@app.get("/admin/lectures", response_class=HTMLResponse)
def admin_lectures(request: Request, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return page(request, "admin_lectures.html", s=apprentissage.tableau_lectures(db))


@app.get("/admin/lectures/{lecture_id}/fichier")
def admin_lecture_fichier(lecture_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    lecture = db.get(LectureTicket, lecture_id)
    chemin = config.UPLOAD_DIR / lecture.fichier_chemin if lecture and lecture.fichier_chemin else None
    if chemin is None or not chemin.resolve().is_relative_to(config.UPLOAD_DIR.resolve()) or not chemin.exists():
        raise HTTPException(status_code=404)
    return FileResponse(chemin)


@app.get("/admin/export/{quoi}.jsonl")
def admin_export(quoi: str, _: User = Depends(require_admin)):
    modele = {"questions": Question, "lectures": LectureTicket}.get(quoi)
    if modele is None:
        raise HTTPException(status_code=404)

    def lignes():
        with SessionLocal() as db:
            yield from apprentissage.exporter(db, modele)
    return StreamingResponse(lignes(), media_type="application/x-ndjson",
                             headers={"Content-Disposition": f'attachment; filename="fairbasket-{quoi}.jsonl"'})


@app.post("/admin/avis/{avis_id}/traite")
def admin_avis_traite(avis_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    a = db.get(Avis, avis_id)
    if a is not None:
        a.traite = not a.traite
        db.commit()
    return RedirectResponse("/admin#avis", status_code=303)


@app.post("/admin/open-prices")
def admin_open_prices(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        openprices.synchroniser(db)
    except Exception as e:
        log.error("Open Prices : synchronisation manuelle impossible : %s", e)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/bio")
def admin_bio(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    n = tickets.corriger_bio(db)
    log.info("Achats en magasin bio rattachés au produit bio : %s", n)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/magasins")
def admin_magasins(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    n = tickets.fusionner_magasins(db)
    log.info("Magasins en double fusionnés : %s", n)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/activer/{user_id}")
def admin_activer(user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    _activer(db, user)
    return RedirectResponse("/admin", status_code=303)


def _activer(db: Session, user: User) -> None:
    """Accepte le compte et lui envoie son lien de connexion."""
    if user.statut != "actif":
        user.statut, user.activated_at = "actif", now()
        db.commit()
        link = auth.create_login_link(db, user)
        if link and not auth.send_login_email(user, link):
            auth.annuler_lien(db, link)
