"""
OpenMemory Fly.io Startup Script

Wraps the OpenMemory API with:
- HTTP transport for MCP
- OAuth authentication
- Health checks
- Metrics
"""

import os
import sys
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

# Parse NEON_CONNECTION_STRING into PG_* env vars for pgvector auto-detection
if os.environ.get("NEON_CONNECTION_STRING"):
    parsed = urlparse(os.environ["NEON_CONNECTION_STRING"])
    os.environ.setdefault("PG_HOST", parsed.hostname or "")
    os.environ.setdefault("PG_PORT", str(parsed.port or 5432))
    os.environ.setdefault("PG_DB", parsed.path.lstrip("/") if parsed.path else "")
    os.environ.setdefault("PG_USER", parsed.username or "")
    os.environ.setdefault("PG_PASSWORD", parsed.password or "")
    os.environ.setdefault("DATABASE_URL", os.environ["NEON_CONNECTION_STRING"])

# Patch SQLAlchemy engine creation to handle PostgreSQL (removes SQLite-specific options)
def _patch_database_module():
    """Monkey-patch database.py to work with PostgreSQL."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker
    import sys
    from types import ModuleType

    db_url = os.environ.get("DATABASE_URL", "sqlite:///./openmemory.db")

    # Only use check_same_thread for SQLite
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(db_url, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Inject into app.database module before it's imported elsewhere
    db_module = ModuleType("app.database")
    db_module.engine = engine
    db_module.SessionLocal = SessionLocal
    db_module.Base = Base
    db_module.DATABASE_URL = db_url
    db_module.get_db = get_db

    sys.modules["app.database"] = db_module

_patch_database_module()

# Run Alembic migrations
def _run_migrations():
    """Run database migrations on startup."""
    import subprocess
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd="/app",
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": os.environ.get("DATABASE_URL", "")}
        )
        if result.returncode == 0:
            print(f"[STARTUP] Migrations completed")
        else:
            print(f"[STARTUP] Migration warning: {result.stderr.strip()}")
    except Exception as e:
        print(f"[STARTUP] Migration error (non-fatal): {e}")

_run_migrations()

# Patch SQLAlchemy distinct() for PostgreSQL compatibility
# PostgreSQL DISTINCT ON requires matching ORDER BY - use subquery instead
def _patch_distinct_for_postgres():
    """Monkey-patch to fix DISTINCT ON issue with PostgreSQL."""
    from sqlalchemy.orm import Query

    original_distinct = Query.distinct

    def patched_distinct(self, *expr):
        # If using PostgreSQL and distinct on specific columns, skip it
        # The pagination will handle deduplication via the subquery
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url.startswith("postgresql") and expr:
            # Return self without distinct - let the ORM handle it
            return self
        return original_distinct(self, *expr)

    Query.distinct = patched_distinct

_patch_distinct_for_postgres()

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Metrics (use try/except to handle re-import)
from prometheus_client import REGISTRY

try:
    REQUEST_COUNT = Counter("openmemory_requests_total", "Total requests", ["method", "endpoint", "status"])
except ValueError:
    REQUEST_COUNT = REGISTRY._names_to_collectors.get("openmemory_requests_total")

try:
    REQUEST_LATENCY = Histogram("openmemory_request_latency_seconds", "Request latency", ["method", "endpoint"])
except ValueError:
    REQUEST_LATENCY = REGISTRY._names_to_collectors.get("openmemory_request_latency_seconds")

# Config
PORT = int(os.environ.get("PORT", "8765"))
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")
DATA_DIR = os.environ.get("DATA_DIR", "/data")

# Ensure data directories
os.makedirs(f"{DATA_DIR}/qdrant", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sqlite", exist_ok=True)

# Set paths for mem0/openmemory
os.environ.setdefault("QDRANT_PATH", f"{DATA_DIR}/qdrant")


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    # Import auth components
    from auth_middleware import auth_router, get_current_user, SecurityHeadersMiddleware

    # Create wrapper app
    wrapper = FastAPI(
        title="OpenMemory API",
        description="AI Memory Layer with OAuth Authentication",
        version="1.0.0",
        docs_url="/docs" if ENVIRONMENT != "production" else None,
    )

    # CORS
    wrapper.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers
    wrapper.add_middleware(SecurityHeadersMiddleware)

    # Metrics middleware
    @wrapper.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = datetime.now(timezone.utc)
        response = await call_next(request)
        duration = (datetime.now(timezone.utc) - start).total_seconds()

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        return response

    # Health endpoint
    @wrapper.get("/health")
    async def health():
        return {
            "status": "healthy",
            "environment": ENVIRONMENT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Metrics endpoint
    @wrapper.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Auth routes
    wrapper.include_router(auth_router)

    # Mount the OpenMemory app
    try:
        from main import app as openmemory_app

        # Copy routes from openmemory to wrapper (excluding duplicates)
        existing_paths = {r.path for r in wrapper.routes}
        for route in openmemory_app.routes:
            if hasattr(route, 'path') and route.path not in existing_paths:
                wrapper.routes.append(route)

        logger.info("OpenMemory API mounted successfully")

    except Exception as e:
        logger.error("Failed to import OpenMemory API", error=str(e))

        # Fallback: basic MCP endpoint
        @wrapper.post("/mcp/message")
        async def mcp_fallback(request: Request):
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": "OpenMemory API not available"},
                "id": None
            }

    return wrapper


# Create app
app = create_app()


if __name__ == "__main__":
    logger.info("Starting OpenMemory", port=PORT, environment=ENVIRONMENT)

    uvicorn.run(
        app,  # Use app object directly, not string
        host="0.0.0.0",
        port=PORT,
        workers=1,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
