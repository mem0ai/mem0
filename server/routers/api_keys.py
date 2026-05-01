from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import generate_api_key, require_auth
from db import get_db
from models import APIKey, User
from schemas import MessageResponse

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateKeyRequest(BaseModel):
    label: str


class CreateKeyResponse(BaseModel):
    id: str
    key: str
    label: str
    key_prefix: str
    created_at: datetime


class KeyListItem(BaseModel):
    id: str
    label: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[KeyListItem])
def list_keys(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    keys = (
        db.execute(
            select(APIKey)
            .where(APIKey.created_by == user.id, APIKey.revoked_at.is_(None))
            .order_by(APIKey.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        KeyListItem(
            id=str(k.id),
            label=k.label,
            key_prefix=k.key_prefix,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in keys
    ]


@router.post("", response_model=CreateKeyResponse, status_code=201)
def create_key(body: CreateKeyRequest, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    full_key, prefix, key_hash = generate_api_key()
    api_key = APIKey(key_prefix=prefix, key_hash=key_hash, label=body.label, created_by=user.id)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return CreateKeyResponse(
        id=str(api_key.id),
        key=full_key,
        label=api_key.label,
        key_prefix=prefix,
        created_at=api_key.created_at,
    )


@router.delete("/{key_id}", response_model=MessageResponse)
def revoke_key(key_id: str, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    api_key = db.get(APIKey, key_id)
    if api_key is None or api_key.created_by != user.id:
        raise HTTPException(status_code=404, detail="API key not found.")
    if api_key.revoked_at is not None:
        raise HTTPException(status_code=400, detail="API key is already revoked.")

    api_key.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="API key revoked.")
