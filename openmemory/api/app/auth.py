# openmemory/api/app/auth.py
import os
import logging
from fastapi import Depends, HTTPException, Request
from supabase import create_client, Client as SupabaseClient
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_500_INTERNAL_SERVER_ERROR
from gotrue.types import User as SupabaseUser
import time
import hashlib
import datetime
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from .settings import config
from .database import get_db
from .models import User, ApiKey
from .local_auth_helper import get_local_dev_user

logger = logging.getLogger(__name__)

# Supabase Client Initialization
supabase_service_client: SupabaseClient = None

def init_supabase_client():
    """Initialize the Supabase client for authentication"""
    global supabase_service_client
    
    if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
        raise RuntimeError(
            f"Supabase configuration missing. "
            f"Environment: {config.environment_name}. "
            f"URL: {'✓' if config.SUPABASE_URL else '✗'}, "
            f"Key: {'✓' if config.SUPABASE_ANON_KEY else '✗'}"
        )
    
    try:
        supabase_service_client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        logger.info(f"Supabase client initialized for {config.environment_name}")
        logger.info(f"Auth URL: {config.SUPABASE_URL}")
        return supabase_service_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}", exc_info=True)
        raise RuntimeError(f"Failed to initialize Supabase client: {e}")

# Initialize the client on module load
try:
    init_supabase_client()
except Exception as e:
    logger.error(f"Failed to initialize Supabase during module load: {e}")
    # Don't raise here to allow the app to start, but auth will fail

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
    Authentication dependency that validates JWT tokens against Supabase.
    
    Works with both local Supabase CLI and production Supabase Cloud.
    No more authentication bypass - always uses real Supabase auth.
    """
    # Bypass auth for local development
    if config.is_local_development:
        local_user = await get_local_dev_user(request, supabase_service_client, config)
        db_user = db.query(User).filter(User.user_id == local_user.id).first()
        if not db_user:
            # Create user if it doesn't exist for local dev
            db_user = User(user_id=local_user.id, email=local_user.email or "dev@example.com")
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
        return await get_local_dev_user(request, supabase_service_client, config)
    
    if not supabase_service_client:
        logger.error("Supabase client not initialized. Cannot authenticate user.")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Authentication service unavailable"
        )

    # Extract Bearer token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.debug("No Authorization header provided")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, 
            detail="Authorization header missing"
        )
    
    if not auth_header.startswith("Bearer "):
        logger.debug("Invalid Authorization header format")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token = auth_header.replace("Bearer ", "")
    
    try:
        start_time = time.time()
        logger.debug(f"Authenticating token with Supabase ({config.environment_name})...")
        
        # Verify the JWT token with Supabase
        user = supabase_service_client.auth.get_user(token)
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        
        if not user or not user.user:
            logger.warning(f"Token validation failed - no user returned")
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED, 
                detail="Invalid or expired token"
            )
        
        logger.info(
            f"Authentication successful for user {user.user.id} "
            f"({user.user.email}) in {duration:.2f}ms"
        )
        
        return user.user
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        end_time = time.time()
        duration = (end_time - start_time) * 1000
        
        logger.error(
            f"Authentication failed after {duration:.2f}ms. "
            f"Error: {e}", exc_info=True
        )
        
        # Provide different error messages based on the error type
        if "Invalid JWT" in str(e) or "jwt" in str(e).lower():
            detail = "Invalid or expired token"
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            detail = "Authentication service temporarily unavailable"
        else:
            detail = "Authentication failed"
            
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=detail
        )

async def get_service_client() -> SupabaseClient:
    """
    Get the Supabase service client for backend operations.
    Use the service role key for administrative operations.
    """
    if not config.SUPABASE_SERVICE_KEY:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service client not configured"
        )
    
    try:
        service_client = create_client(
            config.SUPABASE_URL, 
            config.SUPABASE_SERVICE_KEY
        )
        return service_client
    except Exception as e:
        logger.error(f"Failed to create service client: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize service client"
        )

def create_client_for_user(user_token: str) -> SupabaseClient:
    """
    Create a Supabase client with a user's token for user-scoped operations.
    """
    try:
        client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        client.auth.set_session(user_token, refresh_token=None)
        return client
    except Exception as e:
        logger.error(f"Failed to create user client: {e}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Failed to create authenticated client"
        ) 