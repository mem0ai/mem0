"""Shared pytest fixtures for server/ tests.

Strategy:
- SQLite in-memory engine for the auth DB (Users, APIKey, RefreshTokenJti, etc).
- get_memory_instance() is patched to return a MagicMock so routes that touch
  the memory backend don't need pgvector.
- The FastAPI app is imported lazily after env vars are set so module-level
  constants in server.auth (JWT_SECRET, AUTH_DISABLED, ADMIN_API_KEY) bind
  to the test values, not whatever the host shell has.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make server/ importable as a top-level package (matches uvicorn's CWD).
SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

# Required for JWT issuance during tests.
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-" + "x" * 32)
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("POSTGRES_HOST", "localhost")  # silence db url builder


@pytest.fixture
def test_engine():
    """Fresh in-memory SQLite engine per test (no cross-test pollution)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Import Base AFTER env vars are set.
    from db import Base  # noqa: E402

    # Importing models registers them on Base.metadata.
    import models  # noqa: F401, E402

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session_factory(test_engine):
    return sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def mock_memory():
    """A MagicMock standing in for the global Memory instance."""
    mock = MagicMock()
    mock.get_all.return_value = {"results": []}
    mock.search.return_value = {"results": []}
    mock.add.return_value = {"results": [], "events": []}
    mock.get.return_value = {"id": "memory-id", "memory": "stub"}
    mock.history.return_value = []
    mock.delete.return_value = None
    mock.delete_all.return_value = None
    mock.reset.return_value = None
    mock.vector_store.list.return_value = [[]]
    return mock


@pytest.fixture
def client(test_session_factory, mock_memory, monkeypatch):
    """FastAPI TestClient with overridden DB session and mocked memory instance."""
    from db import get_db  # noqa: E402
    import server_state  # noqa: E402

    # Neutralize the real Memory.from_config() call that initialize_state()
    # makes during main.py import — pgvector and the history sqlite path are
    # both unavailable in tests.
    monkeypatch.setattr(server_state, "initialize_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server_state, "get_memory_instance", lambda: mock_memory)

    from main import app  # noqa: E402

    # Also patch the binding inside main.py since it imported get_memory_instance by name.
    monkeypatch.setattr("main.get_memory_instance", lambda: mock_memory)

    def _override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_session(test_session_factory):
    """A direct DB session for tests that need to insert User rows."""
    session = test_session_factory()
    try:
        yield session
    finally:
        session.close()


def _make_user(db_session, *, role: str, email: str | None = None):
    from auth import hash_password
    from models import User

    user = User(
        id=uuid.uuid4(),
        name=f"{role}-user",
        email=email or f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("test-password-123"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    return _make_user(db_session, role="admin")


@pytest.fixture
def member_user(db_session):
    """Non-admin User. No public endpoint produces these today; we insert directly."""
    return _make_user(db_session, role="member")


@pytest.fixture
def admin_jwt(admin_user):
    from auth import create_access_token

    return create_access_token(str(admin_user.id), admin_user.role)


@pytest.fixture
def member_jwt(member_user):
    from auth import create_access_token

    return create_access_token(str(member_user.id), member_user.role)


@pytest.fixture
def auth_admin_header(admin_jwt):
    return {"Authorization": f"Bearer {admin_jwt}"}


@pytest.fixture
def auth_member_header(member_jwt):
    return {"Authorization": f"Bearer {member_jwt}"}


@pytest.fixture
def admin_api_key_env(monkeypatch):
    """Activates the legacy ADMIN_API_KEY escape hatch."""
    import auth

    key = "admin-api-key-test-value-" + "y" * 16
    monkeypatch.setattr(auth, "ADMIN_API_KEY", key)
    return {"X-API-Key": key}


@pytest.fixture
def auth_disabled_env(monkeypatch):
    """Activates AUTH_DISABLED=true."""
    import auth

    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    return {}  # no headers needed
