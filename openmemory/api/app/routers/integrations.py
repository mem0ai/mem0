from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict
from app.database import get_db
from app.auth import get_current_user
from app.models import User, Document
from app.integrations.substack_service import SubstackService
import asyncio

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

@router.post("/substack/sync")
async def sync_substack(
    request: Dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sync Substack essays for the authenticated user"""
    substack_url = request.get("substack_url")
    max_posts = request.get("max_posts", 20)
    
    if not substack_url:
        raise HTTPException(status_code=400, detail="Substack URL is required")
    
    # Use the SubstackService to handle the sync
    service = SubstackService()
    synced_count, message = await service.sync_substack_posts(
        db=db,
        supabase_user_id=current_user.user_id,
        substack_url=substack_url,
        max_posts=max_posts,
        use_mem0=True  # Try to use mem0, but it will gracefully degrade if not available
    )
    
    if synced_count == 0 and "Error" in message:
        raise HTTPException(status_code=400, detail=message)
    
    return {"message": message, "synced_count": synced_count}


@router.get("/documents/count")
async def get_document_count(
    document_type: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get count of documents for the authenticated user"""
    query = db.query(Document).filter(Document.user_id == current_user.id)
    
    if document_type:
        query = query.filter(Document.document_type == document_type)
    
    count = query.count()
    return {"count": count} 