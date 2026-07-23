from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _normalize_database_url(url: str) -> str:
    # Railway commonly provides postgres:// or postgresql:// URLs.
    # Pin SQLAlchemy to psycopg3 to match installed dependency set.
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


engine = create_engine(_normalize_database_url(settings.database_url), future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
