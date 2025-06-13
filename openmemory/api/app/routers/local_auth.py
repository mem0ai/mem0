"""
Local Development Authentication Endpoints
Only available in local development mode
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from supabase import Client as SupabaseClient
import logging

from app.auth import get_service_client
from app.local_auth_helper import create_local_user, sign_in_local_user
from app.settings import config

logger = logging.getLogger(__name__)

# Only create this router in local development
if config.is_local_development:
    router = APIRouter(prefix="/local-auth", tags=["Local Development Auth"])
else:
    router = APIRouter()

class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = "Local User"
    role: str = "user"

class UserSignInRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user_id: str
    email: str
    access_token: str
    refresh_token: str = None
    expires_in: int

@router.post("/create-user", response_model=AuthResponse)
async def create_local_dev_user(
    user_data: UserCreateRequest,
    supabase_client: SupabaseClient = Depends(get_service_client)
):
    """
    Create a new local development user.
    Only available in local development mode.
    """
    if not config.is_local_development:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This endpoint is only available in local development"
        )
    
    try:
        user_metadata = {
            "name": user_data.name,
            "role": user_data.role
        }
        
        auth_response = await create_local_user(
            supabase_client,
            user_data.email,
            user_data.password,
            user_metadata
        )
        
        return AuthResponse(
            user_id=auth_response.user.id,
            email=auth_response.user.email,
            access_token=auth_response.session.access_token if auth_response.session else "",
            refresh_token=auth_response.session.refresh_token if auth_response.session else None,
            expires_in=auth_response.session.expires_in if auth_response.session else 3600
        )
        
    except Exception as e:
        logger.error(f"Failed to create local user: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create user: {str(e)}"
        )

@router.post("/sign-in", response_model=AuthResponse)
async def sign_in_local_dev_user(
    credentials: UserSignInRequest,
    supabase_client: SupabaseClient = Depends(get_service_client)
):
    """
    Sign in a local development user.
    Returns access token that can be used in Authorization header.
    """
    if not config.is_local_development:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This endpoint is only available in local development"
        )
    
    try:
        auth_response = await sign_in_local_user(
            supabase_client,
            credentials.email,
            credentials.password
        )
        
        return AuthResponse(
            user_id=auth_response.user.id,
            email=auth_response.user.email,
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token,
            expires_in=auth_response.session.expires_in
        )
        
    except Exception as e:
        logger.error(f"Failed to sign in local user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@router.get("/users")
async def list_local_users(
    supabase_client: SupabaseClient = Depends(get_service_client)
):
    """
    List all local development users.
    Useful for debugging and testing.
    """
    if not config.is_local_development:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This endpoint is only available in local development"
        )
    
    try:
        # In a real implementation, you'd query the auth.users table
        # For now, return a simple message
        return {
            "message": "To list users, check your local Supabase dashboard at http://127.0.0.1:54323",
            "note": "This endpoint is for local development only"
        }
        
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )

# Health check for local auth
@router.get("/health")
async def local_auth_health():
    """Check if local auth endpoints are available"""
    if config.is_local_development:
        return {
            "status": "healthy",
            "mode": "local_development",
            "supabase_url": config.SUPABASE_URL,
            "endpoints": [
                "POST /local-auth/create-user",
                "POST /local-auth/sign-in", 
                "GET /local-auth/users",
                "GET /local-auth/health"
            ]
        }
    else:
        return {
            "status": "disabled",
            "mode": "production",
            "message": "Local auth endpoints are disabled in production"
        } 