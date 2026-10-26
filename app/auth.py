"""Liens magiques, sessions et envoi des e-mails de connexion."""

import hashlib
import json
import logging
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .models import LoginToken, User, UserSession, now

log = logging.getLogger("fairbasket.auth")
SESSION_COOKIE = "fb_session"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(dt: datetime) -> datetime:
    # SQLite rend des dates sans fuseau : on les considere en UTC
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def links_last_hour(db: Session, user: User) -> int:
    since = now() - timedelta(hours=1)
    return db.scalar(
        select(func.count()).select_from(LoginToken).where(LoginToken.user_id == user.id, LoginToken.created_at >= since)
    )


def create_login_link(db: Session, user: User) -> Optional[str]:
    """Cree un lien valable 15 minutes. None si l'adresse a deja demande trop de liens."""
    if links_last_hour(db, user) >= config.MAX_LINKS_PER_HOUR:
        return None
    token = secrets.token_urlsafe(32)
    db.add(LoginToken(user_id=user.id, token_hash=_hash(token),
                      expires_at=now() + timedelta(minutes=config.LOGIN_TOKEN_MINUTES)))
    db.commit()
    return f"{config.BASE_URL}/auth/{token}"


def use_login_token(db: Session, token: str) -> Optional[User]:
    """Valide le jeton (une seule fois, avant expiration) et rend l'utilisateur."""
    row = db.scalar(select(LoginToken).where(LoginToken.token_hash == _hash(token)))
    if row is None or row.used_at is not None or _aware(row.expires_at) < now():
        return None
    if row.user.statut != "actif":
        return None
    row.used_at = now()
    db.commit()
    return row.user


def create_session(db: Session, user: User) -> str:
    sid = secrets.token_urlsafe(32)
    db.add(UserSession(id=_hash(sid), user_id=user.id, expires_at=now() + timedelta(days=config.SESSION_DAYS)))
    db.commit()
    return sid


def user_from_session(db: Session, sid: Optional[str]) -> Optional[User]:
    if not sid:
        return None
    row = db.get(UserSession, _hash(sid))
    if row is None or _aware(row.expires_at) < now():
        return None
    return row.user


def delete_session(db: Session, sid: Optional[str]) -> None:
    if sid:
        row = db.get(UserSession, _hash(sid))
        if row:
            db.delete(row)
            db.commit()


MAILS = {
    "fr": ("Votre lien de connexion FairBasket",
           "Bonjour {prenom},\n\nVoici votre lien pour vous connecter à FairBasket :\n{lien}\n\n"
           "Il est valable 15 minutes et ne sert qu'une fois. Si vous n'avez rien demandé, ignorez ce message."),
    "en": ("Your FairBasket login link",
           "Hello {prenom},\n\nHere is your link to log in to FairBasket:\n{lien}\n\n"
           "It is valid for 15 minutes and works once. If you did not ask for it, ignore this message."),
}


def _html(texte: str, lien: str) -> str:
    from html import escape
    corps = escape(texte).replace(escape(lien), f'<a href="{escape(lien)}">{escape(lien)}</a>').replace("\n", "<br>")
    return f'<div style="font-family:Arial,sans-serif;font-size:16px;line-height:1.5;color:#111">{corps}</div>'


def send_login_email(user: User, link: str) -> None:
    if config.EMAIL_BACKEND == "console":
        # developpement : pas d'envoi, le lien s'affiche dans le terminal
        log.warning("Lien de connexion pour %s : %s", user.email, link)
        return
    sujet, modele = MAILS.get(user.lang, MAILS["fr"])
    texte = modele.format(prenom=user.prenom, lien=link)
    corps = json.dumps({
        "sender": {"name": config.EMAIL_FROM_NAME, "email": config.EMAIL_FROM},
        "to": [{"email": user.email, "name": user.prenom}],
        "subject": sujet, "textContent": texte, "htmlContent": _html(texte, link),
    }).encode()
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=corps, method="POST", headers={
        "api-key": config.BREVO_API_KEY, "content-type": "application/json", "accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as rep:
            log.info("E-mail de connexion envoyé à %s (Brevo : %s)", user.email, rep.status)
    except urllib.error.HTTPError as e:  # reponse de Brevo : on garde son message, utile pour comprendre
        log.error("Échec d'envoi de l'e-mail de connexion à %s : Brevo %s %s", user.email, e.code,
                  e.read().decode(errors="replace")[:300])
    except Exception as e:  # reseau... ; on ne bloque pas la page, et jamais le lien dans les logs
        log.error("Échec d'envoi de l'e-mail de connexion à %s : %s", user.email, e)


def is_admin(user: Optional[User]) -> bool:
    return user is not None and user.email in config.ADMIN_EMAILS
