import sqlite3
import threading
import uuid
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class SQLiteManager:
    def __init__(self, db_path=":memory:"):
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._ensure_history_table_schema()

    def _execute_query(self, query: str, params: tuple = (), commit: bool = False):
        """Helper to execute queries with lock and connection management."""
        with self._lock:
            # Ensure connection is alive, especially for file-based DBs that might be closed
            if not self.connection:
                self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            
            with self.connection: # Context manager handles begin/commit/rollback
                cursor = self.connection.cursor()
                cursor.execute(query, params)
                if commit: # Only commit if it's a data-modifying statement that needs it
                    self.connection.commit() 
                return cursor

    def _ensure_history_table_schema(self):
        """
        Ensures the history table exists and has the correct schema,
        adding new columns if necessary.
        """
        base_create_query = """
            CREATE TABLE IF NOT EXISTS history (
                id TEXT PRIMARY KEY,
                memory_id TEXT,
                old_memory TEXT,
                new_memory TEXT, 
                event TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                is_deleted INTEGER DEFAULT 0
            );
        """
        self._execute_query(base_create_query, commit=True)

        # Add new columns if they don't exist
        columns_to_add = {
            "conversation_id": "TEXT",
            "participant_id": "TEXT"
        }
        
        cursor = self._execute_query("PRAGMA table_info(history)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_columns:
                try:
                    self._execute_query(f"ALTER TABLE history ADD COLUMN {col_name} {col_type}", commit=True)
                    logger.info(f"Added column '{col_name}' to 'history' table.")
                except sqlite3.OperationalError as e:
                    # This might happen in rare race conditions or if the column was just added
                    logger.warning(f"Could not add column '{col_name}': {e}. It might already exist.")

    def add_history(
        self,
        memory_id: str,
        old_memory: Optional[str],
        new_memory: Optional[str],
        event: str,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        is_deleted: int = 0,
        conversation_id: Optional[str] = None, 
        participant_id: Optional[str] = None,
    ):
        query = """
            INSERT INTO history (
                id, memory_id, conversation_id, participant_id,
                old_memory, new_memory, event, 
                created_at, updated_at, is_deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            str(uuid.uuid4()),
            memory_id,
            conversation_id,
            participant_id,
            old_memory,
            new_memory,
            event,
            created_at,
            updated_at,
            is_deleted,
        )
        self._execute_query(query, params, commit=True)

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT id, memory_id, conversation_id, participant_id,
                   old_memory, new_memory, event, created_at, updated_at, is_deleted
            FROM history
            WHERE memory_id = ?
            ORDER BY created_at ASC, DATETIME(updated_at) ASC
        """ 
        # DATETIME(updated_at) ensures correct sorting if updated_at can be NULL for ADD events
        cursor = self._execute_query(query, (memory_id,))
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "memory_id": row[1],
                "conversation_id": row[2],
                "participant_id": row[3],
                "old_memory": row[4],
                "new_memory": row[5],
                "event": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "is_deleted": bool(row[9]) # Convert to boolean
            }
            for row in rows
        ]

    def get_history_by_conversation(
        self, 
        conversation_id: str, 
        participant_id: Optional[str] = None, 
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [conversation_id]
        query = """
            SELECT id, memory_id, conversation_id, participant_id,
                   old_memory, new_memory, event, created_at, updated_at, is_deleted
            FROM history
            WHERE conversation_id = ?
        """
        if participant_id:
            query += " AND participant_id = ?"
            params.append(participant_id)
        
        query += " ORDER BY created_at ASC, DATETIME(updated_at) ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._execute_query(query, tuple(params))
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "memory_id": row[1],
                "conversation_id": row[2],
                "participant_id": row[3],
                "old_memory": row[4],
                "new_memory": row[5],
                "event": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "is_deleted": bool(row[9])
            }
            for row in rows
        ]

    def reset(self):
        """Drops and recreates the history table."""
        self._execute_query("DROP TABLE IF EXISTS history", commit=True)
        self._ensure_history_table_schema() # Recreate with the new schema

    def close(self): # Good practice to have a close method
        if self.connection:
            self.connection.close()
            self.connection = None

    def __del__(self): # Ensure connection is closed when object is garbage collected
        self.close()
