"""Tests for POST /api/v1/memories/upload in app.routers.memories."""

import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Set dummy keys before any imports that initialize the OpenAI client.
os.environ.setdefault("OPENAI_API_KEY", "dummy")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_engine():
    """In-memory SQLite engine used for all upload endpoint tests."""
    import app.models  # noqa: F401 — registers ORM event listeners
    from app.database import Base

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(test_engine):
    """Fresh session per test, rolled back on teardown."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def test_app(db_session):
    """FastAPI app with the memories router and the DB dependency overridden."""
    from app.database import get_db
    from app.routers.memories import router
    from fastapi import FastAPI
    from fastapi_pagination import add_pagination

    app = FastAPI()
    app.include_router(router)
    add_pagination(app)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest_asyncio.fixture()
async def client(test_app):
    """Async HTTP client wired to the test app via ASGI transport."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture()
def test_user(db_session):
    """Create a test user in the DB before each test."""
    from app.models import User

    user = User(user_id="upload_test_user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def mock_memory_client():
    """Fake memory client whose add() returns a single ADD result."""
    client = MagicMock()
    client.add.return_value = {
        "results": [
            {"id": str(uuid4()), "memory": "Uploaded memory content.", "event": "ADD"}
        ]
    }
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadEndpoint:
    @pytest.mark.asyncio
    async def test_upload_txt_success(self, client, test_user, mock_memory_client):
        """Uploading a valid .txt file returns 200 and memories_created > 0."""
        with patch(
            "app.routers.memories.get_memory_client", return_value=mock_memory_client
        ):
            with patch(
                "app.utils.categorization.get_categories_for_memories", return_value=[]
            ):
                response = await client.post(
                    "/api/v1/memories/upload",
                    data={"user_id": "upload_test_user"},
                    files={"file": ("notes.txt", b"My test note.", "text/plain")},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["memories_created"] > 0

    @pytest.mark.asyncio
    async def test_upload_unsupported_extension_returns_400(self, client, test_user):
        """Uploading a .csv file is rejected with HTTP 400."""
        response = await client.post(
            "/api/v1/memories/upload",
            data={"user_id": "upload_test_user"},
            files={"file": ("data.csv", b"a,b,c", "text/csv")},
        )

        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_missing_user_returns_404(self, client):
        """Uploading a file for a non-existent user returns HTTP 404."""
        response = await client.post(
            "/api/v1/memories/upload",
            data={"user_id": "no_such_user"},
            files={"file": ("notes.txt", b"Hello.", "text/plain")},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_empty_file_returns_zero_memories(
        self, client, test_user, mock_memory_client
    ):
        """Uploading an empty .txt file returns 200 with memories_created == 0."""
        # Simulate main.py returning no ADD results for an empty file
        mock_memory_client.add.return_value = {"results": []}

        with patch(
            "app.routers.memories.get_memory_client", return_value=mock_memory_client
        ):
            with patch(
                "app.utils.categorization.get_categories_for_memories", return_value=[]
            ):
                response = await client.post(
                    "/api/v1/memories/upload",
                    data={"user_id": "upload_test_user"},
                    files={"file": ("empty.txt", b"", "text/plain")},
                )

        assert response.status_code == 200
        assert response.json()["memories_created"] == 0

    @pytest.mark.asyncio
    async def test_memory_client_returns_none_gives_500(self, client, test_user):
        """When memory_client.add() returns None, the endpoint returns HTTP 500."""
        none_client = MagicMock()
        none_client.add.return_value = None

        with patch("app.routers.memories.get_memory_client", return_value=none_client):
            response = await client.post(
                "/api/v1/memories/upload",
                data={"user_id": "upload_test_user"},
                files={"file": ("notes.txt", b"Some content.", "text/plain")},
            )

        assert response.status_code == 500
        assert "invalid or empty response" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unlink_failure_does_not_mask_success_response(
        self, client, test_user, mock_memory_client
    ):
        """If os.unlink raises OSError, the endpoint still returns the normal response."""
        with patch("app.routers.memories.get_memory_client", return_value=mock_memory_client):
            with patch("app.utils.categorization.get_categories_for_memories", return_value=[]):
                with patch("app.routers.memories.os.unlink", side_effect=OSError("unlink failed")):
                    response = await client.post(
                        "/api/v1/memories/upload",
                        data={"user_id": "upload_test_user"},
                        files={"file": ("notes.txt", b"My test note.", "text/plain")},
                    )

        assert response.status_code == 200
        assert response.json()["memories_created"] > 0

    @pytest.mark.asyncio
    async def test_skip_categorization_prevents_per_insert_calls(
        self, client, test_user, mock_memory_client
    ):
        """The upload endpoint skips per-insert categorization and uses batch instead."""
        with patch(
            "app.routers.memories.get_memory_client", return_value=mock_memory_client
        ):
            with patch(
                "app.utils.categorization.get_categories_for_memories", return_value=[]
            ) as mock_batch:
                with patch("app.models.categorize_memory") as mock_per_insert:
                    response = await client.post(
                        "/api/v1/memories/upload",
                        data={"user_id": "upload_test_user"},
                        files={
                            "file": ("notes.txt", b"My test note.", "text/plain")
                        },
                    )

        assert response.status_code == 200
        # Per-insert categorization must never fire
        mock_per_insert.assert_not_called()
        # Batch categorization is called once for all memories
        mock_batch.assert_called_once()
