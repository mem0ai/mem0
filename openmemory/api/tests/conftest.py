"""Pytest configuration and fixtures for OpenMemory tests."""
import pytest
import asyncio
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from httpx import AsyncClient
from database import Base, engine, SessionLocal
from models import User, App, Memory, MemoryState
import os

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "test-key")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
async def client():
    """Create async HTTP client for API testing."""
    from main import app as fastapi_app
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_user(db):
    """Create a test user."""
    user = User(user_id="test_user", name="Test User", email="test@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_app(db, test_user):
    """Create a test app."""
    app_obj = App(owner_id=test_user.id, name="test_app", description="Test App")
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return app_obj
