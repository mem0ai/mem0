import asyncio
import os
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, call
from uuid import uuid4

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.models import MemoryState
from app.routers import memories as memories_router
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_create_memory_does_not_block_concurrent_requests(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    app_record = SimpleNamespace(id=uuid4(), is_active=True)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [user, app_record]

    started = threading.Event()
    release = threading.Event()

    def slow_add(*args, **kwargs):
        started.set()
        release.wait(timeout=3)
        return {"results": []}

    memory_client = MagicMock()
    memory_client.add.side_effect = slow_add
    monkeypatch.setattr(memories_router, "get_memory_client", MagicMock(return_value=memory_client))

    app = FastAPI()
    app.include_router(memories_router.router)

    def override_get_db():
        yield db

    app.dependency_overrides[memories_router.get_db] = override_get_db

    @app.get("/probe")
    async def probe():
        return {"status": "ok"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        timer = threading.Timer(2, release.set)
        timer.start()
        started_at = asyncio.get_running_loop().time()
        create_task = asyncio.create_task(
            client.post(
                "/api/v1/memories/",
                json={"user_id": "alice", "text": "Remember this", "app": "test-app"},
            )
        )

        try:
            assert await asyncio.to_thread(started.wait, 2)
            response = await client.get("/probe")
            elapsed = asyncio.get_running_loop().time() - started_at
        finally:
            release.set()
            create_response = await create_task
            timer.cancel()

    assert response.status_code == 200
    assert create_response.status_code == 200
    assert elapsed < 1.5


def test_update_memory_updates_vector_store_before_sql(monkeypatch):
    memory_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    memory = SimpleNamespace(id=memory_id, content="Old content")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    memory_client = MagicMock()

    monkeypatch.setattr(memories_router, "get_memory_or_404", MagicMock(return_value=memory))
    monkeypatch.setattr(memories_router, "get_memory_client", MagicMock(return_value=memory_client))

    request = memories_router.UpdateMemoryRequest(memory_content="New content", user_id="alice")
    result = memories_router.update_memory(memory_id, request, db)

    memory_client.update.assert_called_once_with(str(memory_id), text="New content")
    assert memory.content == "New content"
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(memory)
    assert result is memory


def test_update_memory_preserves_sql_when_vector_update_fails(monkeypatch):
    memory_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    memory = SimpleNamespace(id=memory_id, content="Old content")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    memory_client = MagicMock()
    memory_client.update.side_effect = RuntimeError("vector unavailable")

    monkeypatch.setattr(memories_router, "get_memory_or_404", MagicMock(return_value=memory))
    monkeypatch.setattr(memories_router, "get_memory_client", MagicMock(return_value=memory_client))

    request = memories_router.UpdateMemoryRequest(memory_content="New content", user_id="alice")
    with pytest.raises(HTTPException) as exc_info:
        memories_router.update_memory(memory_id, request, db)

    assert exc_info.value.status_code == 502
    assert "vector store" in exc_info.value.detail
    assert memory.content == "Old content"
    db.commit.assert_not_called()


def test_update_memory_restores_vector_when_sql_commit_fails(monkeypatch):
    memory_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    memory = SimpleNamespace(id=memory_id, content="Old content")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.commit.side_effect = RuntimeError("database unavailable")
    memory_client = MagicMock()

    monkeypatch.setattr(memories_router, "get_memory_or_404", MagicMock(return_value=memory))
    monkeypatch.setattr(memories_router, "get_memory_client", MagicMock(return_value=memory_client))

    request = memories_router.UpdateMemoryRequest(memory_content="New content", user_id="alice")
    with pytest.raises(HTTPException) as exc_info:
        memories_router.update_memory(memory_id, request, db)

    assert exc_info.value.status_code == 500
    assert memory_client.update.call_args_list == [
        call(str(memory_id), text="New content"),
        call(str(memory_id), text="Old content"),
    ]
    db.rollback.assert_called_once_with()


def test_delete_memories_preserves_sql_when_vector_delete_fails(monkeypatch):
    memory_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    memory = SimpleNamespace(id=memory_id, state=MemoryState.active)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    memory_client = MagicMock()
    memory_client.delete.side_effect = RuntimeError("vector unavailable")
    update_memory_state = MagicMock()

    monkeypatch.setattr(memories_router, "get_memory_or_404", MagicMock(return_value=memory))
    monkeypatch.setattr(memories_router, "get_memory_client", MagicMock(return_value=memory_client))
    monkeypatch.setattr(memories_router, "update_memory_state", update_memory_state)

    request = memories_router.DeleteMemoriesRequest(memory_ids=[memory_id], user_id="alice")
    with pytest.raises(HTTPException) as exc_info:
        memories_router.delete_memories(request, db)

    assert exc_info.value.status_code == 502
    assert "vector store" in exc_info.value.detail
    update_memory_state.assert_not_called()
    assert memory.state == MemoryState.active
