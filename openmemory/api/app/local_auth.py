"""
Local Authentication Module for Development without Supabase Auth

This module provides a FastAPI dependency that can be used as a replacement for
get_current_supa_user in local development environments.
"""
import os
import logging
from fastapi import Depends, Request, HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED
from .settings import config

logger = logging.getLogger(__name__)

# Mock Supabase User for local development
class MockSupabaseUser:
    """Mock implementation of Supabase's User class for local development"""
    def __init__(self, id, email="local@example.com"):
        self.id = id
        self.email = email
        self.app_metadata = {}
        self.user_metadata = {}
        self.aud = "authenticated"
        # Add any other properties required by your application

async def get_local_dev_user(request: Request):
    """
    A replacement for get_current_supa_user that works in local development
    without requiring Supabase authentication.
    
    This will return a MockSupabaseUser with the USER_ID from the environment
    when development mode is active.
    """
    user_id = config.get_default_user_id()
    if not user_id:
        logger.error("USER_ID not set in environment for local authentication")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, 
            detail="Local development authentication not configured properly"
        )
        
    # Get the Authorization header for compatibility with frontend that might still send it
    auth_header = request.headers.get("Authorization")
    
    # Log but don't require the auth header in local dev mode
    if not auth_header:
        logger.debug("Using local development authentication (no token provided)")
    else:
        logger.debug(f"Using local development authentication (ignoring provided token)")
    
    # Return a mock user with the configured USER_ID
    return MockSupabaseUser(id=user_id)
