from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """SQLite (developpement, tests) : tables creees directement.
    PostgreSQL (en ligne) : la structure est geree par les migrations Alembic (alembic upgrade head)."""
    from . import models  # noqa: F401  (enregistre les tables)

    if config.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(engine)
