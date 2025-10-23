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
        self._create_profiles_table()
        self._create_profile_history_table()

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

    def _create_profiles_table(self) -> None:
        """Create the profiles table for storing user profiles."""
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS profiles (
                        user_id                      TEXT PRIMARY KEY,
                        agent_id                     TEXT,
                        run_id                       TEXT,
                        profile_text                 TEXT,
                        created_at                   DATETIME,
                        updated_at                   DATETIME,
                        memory_count_at_last_update  INTEGER DEFAULT 0,
                        last_update_timestamp        INTEGER
                    )
                """
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to create profiles table: {e}")
                raise

    def _create_profile_history_table(self) -> None:
        """Create the profile_history table for tracking profile evolution."""
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS profile_history (
                        id                      TEXT PRIMARY KEY,
                        user_id                 TEXT,
                        agent_id                TEXT,
                        run_id                  TEXT,
                        profile_text            TEXT,
                        version                 INTEGER,
                        created_at              DATETIME,
                        memory_count            INTEGER,
                        update_reason           TEXT
                    )
                    """
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to create profile_history table: {e}")
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

    def get_profile(
        self,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a profile for a given user_id, agent_id, or run_id.

        Args:
            user_id: User identifier
            agent_id: Agent identifier
            run_id: Run identifier

        Returns:
            Profile dict or None if not found
        """
        if not any([user_id, agent_id, run_id]):
            raise ValueError("At least one of user_id, agent_id, or run_id must be provided")

        # Build the query dynamically based on provided identifiers
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)

        where_clause = " AND ".join(conditions)

        with self._lock:
            cur = self.connection.execute(
                f"""
                SELECT user_id, agent_id, run_id, profile_text, created_at, updated_at,
                       memory_count_at_last_update, last_update_timestamp
                FROM profiles
                WHERE {where_clause}
                """,
                tuple(params),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {
            "user_id": row[0],
            "agent_id": row[1],
            "run_id": row[2],
            "profile": row[3],
            "created_at": row[4],
            "updated_at": row[5],
            "memory_count_at_last_update": row[6],
            "last_update_timestamp": row[7],
        }

    def upsert_profile(
        self,
        profile_text: str,
        memory_count: int,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        update_reason: str = "manual",
    ) -> None:
        """
        Insert or update a profile for a given user_id, agent_id, or run_id.

        Args:
            profile_text: The generated profile text
            memory_count: Number of memories at the time of profile generation
            user_id: User identifier
            agent_id: Agent identifier
            run_id: Run identifier
            created_at: Creation timestamp
            updated_at: Update timestamp
            update_reason: Reason for update ('initial', 'memory_count', 'time_elapsed', 'manual')
        """
        if not any([user_id, agent_id, run_id]):
            raise ValueError("At least one of user_id, agent_id, or run_id must be provided")

        import time

        current_timestamp = int(time.time())

        with self._lock:
            try:
                self.connection.execute("BEGIN")

                # Check if profile exists (without using get_profile to avoid lock issues)
                conditions = []
                params = []
                if user_id:
                    conditions.append("user_id = ?")
                    params.append(user_id)
                if agent_id:
                    conditions.append("agent_id = ?")
                    params.append(agent_id)
                if run_id:
                    conditions.append("run_id = ?")
                    params.append(run_id)

                where_clause = " AND ".join(conditions)
                cur = self.connection.execute(
                    f"SELECT COUNT(*) FROM profiles WHERE {where_clause}",
                    tuple(params),
                )
                exists = cur.fetchone()[0] > 0

                if exists:
                    # Update existing profile - use the same WHERE clause we just built
                    update_params = [
                        profile_text,
                        updated_at,
                        memory_count,
                        current_timestamp,
                    ] + params

                    self.connection.execute(
                        f"""
                        UPDATE profiles
                        SET profile_text = ?,
                            updated_at = ?,
                            memory_count_at_last_update = ?,
                            last_update_timestamp = ?
                        WHERE {where_clause}
                        """,
                        tuple(update_params),
                    )
                else:
                    # Insert new profile
                    self.connection.execute(
                        """
                        INSERT INTO profiles (
                            user_id, agent_id, run_id, profile_text,
                            created_at, updated_at, memory_count_at_last_update,
                            last_update_timestamp
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            agent_id,
                            run_id,
                            profile_text,
                            created_at,
                            updated_at,
                            memory_count,
                            current_timestamp,
                        ),
                    )

                # Save to history - build params for WHERE clause in subquery
                history_params = [
                    str(uuid.uuid4()),
                    user_id,
                    agent_id,
                    run_id,
                    profile_text,
                ]
                # Add params for WHERE clause in subquery
                history_params.extend(params)
                # Add remaining fields
                history_params.extend([updated_at or created_at, memory_count, update_reason])

                self.connection.execute(
                    """
                    INSERT INTO profile_history (
                        id, user_id, agent_id, run_id, profile_text,
                        version, created_at, memory_count, update_reason
                    )
                    SELECT ?, ?, ?, ?, ?,
                           COALESCE((SELECT MAX(version) FROM profile_history WHERE """
                    + where_clause
                    + """), 0) + 1,
                           ?, ?, ?
                    """,
                    tuple(history_params),
                )

                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to upsert profile: {e}")
                raise

    def delete_profile(
        self,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        """Delete a profile for a given user_id, agent_id, or run_id."""
        if not any([user_id, agent_id, run_id]):
            raise ValueError("At least one of user_id, agent_id, or run_id must be provided")

        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)

        where_clause = " AND ".join(conditions)

        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    f"DELETE FROM profiles WHERE {where_clause}",
                    tuple(params),
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to delete profile: {e}")
                raise

    def add_profile_history(
        self,
        profile_text: str,
        memory_count: int,
        update_reason: str,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> None:
        """
        Add a profile version to history.

        Args:
            profile_text: The profile text
            memory_count: Number of memories at profile generation
            update_reason: Reason for update ('memory_count', 'time_elapsed', 'manual', 'initial')
            user_id: User identifier
            agent_id: Agent identifier
            run_id: Run identifier
            created_at: Creation timestamp
        """
        if not any([user_id, agent_id, run_id]):
            raise ValueError("At least one of user_id, agent_id, or run_id must be provided")

        with self._lock:
            try:
                self.connection.execute("BEGIN")

                # Get current max version for this user/agent/run
                conditions = []
                params = []
                if user_id:
                    conditions.append("user_id = ?")
                    params.append(user_id)
                if agent_id:
                    conditions.append("agent_id = ?")
                    params.append(agent_id)
                if run_id:
                    conditions.append("run_id = ?")
                    params.append(run_id)

                where_clause = " AND ".join(conditions)
                cur = self.connection.execute(
                    f"SELECT MAX(version) FROM profile_history WHERE {where_clause}",
                    tuple(params),
                )
                max_version = cur.fetchone()[0]
                new_version = (max_version or 0) + 1

                # Insert new history record
                self.connection.execute(
                    """
                    INSERT INTO profile_history (
                        id, user_id, agent_id, run_id, profile_text,
                        version, created_at, memory_count, update_reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        agent_id,
                        run_id,
                        profile_text,
                        new_version,
                        created_at,
                        memory_count,
                        update_reason,
                    ),
                )

                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to add profile history: {e}")
                raise

    def get_profile_history(
        self,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get profile history for a given user_id, agent_id, or run_id.

        Args:
            user_id: User identifier
            agent_id: Agent identifier
            run_id: Run identifier
            limit: Maximum number of versions to return (most recent first)

        Returns:
            List of profile history dicts, ordered by version descending
        """
        if not any([user_id, agent_id, run_id]):
            raise ValueError("At least one of user_id, agent_id, or run_id must be provided")

        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)

        where_clause = " AND ".join(conditions)
        limit_clause = f"LIMIT {limit}" if limit else ""

        with self._lock:
            cur = self.connection.execute(
                f"""
                SELECT id, user_id, agent_id, run_id, profile_text,
                       version, created_at, memory_count, update_reason
                FROM profile_history
                WHERE {where_clause}
                ORDER BY version DESC
                {limit_clause}
                """,
                tuple(params),
            )
            rows = cur.fetchall()

        return [
            {
                "id": r[0],
                "user_id": r[1],
                "agent_id": r[2],
                "run_id": r[3],
                "profile": r[4],
                "version": r[5],
                "created_at": r[6],
                "memory_count": r[7],
                "update_reason": r[8],
            }
            for r in rows
        ]

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def __del__(self):
        self.close()
