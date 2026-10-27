"""Tables de la base. Chaque ticket appartient a un utilisateur ; les prix partages sont anonymes."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy import false as sa_false
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
    liste: Mapped[list["ShoppingItem"]] = relationship(cascade="all, delete-orphan", order_by="ShoppingItem.id")
    evenements: Mapped[list["Evenement"]] = relationship(cascade="all, delete-orphan")
    avis: Mapped[list["Avis"]] = relationship(cascade="all, delete-orphan")


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
    # position du magasin : situe ou la personne fait ses courses, pour les prix du quartier
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lon: Mapped[Optional[float]] = mapped_column(Float)


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
    importe: Mapped[bool] = mapped_column(Boolean, default=False)  # historique importe : hors quota mensuel
    # adresse du magasin imprimee sur le ticket, ou confirmee par la personne (comme le total, elle se valide)
    adresse_ok: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
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
    nom: Mapped[str] = mapped_column(String(120))
    # nom sans accents ni majuscules : « Œufs bio ×6 » et « oeufs bio x6 » sont le meme produit
    cle: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    categorie: Mapped[Optional[str]] = mapped_column(String(40))
    # famille generique (« poisson », « fromage », « œufs ») : pour chercher par le sens
    famille: Mapped[Optional[str]] = mapped_column(String(60))


class ProductAlias(Base):
    """Memorise qu'un libelle d'une enseigne correspond a un produit : la meme ligne n'est plus redevinee."""

    __tablename__ = "product_aliases"
    __table_args__ = (UniqueConstraint("enseigne", "libelle"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    enseigne: Mapped[str] = mapped_column(String(60))
    libelle: Mapped[str] = mapped_column(String(120))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product: Mapped[Product] = relationship()


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


class ShoppingItem(Base):
    """Ligne de la liste de courses d'un utilisateur."""

    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nom: Mapped[str] = mapped_column(String(120))
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"))
    coche: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    product: Mapped[Optional[Product]] = relationship()


class OpenPrice(Base):
    """Prix releve en magasin, copie depuis Open Prices (Open Food Facts, licence ODbL).

    Copie locale des 90 derniers jours autour des zones des utilisateurs, rafraichie chaque jour."""

    __tablename__ = "open_prices"

    id: Mapped[int] = mapped_column(primary_key=True)  # identifiant du prix chez Open Prices
    nom: Mapped[str] = mapped_column(String(200))
    marque: Mapped[Optional[str]] = mapped_column(String(120))
    code_barres: Mapped[Optional[str]] = mapped_column(String(32))
    quantite: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    unite: Mapped[Optional[str]] = mapped_column(String(8))  # g, ml, kg, l…
    prix: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    prix_par: Mapped[Optional[str]] = mapped_column(String(10))  # KILOGRAM pour un prix au kilo
    promo: Mapped[bool] = mapped_column(Boolean, default=False)
    jour: Mapped[date] = mapped_column(Date, index=True)
    magasin: Mapped[str] = mapped_column(String(120))
    ville: Mapped[Optional[str]] = mapped_column(String(80))
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lon: Mapped[Optional[float]] = mapped_column(Float)
    synchronise_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ZonePrix(Base):
    """Zone dont on copie les prix Open Prices : un carre d'environ 10 km autour des magasins des tickets,
    ou d'une position « Autour de moi ». Aucun lien vers un utilisateur."""

    __tablename__ = "zones_prix"
    __table_args__ = (UniqueConstraint("lat", "lon"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lat: Mapped[float] = mapped_column(Float)  # centre arrondi au dixieme de degre
    lon: Mapped[float] = mapped_column(Float)
    copie_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Evenement(Base):
    """Journal d'utilisation pour l'administration : pages vues, tickets, erreurs. Garde 180 jours.

    page : le modele de l'adresse (« /tickets/{receipt_id} »), jamais une recherche ou le contenu d'un ticket."""

    __tablename__ = "evenements"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quand: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    # page, ticket_ok, ticket_ecart, ticket_illisible, ticket_refuse, erreur
    type: Mapped[str] = mapped_column(String(20), index=True)
    page: Mapped[Optional[str]] = mapped_column(String(80))
    detail: Mapped[Optional[str]] = mapped_column(String(300))


class Avis(Base):
    """Un souci ou une idee envoye depuis l'application."""

    __tablename__ = "avis"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quand: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    page: Mapped[Optional[str]] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(String(2000))
    traite: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
