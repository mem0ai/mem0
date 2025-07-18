import datetime
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from app.database import engine, Base, SessionLocal
from app.mcp_server import setup_mcp_server
from app.routers import memories_router, apps_router, stats_router, integrations_router, profile_router, webhooks_router
from app.routers import keys as keys_router
from app.routers.admin import router as admin_router
from app.routers.stripe_webhooks import router as stripe_webhooks_router
from app.routers.migration import router as migration_router

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
    
    # 🚧 Phase 1: Check Neo4j connection status
    logger.info("🚧 Checking Neo4j connection status...")
    try:
        from app.utils.neo4j_connection import get_neo4j_status
        neo4j_status = get_neo4j_status()
        
        if neo4j_status["connected"]:
            logger.info(f"✅ Neo4j connected successfully!")
            logger.info(f"   Neo4j URI: {neo4j_status['uri']}")
            logger.info(f"   Neo4j Database: {neo4j_status['database']}")
            logger.info(f"   Overall Status: {neo4j_status['overall_status']}")
        else:
            logger.warning(f"⚠️ Neo4j connection failed (Phase 1 - not critical)")
            logger.warning(f"   Status: {neo4j_status['overall_status']}")
            logger.warning(f"   URI: {neo4j_status['uri']}")
            if 'result' in neo4j_status and 'error' in neo4j_status['result']:
                logger.warning(f"   Error: {neo4j_status['result']['error']}")
    except Exception as e:
        logger.warning(f"⚠️ Neo4j status check failed: {e}")
        logger.warning("   This is expected if Neo4j environment variables are not set")
    
    # 🚧 Phase 2: Check pgvector connection status
    logger.info("🚧 Checking pgvector connection status...")
    try:
        from app.utils.pgvector_connection import get_pgvector_status
        pgvector_status = get_pgvector_status()
        
        if pgvector_status["connected"]:
            logger.info(f"✅ pgvector connected successfully!")
            logger.info(f"   pgvector Host: {pgvector_status['host']}:{pgvector_status['port']}")
            logger.info(f"   pgvector Database: {pgvector_status['database']}")
            logger.info(f"   Extension Available: {pgvector_status.get('extension_available', False)}")
            logger.info(f"   Extension Installed: {pgvector_status.get('extension_installed', False)}")
            logger.info(f"   Overall Status: {pgvector_status['overall_status']}")
        else:
            logger.warning(f"⚠️ pgvector connection failed (Phase 2 - not critical)")
            logger.warning(f"   Status: {pgvector_status['overall_status']}")
            logger.warning(f"   Host: {pgvector_status['host']}:{pgvector_status['port']}")
            if 'result' in pgvector_status and 'error' in pgvector_status['result']:
                logger.warning(f"   Error: {pgvector_status['result']['error']}")
    except Exception as e:
        logger.warning(f"⚠️ pgvector status check failed: {e}")
        logger.warning("   This is expected if pgvector environment variables are not set")
    
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
        "https://jean-memory-ui-virginia.onrender.com", # Render.com frontend URL (Virginia)
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

@app.api_route("/health/detailed", methods=["GET"])
async def detailed_health_check():
    """Detailed health check including Neo4j and pgvector status"""
    try:
        from app.utils.neo4j_connection import get_neo4j_status
        from app.utils.pgvector_connection import get_pgvector_status
        from app.db_init import check_database_health
        
        # Get database health
        db_healthy = check_database_health()
        
        # Get Neo4j status
        neo4j_status = get_neo4j_status()
        
        # Get pgvector status
        pgvector_status = get_pgvector_status()
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "environment": config.ENVIRONMENT,
            "database": {
                "healthy": db_healthy,
                "status": "connected" if db_healthy else "disconnected"
            },
            "neo4j": {
                "available": neo4j_status["available"],
                "configured": neo4j_status["configured"],
                "connected": neo4j_status["connected"],
                "uri": neo4j_status["uri"],
                "database": neo4j_status["database"],
                "overall_status": neo4j_status["overall_status"]
            },
            "pgvector": {
                "available": pgvector_status["available"],
                "configured": pgvector_status["configured"],
                "connected": pgvector_status["connected"],
                "host": pgvector_status["host"],
                "port": pgvector_status["port"],
                "database": pgvector_status["database"],
                "extension_available": pgvector_status.get("extension_available", False),
                "extension_installed": pgvector_status.get("extension_installed", False),
                "overall_status": pgvector_status["overall_status"]
            }
        }
        
        # Add error details if Neo4j has issues
        if not neo4j_status["connected"] and "result" in neo4j_status:
            health_data["neo4j"]["error"] = neo4j_status["result"].get("error", "Unknown error")
            health_data["neo4j"]["error_type"] = neo4j_status["result"].get("type", "unknown")
        
        # Add error details if pgvector has issues
        if not pgvector_status["connected"] and "result" in pgvector_status:
            health_data["pgvector"]["error"] = pgvector_status["result"].get("error", "Unknown error")
            health_data["pgvector"]["error_type"] = pgvector_status["result"].get("type", "unknown")
        
        return health_data
        
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "error": str(e)
        }

@app.get("/download/claude-extension")
async def download_claude_extension(transport: str = "sse"):
    """Serve the Jean Memory Claude Desktop Extension file"""
    
    # Choose extension based on transport type
    if transport == "http":
        filename = "jean-memory-http-v2.dxt"
        description = "Jean Memory Claude Desktop Extension (HTTP Transport - 50% faster)"
    else:
        filename = "jean-memory.dxt"
        description = "Jean Memory Claude Desktop Extension (SSE Transport - Legacy)"
    
    file_path = os.path.join(os.path.dirname(__file__), "app", "static", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Extension file not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Description": description
        }
    )

# Additional endpoint for HTTP v2 extension specifically
@app.get("/download/claude-extension-http")
async def download_claude_extension_http():
    """Serve the Jean Memory Claude Desktop Extension file with HTTP transport"""
    return await download_claude_extension(transport="http")

@app.get("/api/v1/vcard")
async def serve_vcard(data: str):
    """Serve vCard file for MMS contact cards"""
    try:
        import base64
        from fastapi.responses import Response
        
        # Decode the base64 vCard data
        vcf_content = base64.b64decode(data).decode('utf-8')
        
        # Return the vCard with proper MIME type
        return Response(
            content=vcf_content,
            media_type="text/vcard",
            headers={
                "Content-Disposition": "attachment; filename=JeanMemory.vcf",
                "Content-Type": "text/vcard"
            }
        )
    except Exception as e:
        logger.error(f"Error serving vCard: {e}")
        raise HTTPException(status_code=400, detail="Invalid vCard data")

# Include routers - Now using get_current_supa_user from app.auth
app.include_router(keys_router.router, dependencies=[Depends(get_current_supa_user)])
# Local Auth Router (only active in local development)
app.include_router(local_auth_router, prefix="/api/v1")
app.include_router(memories_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
app.include_router(apps_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
app.include_router(stats_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])
app.include_router(integrations_router, dependencies=[Depends(get_current_supa_user)])
app.include_router(profile_router, dependencies=[Depends(get_current_supa_user)])  # SMS profile management
app.include_router(webhooks_router)  # SMS webhooks (no auth - verified by Twilio signature)
app.include_router(admin_router)  # Admin router has its own authentication
app.include_router(agent_mcp_router) # New secure agent endpoint
app.include_router(migration_router, prefix="/api/v1", dependencies=[Depends(get_current_supa_user)])  # Migration status endpoint
app.include_router(stripe_webhooks_router)  # Stripe webhooks (no auth needed - verified by signature)



# Setup MCP server after routers but outside of lifespan to ensure it doesn't block health checks
setup_mcp_server(app)

# add_pagination(app) # Keep if used

logger.info("FastAPI application configured and routers included.")
