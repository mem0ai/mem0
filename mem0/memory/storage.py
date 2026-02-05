import logging
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

try:
    import psycopg
    from psycopg_pool import ConnectionPool as PsycopgPool
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None
    PsycopgPool = None

try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool as Psycopg2Pool
except ImportError:  # pragma: no cover - optional dependency
    psycopg2 = None
    Psycopg2Pool = None

logger = logging.getLogger(__name__)


class SQLiteManager:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._migrate_history_table()
        self._create_history_table()

    def _migrate_history_table(self) -> None:
        """
        If a pre-existing history table had the old group-chat columns,
        rename it, create the new schema, copy the intersecting data, then
        drop the old table.
        """
        with self._lock:
            try:
                # Start a transaction
                self.connection.execute("BEGIN")
                cur = self.connection.cursor()

                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history'")
                if cur.fetchone() is None:
                    self.connection.execute("COMMIT")
                    return  # nothing to migrate

                cur.execute("PRAGMA table_info(history)")
                old_cols = {row[1] for row in cur.fetchall()}

                expected_cols = {
                    "id",
                    "memory_id",
                    "old_memory",
                    "new_memory",
                    "event",
                    "created_at",
                    "updated_at",
                    "is_deleted",
                    "actor_id",
                    "role",
                }

                if old_cols == expected_cols:
                    self.connection.execute("COMMIT")
                    return

                logger.info("Migrating history table to new schema (no convo columns).")

                # Clean up any existing history_old table from previous failed migration
                cur.execute("DROP TABLE IF EXISTS history_old")

                # Rename the current history table
                cur.execute("ALTER TABLE history RENAME TO history_old")

                # Create the new history table with updated schema
                cur.execute(
                    """
                    CREATE TABLE history (
                        id           TEXT PRIMARY KEY,
                        memory_id    TEXT,
                        old_memory   TEXT,
                        new_memory   TEXT,
                        event        TEXT,
                        created_at   DATETIME,
                        updated_at   DATETIME,
                        is_deleted   INTEGER,
                        actor_id     TEXT,
                        role         TEXT
                    )
                """
                )

                # Copy data from old table to new table
                intersecting = list(expected_cols & old_cols)
                if intersecting:
                    cols_csv = ", ".join(intersecting)
                    cur.execute(f"INSERT INTO history ({cols_csv}) SELECT {cols_csv} FROM history_old")

                # Drop the old table
                cur.execute("DROP TABLE history_old")

                # Commit the transaction
                self.connection.execute("COMMIT")
                logger.info("History table migration completed successfully.")

            except Exception as e:
                # Rollback the transaction on any error
                self.connection.execute("ROLLBACK")
                logger.error(f"History table migration failed: {e}")
                raise

    def _create_history_table(self) -> None:
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS history (
                        id           TEXT PRIMARY KEY,
                        memory_id    TEXT,
                        old_memory   TEXT,
                        new_memory   TEXT,
                        event        TEXT,
                        created_at   DATETIME,
                        updated_at   DATETIME,
                        is_deleted   INTEGER,
                        actor_id     TEXT,
                        role         TEXT
                    )
                """
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to create history table: {e}")
                raise

    def add_history(
        self,
        memory_id: str,
        old_memory: Optional[str],
        new_memory: Optional[str],
        event: str,
        *,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        is_deleted: int = 0,
        actor_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    """
                    INSERT INTO history (
                        id, memory_id, old_memory, new_memory, event,
                        created_at, updated_at, is_deleted, actor_id, role
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(uuid.uuid4()),
                        memory_id,
                        old_memory,
                        new_memory,
                        event,
                        created_at,
                        updated_at,
                        is_deleted,
                        actor_id,
                        role,
                    ),
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to add history record: {e}")
                raise

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self.connection.execute(
                """
                SELECT id, memory_id, old_memory, new_memory, event,
                       created_at, updated_at, is_deleted, actor_id, role
                FROM history
                WHERE memory_id = ?
                ORDER BY created_at ASC, DATETIME(updated_at) ASC
            """,
                (memory_id,),
            )
            rows = cur.fetchall()

        return [
            {
                "id": r[0],
                "memory_id": r[1],
                "old_memory": r[2],
                "new_memory": r[3],
                "event": r[4],
                "created_at": r[5],
                "updated_at": r[6],
                "is_deleted": bool(r[7]),
                "actor_id": r[8],
                "role": r[9],
            }
            for r in rows
        ]

    def reset(self) -> None:
        """Drop and recreate the history table."""
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute("DROP TABLE IF EXISTS history")
                self.connection.execute("COMMIT")
                self._create_history_table()
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to reset history table: {e}")
                raise

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def __del__(self):
        self.close()


def _sanitize_identifier(name: str) -> str:
    if not name:
        raise ValueError("History table name cannot be empty.")
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError("History table name contains invalid characters.")
    return name


class PostgresHistoryManager:
    def __init__(self, dsn: str, table_name: str = "history", minconn: int = 1, maxconn: int = 5):
        if not dsn:
            raise ValueError("history_db_url is required for postgres history store.")
        self.table_name = _sanitize_identifier(table_name)
        self._pool_kind = None
        self._pool = None
        self._dsn = dsn

        if psycopg and PsycopgPool:
            self._pool = PsycopgPool(conninfo=dsn, min_size=minconn, max_size=maxconn, open=True)
            self._pool_kind = "psycopg3"
        elif psycopg2 and Psycopg2Pool:
            self._pool = Psycopg2Pool(minconn=minconn, maxconn=maxconn, dsn=dsn)
            self._pool_kind = "psycopg2"
        elif psycopg:
            # Fallback: create a connection per operation
            self._pool_kind = "psycopg3"
        else:
            raise ImportError(
                "Postgres history store requires 'psycopg' or 'psycopg2'. "
                "Install psycopg[pool] or psycopg2."
            )

        self._create_history_table()

    @contextmanager
    def _get_connection(self):
        if self._pool_kind == "psycopg3" and self._pool is not None:
            with self._pool.connection() as conn:
                yield conn
        elif self._pool_kind == "psycopg2" and self._pool is not None:
            conn = self._pool.getconn()
            try:
                yield conn
            finally:
                self._pool.putconn(conn)
        else:
            conn = psycopg.connect(self._dsn)
            try:
                yield conn
            finally:
                conn.close()

    def _execute(self, query: str, params: Optional[tuple] = None, fetch: bool = False):
        params = params or tuple()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall() if fetch else None
            conn.commit()
        return rows

    def _create_history_table(self) -> None:
        query = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id           TEXT PRIMARY KEY,
                memory_id    TEXT,
                old_memory   TEXT,
                new_memory   TEXT,
                event        TEXT,
                created_at   TEXT,
                updated_at   TEXT,
                is_deleted   INTEGER,
                actor_id     TEXT,
                role         TEXT
            )
        """
        self._execute(query)

    def add_history(
        self,
        memory_id: str,
        old_memory: Optional[str],
        new_memory: Optional[str],
        event: str,
        *,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        is_deleted: int = 0,
        actor_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        query = f"""
            INSERT INTO {self.table_name} (
                id, memory_id, old_memory, new_memory, event,
                created_at, updated_at, is_deleted, actor_id, role
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        self._execute(
            query,
            (
                str(uuid.uuid4()),
                memory_id,
                old_memory,
                new_memory,
                event,
                created_at,
                updated_at,
                is_deleted,
                actor_id,
                role,
            ),
        )

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        query = f"""
            SELECT id, memory_id, old_memory, new_memory, event,
                   created_at, updated_at, is_deleted, actor_id, role
            FROM {self.table_name}
            WHERE memory_id = %s
            ORDER BY created_at ASC, updated_at ASC
        """
        rows = self._execute(query, (memory_id,), fetch=True) or []
        return [
            {
                "id": r[0],
                "memory_id": r[1],
                "old_memory": r[2],
                "new_memory": r[3],
                "event": r[4],
                "created_at": r[5],
                "updated_at": r[6],
                "is_deleted": bool(r[7]),
                "actor_id": r[8],
                "role": r[9],
            }
            for r in rows
        ]

    def reset(self) -> None:
        query = f"TRUNCATE TABLE {self.table_name}"
        self._execute(query)

    def close(self) -> None:
        if self._pool_kind == "psycopg3" and self._pool is not None:
            self._pool.close()
        elif self._pool_kind == "psycopg2" and self._pool is not None:
            self._pool.closeall()

    def __del__(self):
        self.close()


def create_history_manager(config):
    provider = getattr(config, "history_db_provider", "sqlite")
    provider = (provider or "sqlite").strip().lower()
    if provider in {"postgres", "postgresql", "pg"}:
        dsn = getattr(config, "history_db_url", None)
        table = getattr(config, "history_db_table", "history")
        return PostgresHistoryManager(dsn, table)
    return SQLiteManager(getattr(config, "history_db_path", ":memory:"))
