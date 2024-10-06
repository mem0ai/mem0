from typing import Optional
import uuid
try:
    import sqlite3
    from sqlite3 import Connection
except ImportError:
    raise ImportError(
        "The 'sqlite' library is required. "
        "Please install it using 'pip install sqlite'."
    )
from mem0.history.base import HistoryDBBase


class Sqlite(HistoryDBBase):
    def __init__(
        self,
        conn: Optional[Connection] = None,
        db_path: Optional[str] = ":memory:",
    ):
        super().__init__()
        if conn:
            self.connection = conn
        else:
            self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self._migrate_history_table()
        self._create_history_table()

    
    def _migrate_history_table(self):
        with self.connection:
            cursor = self.connection.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mem_history'")
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # Get the current schema of the history table
                cursor.execute("PRAGMA table_info(mem_history)")
                current_schema = {row[1]: row[2] for row in cursor.fetchall()}

                # Define the expected schema
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

                # Check if the schemas are the same
                if current_schema != expected_schema:
                    # Rename the old table
                    cursor.execute("ALTER TABLE mem_history RENAME TO old_history")

                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS mem_history (
                            id TEXT PRIMARY KEY,
                            memory_id TEXT,
                            old_memory TEXT,
                            new_memory TEXT,
                            new_value TEXT,
                            event TEXT,
                            created_at DATETIME,
                            updated_at DATETIME,
                            is_deleted INTEGER
                        )
                    """
                    )

                    # Copy data from the old table to the new table
                    cursor.execute(
                        """
                        INSERT INTO mem_history
                        (id, memory_id, old_memory, new_memory, new_value, event, created_at, updated_at, is_deleted)
                        SELECT id, memory_id, prev_value, new_value, new_value, event, timestamp, timestamp, is_deleted
                        FROM old_history
                    """  # noqa: E501
                    )

                    cursor.execute("DROP TABLE old_history")

                    self.connection.commit()

    def _create_history_table(self):
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mem_history (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT,
                    old_memory TEXT,
                    new_memory TEXT,
                    new_value TEXT,
                    event TEXT,
                    created_at DATETIME,
                    updated_at DATETIME,
                    is_deleted INTEGER
                )
                """
            )

    def add_history(
        self,
        memory_id,
        old_memory,
        new_memory,
        event,
        created_at=None,
        updated_at=None,
        is_deleted=0,
    ):
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO mem_history
                (id, memory_id, old_memory, new_memory, event, created_at, updated_at, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

    def get_history(self, memory_id):
        cursor = self.connection.execute(
            """
            SELECT id, memory_id, old_memory, new_memory, event, created_at, updated_at
            FROM mem_history
            WHERE memory_id = ?
            ORDER BY updated_at ASC
            """,
            (memory_id,),
        )
        rows = cursor.fetchall()
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

    def reset(self):
        with self.connection:
            self.connection.execute("DROP TABLE IF EXISTS history")
