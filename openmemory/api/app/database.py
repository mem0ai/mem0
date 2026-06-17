import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./openmemory.db")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment")


def is_sqlite(url: str | None = None) -> bool:
    """Whether ``url`` uses the SQLite dialect."""
    return (url or DATABASE_URL).startswith("sqlite")


def is_postgresql(url: str | None = None) -> bool:
    """Whether ``url`` uses the PostgreSQL dialect."""
    return (url or DATABASE_URL).startswith("postgresql")


def engine_connect_args(url: str | None = None) -> dict:
    """SQLAlchemy ``connect_args`` appropriate for the dialect in ``url``.

    SQLite requires ``check_same_thread=False`` for multi-threaded access;
    PostgreSQL (via PgBouncer or direct) must not receive that argument.
    """
    if is_sqlite(url):
        return {"check_same_thread": False}
    return {}


engine = create_engine(DATABASE_URL, connect_args=engine_connect_args())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
