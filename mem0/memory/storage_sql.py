import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, insert, select

from mem0.memory.storage_base import HistoryStoreBase

logger = logging.getLogger(__name__)


def _make_table(table_name: str, metadata: MetaData) -> Table:
    """Create a history Table bound to the given MetaData."""
    return Table(
        table_name,
        metadata,
        Column("id", String(36), primary_key=True),
        Column("memory_id", String(255), index=True),
        Column("old_memory", Text, nullable=True),
        Column("new_memory", Text, nullable=True),
        Column("event", String(50)),
        Column("created_at", String(50), nullable=True),
        Column("updated_at", String(50), nullable=True),
        Column("is_deleted", Integer, default=0),
        Column("actor_id", String(255), nullable=True),
        Column("role", String(50), nullable=True),
        extend_existing=True,
    )


class SQLHistoryStore(HistoryStoreBase):
    """History store backed by any SQLAlchemy-compatible database.

    Supports PostgreSQL, MySQL, SQLite (via SQLAlchemy), and any other
    database with a SQLAlchemy dialect.

    Args:
        url: SQLAlchemy database URL, e.g.:
            - ``postgresql://user:pass@host:5432/dbname``
            - ``mysql+pymysql://user:pass@host/dbname``
            - ``sqlite:///path/to/history.db``
        table_name: Name of the history table. Defaults to ``mem0_history``.
    """

    def __init__(self, url: str, table_name: str = "mem0_history"):
        self.table_name = table_name
        self.engine = create_engine(url)
        self.metadata = MetaData()
        self.table = _make_table(table_name, self.metadata)
        self.metadata.create_all(self.engine, tables=[self.table])

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
        stmt = insert(self.table).values(
            id=str(uuid.uuid4()),
            memory_id=memory_id,
            old_memory=old_memory,
            new_memory=new_memory,
            event=event,
            created_at=created_at,
            updated_at=updated_at,
            is_deleted=is_deleted,
            actor_id=actor_id,
            role=role,
        )
        with self.engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        stmt = (
            select(self.table)
            .where(self.table.c.memory_id == memory_id)
            .order_by(self.table.c.created_at.asc(), self.table.c.updated_at.asc())
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "id": row.id,
                    "memory_id": row.memory_id,
                    "old_memory": row.old_memory,
                    "new_memory": row.new_memory,
                    "event": row.event,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "is_deleted": bool(row.is_deleted),
                    "actor_id": row.actor_id,
                    "role": row.role,
                }
                for row in rows
            ]

    def reset(self) -> None:
        self.table.drop(self.engine, checkfirst=True)
        self.metadata.create_all(self.engine, tables=[self.table])

    def close(self) -> None:
        if self.engine:
            self.engine.dispose()
