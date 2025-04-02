import datetime
import threading
import uuid
from contextlib import contextmanager
from enum import Enum
from typing import Any, Dict, Generator, List, Optional

from pydantic import BaseModel, Field

# SQLAlchemy and database drivers
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.engine import Connection

# For URL parsing
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import QueuePool


class DatabaseType(Enum):
    """Supported database types"""

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class HistoryDBConfig(BaseModel):
    """Configuration for the history database."""

    type: DatabaseType = Field(
        DatabaseType.SQLITE, description="Type of database (SQLite, PostgreSQL, MySQL)"
    )
    url: str = Field(
        "sqlite:///:memory:", description="Complete database connection URL or path"
    )


class SQLDatabaseManager:
    """
    Database manager that supports SQLite, PostgreSQL, and MySQL databases
    with a consistent API across all database types.
    """

    def __init__(
        self,
        db_type: DatabaseType = DatabaseType.SQLITE,
        db_url: str = "sqlite:///:memory:",
        **kwargs,
    ):
        """
        Initialize database manager with the specified database type and connection URL.
        Args:
            db_type: Type of database (SQLite, PostgreSQL, MySQL)
            db_url: Complete database connection URL
            **kwargs: Additional connection parameters
        """
        self.db_type = db_type
        self._lock = threading.Lock()

        # Process URLs for SQLite that might be direct file paths
        if db_type == DatabaseType.SQLITE:
            if not db_url.startswith("sqlite:///") and not db_url.startswith(
                "sqlite://"
            ):
                if db_url == ":memory:" or not db_url:
                    db_url = "sqlite:///:memory:"
                else:
                    db_url = f"sqlite:///{db_url}"
            kwargs.setdefault("connect_args", {"check_same_thread": False})

        # For PostgreSQL: create the database if it does not exist.
        if db_type == DatabaseType.POSTGRESQL:
            url_obj = make_url(db_url)
            db_name = url_obj.database
            if not db_name:
                raise ValueError("No database name specified in db_url for PostgreSQL")
            # Change database to "postgres" so we can check for and create the target database
            master_url = url_obj.set(database="postgres")
            kwargs.pop("connect_args", None)
            try:
                master_engine = create_engine(
                    master_url.render_as_string(hide_password=False),
                    isolation_level="AUTOCOMMIT",
                    **kwargs,
                )
                with master_engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname=:dbname"),
                        {"dbname": db_name},
                    )
                    if result.scalar() is None:
                        conn.execute(text(f"CREATE DATABASE {db_name}"))
            except Exception as e:
                raise ConnectionError(
                    f"Failed to connect to PostgreSQL or create database: {e}"
                ) from e
            finally:
                master_engine.dispose()

        # Create engine for all database types
        self._engine = create_engine(db_url, poolclass=QueuePool, **kwargs)

        # Check the engine by performing a simple connection test
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            raise ConnectionError(f"Failed to establish connection with engine: {e}")

        # Set up database schema using SQLAlchemy MetaData
        self.metadata = MetaData()
        self.history_table = Table(
            "history",
            self.metadata,
            Column("id", String(36), primary_key=True),
            Column("memory_id", String(255), index=True),
            Column("old_memory", String),
            Column("new_memory", String),
            Column("new_value", String),
            Column("event", String(255)),
            Column("created_at", DateTime),
            Column("updated_at", DateTime, index=True),
            Column("is_deleted", Integer, default=0),
        )

        # Migrate and create table
        self._migrate_history_table()
        self._create_history_table()

    @contextmanager
    def _get_connection(self) -> Generator[Connection, None, None]:
        """Context manager for SQLAlchemy connections."""
        with self._engine.connect() as conn:
            yield conn

    def _create_history_table_sqlalchemy(self, conn: Connection) -> None:
        """Create history table for SQLite using SQLAlchemy raw SQL."""
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS history (
                id TEXT PRIMARY KEY,
                memory_id TEXT,
                old_memory TEXT,
                new_memory TEXT,
                new_value TEXT,
                event TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                is_deleted INTEGER DEFAULT 0
            )
            """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_history_memory_id ON history(memory_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_history_updated_at ON history(updated_at)"
            )
        )

    def _migrate_history_table(self) -> None:
        """Migrate history table schema if needed."""
        with self._lock:
            if self.db_type == DatabaseType.SQLITE:
                with self._get_connection() as conn:
                    result = conn.execute(
                        text(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
                        )
                    ).fetchone()
                    if result:
                        rows = conn.execute(
                            text("PRAGMA table_info(history)")
                        ).fetchall()
                        current_schema = {row[1]: row[2] for row in rows}
                        expected_schema = {
                            "id": "TEXT",
                            "memory_id": "TEXT",
                            "old_memory": "TEXT",
                            "new_memory": "TEXT",
                            "new_value": "TEXT",
                            "event": "TEXT",
                            "created_at": "DATETIME",
                            "updated_at": "DATETIME",
                            "is_deleted": "INTEGER",
                        }
                        missing_columns = set(expected_schema.keys()) - set(
                            current_schema.keys()
                        )
                        if missing_columns:
                            conn.execute(
                                text("ALTER TABLE history RENAME TO old_history")
                            )
                            self._create_history_table_sqlalchemy(conn)
                            common_columns = list(
                                set(current_schema.keys()) & set(expected_schema.keys())
                            )
                            cols = ", ".join(common_columns)
                            conn.execute(
                                text(
                                    f"INSERT INTO history ({cols}) SELECT {cols} FROM old_history"
                                )
                            )
                            conn.execute(text("DROP TABLE old_history"))
            else:
                with self._engine.begin() as conn:
                    inspector = inspect(conn)
                    tables = inspector.get_table_names()
                    if "history" in tables:
                        pass

    def _create_history_table(self) -> None:
        """Create history table if it doesn't exist."""
        with self._lock:
            if self.db_type == DatabaseType.SQLITE:
                with self._get_connection() as conn:
                    self._create_history_table_sqlalchemy(conn)
            else:
                self.metadata.create_all(self._engine, tables=[self.history_table])

    def _ensure_datetime(self, dt: Any) -> datetime.datetime:
        """Ensure the input is a datetime object. Convert from ISO format string if needed."""
        if isinstance(dt, datetime.datetime):
            return dt
        if isinstance(dt, str):
            try:
                return datetime.datetime.fromisoformat(dt)
            except Exception as e:
                raise TypeError(f"Invalid datetime string provided: {dt}") from e
        raise TypeError(
            "Value must be a datetime object or an ISO format datetime string."
        )

    def add_history(
        self,
        memory_id: str,
        old_memory: str,
        new_memory: str,
        event: str,
        created_at: Optional[datetime.datetime] = None,
        updated_at: Optional[datetime.datetime] = None,
        is_deleted: int = 0,
    ) -> str:
        """
        Add a history record to the database.
        Returns:
            The ID of the newly created history record
        """
        now = datetime.datetime.now()
        if created_at is None:
            created_at = now
        if updated_at is None:
            updated_at = now
        created_at = self._ensure_datetime(created_at)
        updated_at = self._ensure_datetime(updated_at)
        record_id = str(uuid.uuid4())
        with self._lock, self._engine.begin() as conn:
            stmt = insert(self.history_table).values(
                id=record_id,
                memory_id=memory_id,
                old_memory=old_memory,
                new_memory=new_memory,
                new_value=new_memory,
                event=event,
                created_at=created_at,
                updated_at=updated_at,
                is_deleted=is_deleted,
            )
            conn.execute(stmt)
        return record_id

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        """
        Get history records for a specific memory ID.
        Returns:
            List of history records as dictionaries
        """
        with self._lock, self._engine.connect() as conn:
            query = (
                select(
                    self.history_table.c.id,
                    self.history_table.c.memory_id,
                    self.history_table.c.old_memory,
                    self.history_table.c.new_memory,
                    self.history_table.c.event,
                    self.history_table.c.created_at,
                    self.history_table.c.updated_at,
                )
                .where(
                    self.history_table.c.memory_id == memory_id,
                    self.history_table.c.is_deleted == 0,
                )
                .order_by(self.history_table.c.updated_at.asc())
            )
            result = conn.execute(query)
            rows = result.fetchall()
            return [
                {
                    "id": row[0],
                    "memory_id": row[1],
                    "old_memory": row[2],
                    "new_memory": row[3],
                    "event": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                }
                for row in rows
            ]

    def delete_history(self, memory_id: str) -> int:
        """
        Soft delete history records for a specific memory ID.
        Returns:
            Number of records deleted
        """
        with self._lock, self._engine.begin() as conn:
            stmt = (
                update(self.history_table)
                .where(
                    self.history_table.c.memory_id == memory_id,
                    self.history_table.c.is_deleted == 0,
                )
                .values(is_deleted=1)
            )
            result = conn.execute(stmt)
            return result.rowcount

    def reset(self) -> None:
        """Reset database by dropping and recreating the history table."""
        with self._lock, self._engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS history"))
            self._create_history_table_sqlalchemy(conn)

    def close(self) -> None:
        """Close database connections properly."""
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def __enter__(self):
        """Enable context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connections when exiting context."""
        self.close()
        return False
