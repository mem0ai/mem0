import datetime
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer
from app.database import engine, Base, SessionLocal
from app.mcp_server import setup_mcp_server
from app.routers import memories_router, apps_router, stats_router, integrations_router, mcp_tools_router
from app.routers import keys as keys_router
from app.routers.admin import router as admin_router
from app.routers.stripe_webhooks import router as stripe_webhooks_router

from fastapi_pagination import add_pagination
from fastapi.middleware.cors import CORSMiddleware
from app.models import User, App
from app.auth import get_current_supa_user
from app.middleware.memory_monitor import MemoryMonitorMiddleware
from app.background_tasks import cleanup_old_tasks
from app.services.background_processor import background_processor
from app.settings import config
from app.db_init import init_database, check_database_health
from app.routers.agent_mcp import agent_mcp_router
from app.routers.local_auth import router as local_auth_router
import asyncio

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
    logger.info(f"Running in {'local development' if config.is_local_development else 'production'} mode")
    
    # Initialize database - THIS MUST RUN IN ALL ENVIRONMENTS
    init_database()
    
    # Check database health
    if not check_database_health():
        logger.error("Database health check failed - application may not work properly")
    
    # Schema fix completed successfully - this code block has been removed
    logger.info("Database and services initialization completed.")
    
    # Start periodic cleanup task
    async def periodic_cleanup():
        while True:
            try:
                cleanup_old_tasks()
                logger.info("Periodic cleanup completed")
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
            await asyncio.sleep(3600)  # Run every hour
    
    # Start cleanup in background
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    # Start background processor for Phase 2 document processing
    processor_task = asyncio.create_task(background_processor.start())
    
    yield
    
    # Cancel all background tasks on shutdown
    background_processor.stop()
    cleanup_task.cancel()
    processor_task.cancel()
    
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    try:
        await processor_task
    except asyncio.CancelledError:
        pass
    
    logger.info("Application shutdown.")

app = FastAPI(
    title=f"{config.APP_NAME} API {'(Local Dev)' if config.is_local_development else '(Production)'}", 
    version=config.API_VERSION,
    lifespan=lifespan
)

# Add memory monitoring middleware (before CORS)
app.add_middleware(MemoryMonitorMiddleware)

# CORS Middleware Configuration
# When allow_credentials=True, allow_origins cannot be "*"
# It must be a list of specific origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:3001", 
        "https://app.jeanmemory.com",  # Updated to new custom domain
        "https://jeanmemory.com", # New custom domain
        "https://www.jeanmemory.com", # New custom domain with www
        "https://jean-memory-ui.onrender.com", # Render.com frontend URL
        "https://api.jeanmemory.com", # API domain used by some components
        "https://platform.openai.com", # OpenAI API Playground
    ],  
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"], # Added PATCH
    allow_headers=["*"], # Allow all headers to fix CORS issues
    expose_headers=["*"], # Expose all headers
    max_age=3600, # Cache preflight requests for 1 hour
)

# Add health check endpoints early before any dependencies
@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    """Root endpoint - redirects to documentation"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint for deployment services"""
    # Keep it simple for fast response
    return {"status": "healthy", "timestamp": datetime.datetime.now(datetime.UTC).isoformat()}

# Include routers - Now using get_current_supa_user from app.auth
app.include_router(keys_router.router, dependencies=[Depends(get_current_supa_user)])
# Local Auth Router (only active in local development)
app.include_router(local_auth_router, prefix="/api/v1")
app.include_router(memories_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
app.include_router(apps_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
app.include_router(stats_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
app.include_router(integrations_router, dependencies=[Depends(get_current_supa_user)])
app.include_router(mcp_tools_router, dependencies=[Depends(get_current_supa_user)])
app.include_router(admin_router)  # Admin router has its own authentication
app.include_router(agent_mcp_router) # New secure agent endpoint
app.include_router(stripe_webhooks_router)  # Stripe webhooks (no auth needed - verified by signature)



# Setup MCP server after routers but outside of lifespan to ensure it doesn't block health checks
setup_mcp_server(app)

# add_pagination(app) # Keep if used

logger.info("FastAPI application configured and routers included.")
