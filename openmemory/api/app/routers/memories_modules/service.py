"""
Memory service layer for business logic.
Contains service functions for memory operations, decoupled from API routes.
"""

import datetime
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

# Python 3.10 compatibility for datetime.UTC
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Memory, MemoryState, MemoryAccessLog, App,
    MemoryStatusHistory, User, Category
)
from app.schemas import MemoryResponse
from app.utils.permissions import check_memory_access_permissions
from .utils import get_memory_or_404, update_memory_state

logger = logging.getLogger(__name__)


class MemoryService:
    """Service layer for memory operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_memory(self, user_id: UUID, app_name: str, text: str, metadata: dict = None, infer: bool = True) -> MemoryResponse:
        """Create a new memory with validation and processing."""
        if metadata is None:
            metadata = {}
        
        # Get user and app
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        app = self.db.query(App).filter(App.name == app_name, App.user_id == user_id).first()
        if not app:
            raise HTTPException(status_code=404, detail=f"App '{app_name}' not found")
        
        if not app.is_active:
            raise HTTPException(status_code=400, detail="App is not active")
        
        # Create memory
        memory = Memory(
            content=text,
            user_id=user_id,
            app_id=app.id,
            metadata_=metadata,
            state=MemoryState.active
        )
        
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        
        # Log access
        access_log = MemoryAccessLog(
            memory_id=memory.id,
            accessed_by=user_id,
            access_type="create"
        )
        self.db.add(access_log)
        self.db.commit()
        
        logger.info(f"✅ Created memory {memory.id} for user {user_id}")
        
        return MemoryResponse(
            id=memory.id,
            content=memory.content,
            created_at=memory.created_at,
            state=memory.state.value,
            app_id=memory.app_id,
            app_name=app.name,
            categories=[cat.name for cat in memory.categories],
            metadata_=memory.metadata_
        )
    
    def get_memory(self, memory_id: UUID, user_id: UUID) -> MemoryResponse:
        """Get a single memory by ID."""
        memory = get_memory_or_404(self.db, memory_id, user_id)
        
        # Log access
        access_log = MemoryAccessLog(
            memory_id=memory.id,
            accessed_by=user_id,
            access_type="read"
        )
        self.db.add(access_log)
        self.db.commit()
        
        return MemoryResponse(
            id=memory.id,
            content=memory.content,
            created_at=memory.created_at,
            state=memory.state.value,
            app_id=memory.app_id,
            app_name=memory.app.name if memory.app else "Unknown App",
            categories=[cat.name for cat in memory.categories],
            metadata_=memory.metadata_
        )
    
    def update_memory(self, memory_id: UUID, user_id: UUID, content: str) -> MemoryResponse:
        """Update memory content."""
        memory = get_memory_or_404(self.db, memory_id, user_id)
        
        memory.content = content
        memory.updated_at = datetime.datetime.now(UTC)
        
        self.db.commit()
        self.db.refresh(memory)
        
        # Log access
        access_log = MemoryAccessLog(
            memory_id=memory.id,
            accessed_by=user_id,
            access_type="update"
        )
        self.db.add(access_log)
        self.db.commit()
        
        logger.info(f"✅ Updated memory {memory.id}")
        
        return MemoryResponse(
            id=memory.id,
            content=memory.content,
            created_at=memory.created_at,
            state=memory.state.value,
            app_id=memory.app_id,
            app_name=memory.app.name if memory.app else "Unknown App",
            categories=[cat.name for cat in memory.categories],
            metadata_=memory.metadata_
        )
    
    def delete_memories(self, memory_ids: List[UUID], user_id: UUID) -> Dict[str, Any]:
        """Delete multiple memories."""
        archived_count = 0
        not_found_count = 0
        
        for memory_id in memory_ids:
            try:
                update_memory_state(self.db, memory_id, MemoryState.deleted, user_id)
                
                # Log access
                access_log = MemoryAccessLog(
                    memory_id=memory_id,
                    accessed_by=user_id,
                    access_type="delete"
                )
                self.db.add(access_log)
                archived_count += 1
            except HTTPException:
                not_found_count += 1
        
        self.db.commit()
        logger.info(f"✅ Archived {archived_count} memories, {not_found_count} not found")
        
        return {
            "message": f"Successfully archived {archived_count} memories. Not found: {not_found_count}."
        }
    
    def get_categories(self, user_id: UUID) -> Dict[str, Any]:
        """Get all categories for a user."""
        memories = self.db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.state != MemoryState.deleted,
            Memory.state != MemoryState.archived
        ).all()
        
        categories_set = set()
        for memory in memories:
            for category in memory.categories:
                categories_set.add(category.name)
        
        return {
            "categories": list(categories_set),
            "total": len(categories_set)
        }