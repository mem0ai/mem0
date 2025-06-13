"""
Local Development Authentication Helper
Uses real Supabase CLI authentication for local development with multi-user support
"""
import logging
from fastapi import Request, HTTPException
from supabase import Client as SupabaseClient
from gotrue.types import User as SupabaseUser
from starlette.status import HTTP_401_UNAUTHORIZED

logger = logging.getLogger(__name__)

async def get_local_dev_user_from_token(
    request: Request, 
    supabase_client: SupabaseClient,
    token: str,
    config
) -> SupabaseUser:
    """
    Authenticate a real user token using local Supabase CLI.
    This function mirrors production authentication exactly.
    """
    if not config.is_local_development:
        raise RuntimeError("Local dev auth should only be used in development")
    
    try:
        # Use the same authentication flow as production
        user_response = supabase_client.auth.get_user(token)
        if user_response and user_response.user:
            logger.debug(f"Local user authenticated: {user_response.user.email}")
            return user_response.user
        else:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
            
    except Exception as e:
        logger.debug(f"Local auth failed: {e}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

async def get_local_dev_user(
    request: Request, 
    supabase_client: SupabaseClient,
    config
) -> SupabaseUser:
    """
    Get user from Authorization header in local development.
    If no valid token, create/return a default developer user for API testing.
    """
    if not config.is_local_development:
        raise RuntimeError("get_local_dev_user should only be called in local development")
    
    # Check if there's an Authorization header with a real token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        if token and token != "dummy-token" and len(token) > 20:  # Real JWT tokens are longer
            try:
                return await get_local_dev_user_from_token(request, supabase_client, token, config)
            except HTTPException:
                # If token is invalid, fall back to default user
                pass
    
    # Fallback: Create/return default developer user for testing
    dev_email = "developer@localhost.dev"
    dev_password = "local-dev-password-123"
    
    try:
        # Try to sign in the existing default dev user
        auth_response = supabase_client.auth.sign_in_with_password({
            "email": dev_email,
            "password": dev_password
        })
        logger.debug(f"Default local dev user signed in: {auth_response.user.id}")
        return auth_response.user
        
    except Exception as sign_in_error:
        logger.debug(f"Default dev user sign in failed, attempting to create: {sign_in_error}")
        
        try:
            # Create the default dev user if it doesn't exist
            auth_response = supabase_client.auth.sign_up({
                "email": dev_email,
                "password": dev_password,
                "options": {
                    "data": {
                        "name": "Local Developer",
                        "role": "developer"
                    }
                }
            })
            logger.info(f"Created new default local dev user: {auth_response.user.id}")
            return auth_response.user
            
        except Exception as sign_up_error:
            logger.error(f"Failed to create default local dev user: {sign_up_error}")
            
            # Final fallback to mock user (if Supabase CLI not running)
            class MockLocalUser:
                def __init__(self):
                    self.id = "00000000-0000-0000-0000-000000000001"
                    self.email = dev_email
                    self.user_metadata = {"name": "Local Developer", "role": "developer"}
                    self.app_metadata = {}
                    self.aud = "authenticated"
                    self.created_at = "2024-01-01T00:00:00Z"
                    
            logger.warning("Using mock user - Supabase CLI may not be running")
            return MockLocalUser()

async def create_local_user(supabase_client: SupabaseClient, email: str, password: str, user_data: dict = None):
    """
    Helper function to create new local users for testing.
    This mirrors the production user creation flow.
    """
    try:
        signup_data = {
            "email": email,
            "password": password
        }
        
        if user_data:
            signup_data["options"] = {"data": user_data}
            
        auth_response = supabase_client.auth.sign_up(signup_data)
        logger.info(f"Created local user: {email}")
        return auth_response
        
    except Exception as e:
        logger.error(f"Failed to create local user {email}: {e}")
        raise

async def sign_in_local_user(supabase_client: SupabaseClient, email: str, password: str):
    """
    Helper function to sign in local users.
    Returns the session token that can be used in Authorization headers.
    """
    try:
        auth_response = supabase_client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        logger.info(f"Local user signed in: {email}")
        return auth_response
        
    except Exception as e:
        logger.error(f"Failed to sign in local user {email}: {e}")
        raise 