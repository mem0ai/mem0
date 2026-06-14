import datetime
import hmac
import os
from uuid import uuid4

from app.config import DEFAULT_APP_ID, USER_ID
from app.database import Base, SessionLocal, engine
from app.mcp_server import setup_mcp_server
from app.models import App, User
from app.routers import apps_router, backup_router, config_router, memories_router, stats_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

app = FastAPI(title="OpenMemory API")

# --- Optional API-key authentication ---------------------------------------
# The MCP/REST endpoints derive user_id from the URL path / request body with no
# identity check, so on a public URL anyone who guesses a user_id can read/write
# that user's memories. Setting OPENMEMORY_API_KEY turns on a constant-time key
# check on the data endpoints. It is OFF by default to avoid breaking existing
# MCP clients; enabling it is strongly recommended for any internet-facing deploy.
_API_KEY = os.environ.get("OPENMEMORY_API_KEY")
_PROTECTED_PREFIXES = ("/mcp", "/api/")


async def _api_key_dispatch(request, call_next):
    if (
        _API_KEY
        and request.method != "OPTIONS"  # let CORS preflight through
        and request.url.path.startswith(_PROTECTED_PREFIXES)
    ):
        provided = request.headers.get("x-api-key")
        if not provided:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                provided = auth[7:]
        if not provided or not hmac.compare_digest(provided, _API_KEY):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# Registered BEFORE CORS so CORS ends up the outer layer and even 401 responses
# carry CORS headers.
app.add_middleware(BaseHTTPMiddleware, dispatch=_api_key_dispatch)

# --- CORS ------------------------------------------------------------------
# Origins are env-configurable (comma-separated). Credentials are only allowed
# with an explicit allowlist — the wildcard '*' + credentials combination is
# invalid per the CORS spec and unsafe, so credentials are disabled for '*'.
_cors_origins = [o.strip() for o in os.environ.get("OPENMEMORY_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables
Base.metadata.create_all(bind=engine)

# Check for USER_ID and create default user if needed
def create_default_user():
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            # Create default user
            user = User(
                id=uuid4(),
                user_id=USER_ID,
                name="Default User",
                created_at=datetime.datetime.now(datetime.UTC)
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


def create_default_app():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            return

        # Check if app already exists
        existing_app = db.query(App).filter(
            App.name == DEFAULT_APP_ID,
            App.owner_id == user.id
        ).first()

        if existing_app:
            return

        app = App(
            id=uuid4(),
            name=DEFAULT_APP_ID,
            owner_id=user.id,
            created_at=datetime.datetime.now(datetime.UTC),
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(app)
        db.commit()
    finally:
        db.close()

# Create default user on startup
create_default_user()
create_default_app()

# Setup MCP server
setup_mcp_server(app)

# Include routers
app.include_router(memories_router)
app.include_router(apps_router)
app.include_router(stats_router)
app.include_router(config_router)
app.include_router(backup_router)

# Add pagination support
add_pagination(app)
