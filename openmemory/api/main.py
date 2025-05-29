import datetime
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer
from app.database import engine, Base, SessionLocal
from app.mcp_server import setup_mcp_server
from app.routers import memories_router, apps_router, stats_router, integrations_router, mcp_tools_router
from fastapi_pagination import add_pagination
from fastapi.middleware.cors import CORSMiddleware
from app.models import User, App
from app.auth import get_current_supa_user

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

# Supabase client is now initialized in app.auth.py
# oauth2_scheme can also be moved to app.auth.py if only used there, or keep if needed by main app
# For simplicity, if oauth2_scheme was only for get_current_supa_user, it's implicitly handled by FastAPI's Depends with security schemes.
# If you used OAuth2PasswordBearer for other things in main, keep it. Otherwise, it might not be needed here directly.
# Let's assume it's not directly needed in main.py anymore.

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup...")
    # Base.metadata.create_all(bind=engine) # Alembic handles this
    logger.info("Database and services initialization (if any at startup beyond Supabase client)." )
    yield
    logger.info("Application shutdown.")

app = FastAPI(
    title="Jonathan's Memory API (Supabase Auth)", 
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware Configuration
# When allow_credentials=True, allow_origins cannot be "*"
# It must be a list of specific origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:3001", 
        "https://jean-memory-ui.onrender.com",  # UPDATED to new frontend name
        "https://jeanmemory.com", # New custom domain
        "https://www.jeanmemory.com", # New custom domain with www
    ],  
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"], # Added PATCH
    allow_headers=["*"], # Allow all headers to fix CORS issues
    expose_headers=["*"], # Expose all headers
    max_age=3600, # Cache preflight requests for 1 hour
)

# Add health check endpoints early before any dependencies
@app.get("/")
async def root():
    """Root endpoint - redirects to documentation"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment services"""
    # Keep it simple for fast response
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}

# Include routers - Now using get_current_supa_user from app.auth
app.include_router(memories_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
app.include_router(apps_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
# Conditionally include other routers if they exist and are set up
# if 'users_router' in globals(): # A way to check, or just comment out
# app.include_router(users_router, prefix="/api/v1")
# if 'feedback_router' in globals():
# app.include_router(feedback_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
app.include_router(stats_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
app.include_router(integrations_router, dependencies=[Depends(get_current_supa_user)])
app.include_router(mcp_tools_router, dependencies=[Depends(get_current_supa_user)])

# Setup MCP server after routers but outside of lifespan to ensure it doesn't block health checks
setup_mcp_server(app)

# add_pagination(app) # Keep if used

logger.info("FastAPI application configured and routers included.")
