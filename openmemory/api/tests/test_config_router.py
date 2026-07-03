"""Tests for the configuration API router.

Covers the PUT /api/v1/config/ handler, which previously built the updated
configuration but never persisted it, never reset the memory client, and
returned None (causing a ResponseValidationError / HTTP 500 on every call).
"""

import os

# Set dummy keys before any imports that trigger client initialization
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Config as ConfigModel
from app.routers import config as config_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session_factory():
    """In-memory SQLite database shared across sessions via StaticPool."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


@pytest.fixture
def reset_calls(monkeypatch):
    """Stub out reset_memory_client and record invocations."""
    calls = []
    monkeypatch.setattr(config_router, "reset_memory_client", lambda: calls.append(1))
    return calls


@pytest.fixture
def client(db_session_factory, reset_calls):
    """TestClient wired to the config router with the test database."""
    app = FastAPI()
    app.include_router(config_router.router)

    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _sample_config():
    return {
        "openmemory": {"custom_instructions": "Remember dietary preferences."},
        "mem0": {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "max_tokens": 1500,
                    "api_key": "env:OPENAI_API_KEY",
                },
            }
        },
    }


# ---------------------------------------------------------------------------
# PUT /api/v1/config/
# ---------------------------------------------------------------------------

class TestUpdateConfiguration:
    def test_put_returns_updated_config(self, client):
        """PUT should return the updated configuration, not None (500)."""
        resp = client.put("/api/v1/config/", json=_sample_config())
        assert resp.status_code == 200
        data = resp.json()
        assert data["mem0"]["llm"]["config"]["model"] == "gpt-4o"
        assert data["openmemory"]["custom_instructions"] == "Remember dietary preferences."

    def test_put_persists_config(self, client, db_session_factory):
        """PUT should save the updated configuration to the database."""
        client.put("/api/v1/config/", json=_sample_config())

        db = db_session_factory()
        try:
            stored = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
            assert stored is not None
            assert stored.value["mem0"]["llm"]["config"]["model"] == "gpt-4o"
        finally:
            db.close()

        # And a subsequent GET reflects the update
        resp = client.get("/api/v1/config/")
        assert resp.status_code == 200
        assert resp.json()["mem0"]["llm"]["config"]["model"] == "gpt-4o"

    def test_put_resets_memory_client(self, client, reset_calls):
        """PUT should reset the memory client so the new config takes effect."""
        client.put("/api/v1/config/", json=_sample_config())
        assert len(reset_calls) == 1

    def test_put_without_mem0_section(self, client):
        """PUT with only openmemory settings should not fail on the absent mem0 key."""
        resp = client.put(
            "/api/v1/config/",
            json={"openmemory": {"custom_instructions": "Only openmemory."}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["openmemory"]["custom_instructions"] == "Only openmemory."
        # mem0 section keeps its existing (default) values
        assert data["mem0"]["llm"]["provider"] == "openai"
