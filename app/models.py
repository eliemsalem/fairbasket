"""Tables de la base. Chaque ticket appartient a un utilisateur ; les prix partages sont anonymes."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
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
    receipts: Mapped[list["Receipt"]] = relationship(cascade="all, delete-orphan")


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


class Store(Base):
    """Magasin, partage entre utilisateurs (une enseigne + un nom de magasin)."""

    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("enseigne", "nom"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    enseigne: Mapped[str] = mapped_column(String(60), index=True)
    nom: Mapped[str] = mapped_column(String(120))
    adresse: Mapped[Optional[str]] = mapped_column(String(200))
    code_postal: Mapped[Optional[str]] = mapped_column(String(10))
    ville: Mapped[Optional[str]] = mapped_column(String(80))


class Receipt(Base):
    """Ticket de caisse d'un utilisateur. Jamais visible par un autre utilisateur."""

    __tablename__ = "receipts"
    __table_args__ = (UniqueConstraint("user_id", "file_sha256"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stores.id"))
    achete_le: Mapped[Optional[datetime]] = mapped_column(DateTime)  # heure locale du ticket
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    somme_articles: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    remises_globales: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    # "ok" : somme des articles = total ; "ecart" : a corriger ; "illisible" ; "erreur"
    statut: Mapped[str] = mapped_column(String(10), default="ok")
    remarques: Mapped[Optional[str]] = mapped_column(String(500))

    source: Mapped[str] = mapped_column(String(5))  # "pdf" ou "photo"
    fichier_nom: Mapped[str] = mapped_column(String(200))
    file_sha256: Mapped[str] = mapped_column(String(64))
    fichier_chemin: Mapped[Optional[str]] = mapped_column(String(300))

    # suivi du cout de lecture par l'IA
    modele: Mapped[Optional[str]] = mapped_column(String(40))
    tokens_entree: Mapped[int] = mapped_column(Integer, default=0)
    tokens_sortie: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    store: Mapped[Optional[Store]] = relationship()
    items: Mapped[list["ReceiptItem"]] = relationship(back_populates="receipt", cascade="all, delete-orphan",
                                                      order_by="ReceiptItem.position")


class ReceiptItem(Base):
    """Ligne d'article telle que lue sur le ticket."""

    __tablename__ = "receipt_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    libelle: Mapped[str] = mapped_column(String(120))  # tel qu'imprime ("PAVE SAUM MONOPRIX")
    quantite: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=1)
    prix_unitaire: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    montant: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # paye pour la ligne, remise de ligne deduite
    remise: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    poids_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3))
    prix_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    illisible: Mapped[bool] = mapped_column(Boolean, default=False)
    # rempli a l'etape de restructuration (nom lisible, categorie, meme produit entre enseignes)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"))

    receipt: Mapped[Receipt] = relationship(back_populates="items")
    product: Mapped[Optional["Product"]] = relationship()


class Product(Base):
    """Produit normalise : « Pave de saumon », categorie, unite de comparaison."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(120), unique=True)
    categorie: Mapped[Optional[str]] = mapped_column(String(40))


class SharedPrice(Base):
    """Prix partage anonymement (accord facultatif) : aucun lien vers l'utilisateur ni le ticket."""

    __tablename__ = "shared_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    libelle: Mapped[str] = mapped_column(String(120))
    store: Mapped[Store] = relationship()
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"))
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    prix_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    jour: Mapped[date] = mapped_column(Date)  # le jour seulement, pas l'heure
