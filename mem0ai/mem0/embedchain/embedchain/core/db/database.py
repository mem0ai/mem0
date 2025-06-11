import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import scoped_session, sessionmaker

from .models import Base


class DatabaseManager:
    def __init__(self, echo: bool = False):
        self.database_uri = os.environ.get("EMBEDCHAIN_DB_URI")
        self.echo = echo
        self.engine: Engine = None
        self._session_factory = None

    def setup_engine(self) -> None:
        """Initializes the database engine and session factory."""
        if not self.database_uri:
            raise RuntimeError("Database URI is not set. Set the EMBEDCHAIN_DB_URI environment variable.")
        connect_args = {}
        if self.database_uri.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self.engine = create_engine(self.database_uri, echo=self.echo, connect_args=connect_args)
        self._session_factory = scoped_session(sessionmaker(bind=self.engine))
        Base.metadata.bind = self.engine

    def init_db(self) -> None:
        """Creates all tables defined in the Base metadata."""
        if not self.engine:
            raise RuntimeError("Database engine is not initialized. Call setup_engine() first.")
        Base.metadata.create_all(self.engine)

    def get_session(self) -> SQLAlchemySession:
        """Provides a session for database operations."""
        if not self._session_factory:
            raise RuntimeError("Session factory is not initialized. Call setup_engine() first.")
        return self._session_factory()

    def close_session(self) -> None:
        """Closes the current session."""
        if self._session_factory:
            self._session_factory.remove()

    def execute_transaction(self, transaction_block):
        """Executes a block of code within a database transaction."""
        session = self.get_session()
        try:
            transaction_block(session)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            self.close_session()


# Singleton pattern to use throughout the application
database_manager = DatabaseManager()


# Convenience functions for backward compatibility and ease of use
def setup_engine(database_uri: str, echo: bool = False) -> None:
    database_manager.database_uri = database_uri
    database_manager.echo = echo
    database_manager.setup_engine()


def alembic_upgrade() -> None:
    """Upgrades the database to the latest version."""
    alembic_config_path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
    alembic_cfg = Config(alembic_config_path)
    command.upgrade(alembic_cfg, "head")


def init_db() -> None:
    alembic_upgrade()


def get_session() -> SQLAlchemySession:
    return database_manager.get_session()


def execute_transaction(transaction_block):
    database_manager.execute_transaction(transaction_block)
