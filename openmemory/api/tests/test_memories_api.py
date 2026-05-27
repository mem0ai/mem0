import os
from uuid import UUID, uuid4

# Set dummy keys before imports that may initialize providers
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import Base, SessionLocal, engine
from app.models import App, Memory, User
from app.routers.memories import router as memories_router


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(memories_router)
    return app


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class DummyMemoryClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def add(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


@pytest.mark.asyncio
async def test_create_memory_creates_missing_user_and_app(client, monkeypatch):
    memory_id = str(uuid4())
    dummy_client = DummyMemoryClient(
        {
            "results": [
                {"id": memory_id, "memory": "René likes self-hosting", "event": "ADD"}
            ]
        }
    )
    monkeypatch.setattr("app.routers.memories.get_memory_client", lambda: dummy_client)

    response = await client.post(
        "/api/v1/memories/",
        json={
            "user_id": "rene-test-user",
            "text": "René likes self-hosting",
            "app": "hermes",
            "infer": False,
            "metadata": {"source": "test"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == memory_id
    assert body["content"] == "René likes self-hosting"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == "rene-test-user").first()
        assert user is not None

        app = db.query(App).filter(App.owner_id == user.id, App.name == "hermes").first()
        assert app is not None

        memory = db.query(Memory).filter(Memory.id == UUID(body["id"])).first()
        assert memory is not None
        assert memory.user_id == user.id
        assert memory.app_id == app.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_create_memory_returns_422_when_backend_returns_no_results(client, monkeypatch):
    monkeypatch.setattr("app.routers.memories.get_memory_client", lambda: DummyMemoryClient({"results": []}))

    response = await client.post(
        "/api/v1/memories/",
        json={
            "user_id": "rene-empty-results",
            "text": "This may extract to nothing",
            "app": "hermes",
        },
    )

    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "Memory extraction produced no persisted memories"}
