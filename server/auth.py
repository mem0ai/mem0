import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import APIKey, User

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, hash)."""
    raw = secrets.token_urlsafe(32)
    full_key = f"m0sk_{raw}"
    prefix = full_key[:12]
    key_hash = pwd_context.hash(full_key)
    return full_key, prefix, key_hash


def verify_api_key_hash(plain_key: str, hashed: str) -> bool:
    return pwd_context.verify(plain_key, hashed)


def _get_secret() -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET is not configured.")
    return JWT_SECRET


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")


bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _resolve_user_from_jwt(token: str, db: Session) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type.")
    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")
    return user


def _resolve_user_from_api_key(key: str, db: Session) -> User:
    prefix = key[:12] if len(key) >= 12 else key
    candidates = (
        db.execute(select(APIKey).where(APIKey.key_prefix == prefix, APIKey.revoked_at.is_(None))).scalars().all()
    )

    for candidate in candidates:
        if verify_api_key_hash(key, candidate.key_hash):
            candidate.last_used_at = datetime.now(timezone.utc)
            db.commit()
            user = db.get(User, candidate.created_by)
            if user is None:
                raise HTTPException(status_code=401, detail="API key owner not found.")
            return user

    raise HTTPException(status_code=401, detail="Invalid API key.")


async def verify_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> User | None:
    """Authenticate via JWT, X-API-Key, or legacy ADMIN_API_KEY. Returns User or None."""
    if credentials is not None:
        return _resolve_user_from_jwt(credentials.credentials, db)

    if x_api_key is not None:
        if ADMIN_API_KEY and secrets.compare_digest(x_api_key, ADMIN_API_KEY):
            return None
        return _resolve_user_from_api_key(x_api_key, db)

    if ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a Bearer token or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return None


async def require_auth(user: User | None = Depends(verify_auth)) -> User:
    """Like verify_auth but guarantees a non-None User. Use for endpoints that require auth."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user
