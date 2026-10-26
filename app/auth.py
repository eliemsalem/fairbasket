"""Liens magiques, sessions et envoi des e-mails de connexion."""

import hashlib
import logging
import secrets
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


def send_login_email(user: User, link: str) -> None:
    if config.EMAIL_BACKEND == "console":
        # developpement : pas d'envoi, le lien s'affiche dans le terminal
        log.warning("Lien de connexion pour %s : %s", user.email, link)
        return
    raise NotImplementedError("Envoi d'e-mails (Brevo) a brancher avant la mise en ligne")


def is_admin(user: Optional[User]) -> bool:
    return user is not None and user.email in config.ADMIN_EMAILS
