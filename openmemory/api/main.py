import datetime
from uuid import uuid4

from app.config import DEFAULT_APP_ID, USER_ID
from app.database import Base, SessionLocal, engine
from app.mcp_server import setup_mcp_server
from app.models import App, User
from app.routers import apps_router, backup_router, config_router, memories_router, stats_router
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from mem0.telemetry import otel as mem0_otel

# Turnkey OTLP export for the MCP memory server when OTEL_EXPORTER_OTLP_ENDPOINT
# is set (no-op otherwise; never clobbers an operator-installed provider).
mem0_otel.bootstrap_tracing("mem0-mcp-server")

app = FastAPI(title="OpenMemory API")


@app.middleware("http")
async def otel_server_trace(request: Request, call_next):
    """Continue the agent's distributed trace through the MCP memory server.

    Extracts the inbound W3C ``traceparent`` and opens a SERVER span so the
    downstream ``memory.<op>`` spans (and their embedding / vector-store / LLM
    children, emitted by ``mem0.Memory``) render as one
    ``agent → mcp-memory-server → mem0`` trace instead of a detached single-span
    root. No-op when ``mem0[otel]`` is not installed.
    """
    span_attrs = {
        "http.request.method": request.method,
        "url.path": request.url.path,
        mem0_otel.ATTR_OPERATION: "mcp.server.request",
    }
    with mem0_otel.start_server_span(
        f"{request.method} {request.url.path}", dict(request.headers), span_attrs
    ) as span:
        response = await call_next(request)
        try:
            if span is not None:
                span.set_attribute("http.response.status_code", response.status_code)
        except Exception:
            pass
        return response


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
app.include_router(memories_router)
app.include_router(apps_router)
app.include_router(stats_router)
app.include_router(config_router)
app.include_router(backup_router)

# Add pagination support
add_pagination(app)
