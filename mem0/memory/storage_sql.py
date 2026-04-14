import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base

from mem0.memory.storage_base import HistoryStoreBase

logger = logging.getLogger(__name__)

Base = declarative_base()


class HistoryRecord(Base):
    __tablename__ = "mem0_history"

    id = Column(String, primary_key=True)
    memory_id = Column(String, index=True)
    old_memory = Column(Text, nullable=True)
    new_memory = Column(Text, nullable=True)
    event = Column(String)
    created_at = Column(String, nullable=True)
    updated_at = Column(String, nullable=True)
    is_deleted = Column(Integer, default=0)
    actor_id = Column(String, nullable=True)
    role = Column(String, nullable=True)


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
        self.url = url
        self.table_name = table_name

        if table_name != "mem0_history":
            HistoryRecord.__tablename__ = table_name
            HistoryRecord.__table__.name = table_name

        self.engine = create_engine(url)
        Base.metadata.create_all(self.engine, tables=[HistoryRecord.__table__])

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
        record = HistoryRecord(
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
        with Session(self.engine) as session:
            session.add(record)
            session.commit()

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        with Session(self.engine) as session:
            rows = (
                session.query(HistoryRecord)
                .filter(HistoryRecord.memory_id == memory_id)
                .order_by(HistoryRecord.created_at.asc(), HistoryRecord.updated_at.asc())
                .all()
            )
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
        HistoryRecord.__table__.drop(self.engine, checkfirst=True)
        Base.metadata.create_all(self.engine, tables=[HistoryRecord.__table__])

    def close(self) -> None:
        if self.engine:
            self.engine.dispose()
