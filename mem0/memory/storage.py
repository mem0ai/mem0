import sqlite3
import uuid
from datetime import datetime


class SQLiteManager:
    def __init__(self, db_path=":memory:"):
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self._create_history_table()

    def _create_history_table(self):
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT,
                    prev_value TEXT,
                    new_value TEXT,
                    event TEXT,
                    timestamp DATETIME,
                    is_deleted INTEGER
                )
            """
            )

    def add_history(self, memory_id, prev_value, new_value, event, is_deleted=0):
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO history (id, memory_id, prev_value, new_value, event, timestamp, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(uuid.uuid4()),
                    memory_id,
                    prev_value,
                    new_value,
                    event,
                    datetime.utcnow(),
                    is_deleted,
                ),
            )

    def get_history(self, memory_id):
        cursor = self.connection.execute(
            """
            SELECT id, memory_id, prev_value, new_value, event, timestamp, is_deleted
            FROM history
            WHERE memory_id = ?
            ORDER BY timestamp ASC
        """,
            (memory_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "memory_id": row[1],
                "prev_value": row[2],
                "new_value": row[3],
                "event": row[4],
                "timestamp": row[5],
                "is_deleted": row[6],
            }
            for row in rows
        ]

    def reset(self):
        with self.connection:
            self.connection.execute("DROP TABLE IF EXISTS history")
