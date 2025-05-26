import logging
import sqlite3
import threading
import uuid
from typing import Any, Dict, List, Optional

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
        with self._lock, self.connection:
            cur = self.connection.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history'")
            if cur.fetchone() is None:
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
                return

            logger.info("Migrating history table to new schema (no convo columns).")
            cur.execute("ALTER TABLE history RENAME TO history_old")

            self._create_history_table()

            intersecting = list(expected_cols & old_cols)
            cols_csv = ", ".join(intersecting)
            cur.execute(f"INSERT INTO history ({cols_csv}) SELECT {cols_csv} FROM history_old")
            cur.execute("DROP TABLE history_old")

    def _create_history_table(self) -> None:
        with self._lock, self.connection:
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
        with self._lock, self.connection:
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
        with self._lock, self.connection:
            self.connection.execute("DROP TABLE IF EXISTS history")
        self._create_history_table()

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def __del__(self):
        self.close()
