import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
import datetime
import logging

from app.database import get_db
from app.models import ApiKey, User
from app.auth import get_current_supa_user, hash_api_key
from gotrue.types import User as SupabaseUser
from pydantic import BaseModel
from app.utils.auth_utils import generate_api_key, get_key_hash

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/keys",
    tags=["api-keys"],
    dependencies=[Depends(get_current_supa_user)]
)

# Pydantic models for request and response
class ApiKeyCreate(BaseModel):
    name: str

class ApiKeyInfo(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime.datetime
    last_used_at: datetime.datetime | None = None
    is_active: bool

    class Config:
        from_attributes = True

class NewApiKeyResponse(BaseModel):
    key: str
    info: ApiKeyInfo

@router.post("", response_model=NewApiKeyResponse, status_code=201)
def create_api_key(
    key_create: ApiKeyCreate,
    db: Session = Depends(get_db),
    supa_user: SupabaseUser = Depends(get_current_supa_user)
):
    """
    Generate a new API key for the current user.
    The key is returned in plaintext only once.
    """
    logger.info(f"User {supa_user.user.id} requesting to create a new API key with name: '{key_create.name}'")
    db_user = db.query(User).filter(User.user_id == str(supa_user.user.id)).first()
    if not db_user:
        logger.error(f"User with Supabase ID {supa_user.user.id} not found in our database.")
        raise HTTPException(status_code=404, detail="User not found")

    # 1. Generate a new plaintext key and its metadata
    plaintext_key = generate_api_key()
    
    # 2. Hash the key and get its prefix for storage
    hashed_key = get_key_hash(plaintext_key)
    key_prefix = plaintext_key.split('_')[-1][:8]
    
    # 3. Create the database record
    db_api_key = ApiKey(
        name=key_create.name,
        key_hash=hashed_key,
        user_id=db_user.id
    )
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)

    logger.info(f"Successfully created API key ID {db_api_key.id} for user {db_user.id}.")

    # 5. Return the plaintext key and key info
    return NewApiKeyResponse(
        key=plaintext_key,
        info=ApiKeyInfo.from_orm(db_api_key)
    )

@router.get("", response_model=List[ApiKeyInfo])
def get_api_keys(
    db: Session = Depends(get_db),
    supa_user: SupabaseUser = Depends(get_current_supa_user)
):
    """
    List all active API keys for the current user.
    """
    logger.info(f"User {supa_user.user.id} requesting to list their API keys.")
    db_user = db.query(User).filter(User.user_id == str(supa_user.user.id)).first()
    if not db_user:
        logger.error(f"User with Supabase ID {supa_user.user.id} not found in our database during key listing.")
        raise HTTPException(status_code=404, detail="User not found")
        
    keys = db.query(ApiKey).filter(ApiKey.user_id == db_user.id, ApiKey.is_active == True).all()
    logger.info(f"Found {len(keys)} active API keys for user {db_user.id}.")
    return keys

@router.delete("/{key_id}", status_code=204)
def revoke_api_key(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    supa_user: SupabaseUser = Depends(get_current_supa_user)
):
    """
    Revoke (deactivate) an API key.
    """
    logger.info(f"User {supa_user.user.id} requesting to revoke API key ID: {key_id}")
    db_user = db.query(User).filter(User.user_id == str(supa_user.user.id)).first()
    if not db_user:
        logger.error(f"User with Supabase ID {supa_user.user.id} not found when trying to revoke key {key_id}.")
        raise HTTPException(status_code=404, detail="User not found")

    db_key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == db_user.id).first()

    if not db_key:
        logger.warning(f"User {db_user.id} failed to revoke key {key_id}: Key not found or permission denied.")
        raise HTTPException(status_code=404, detail="API Key not found or you do not have permission to revoke it.")

    if not db_key.is_active:
        logger.warning(f"User {db_user.id} attempted to revoke already-revoked key {key_id}.")
        raise HTTPException(status_code=400, detail="API Key is already revoked.")

    db_key.is_active = False
    db.commit()

    logger.info(f"Successfully revoked API key {key_id} for user {db_user.id}.")

    return None 