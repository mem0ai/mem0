import uuid
from typing import Any

from peewee import SqliteDatabase, MySQLDatabase, Model, TextField, DateTimeField, UUIDField, BooleanField, \
    DatabaseProxy
from playhouse.cockroachdb import CockroachDatabase
from typing_extensions import Literal
from uuid import UUID

SupportedStorageBackends = Literal["sqlite", "mysql", "cockroachdb"]

_database_proxy = DatabaseProxy()  # Create a proxy so it can be set up dynamically


# Simple way to set up the database for all models
class BaseModel(Model):
    class Meta:
        database = _database_proxy


# Define Tables
class History(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    memory_id = UUIDField()
    old_memory = TextField(null=True)
    new_memory = TextField()
    new_value = TextField()
    event = TextField()
    created_at = DateTimeField(default=None, null=True)
    updated_at = DateTimeField(default=None, null=True)
    is_deleted = BooleanField(default=False)


# array holding all tables to be initialized
_tables_to_initialize = [History]


class PeeweeManager:
    def __init__(self, db_connection_string: str,
                 db_backend: SupportedStorageBackends, db_params: dict,
                 init: bool):

        self.connection = PeeweeManager._connection_builder(db_connection_string, db_backend, db_params)
        _database_proxy.initialize(self.connection)

        self.connection.connect()
        if init:  #skiping the initialization of the database (and migrations) if the flag is set
            if db_backend == "sqlite":  # sqlite specific migrations
                self._migrate_history_table_sqlite()
            self._create_tables()

    @classmethod
    def _connection_builder(cls, db_connection_string,
                            db_backend: SupportedStorageBackends, db_params: dict[str, Any]):
        """Creates a connection to the database"""
        if db_backend == "sqlite":
            return SqliteDatabase(db_connection_string, check_same_thread=False, **db_params)
        elif db_backend == "mysql":
            return MySQLDatabase(db_connection_string, **db_params)
        elif db_backend == "cockroachdb":
            return CockroachDatabase(db_connection_string, **db_params)
        else:
            raise ValueError(f"Unsupported backend {db_backend}")

    def _migrate_history_table_sqlite(self):
        with self.connection.atomic():
            cursor = self.connection.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
            )
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # Get the current schema of the history table
                cursor.execute("PRAGMA table_info(history)")
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
                    cursor.execute("ALTER TABLE history RENAME TO old_history")

                    self.connection.create_tables([History], safe=True)

                    # Copy data from the old table to the new table
                    cursor.execute(
                        """
                        INSERT INTO history (id, memory_id, old_memory, new_memory, new_value, event, created_at, updated_at, is_deleted)
                        SELECT id, memory_id, prev_value, new_value, new_value, event, timestamp, timestamp, is_deleted
                        FROM old_history
                    """
                    )

                    cursor.execute("DROP TABLE old_history")

                    self.connection.commit()

    def _create_tables(self):
        """creates the tables if they do not exist in the database in transaction"""
        with self.connection.atomic():
            self.connection.create_tables(_tables_to_initialize, safe=True)

    def add_history(
            self,
            history: History
    ):
        """adds a history to the database atomically"""
        with self.connection.atomic():
            history.save()

    def get_history(self, memory_id: UUID) -> list[History]:
        """gets all history for a memory consistently"""
        with self.connection.atomic():
            return [history for history in History.select().where(History.memory_id == memory_id)]

    def reset(self):
        """drops history table atomically"""
        with self.connection.atomic():
            self.connection.drop_tables([History])
