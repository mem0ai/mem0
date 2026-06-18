import os

# Fail-closed: in team local-only mode, force-disable mem0's PostHog telemetry
# BEFORE any (transitive) mem0 import — mem0.memory.telemetry reads MEM0_TELEMETRY
# at module load time, so this must run before the app.* imports below.
if (os.environ.get("MEM0_LOCAL_ONLY") or "").strip().lower() in ("1", "true", "yes", "on"):
    os.environ["MEM0_TELEMETRY"] = "false"

import datetime
from uuid import uuid4

from app.config import DEFAULT_APP_ID, USER_ID
from app.database import Base, SessionLocal, engine
from app.mcp_server import setup_mcp_server
from app.middleware.request_id import RequestIdMiddleware
from app.models import App, User
from app.routers import (
    admin_router,
    apps_router,
    backup_router,
    compat_v3_router,
    config_router,
    discovery_router,
    health_router,
    memories_router,
    ops_metrics_router,
    provision_router,
    stats_router,
)
from app.workers.write_worker import embedded_worker_enabled, write_worker
from app.utils.logging_context import install_structured_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination

install_structured_logging()

app = FastAPI(title="OpenMemory API")

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
app.include_router(admin_router)
app.include_router(memories_router)
app.include_router(apps_router)
app.include_router(stats_router)
app.include_router(config_router)
app.include_router(backup_router)
app.include_router(discovery_router)
app.include_router(compat_v3_router)
app.include_router(provision_router)
app.include_router(health_router)
app.include_router(ops_metrics_router)

# Add pagination support
add_pagination(app)


# Start/stop the background write worker that consumes the write queue and runs
# the LLM extraction/persistence out of band (task_06 / ADR-004). In scale
# deployments the worker runs as a separate service (RUN_EMBEDDED_WORKER=false).
@app.on_event("startup")
async def _start_write_worker():
    if embedded_worker_enabled():
        write_worker.start()


@app.on_event("shutdown")
async def _stop_write_worker():
    if embedded_worker_enabled():
        await write_worker.stop()
