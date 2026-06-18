import datetime
import enum
import uuid

import sqlalchemy as sa
from app.database import Base
from app.utils.categorization import get_categories_for_memory
from sqlalchemy import (
    JSON,
    UUID,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    event,
)
from sqlalchemy.orm import Session, relationship


def get_current_utc_time():
    """Get current UTC time"""
    return datetime.datetime.now(datetime.UTC)


class MemoryState(enum.Enum):
    active = "active"
    paused = "paused"
    archived = "archived"
    deleted = "deleted"


class WriteQueueStatus(enum.Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    failed = "failed"


class MigrationStatus(enum.Enum):
    """Lifecycle of the blue-green partition migration (task_01 / ADR-003)."""
    planned = "planned"
    copying = "copying"
    validating = "validating"
    flipped = "flipped"
    rolled_back = "rolled_back"
    done = "done"


class PartitionTier(enum.Enum):
    """Partition tier of a project in the shared Qdrant collection (ADR-002).

    ``shared`` projects live in the shared shard; ``dedicated`` projects have
    been promoted to their own custom shard key (task_08).
    """
    shared = "shared"
    dedicated = "dedicated"


class WriteQueueJob(Base):
    """Persistent write-queue row that decouples the MCP agent from LLM extraction.

    Each row represents a write job enqueued by ``add_memories`` and consumed by
    the background worker. Being SQLite-backed, jobs survive process restarts.

    NOTE: this is the ORM row model (table ``write_queue``). The queue *access
    layer* class is named ``WriteQueue`` and lives in ``app.utils.write_queue``.
    """
    __tablename__ = "write_queue"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    project = Column(String, nullable=False, index=True)
    hostname = Column(String, nullable=False, index=True)
    client_name = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    status = Column(Enum(WriteQueueStatus),
                    default=WriteQueueStatus.queued,
                    nullable=False,
                    index=True)
    error = Column(String, nullable=True)
    # Number of processing attempts already made; the worker retries a failed job
    # (re-queues it) until this reaches its configured ceiling, then marks it
    # terminally ``failed`` (task_06 / ADR-004).
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)
    updated_at = Column(DateTime,
                        default=get_current_utc_time,
                        onupdate=get_current_utc_time)

    __table_args__ = (
        Index('idx_write_queue_status_created', 'status', 'created_at'),
    )


class Project(Base):
    """Internal project catalog auto-managed by the memory.

    Spaces represent the company's projects (see ADR-002) and are auto-created
    and auto-cataloged on the first write of each project -- there is no manual
    administration. Each row is keyed by the project ``name`` and is materialized
    via the idempotent ``upsert_project`` helper (``app.utils.projects``), which
    the background worker (task_06) calls on the first write it processes for a
    given project.
    """
    __tablename__ = "projects"
    name = Column(String, primary_key=True)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)
    first_seen_hostname = Column(String, nullable=True)
    memory_count = Column(Integer, nullable=True, default=0)
    # Partitioning state (task_01 / ADR-002): every project starts ``shared`` and
    # may be promoted to a dedicated custom shard key (task_08).
    partition_tier = Column(
        Enum(PartitionTier),
        nullable=False,
        default=PartitionTier.shared,
        server_default=PartitionTier.shared.value,
    )
    shard_key = Column(String, nullable=True)


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

    __table_args__ = (
        sa.UniqueConstraint('owner_id', 'name', name='idx_app_owner_name'),
    )


class Config(Base):
    __tablename__ = "configs"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=get_current_utc_time)
    updated_at = Column(DateTime,
                        default=get_current_utc_time,
                        onupdate=get_current_utc_time)


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
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC), index=True)
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


class WriteAuditLog(Base):
    """Durable audit trail of write requests (task_04 / ADR-003).

    The shared-memory write path is asynchronous: ``add_memories`` enqueues a job
    and the memory is only materialized later by the background worker, so there
    is no ``memory_id`` to reference at request time (which is why the legacy
    ``MemoryAccessLog`` — FK-bound to ``memories`` — does not fit this flow).
    This table records *who* originated each write (hostname attribution) and the
    target project/client, keyed by the queue ``job_id``, so attribution is
    queryable and survives restarts without depending on log scraping.
    """
    __tablename__ = "write_audit_logs"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    job_id = Column(UUID, nullable=True, index=True)
    project = Column(String, nullable=False, index=True)
    hostname = Column(String, nullable=False, index=True)
    client_name = Column(String, nullable=True)
    action = Column(String, nullable=False, default="enqueue", index=True)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)

    __table_args__ = (
        Index('idx_write_audit_project_time', 'project', 'created_at'),
        Index('idx_write_audit_hostname_time', 'hostname', 'created_at'),
    )


class MigrationState(Base):
    """Global state of the blue-green partition migration (task_01 / ADR-003).

    A single logical row tracks the source (blue) and target (green) collections,
    which collection is currently served (``active_collection`` — the flip
    pointer), whether the write path is mirroring to the target
    (``dual_write_enabled``), and the copy checkpoint (``scroll_cursor``) used by
    the dedicated migration worker (task_06) to resume idempotently.
    """
    __tablename__ = "migration_state"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_collection = Column(String, nullable=False)
    target_collection = Column(String, nullable=False)
    active_collection = Column(String, nullable=False)
    dual_write_enabled = Column(
        Boolean, nullable=False, default=False, server_default=sa.false()
    )
    scroll_cursor = Column(String, nullable=True)
    status = Column(
        Enum(MigrationStatus),
        nullable=False,
        default=MigrationStatus.planned,
        server_default=MigrationStatus.planned.value,
    )
    updated_at = Column(
        DateTime, default=get_current_utc_time, onupdate=get_current_utc_time
    )


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
