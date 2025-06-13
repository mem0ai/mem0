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
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
        logger.error("Supabase URL and Service Role Key must be set in environment variables for production.")
    else:
        try:
            supabase_service_client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
            logger.info("Supabase client initialized in auth module with service role.")
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

# This is the original, untouched dependency for the UI and production services.
async def get_current_supa_user(request: Request) -> SupabaseUser:
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
            # This case might happen if Supabase is down or the JWT is invalid in a way that doesn't raise an exception
            logger.warning("get_current_supa_user: No user object returned from Supabase despite valid token.")
            raise HTTPException(status_code=401, detail="Could not validate credentials, no user returned")
        return user
    except Exception as e:
        end_time = time.time()
        duration = (end_time - start_time) * 1000
        logger.error(f"Supabase authentication failed after {duration:.2f}ms. Error: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail=f"Could not validate credentials: {e}")

# This is the NEW, ISOLATED dependency for agent API keys.
# It is only used by the new /agent/* endpoints.
api_key_header_scheme = APIKeyHeader(name="Authorization", auto_error=False)

async def get_current_agent(
    api_key: str = Depends(api_key_header_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Authentication dependency that validates an API key for AGENT access.
    """
    if config.is_local_development:
        # In local dev, an agent can use the default local user
        logger.info("get_current_agent: Bypassing key auth for local development.")
        local_user = await get_local_dev_user(Request(scope={"type": "http", "headers": []}))
        db_user = db.query(User).filter(User.user_id == local_user.id).first()
        if not db_user:
            logger.error("get_current_agent: Local dev user not found in database.")
            raise HTTPException(status_code=404, detail="Local dev user not found in database.")
        return db_user

    if not api_key or not api_key.startswith("Bearer "):
        logger.warning("get_current_agent: Invalid or missing Authorization header format.")
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or missing Authorization header for API key.")
    
    key = api_key.replace("Bearer ", "")
    
    if not key.startswith("jean_sk_"):
        logger.warning(f"get_current_agent: Invalid API key format for key starting with '{key[:12]}...'")
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid API key format.")

    logger.debug(f"get_current_agent: Attempting to authenticate with key starting with '{key[:12]}...'")
    hashed_key = hash_api_key(key)
    
    db_api_key = db.query(ApiKey).filter(ApiKey.key_hash == hashed_key).first()
    
    if not db_api_key:
        logger.warning(f"get_current_agent: No API key found for hash of key starting with '{key[:12]}...'")
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or inactive API key.")

    if not db_api_key.is_active:
        logger.warning(f"get_current_agent: Authentication attempt with inactive key ID: {db_api_key.id}")
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or inactive API key.")
    
    db_api_key.last_used_at = datetime.datetime.now(datetime.UTC)
    db.commit()
    
    logger.info(f"get_current_agent: Successfully authenticated user {db_api_key.user.id} via API key ID {db_api_key.id}")
    return db_api_key.user