import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import (
    consume_refresh_jti,
    create_access_token,
    create_refresh_token,
    decode_token,
    dummy_verify_password,
    hash_password,
    require_auth,
    verify_password,
)
from db import get_db
from models import User
from rate_limit import limiter
from schemas import MessageResponse
from telemetry import capture_admin_registered, capture_onboarding_completed

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8


def _require_password_length(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class OnboardingCompleteRequest(BaseModel):
    use_case: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SetupStatusResponse(BaseModel):
    needsSetup: bool


@router.get("/setup-status", response_model=SetupStatusResponse)
def setup_status(db: Session = Depends(get_db)):
    count = db.scalar(select(func.count(User.id)))
    return SetupStatusResponse(needsSetup=count == 0)


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    """Create the first admin account. Blocked once any user exists."""
    _require_password_length(body.password)

    if db.scalar(select(func.count(User.id))) > 0:
        raise HTTPException(status_code=403, detail="Registration is closed. An admin account already exists.")

    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role="admin",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=403, detail="Registration is closed. An admin account already exists.")
    db.refresh(user)

    capture_admin_registered(email=body.email)

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role),
        refresh_token=create_refresh_token(str(user.id), db),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        dummy_verify_password()
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role),
        refresh_token=create_refresh_token(str(user.id), db),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(request: Request, body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type.")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Refresh token is no longer valid.")

    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")

    consume_refresh_jti(jti, db)

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role),
        refresh_token=create_refresh_token(str(user.id), db),
    )


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(require_auth)):
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    if body.name is not None and body.name.strip():
        user.name = body.name.strip()

    if body.email is not None and body.email != user.email:
        collision = db.scalar(select(User).where(User.email == body.email, User.id != user.id))
        if collision is not None:
            raise HTTPException(status_code=409, detail="Email is already in use.")
        user.email = body.email

    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    _require_password_length(body.new_password)

    user.password_hash = hash_password(body.new_password)
    db.commit()
    return MessageResponse(message="Password updated.")


@router.post("/onboarding-complete", response_model=MessageResponse)
def onboarding_complete(body: OnboardingCompleteRequest, user: User = Depends(require_auth)):
    """Fire the one-shot telemetry event after the setup wizard reaches its success state."""
    capture_onboarding_completed(email=user.email, use_case=body.use_case)
    return MessageResponse(message="Onboarding completed.")
