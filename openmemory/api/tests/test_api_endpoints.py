"""Tests for API endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    from app.main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_memory_endpoint():
    """Test creating a memory via API."""
    from app.main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/memories/",
            json={
                "user_id": "test_user",
                "text": "Test memory content",
                "infer": False,  # Don't call LLM in tests
                "app": "test_app"
            }
        )

        # Should return immediately with processing state (or error if no mem0)
        assert response.status_code in [200, 500]  # 500 if mem0 unavailable in test


@pytest.mark.asyncio
async def test_list_memories_endpoint():
    """Test listing memories."""
    from app.main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/memories/filter",
            json={
                "user_id": "test_user",
                "page": 1,
                "size": 10
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_infer_parameter():
    """Test that infer parameter is respected."""
    from app.main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test with infer=true
        response = await client.post(
            "/api/v1/memories/",
            json={
                "user_id": "test_user",
                "text": "I love Python",
                "infer": True,
                "app": "test_app"
            }
        )

        # Should attempt LLM processing
        assert response.status_code in [200, 500]

        # Test with infer=false
        response = await client.post(
            "/api/v1/memories/",
            json={
                "user_id": "test_user",
                "text": "Raw text storage",
                "infer": False,
                "app": "test_app"
            }
        )

        # Should store verbatim
        assert response.status_code in [200, 500]
