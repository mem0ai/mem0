import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
import datetime

from app.database import get_db
from app.models import ApiKey, User
from app.auth import get_current_supa_user, hash_api_key
from gotrue.types import User as SupabaseUser
from pydantic import BaseModel

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

@router.post("/", response_model=NewApiKeyResponse, status_code=201)
def create_api_key(
    key_create: ApiKeyCreate,
    db: Session = Depends(get_db),
    supa_user: SupabaseUser = Depends(get_current_supa_user)
):
    """
    Generate a new API key for the current user.
    The key is returned in plaintext only once.
    """
    # 1. Generate a secure, random key string
    plaintext_key = f"jean_sk_{secrets.token_urlsafe(32)}"
    
    # 2. Hash the key for storage
    hashed_key = hash_api_key(plaintext_key)
    
    # 3. Get the internal User object
    db_user = db.query(User).filter(User.user_id == str(supa_user.id)).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # 4. Store the hashed key in the database
    db_api_key = ApiKey(
        name=key_create.name,
        key_hash=hashed_key,
        user_id=db_user.id
    )
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)

    # 5. Return the plaintext key and key info
    return NewApiKeyResponse(
        key=plaintext_key,
        info=ApiKeyInfo.from_orm(db_api_key)
    )

@router.get("/", response_model=List[ApiKeyInfo])
def get_api_keys(
    db: Session = Depends(get_db),
    supa_user: SupabaseUser = Depends(get_current_supa_user)
):
    """
    List all active API keys for the current user.
    """
    db_user = db.query(User).filter(User.user_id == str(supa_user.id)).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    keys = db.query(ApiKey).filter(ApiKey.user_id == db_user.id, ApiKey.is_active == True).all()
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
    db_user = db.query(User).filter(User.user_id == str(supa_user.id)).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == db_user.id).first()

    if not db_key:
        raise HTTPException(status_code=404, detail="API Key not found or you do not have permission to revoke it.")

    if not db_key.is_active:
        raise HTTPException(status_code=400, detail="API Key is already revoked.")

    db_key.is_active = False
    db.commit()

    return None 