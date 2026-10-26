"""Tables de la base. Chaque ticket appartiendra a un utilisateur (etape suivante)."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    prenom: Mapped[str] = mapped_column(String(50))
    # "attente" (liste d'attente) ou "actif"
    statut: Mapped[str] = mapped_column(String(10), default="attente")
    lang: Mapped[str] = mapped_column(String(2), default="fr")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)

    # accords : on garde la date (et la version des conditions) comme preuve
    age_ok_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cgu_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cgu_version: Mapped[str] = mapped_column(String(20))
    ia_consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    partage_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    partage_consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    login_tokens: Mapped[list["LoginToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class LoginToken(Base):
    """Lien magique : seul le hash du jeton est stocke."""

    __tablename__ = "login_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="login_tokens")


class UserSession(Base):
    """Session de connexion (30 jours), supprimable a la deconnexion."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")
