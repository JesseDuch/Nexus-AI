"""SQLAlchemy engine / session setup (SQLite by default, Postgres via DATABASE_URL)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

# Ensure the SQLite parent directory exists.
if settings.database_url.startswith("sqlite:///"):
    from pathlib import Path

    Path(settings.database_url.removeprefix("sqlite:///")).expanduser().parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
