import pytest
from httpx import AsyncClient, ASGITransport
from fastapi.security import HTTPAuthorizationCredentials
from fastapi import HTTPException
import os

from main import app as fastapi_app
from app.mcp_server import verify_api_key

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_mcp_sse_unauthorized_without_key(monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-valid-key")
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        response = await ac.get("/mcp/test-client/sse/test-user")
    assert response.status_code == 403

@pytest.mark.anyio
async def test_mcp_messages_unauthorized_without_key(monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-valid-key")
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        response = await ac.post("/mcp/messages/")
    assert response.status_code == 403

def test_verify_api_key_valid(monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-valid-key")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="m0-test-valid-key")
    result = verify_api_key(credentials)
    assert result == "m0-test-valid-key"

def test_verify_api_key_invalid(monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-valid-key")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-key")
    with pytest.raises(HTTPException) as excinfo:
        verify_api_key(credentials)
    assert excinfo.value.status_code == 401
