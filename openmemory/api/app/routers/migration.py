import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from gotrue.types import User as SupabaseUser

from app.database import get_db
from app.auth import get_current_supa_user
from app.models import Memory
from app.settings import config as settings
from app.schemas import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/migration", tags=["migration"])


class MigrationStatusResponse(BaseModel):
    is_migrated: bool
    qdrant_memory_count: Optional[int] = None
    sql_memory_count: int
    error: Optional[str] = None


@router.get("/status", response_model=MigrationStatusResponse)
async def get_migration_status(
    current_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db),
):
    """Check if a user's data has been migrated to Qdrant"""
    try:
        user_id = current_user.id
        collection_name = f"mem0_{user_id}"
        
        # Get SQL memory count
        sql_memory_count = db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.state == "active"
        ).count()
        
        # Check Qdrant collection
        try:
            qdrant_client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.QDRANT_API_KEY,
            )
            
            # Check if collection exists
            collections = qdrant_client.get_collections()
            collection_exists = any(
                collection.name == collection_name 
                for collection in collections.collections
            )
            
            if not collection_exists:
                return MigrationStatusResponse(
                    is_migrated=False,
                    sql_memory_count=sql_memory_count
                )
            
            # Get collection info
            collection_info = qdrant_client.get_collection(collection_name)
            qdrant_memory_count = collection_info.points_count
            
            # Consider migrated if collection has vectors
            is_migrated = qdrant_memory_count > 0
            
            return MigrationStatusResponse(
                is_migrated=is_migrated,
                qdrant_memory_count=qdrant_memory_count,
                sql_memory_count=sql_memory_count
            )
            
        except Exception as e:
            logger.error(f"Error checking Qdrant status for user {user_id}: {str(e)}")
            return MigrationStatusResponse(
                is_migrated=False,
                sql_memory_count=sql_memory_count,
                error="Failed to check migration status"
            )
            
    except Exception as e:
        logger.error(f"Error in migration status check: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")