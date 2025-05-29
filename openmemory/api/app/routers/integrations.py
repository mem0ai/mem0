from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict
from app.database import get_db
from app.auth import get_current_supa_user
from gotrue.types import User as SupabaseUser
from app.utils.db import get_or_create_user, get_user_and_app
from app.models import User, Document, App, Memory, MemoryState
from app.integrations.substack_service import SubstackService
import asyncio
from app.services.chunking_service import ChunkingService
from app.integrations.twitter_service import sync_twitter_to_memory
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

@router.post("/substack/sync")
async def sync_substack(
    request: Dict,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Sync Substack essays for the authenticated user"""
    substack_url = request.get("substack_url")
    max_posts = request.get("max_posts", 20)
    
    if not substack_url:
        raise HTTPException(status_code=400, detail="Substack URL is required")
    
    # Get the local user record
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found or could not be created")
    
    # Use the SubstackService to handle the sync
    service = SubstackService()
    synced_count, message = await service.sync_substack_posts(
        db=db,
        supabase_user_id=supabase_user_id_str,
        substack_url=substack_url,
        max_posts=max_posts,
        use_mem0=True  # Try to use mem0, but it will gracefully degrade if not available
    )
    
    if synced_count == 0 and "Error" in message:
        raise HTTPException(status_code=400, detail=message)
    
    return {"message": message, "synced_count": synced_count}


@router.get("/documents/count")
async def get_document_count(
    document_type: str,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Get count of documents by type for the authenticated user (only documents with active memories)"""
    user = get_or_create_user(db, current_supa_user.id, current_supa_user.email)
    
    # Count documents that have at least one active memory
    count = db.query(Document).filter(
        Document.user_id == user.id,
        Document.document_type == document_type
    ).filter(
        # Only include documents that have active memories
        Document.id.in_(
            db.query(Document.id).join(
                Memory,
                text("memories.metadata_->>'document_id' = CAST(documents.id AS TEXT)")
            ).filter(
                Memory.user_id == user.id,
                Memory.state == MemoryState.active
            )
        )
    ).count()
    
    return {"count": count}


@router.post("/documents/chunk")
async def chunk_documents(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """Chunk all documents for the authenticated user"""
    user = get_or_create_user(db, current_supa_user.id, current_supa_user.email)
    
    # Run chunking in background
    chunking_service = ChunkingService()
    processed = await asyncio.to_thread(
        chunking_service.chunk_all_documents,
        db,
        user.id
    )
    
    return {
        "status": "success",
        "documents_processed": processed,
        "message": f"Successfully chunked {processed} documents"
    }


@router.post("/sync/twitter")
async def sync_twitter(
    username: str = Query(..., description="Twitter username without @"),
    max_posts: int = Query(20, description="Maximum number of tweets to sync (max 40)"),
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """
    Sync recent tweets from a Twitter user to memory.
    """
    try:
        # Limit max_posts to prevent resource exhaustion
        max_posts = min(max_posts, 40)
        
        # Get user and Twitter app (create if doesn't exist)
        user, app = get_user_and_app(
            db,
            supabase_user_id=str(current_supa_user.id),
            app_name="twitter",
            email=current_supa_user.email
        )
        
        if not app.is_active:
            raise HTTPException(
                status_code=400,
                detail="Twitter app is paused. Cannot sync tweets."
            )
        
        # Sync tweets with timeout protection
        try:
            synced_count = await asyncio.wait_for(
                sync_twitter_to_memory(
                    username=username.lstrip('@'),
                    user_id=str(current_supa_user.id),  # Use Supabase ID for mem0
                    app_id=str(app.id),
                    db_session=db
                ),
                timeout=300.0  # 5 minute timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Twitter sync timed out for user {current_supa_user.id}")
            raise HTTPException(
                status_code=408,
                detail="Twitter sync timed out. Please try with fewer tweets."
            )
        
        return {
            "status": "success",
            "message": f"Successfully synced {synced_count} tweets from @{username}",
            "synced_count": synced_count,
            "username": username
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error syncing Twitter for user {current_supa_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync Twitter posts: {str(e)}"
        ) 