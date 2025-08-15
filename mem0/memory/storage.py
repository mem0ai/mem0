import logging
import uuid
from datetime import datetime
from typing import Any, Optional, Union

from sqlalchemy import (
    Column,
    DateTime,
    SmallInteger,
    String,
    create_engine,
    text,
)
from sqlalchemy.engine import url as _url
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class History(Base):
    __tablename__ = "history"
    id = Column(String, primary_key=True)
    user_id = Column(String, default="", index=True)
    memory_id = Column(String, default="", index=True)
    old_memory = Column(String, default="")
    new_memory = Column(String, default="")
    event = Column(String, default="", index=True)
    actor_id = Column(String, default="", index=True)
    role = Column(String, default="", index=True)
    is_deleted = Column(SmallInteger, default=0, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class StorageManager:

    def __init__(self, url: Union[str, _url.URL], **kwargs: Any):
        self.engine = create_engine(url, **kwargs)
        self.session = sessionmaker(bind=self.engine)
        self._create_history_table()

    def _create_history_table(self) -> None:
        Base.metadata.create_all(self.engine)

    def _get_db(self):
        db = self.session()
        try:
            yield db
        finally:
            db.close()

    def add_history(
        self,
        memory_id: str,
        old_memory: Optional[str],
        new_memory: Optional[str],
        event: str,
        *,
        user_id: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        is_deleted: int = 0,
        actor_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        if created_at:
            created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%S.%f%z')
        if updated_at:
            updated_at = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M:%S.%f%z')

        entry = History(
            id=str(uuid.uuid4()),
            user_id=user_id,
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
        db = next(self._get_db())
        db.add(entry)
        db.commit()
        db.refresh(entry)

    def get_history(self, memory_id: str) -> list[type[History]]:
        db = next(self._get_db())
        results = (
            db.query(History)
            .filter(
                History.memory_id == memory_id,
            )
            .order_by(
                History.created_at.asc(),
                History.updated_at.asc(),
            )
            .all()
        )
        return results

    def reset(self) -> None:
        """Drop and recreate the history table."""
        db = next(self._get_db())
        db.execute(text(f"DROP TABLE IF EXISTS {History.__tablename__}"))
        db.commit()

    def close(self) -> None:
        if self.session:
            self.session.close_all()
            self.session = None

    def __del__(self):
        self.close()
