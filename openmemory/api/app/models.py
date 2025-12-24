import datetime
import enum
import uuid

import sqlalchemy as sa
from sqlalchemy import (
    Column,
    String,
    Boolean,
    ForeignKey,
    Enum,
    Table,
    DateTime,
    JSON,
    Integer,
    UUID,
    Index,
    Text,
    event,
)
from sqlalchemy.orm import relationship
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
    event,
)
from sqlalchemy.orm import Session, relationship


def get_current_utc_time():
    """Get current UTC time"""
    return datetime.datetime.now(datetime.UTC)


def generate_uuid_without_hyphens():
    """Generate UUID without hyphens"""
    return uuid.uuid4().hex


class MemoryState(enum.Enum):
    active = "active"
    paused = "paused"
    archived = "archived"
    deleted = "deleted"


class User(Base):
    __tablename__ = "users"
    id = Column(
        String(32), primary_key=True, default=generate_uuid_without_hyphens
    )  # Modified: specify length, UUID without hyphens
    user_id = Column(
        String(255), nullable=False, unique=True, index=True
    )  # Modified: specify length
    name = Column(String(255), nullable=True, index=True)  # Modified: specify length
    email = Column(
        String(255), unique=True, nullable=True, index=True
    )  # Modified: specify length
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)
    updated_at = Column(
        DateTime, default=get_current_utc_time, onupdate=get_current_utc_time
    )

    apps = relationship("App", back_populates="owner")
    memories = relationship("Memory", back_populates="user")


class App(Base):
    __tablename__ = "apps"
    id = Column(
        String(32), primary_key=True, default=generate_uuid_without_hyphens
    )  # Modified
    owner_id = Column(
        String(32), ForeignKey("users.id"), nullable=False, index=True
    )  # Modified
    name = Column(String(255), nullable=False, index=True)  # Modified: specify length
    description = Column(Text)  # Changed to Text instead of String(1000)
    metadata_ = Column("metadata", JSON, default=dict)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)
    updated_at = Column(
        DateTime, default=get_current_utc_time, onupdate=get_current_utc_time
    )

    owner = relationship("User", back_populates="apps")
    memories = relationship("Memory", back_populates="app")

    __table_args__ = (
        sa.UniqueConstraint("owner_id", "name", name="idx_app_owner_name"),
    )


class Config(Base):
    __tablename__ = "configs"
    id = Column(
        String(32), primary_key=True, default=generate_uuid_without_hyphens
    )  # Modified
    key = Column(
        String(255), unique=True, nullable=False, index=True
    )  # Modified: specify length
    value = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=get_current_utc_time)
    updated_at = Column(
        DateTime, default=get_current_utc_time, onupdate=get_current_utc_time
    )


class Memory(Base):
    __tablename__ = "memories"
    id = Column(String(32), primary_key=True, default=generate_uuid_without_hyphens)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    app_id = Column(String(32), ForeignKey("apps.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)  # Modified: use Text type
    vector = Column(Text)  # Modified: use Text type
    metadata_ = Column("metadata", JSON, default=dict)
    state = Column(Enum(MemoryState), default=MemoryState.active, index=True)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)
    updated_at = Column(
        DateTime, default=get_current_utc_time, onupdate=get_current_utc_time
    )
    archived_at = Column(DateTime, nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    user = relationship("User", back_populates="memories")
    app = relationship("App", back_populates="memories")
    categories = relationship(
        "Category", secondary="memory_categories", back_populates="memories"
    )

    __table_args__ = (
        Index("idx_memory_user_state", "user_id", "state"),
        Index("idx_memory_app_state", "app_id", "state"),
        Index("idx_memory_user_app", "user_id", "app_id"),
    )


class Category(Base):
    __tablename__ = "categories"
    id = Column(
        String(32), primary_key=True, default=generate_uuid_without_hyphens
    )  # Modified
    name = Column(
        String(255), unique=True, nullable=False, index=True
    )  # Modified: specify length
    description = Column(Text)  # Changed to Text instead of String(1000)
    created_at = Column(
        DateTime, default=datetime.datetime.now(datetime.UTC), index=True
    )
    updated_at = Column(
        DateTime, default=get_current_utc_time, onupdate=get_current_utc_time
    )

    memories = relationship(
        "Memory", secondary="memory_categories", back_populates="categories"
    )


memory_categories = Table(
    "memory_categories",
    Base.metadata,
    Column(
        "memory_id", String(32), ForeignKey("memories.id"), primary_key=True, index=True
    ),  # Modified
    Column(
        "category_id",
        String(32),
        ForeignKey("categories.id"),
        primary_key=True,
        index=True,
    ),  # Modified
    Index("idx_memory_category", "memory_id", "category_id"),
)


class AccessControl(Base):
    __tablename__ = "access_controls"
    id = Column(
        String(32), primary_key=True, default=generate_uuid_without_hyphens
    )  # Modified
    subject_type = Column(
        String(100), nullable=False, index=True
    )  # Modified: specify length
    subject_id = Column(String(32), nullable=True, index=True)  # Modified
    object_type = Column(
        String(100), nullable=False, index=True
    )  # Modified: specify length
    object_id = Column(String(32), nullable=True, index=True)  # Modified
    effect = Column(String(50), nullable=False, index=True)  # Modified: specify length
    created_at = Column(DateTime, default=get_current_utc_time, index=True)

    __table_args__ = (
        Index("idx_access_subject", "subject_type", "subject_id"),
        Index("idx_access_object", "object_type", "object_id"),
    )


class ArchivePolicy(Base):
    __tablename__ = "archive_policies"
    id = Column(
        String(32), primary_key=True, default=generate_uuid_without_hyphens
    )  # Modified
    criteria_type = Column(
        String(100), nullable=False, index=True
    )  # Modified: specify length
    criteria_id = Column(String(32), nullable=True, index=True)  # Modified
    days_to_archive = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=get_current_utc_time, index=True)

    __table_args__ = (Index("idx_policy_criteria", "criteria_type", "criteria_id"),)


class MemoryStatusHistory(Base):
    __tablename__ = "memory_status_history"
    id = Column(
        String(32), primary_key=True, default=generate_uuid_without_hyphens
    )  # Modified
    memory_id = Column(
        String(32), ForeignKey("memories.id"), nullable=False, index=True
    )  # Modified
    changed_by = Column(
        String(32), ForeignKey("users.id"), nullable=False, index=True
    )  # Modified
    old_state = Column(Enum(MemoryState), nullable=False, index=True)
    new_state = Column(Enum(MemoryState), nullable=False, index=True)
    changed_at = Column(DateTime, default=get_current_utc_time, index=True)

    __table_args__ = (
        Index("idx_history_memory_state", "memory_id", "new_state"),
        Index("idx_history_user_time", "changed_by", "changed_at"),
    )


class MemoryAccessLog(Base):
    __tablename__ = "memory_access_logs"
    id = Column(
        String(32), primary_key=True, default=generate_uuid_without_hyphens
    )  # Modified
    memory_id = Column(
        String(32), ForeignKey("memories.id"), nullable=False, index=True
    )  # Modified
    app_id = Column(
        String(32), ForeignKey("apps.id"), nullable=False, index=True
    )  # Modified
    accessed_at = Column(DateTime, default=get_current_utc_time, index=True)
    access_type = Column(
        String(100), nullable=False, index=True
    )  # Modified: specify length
    metadata_ = Column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("idx_access_memory_time", "memory_id", "accessed_at"),
        Index("idx_access_app_time", "app_id", "accessed_at"),
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
                    description=f"Automatically created category for {category_name}",
                )
                db.add(category)
                db.flush()  # Flush to get the category ID

            # Check if the memory-category association already exists
            existing = db.execute(
                memory_categories.select().where(
                    (memory_categories.c.memory_id == memory.id)
                    & (memory_categories.c.category_id == category.id)
                )
            ).first()

            if not existing:
                # Create the association
                db.execute(
                    memory_categories.insert().values(
                        memory_id=memory.id, category_id=category.id
                    )
                )

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error categorizing memory: {e}")


@event.listens_for(Memory, "after_insert")
def after_memory_insert(mapper, connection, target):
    """Trigger categorization after a memory is inserted."""
    db = Session(bind=connection)
    categorize_memory(target, db)
    db.close()


@event.listens_for(Memory, "after_update")
def after_memory_update(mapper, connection, target):
    """Trigger categorization after a memory is updated."""
    db = Session(bind=connection)
    categorize_memory(target, db)
    db.close()


# UUID automatic conversion event listeners (minimal intrusion solution)
@event.listens_for(User, "before_insert")
def convert_user_uuid_before_insert(mapper, connection, target):
    """Automatically convert User UUID format"""
    if hasattr(target.id, "hex"):  # If it's a UUID object
        target.id = target.id.hex  # Convert to string without hyphens
    elif (
        isinstance(target.id, str) and "-" in target.id
    ):  # If it's a string with hyphens
        target.id = target.id.replace("-", "")  # Remove hyphens


@event.listens_for(App, "before_insert")
def convert_app_uuid_before_insert(mapper, connection, target):
    """Automatically convert App UUID format"""
    if hasattr(target.id, "hex"):
        target.id = target.id.hex
    elif isinstance(target.id, str) and "-" in target.id:
        target.id = target.id.replace("-", "")

    # Also handle foreign keys
    if hasattr(target.owner_id, "hex"):
        target.owner_id = target.owner_id.hex
    elif isinstance(target.owner_id, str) and "-" in target.owner_id:
        target.owner_id = target.owner_id.replace("-", "")


@event.listens_for(Memory, "before_insert")
def convert_memory_uuid_before_insert(mapper, connection, target):
    """Automatically convert Memory UUID format"""
    if hasattr(target.id, "hex"):
        target.id = target.id.hex
    elif isinstance(target.id, str) and "-" in target.id:
        target.id = target.id.replace("-", "")

    # Handle foreign keys
    if hasattr(target.user_id, "hex"):
        target.user_id = target.user_id.hex
    elif isinstance(target.user_id, str) and "-" in target.user_id:
        target.user_id = target.user_id.replace("-", "")

    if hasattr(target.app_id, "hex"):
        target.app_id = target.app_id.hex
    elif isinstance(target.app_id, str) and "-" in target.app_id:
        target.app_id = target.app_id.replace("-", "")


@event.listens_for(Category, "before_insert")
def convert_category_uuid_before_insert(mapper, connection, target):
    """Automatically convert Category UUID format"""
    if hasattr(target.id, "hex"):
        target.id = target.id.hex
    elif isinstance(target.id, str) and "-" in target.id:
        target.id = target.id.replace("-", "")


@event.listens_for(Config, "before_insert")
def convert_config_uuid_before_insert(mapper, connection, target):
    """Automatically convert Config UUID format"""
    if hasattr(target.id, "hex"):
        target.id = target.id.hex
    elif isinstance(target.id, str) and "-" in target.id:
        target.id = target.id.replace("-", "")


@event.listens_for(AccessControl, "before_insert")
def convert_access_control_uuid_before_insert(mapper, connection, target):
    """Automatically convert AccessControl UUID format"""
    if hasattr(target.id, "hex"):
        target.id = target.id.hex
    elif isinstance(target.id, str) and "-" in target.id:
        target.id = target.id.replace("-", "")

    # Handle possible UUID foreign keys
    if target.subject_id and hasattr(target.subject_id, "hex"):
        target.subject_id = target.subject_id.hex
    elif (
        target.subject_id
        and isinstance(target.subject_id, str)
        and "-" in target.subject_id
    ):
        target.subject_id = target.subject_id.replace("-", "")

    if target.object_id and hasattr(target.object_id, "hex"):
        target.object_id = target.object_id.hex
    elif (
        target.object_id
        and isinstance(target.object_id, str)
        and "-" in target.object_id
    ):
        target.object_id = target.object_id.replace("-", "")


@event.listens_for(ArchivePolicy, "before_insert")
def convert_archive_policy_uuid_before_insert(mapper, connection, target):
    """Automatically convert ArchivePolicy UUID format"""
    if hasattr(target.id, "hex"):
        target.id = target.id.hex
    elif isinstance(target.id, str) and "-" in target.id:
        target.id = target.id.replace("-", "")

    if target.criteria_id and hasattr(target.criteria_id, "hex"):
        target.criteria_id = target.criteria_id.hex
    elif (
        target.criteria_id
        and isinstance(target.criteria_id, str)
        and "-" in target.criteria_id
    ):
        target.criteria_id = target.criteria_id.replace("-", "")


@event.listens_for(MemoryStatusHistory, "before_insert")
def convert_memory_status_history_uuid_before_insert(mapper, connection, target):
    """Automatically convert MemoryStatusHistory UUID format"""
    if hasattr(target.id, "hex"):
        target.id = target.id.hex
    elif isinstance(target.id, str) and "-" in target.id:
        target.id = target.id.replace("-", "")

    # Handle foreign keys
    if hasattr(target.memory_id, "hex"):
        target.memory_id = target.memory_id.hex
    elif isinstance(target.memory_id, str) and "-" in target.memory_id:
        target.memory_id = target.memory_id.replace("-", "")

    if hasattr(target.changed_by, "hex"):
        target.changed_by = target.changed_by.hex
    elif isinstance(target.changed_by, str) and "-" in target.changed_by:
        target.changed_by = target.changed_by.replace("-", "")


@event.listens_for(MemoryAccessLog, "before_insert")
def convert_memory_access_log_uuid_before_insert(mapper, connection, target):
    """Automatically convert MemoryAccessLog UUID format"""
    if hasattr(target.id, "hex"):
        target.id = target.id.hex
    elif isinstance(target.id, str) and "-" in target.id:
        target.id = target.id.replace("-", "")

    # Handle foreign keys
    if hasattr(target.memory_id, "hex"):
        target.memory_id = target.memory_id.hex
    elif isinstance(target.memory_id, str) and "-" in target.memory_id:
        target.memory_id = target.memory_id.replace("-", "")

    if hasattr(target.app_id, "hex"):
        target.app_id = target.app_id.hex
    elif isinstance(target.app_id, str) and "-" in target.app_id:
        target.app_id = target.app_id.replace("-", "")
