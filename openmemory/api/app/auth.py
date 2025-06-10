# openmemory/api/app/auth.py
import os
import logging
from fastapi import Depends, HTTPException, Request
from supabase import create_client, Client as SupabaseClient
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from typing import Union

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

async def get_current_supa_user(request: Request) -> SupabaseUser:
    """
    Authentication dependency that handles both production and local development.
    
    In production: Validates the JWT token against Supabase
    In dev mode: Returns a mock user with USER_ID from environment variables
    """
    # Check if local development mode is active
    if config.is_local_development:
        logger.debug(f"Using local authentication with USER_ID: {config.USER_ID}")
        return await get_local_dev_user(request)
    
    # Regular Supabase authentication flow for production
    if not supabase_service_client:
        logger.error("Supabase client not initialized in auth module. Cannot authenticate user.")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Authentication service not available"
        )

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        # logger.debug("Missing Authorization header") # Can be noisy
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated (no token provided)"
        )
    
    parts = auth_header.split()
    if parts[0].lower() != "bearer" or len(parts) != 2:
        # logger.debug(f"Invalid token format: {auth_header}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token format"
        )
    
    token = parts[1]
    
    try:
        user_response = supabase_service_client.auth.get_user(jwt=token)
        user = user_response.user
        if not user or not user.id:
            # logger.warning(f"Invalid or expired token. Supabase user: {user}")
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        # logger.debug(f"Authenticated Supabase user: {user.id}, email: {user.email}")
        return user # This is a supabase.lib.auth.user.User object
    except Exception as e:
        # logger.error(f"Error during Supabase token validation: {e}", exc_info=True) # Can be too verbose for prod
        logger.warning(f"Supabase token validation failed: {type(e).__name__}") # Log type of error
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials", # Generic message to client
        ) 