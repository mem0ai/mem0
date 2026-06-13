import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# load .env file (make sure you have DATABASE_URL set)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./openmemory.db")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment")

_is_sqlite = DATABASE_URL.startswith("sqlite")

# SQLAlchemy engine & session.
if _is_sqlite:
    # SQLite (dev/single-node fallback): long busy timeout + WAL so concurrent
    # writers (multiple uvicorn workers) wait for the lock instead of erroring
    # with "database is locked".
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
else:
    # PostgreSQL (production): bounded, validated connection pool. With multiple
    # uvicorn workers each holding a pool, pool_pre_ping avoids serving stale
    # connections (Railway recycles idle ones) and pool_recycle caps lifetime.
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
