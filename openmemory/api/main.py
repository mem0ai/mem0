import datetime
import os
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from supabase import create_client, Client
from starlette.status import HTTP_401_UNAUTHORIZED
from app.database import engine, Base, SessionLocal
from app.mcp_server import setup_mcp_server
from app.routers import memories_router, apps_router, stats_router
from fastapi_pagination import add_pagination
from fastapi.middleware.cors import CORSMiddleware
from app.models import User, App
from uuid import uuid4
from app.config import USER_ID, DEFAULT_APP_ID

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("Supabase URL and Service Key must be set in environment variables.")

supabase_backend_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI(title="Jonathan's Memory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables
Base.metadata.create_all(bind=engine)

# Authentication Dependency
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(request: Request):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated (no token)"
        )
    if token.startswith("Bearer "):
        token = token.split("Bearer ")[1]
    
    try:
        user_response = supabase_backend_client.auth.get_user(jwt=token)
        user = user_response.user
        if not user:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
        return user
    except Exception as e:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e}",
        )

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

# Include routers with auth dependency
app.include_router(memories_router, dependencies=[Depends(get_current_user)])
app.include_router(apps_router, dependencies=[Depends(get_current_user)])
app.include_router(stats_router, dependencies=[Depends(get_current_user)])

# Add pagination support
add_pagination(app)
