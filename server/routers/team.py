import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import hash_password, verify_auth
from db import get_db
from models import APIKey, Invite, User

router = APIRouter(prefix="/team", tags=["team"])

INVITE_EXPIRE_DAYS = 7


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class AcceptInviteRequest(BaseModel):
    token: str
    name: str
    password: str


class MemberResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteResponse(BaseModel):
    id: str
    email: str
    role: str
    token: str
    expires_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[MemberResponse])
def list_members(user: User = Depends(verify_auth), db: Session = Depends(get_db)):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    members = db.execute(select(User).order_by(User.created_at)).scalars().all()
    return [
        MemberResponse(id=str(m.id), name=m.name, email=m.email, role=m.role, created_at=m.created_at) for m in members
    ]


@router.post("/invite/", response_model=InviteResponse, status_code=201)
def invite_member(body: InviteRequest, user: User = Depends(verify_auth), db: Session = Depends(get_db)):
    """Admin only."""
    if user is None or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    if body.role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'member'.")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status_code=409, detail="User with this email already exists.")

    pending = db.scalar(
        select(Invite).where(
            Invite.email == body.email,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
    )
    if pending:
        raise HTTPException(status_code=409, detail="A pending invite already exists for this email.")

    invite = Invite(
        email=body.email,
        token=secrets.token_urlsafe(32),
        invited_by=user.id,
        role=body.role,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRE_DAYS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return InviteResponse(
        id=str(invite.id), email=invite.email, role=invite.role, token=invite.token, expires_at=invite.expires_at
    )


@router.post("/accept-invite/", response_model=MemberResponse, status_code=201)
def accept_invite(body: AcceptInviteRequest, db: Session = Depends(get_db)):
    invite = db.scalar(select(Invite).where(Invite.token == body.token))
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found.")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="Invite has already been used.")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite has expired.")
    if db.scalar(select(User).where(User.email == invite.email)):
        raise HTTPException(status_code=409, detail="User with this email already exists.")

    user = User(name=body.name, email=invite.email, password_hash=hash_password(body.password), role=invite.role)
    db.add(user)
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    return MemberResponse(id=str(user.id), name=user.name, email=user.email, role=user.role, created_at=user.created_at)


@router.delete("/{user_id}/")
def remove_member(user_id: str, user: User = Depends(verify_auth), db: Session = Depends(get_db)):
    """Admin only. Cannot remove yourself. Revokes the member's API keys."""
    if user is None or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    if str(user.id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself.")

    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    now = datetime.now(timezone.utc)
    for key in db.execute(select(APIKey).where(APIKey.created_by == target.id, APIKey.revoked_at.is_(None))).scalars():
        key.revoked_at = now

    db.delete(target)
    db.commit()
    return {"message": "Member removed."}
