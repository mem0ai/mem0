# openmemory/api/app/auth.py
import os
import logging
from fastapi import Depends, HTTPException, Request
from supabase import create_client, Client as SupabaseClient
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from typing import Union
import time
import hashlib
import datetime
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from .database import get_db, SessionLocal
from .models import User, ApiKey
# Import local auth module for development mode
from .local_auth import get_local_dev_user, MockSupabaseUser
from .settings import config

# Type alias for both real and mock user types
SupabaseUser = Union[MockSupabaseUser, 'supabase.lib.auth.user.User']

logger = logging.getLogger(__name__)

# Supabase Client Initialization
supabase_service_client: SupabaseClient = None

# Only initialize Supabase client if not in local development mode
if config.requires_supabase_auth:
    if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
        logger.error("Supabase URL and Anon Key must be set in environment variables for production.")
    else:
        try:
            supabase_service_client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            logger.info("Supabase client initialized in auth module.")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client in auth module: {e}", exc_info=True)
else:
    logger.info("Running in local development mode - Supabase auth disabled")

def hash_api_key(api_key: str) -> str:
    """Hashes the API key using SHA-256."""
    return hashlib.sha256(api_key.encode()).hexdigest()

async def _get_user_from_api_key(api_key: str, db: Session) -> User:
    """Validates an API key and returns the associated user."""
    if not api_key.startswith("jean_sk_"):
        return None

    hashed_key = hash_api_key(api_key)
    db_api_key = db.query(ApiKey).filter(ApiKey.key_hash == hashed_key).first()

    if not db_api_key or not db_api_key.is_active:
        return None

    db_api_key.last_used_at = datetime.datetime.now(datetime.UTC)
    db.commit()
    return db_api_key.user

async def _get_user_from_supabase_jwt(token: str, db: Session) -> User:
    """Validates a Supabase JWT and returns the internal user."""
    if not supabase_service_client:
        raise HTTPException(status_code=500, detail="Supabase client not initialized.")
    try:
        supa_user = supabase_service_client.auth.get_user(token)
        if not supa_user:
            return None
        
        # Get the internal User object
        db_user = db.query(User).filter(User.user_id == str(supa_user.user.id)).first()
        return db_user
    except Exception:
        return None

api_key_header_scheme = APIKeyHeader(name="Authorization", auto_error=True)

async def get_current_user(
    request: Request,
    auth_header: str = Depends(api_key_header_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Primary authentication dependency.
    Validates the 'Authorization' header for either a Supabase JWT or a Jean API Key.
    """
    # Bypass auth for local development
    if config.is_local_development:
        local_user = await get_local_dev_user(request)
        db_user = db.query(User).filter(User.user_id == local_user.id).first()
        if not db_user:
            # Create user if it doesn't exist for local dev
            db_user = User(user_id=local_user.id, email="dev@example.com")
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
        return db_user

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header format")
    
    token = auth_header.replace("Bearer ", "")

    user = None
    # Try API Key auth first
    if token.startswith("jean_sk_"):
        user = await _get_user_from_api_key(token, db)
    # Fallback to Supabase JWT auth
    else:
        user = await _get_user_from_supabase_jwt(token, db)

    if user:
        return user

    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

# The original dependency, kept for compatibility where only Supabase auth is needed.
# For new endpoints, prefer `get_current_user`.
async def get_current_supa_user(request: Request) -> SupabaseUser:
    """
    Authentication dependency that handles both production and local development.
    In production: Validates the JWT token against Supabase.
    In dev mode: Returns a mock user with USER_ID from environment variables.
    """
    if config.is_local_development:
        logger.debug(f"Using local authentication with USER_ID: {config.USER_ID}")
        return await get_local_dev_user(request)

    if not supabase_service_client:
        logger.error("Supabase client not initialized in auth module. Cannot authenticate user.")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Supabase client not initialized."
        )

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Authorization header missing")

    token = auth_header.replace("Bearer ", "")

    try:
        start_time = time.time()
        logger.info("Attempting to authenticate user with Supabase...")
        user = supabase_service_client.auth.get_user(token)
        end_time = time.time()
        duration = (end_time - start_time) * 1000
        logger.info(f"Supabase authentication successful for user: {user.user.id}. Call took {duration:.2f}ms.")

        if not user:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user
    except Exception as e:
        end_time = time.time()
        duration = (end_time - start_time) * 1000
        logger.error(f"Supabase authentication failed after {duration:.2f}ms. Error: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail=f"Could not validate credentials: {e}")