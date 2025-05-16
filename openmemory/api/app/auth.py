# openmemory/api/app/auth.py
import os
import logging
from fastapi import Depends, HTTPException, Request
from supabase import create_client, Client as SupabaseClient
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

logger = logging.getLogger(__name__) # Assuming logger is configured in main or here

# Supabase Client Initialization
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

supabase_service_client: SupabaseClient = None
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.error("Supabase URL and Service Key must be set in environment variables for auth module.")
    # Depending on desired behavior, could raise error or allow None client for offline/testing
else:
    try:
        supabase_service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Supabase client initialized in auth module.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client in auth module: {e}", exc_info=True)

async def get_current_supa_user(request: Request):
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