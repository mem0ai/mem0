import enum
import uuid
import datetime
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Enum, Table,
    DateTime, JSON, Integer, UUID, Index, event, UniqueConstraint, Text, ARRAY, Float, func, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base
from sqlalchemy.orm import Session
from app.utils.categorization import get_categories_for_memory

# Python 3.10 compatibility
try:
    UTC = datetime.UTC
except AttributeError:
    UTC = datetime.timezone.utc


def get_current_utc_time():
    """Get current UTC time"""
    return datetime.datetime.now(UTC)


class MemoryState(enum.Enum):
    active = "active"
    paused = "paused"
    archived = "archived"
    deleted = "deleted"


class User(Base):
    __tablename__ = "users"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    user_id = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    metadata_ = Column('metadata', JSON, default=dict)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)
    updated_at = Column(DateTime,
                        default=get_current_utc_time,
                        onupdate=get_current_utc_time)

    apps = relationship("App", back_populates="owner")
    memories = relationship("Memory", back_populates="user")
    documents = relationship("Document", back_populates="user")


class App(Base):
    __tablename__ = "apps"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    owner_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(String)
    metadata_ = Column('metadata', JSON, default=dict)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)
    updated_at = Column(DateTime,
                        default=get_current_utc_time,
                        onupdate=get_current_utc_time)

    owner = relationship("User", back_populates="apps")
    memories = relationship("Memory", back_populates="app")
    documents = relationship("Document", back_populates="app")

    __table_args__ = (UniqueConstraint('owner_id', 'name', name='uq_user_app_name'),)


class Memory(Base):
    __tablename__ = "memories"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    app_id = Column(UUID, ForeignKey("apps.id"), nullable=False, index=True)
    content = Column(String, nullable=False)
    vector = Column(String)
    metadata_ = Column('metadata', JSON, default=dict)
    state = Column(Enum(MemoryState), default=MemoryState.active, index=True)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)
    updated_at = Column(DateTime,
                        default=get_current_utc_time,
                        onupdate=get_current_utc_time)
    archived_at = Column(DateTime, nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    user = relationship("User", back_populates="memories")
    app = relationship("App", back_populates="memories")
    categories = relationship("Category", secondary="memory_categories", back_populates="memories")
    documents = relationship("Document", secondary="document_memories", back_populates="memories")

    __table_args__ = (
        Index('idx_memory_user_state', 'user_id', 'state'),
        Index('idx_memory_app_state', 'app_id', 'state'),
        Index('idx_memory_user_app', 'user_id', 'app_id'),
    )


class Category(Base):
    __tablename__ = "categories"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now(UTC), index=True)
    updated_at = Column(DateTime,
                        default=get_current_utc_time,
                        onupdate=get_current_utc_time)

    memories = relationship("Memory", secondary="memory_categories", back_populates="categories")

memory_categories = Table(
    "memory_categories", Base.metadata,
    Column("memory_id", UUID, ForeignKey("memories.id"), primary_key=True, index=True),
    Column("category_id", UUID, ForeignKey("categories.id"), primary_key=True, index=True),
    Index('idx_memory_category', 'memory_id', 'category_id')
)


class AccessControl(Base):
    __tablename__ = "access_controls"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    subject_type = Column(String, nullable=False, index=True)
    subject_id = Column(UUID, nullable=True, index=True)
    object_type = Column(String, nullable=False, index=True)
    object_id = Column(UUID, nullable=True, index=True)
    effect = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)

    __table_args__ = (
        Index('idx_access_subject', 'subject_type', 'subject_id'),
        Index('idx_access_object', 'object_type', 'object_id'),
    )


class ArchivePolicy(Base):
    __tablename__ = "archive_policies"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    criteria_type = Column(String, nullable=False, index=True)
    criteria_id = Column(UUID, nullable=True, index=True)
    days_to_archive = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)

    __table_args__ = (
        Index('idx_policy_criteria', 'criteria_type', 'criteria_id'),
    )


class MemoryStatusHistory(Base):
    __tablename__ = "memory_status_history"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    memory_id = Column(UUID, ForeignKey("memories.id"), nullable=False, index=True)
    changed_by = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    old_state = Column(Enum(MemoryState), nullable=False, index=True)
    new_state = Column(Enum(MemoryState), nullable=False, index=True)
    changed_at = Column(DateTime, default=get_current_utc_time, index=True)

    __table_args__ = (
        Index('idx_history_memory_state', 'memory_id', 'new_state'),
        Index('idx_history_user_time', 'changed_by', 'changed_at'),
    )


class MemoryAccessLog(Base):
    __tablename__ = "memory_access_logs"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    memory_id = Column(UUID, ForeignKey("memories.id"), nullable=False, index=True)
    app_id = Column(UUID, ForeignKey("apps.id"), nullable=False, index=True)
    accessed_at = Column(DateTime, default=get_current_utc_time, index=True)
    access_type = Column(String, nullable=False, index=True)
    metadata_ = Column('metadata', JSON, default=dict)

    __table_args__ = (
        Index('idx_access_memory_time', 'memory_id', 'accessed_at'),
        Index('idx_access_app_time', 'app_id', 'accessed_at'),
    )


# Association table for documents and memories
document_memories = Table(
    "document_memories", Base.metadata,
    Column("document_id", UUID, ForeignKey("documents.id"), primary_key=True, index=True),
    Column("memory_id", UUID, ForeignKey("memories.id"), primary_key=True, index=True),
    Index('idx_document_memory', 'document_id', 'memory_id')
)


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=lambda: uuid.uuid4())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id"), nullable=False)
    title = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    document_type = Column(String, nullable=False)  # 'substack', 'obsidian', 'medium', etc.
    content = Column(Text, nullable=False)
    metadata_ = Column('metadata', JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_current_utc_time, onupdate=get_current_utc_time)
    
    # Relationships
    user = relationship("User", back_populates="documents")
    app = relationship("App", back_populates="documents")
    memories = relationship("Memory", secondary=document_memories, back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=lambda: uuid.uuid4())
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(ARRAY(Float), nullable=True)  # For future vector search
    metadata_ = Column('metadata_', JSONB, nullable=True)  # Use actual column name
    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    
    # Indexes are defined in the migration


def categorize_memory(memory: Memory, db: Session) -> None:
    """Categorize a memory using OpenAI and store the categories in the database."""
    try:
        # Get categories from OpenAI
        categories = get_categories_for_memory(memory.content)

        # Get or create categories in the database
        for category_name in categories:
            category = db.query(Category).filter(Category.name == category_name).first()
            if not category:
                category = Category(
                    name=category_name,
                    description=f"Automatically created category for {category_name}"
                )
                db.add(category)
                db.flush()  # Flush to get the category ID

            # Check if the memory-category association already exists
            existing = db.execute(
                memory_categories.select().where(
                    (memory_categories.c.memory_id == memory.id) &
                    (memory_categories.c.category_id == category.id)
                )
            ).first()

            if not existing:
                # Create the association
                db.execute(
                    memory_categories.insert().values(
                        memory_id=memory.id,
                        category_id=category.id
                    )
                )

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error categorizing memory: {e}")


@event.listens_for(Memory, 'after_insert')
def after_memory_insert(mapper, connection, target):
    """Trigger categorization after a memory is inserted."""
    db = Session(bind=connection)
    categorize_memory(target, db)
    db.close()


@event.listens_for(Memory, 'after_update')
def after_memory_update(mapper, connection, target):
    """Trigger categorization after a memory is updated."""
    db = Session(bind=connection)
    categorize_memory(target, db)
    db.close()
