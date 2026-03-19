from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Config as ConfigModel  # noqa: F401 - registers table with Base
from app.routers.config import router

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


@patch("app.routers.config.reset_memory_client")
def test_put_config_saves_and_returns(mock_reset, client):
    payload = {
        "openmemory": {"custom_instructions": "Be concise"},
        "mem0": {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "max_tokens": 1000,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {"model": "text-embedding-3-small"},
            },
        },
    }

    response = client.put("/api/v1/config/", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["mem0"]["llm"]["provider"] == "openai"
    assert data["mem0"]["llm"]["config"]["model"] == "gpt-4o"
    assert data["openmemory"]["custom_instructions"] == "Be concise"
    mock_reset.assert_called_once()

    # Verify persistence by fetching config back
    get_response = client.get("/api/v1/config/")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["mem0"]["llm"]["config"]["model"] == "gpt-4o"
    assert get_data["openmemory"]["custom_instructions"] == "Be concise"
