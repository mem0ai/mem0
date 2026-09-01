import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SQLiteManager:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._migrate_history_table()
        self._create_history_table()
        self._create_messages_table()
        self._create_message_seq_table()



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

    def _create_messages_table(self) -> None:
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT PRIMARY KEY,
                        session_scope TEXT,
                        role TEXT,
                        content TEXT,
                        name TEXT,
                        created_at DATETIME
                    )
                """
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to create messages table: {e}")
                raise

    def _create_message_seq_table(self) -> None:
        """Per-scope counter tracking how many messages were saved since the
        last relevance refresh. Used to trigger periodic cache refreshes
        (relevance-based eviction) instead of pure time-FIFO eviction."""
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS message_seq (
                        session_scope TEXT PRIMARY KEY,
                        saved_count INTEGER DEFAULT 0
                    )
                    """
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to create message_seq table: {e}")
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

    def batch_add_history(self, records: List[Dict[str, Any]]) -> None:
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.executemany(
                    """
                    INSERT INTO history (
                        id, memory_id, old_memory, new_memory, event,
                        created_at, updated_at, is_deleted, actor_id, role
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        (
                            str(uuid.uuid4()),
                            record.get("memory_id"),
                            record.get("old_memory"),
                            record.get("new_memory"),
                            record.get("event"),
                            record.get("created_at"),
                            record.get("updated_at"),
                            record.get("is_deleted", 0),
                            record.get("actor_id"),
                            record.get("role"),
                        )
                        for record in records
                    ],
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to batch add history records: {e}")
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

    def save_messages(
        self, messages: List[Dict[str, Any]], session_scope: str, keep_ids: Optional[set] = None
    ) -> None:
        """Insert messages, then FIFO-evict to the most recent ``window`` rows.

        ``keep_ids`` (set of message ids) are protected from eviction — used by
        the buffer gate so its KEEP decision is not undone by the plain FIFO
        trim. Callers of the gate should pass the keep_ids it returned.
        """
        if not messages:
            return
        keep_ids = keep_ids or set()
        window = 10
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                now = datetime.now(timezone.utc).isoformat()
                for message in messages:
                    self.connection.execute(
                        """
                        INSERT INTO messages (id, session_scope, role, content, name, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            str(uuid.uuid4()),
                            session_scope,
                            message.get("role"),
                            message.get("content"),
                            message.get("name"),
                            now,
                        ),
                    )
                if keep_ids:
                    # Keep the most recent `window` rows PLUS any gate-protected ids,
                    # evicting everything older than the union. Each UNION branch is
                    # wrapped in a derived table so ORDER BY/LIMIT apply per-branch.
                    placeholders = ",".join("?" * len(keep_ids))
                    self.connection.execute(
                        """
                        DELETE FROM messages WHERE session_scope = ? AND id NOT IN (
                            SELECT id FROM (
                                SELECT id FROM (
                                    SELECT id FROM messages
                                    WHERE session_scope = ? ORDER BY created_at DESC LIMIT ?
                                )
                                UNION
                                SELECT id FROM (
                                    SELECT id FROM messages
                                    WHERE session_scope = ? AND id IN ({})
                                )
                            )
                        )
                    """.format(placeholders),
                        (session_scope, session_scope, window, session_scope, *keep_ids),
                    )
                else:
                    # Plain FIFO eviction (no protected ids).
                    self.connection.execute(
                        """
                        DELETE FROM messages WHERE session_scope = ? AND id NOT IN (
                            SELECT id FROM (
                                SELECT id FROM messages WHERE session_scope = ? ORDER BY created_at DESC LIMIT ?
                            )
                        )
                    """,
                        (session_scope, session_scope, window),
                    )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to save messages: {e}")
                raise

    def get_last_messages(self, session_scope: str, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            # Subquery picks the latest N rows (DESC + LIMIT), outer query
            # re-sorts them chronologically (ASC) for the caller.
            cur = self.connection.execute(
                """
                SELECT role, content, name, created_at FROM (
                    SELECT role, content, name, created_at
                    FROM messages
                    WHERE session_scope = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ) ORDER BY created_at ASC
            """,
                (session_scope, limit),
            )
            rows = cur.fetchall()

        return [
            {
                "role": r[0],
                "content": r[1],
                "name": r[2],
                "created_at": r[3],
            }
            for r in rows
        ]

    def reset(self) -> None:
        """Drop both tables. Caller is expected to replace this instance."""
        if not self.connection:
            raise RuntimeError("Cannot reset a closed SQLiteManager")
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute("DROP TABLE IF EXISTS history")
                self.connection.execute("DROP TABLE IF EXISTS messages")
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to reset tables: {e}")
                raise

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def __del__(self):
        self.close()
    # ── Relevance-based cache refresh helpers ──────────────────────────────

    def get_all_messages(self, session_scope: str) -> List[Dict[str, Any]]:
        """Return ALL buffered messages for a scope, newest first, with ids."""
        with self._lock:
            cur = self.connection.execute(
                "SELECT id, role, content, name, created_at FROM messages WHERE session_scope = ? ORDER BY created_at DESC",
                (session_scope,),
            )
            rows = cur.fetchall()
        return [
            {"id": r[0], "role": r[1], "content": r[2], "name": r[3], "created_at": r[4]}
            for r in rows
        ]

    def delete_messages_except(self, session_scope: str, keep_ids: set) -> int:
        """Delete messages in a scope whose id is NOT in keep_ids. Returns count deleted.

        An empty keep_ids set means the LLM judged everything irrelevant, so the
        entire buffer for the scope is cleared (except nothing is kept)."""
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                if not keep_ids:
                    cur = self.connection.execute(
                        "DELETE FROM messages WHERE session_scope = ?", (session_scope,)
                    )
                else:
                    placeholders = ",".join("?" for _ in keep_ids)
                    cur = self.connection.execute(
                        f"DELETE FROM messages WHERE session_scope = ? AND id NOT IN ({placeholders})",
                        (session_scope, *keep_ids),
                    )
                deleted = cur.rowcount
                self.connection.execute("COMMIT")
                return deleted
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to delete messages except keep_ids: {e}")
                raise

    def increment_message_count(self, session_scope: str, delta: int = 1, refresh_interval: int = 0) -> bool:
            """Increment per-scope saved-message counter. Returns True when interval reached."""
            if refresh_interval <= 0:
                return False
            with self._lock:
                try:
                    self.connection.execute("BEGIN")
                    self.connection.execute(
                        "INSERT INTO message_seq (session_scope, saved_count) VALUES (?, ?) "
                        "ON CONFLICT(session_scope) DO UPDATE SET saved_count = saved_count + ?",
                        (session_scope, delta, delta),
                    )
                    cur = self.connection.execute(
                        "SELECT saved_count FROM message_seq WHERE session_scope = ?", (session_scope,)
                    )
                    count = cur.fetchone()[0]
                    if count >= refresh_interval:
                        # Reset counter
                        self.connection.execute(
                            "UPDATE message_seq SET saved_count = 0 WHERE session_scope = ?", (session_scope,)
                        )
                        self.connection.execute("COMMIT")
                        return True
                    self.connection.execute("COMMIT")
                    return False
                except Exception as e:
                    self.connection.execute("ROLLBACK")
                    logger.error(f"Failed to increment message count: {e}")
                    raise

    def reset_message_count(self, session_scope: str) -> None:
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    "UPDATE message_seq SET saved_count = 0 WHERE session_scope = ?", (session_scope,)
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to reset message count: {e}")
                raise

    def reset(self) -> None:
        """Drop both tables. Caller is expected to replace this instance."""
        if not self.connection:
            raise RuntimeError("Cannot reset a closed SQLiteManager")
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute("DROP TABLE IF EXISTS history")
                self.connection.execute("DROP TABLE IF EXISTS messages")
                self.connection.execute("DROP TABLE IF EXISTS message_seq")
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to reset tables: {e}")
                raise

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def __del__(self):
        self.close()
