import uuid

from sqlalchemy import TIMESTAMP, Column, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()
metadata = Base.metadata


class DataSource(Base):
    __tablename__ = "ec_data_sources"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(Text, index=True)
    hash = Column(Text, index=True)
    type = Column(Text, index=True)
    value = Column(Text)
    meta_data = Column(Text, name="metadata")
    is_uploaded = Column(Integer, default=0)


class ChatHistory(Base):
    __tablename__ = "ec_chat_history"

    app_id = Column(String, primary_key=True)
    id = Column(String, primary_key=True)
    session_id = Column(String, primary_key=True, index=True)
    question = Column(Text)
    answer = Column(Text)
    meta_data = Column(Text, name="metadata")
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), index=True)
