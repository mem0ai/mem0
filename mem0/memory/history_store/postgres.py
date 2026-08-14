import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from mem0.memory.history_store.base import HistoryStoreBase

logger = logging.getLogger(__name__)

_CREATE_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS history (
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

_CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id            TEXT PRIMARY KEY,
    session_scope TEXT,
    role          TEXT,
    content       TEXT,
    name          TEXT,
    created_at    TEXT
)
"""

_CREATE_HISTORY_INDEX = "CREATE INDEX IF NOT EXISTS ix_history_memory_id_created_at ON history (memory_id, created_at)"
_CREATE_MESSAGES_INDEX = (
    "CREATE INDEX IF NOT EXISTS ix_messages_session_scope_created_at ON messages (session_scope, created_at)"
)

_INSERT_HISTORY = """
INSERT INTO history (
    id, memory_id, old_memory, new_memory, event,
    created_at, updated_at, is_deleted, actor_id, role
)
VALUES (
    :id, :memory_id, :old_memory, :new_memory, :event,
    :created_at, :updated_at, :is_deleted, :actor_id, :role
)
"""

_INSERT_MESSAGE = """
INSERT INTO messages (id, session_scope, role, content, name, created_at)
VALUES (:id, :session_scope, :role, :content, :name, :created_at)
"""


def _as_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value if isinstance(value, str) else str(value)


class PostgresHistoryStore(HistoryStoreBase):
    """SQLAlchemy history store targeting PostgreSQL (any SQLAlchemy URL works)."""

    def __init__(self, url: str, pool_size: int = 5, max_overflow: int = 10):
        self.url = url
        connect_kwargs: Dict[str, Any] = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            from sqlalchemy.pool import StaticPool

            connect_kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                connect_kwargs["poolclass"] = StaticPool
        else:
            connect_kwargs["pool_size"] = pool_size
            connect_kwargs["max_overflow"] = max_overflow

        try:
            self.engine: Optional[Engine] = create_engine(url, **connect_kwargs)
        except ModuleNotFoundError as exc:
            raise ImportError(
                "PostgreSQL history store requires psycopg. Install with: pip install 'mem0ai[vector-stores]'"
            ) from exc

        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
        if not self.engine:
            raise RuntimeError("Cannot create tables on a closed PostgresHistoryStore")
        with self.engine.begin() as conn:
            conn.execute(text(_CREATE_HISTORY_TABLE))
            conn.execute(text(_CREATE_HISTORY_INDEX))
            conn.execute(text(_CREATE_MESSAGES_TABLE))
            conn.execute(text(_CREATE_MESSAGES_INDEX))

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
        self.batch_add_history(
            [
                {
                    "memory_id": memory_id,
                    "old_memory": old_memory,
                    "new_memory": new_memory,
                    "event": event,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "is_deleted": is_deleted,
                    "actor_id": actor_id,
                    "role": role,
                }
            ]
        )

    def batch_add_history(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        if not self.engine:
            raise RuntimeError("Cannot write to a closed PostgresHistoryStore")
        payload = [
            {
                "id": str(uuid.uuid4()),
                "memory_id": record.get("memory_id"),
                "old_memory": record.get("old_memory"),
                "new_memory": record.get("new_memory"),
                "event": record.get("event"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "is_deleted": record.get("is_deleted", 0),
                "actor_id": record.get("actor_id"),
                "role": record.get("role"),
            }
            for record in records
        ]
        try:
            with self._lock:
                with self.engine.begin() as conn:
                    conn.execute(text(_INSERT_HISTORY), payload)
        except Exception as e:
            logger.error(f"Failed to batch add history records: {e}")
            raise

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        if not self.engine:
            raise RuntimeError("Cannot read from a closed PostgresHistoryStore")
        with self._lock:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT id, memory_id, old_memory, new_memory, event,
                               created_at, updated_at, is_deleted, actor_id, role
                        FROM history
                        WHERE memory_id = :memory_id
                        ORDER BY created_at ASC, updated_at ASC
                        """
                    ),
                    {"memory_id": memory_id},
                ).fetchall()

        return [
            {
                "id": r[0],
                "memory_id": r[1],
                "old_memory": r[2],
                "new_memory": r[3],
                "event": r[4],
                "created_at": _as_iso(r[5]),
                "updated_at": _as_iso(r[6]),
                "is_deleted": bool(r[7]),
                "actor_id": r[8],
                "role": r[9],
            }
            for r in rows
        ]

    def save_messages(self, messages: List[Dict[str, Any]], session_scope: str) -> None:
        if not messages:
            return
        if not self.engine:
            raise RuntimeError("Cannot write to a closed PostgresHistoryStore")
        now = datetime.now(timezone.utc)
        payload = [
            {
                "id": str(uuid.uuid4()),
                "session_scope": session_scope,
                "role": message.get("role"),
                "content": message.get("content"),
                "name": message.get("name"),
                "created_at": (now + timedelta(microseconds=i)).isoformat(),
            }
            for i, message in enumerate(messages)
        ]
        try:
            with self._lock:
                with self.engine.begin() as conn:
                    conn.execute(text(_INSERT_MESSAGE), payload)
                    conn.execute(
                        text(
                            """
                            DELETE FROM messages
                            WHERE session_scope = :session_scope
                              AND id IN (
                                SELECT id FROM (
                                    SELECT id,
                                           ROW_NUMBER() OVER (ORDER BY created_at DESC, id DESC) AS rn
                                    FROM messages
                                    WHERE session_scope = :session_scope
                                ) ranked
                                WHERE rn > 10
                              )
                            """
                        ),
                        {"session_scope": session_scope},
                    )
        except Exception as e:
            logger.error(f"Failed to save messages: {e}")
            raise

    def get_last_messages(self, session_scope: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.engine:
            raise RuntimeError("Cannot read from a closed PostgresHistoryStore")
        with self._lock:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT role, content, name, created_at FROM (
                            SELECT role, content, name, created_at, id
                            FROM messages
                            WHERE session_scope = :session_scope
                            ORDER BY created_at DESC, id DESC
                            LIMIT :limit
                        ) recent
                        ORDER BY created_at ASC, id ASC
                        """
                    ),
                    {"session_scope": session_scope, "limit": limit},
                ).fetchall()

        return [
            {
                "role": r[0],
                "content": r[1],
                "name": r[2],
                "created_at": _as_iso(r[3]),
            }
            for r in rows
        ]

    def reset(self) -> None:
        if not self.engine:
            raise RuntimeError("Cannot reset a closed PostgresHistoryStore")
        try:
            with self._lock:
                with self.engine.begin() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS history"))
                    conn.execute(text("DROP TABLE IF EXISTS messages"))
        except Exception as e:
            logger.error(f"Failed to reset tables: {e}")
            raise

    def close(self) -> None:
        if self.engine:
            self.engine.dispose()
            self.engine = None
