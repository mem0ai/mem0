"""Memory lifecycle must release owned Qdrant clients without deleting data."""

from contextlib import closing
from unittest.mock import MagicMock

import pytest
from qdrant_client import QdrantClient, models

from mem0 import AsyncMemory, Memory
from mem0.configs.base import MemoryConfig
from mem0.memory import main


@pytest.fixture
def memory_factory(tmp_path, monkeypatch):
    # Storage and lifecycle are real. No LLM, embedding or telemetry requests.
    monkeypatch.setattr(main.LlmFactory, "create", lambda *args: MagicMock())
    monkeypatch.setattr(main.EmbedderFactory, "create", lambda *args: MagicMock())
    monkeypatch.setattr(main, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(main, "capture_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "mem0_dir", str(tmp_path / "telemetry"))
    instances = []

    def create(memory_cls, **store_options):
        config = MemoryConfig(
            vector_store={
                "provider": "qdrant",
                "config": {
                    "path": str(tmp_path / "qdrant"),
                    "collection_name": "lifecycle",
                    "embedding_model_dims": 2,
                    **store_options,
                },
            },
            history_db_path=":memory:",
        )
        instance = memory_cls(config)
        instances.append(instance)
        return instance

    yield create
    # Cleanup even on the pre-fix red run, which leaves Qdrant open.
    for instance in instances:
        instance.close()
        instance.vector_store.client.close()
        telemetry = getattr(instance, "_telemetry_vector_store", None)
        if telemetry is not None:
            telemetry.client.close()


@pytest.mark.parametrize("memory_cls", [Memory, AsyncMemory])
@pytest.mark.parametrize("initialize_entities", [False, True])
def test_close_releases_owned_clients_and_preserves_data(
    memory_factory, tmp_path, monkeypatch, memory_cls, initialize_entities
):
    monkeypatch.setattr(main, "MEM0_TELEMETRY", True)
    memory = memory_factory(memory_cls)
    client = memory.vector_store.client
    client.upsert("lifecycle", [models.PointStruct(id=1, vector=[1.0, 0.0], payload={"data": "keep me"})])
    if initialize_entities:
        assert memory.entity_store.client is client
    close_calls = []
    original_close = client.close

    def close_once(*args, **kwargs):
        close_calls.append(True)
        return original_close(*args, **kwargs)

    monkeypatch.setattr(client, "close", close_once)
    memory.close()
    memory.close()

    assert memory.db is None
    assert close_calls == [True]
    assert (memory._entity_store is not None) == initialize_entities
    with closing(QdrantClient(path=str(tmp_path / "qdrant"))) as reopened:
        assert reopened.retrieve("lifecycle", [1])[0].payload == {"data": "keep me"}
    with closing(QdrantClient(path=str(tmp_path / "telemetry" / "migrations_qdrant"))) as reopened:
        assert reopened.collection_exists("mem0migrations")


@pytest.mark.parametrize("memory_cls", [Memory, AsyncMemory])
def test_close_leaves_caller_owned_shared_client_usable(memory_factory, tmp_path, memory_cls):
    client = QdrantClient(path=str(tmp_path / "shared"))
    try:
        first = memory_factory(memory_cls, client=client)
        second = memory_factory(memory_cls, client=client)
        assert first.entity_store.client is client
        first.close()
        first.close()
        assert second.vector_store.client.collection_exists("lifecycle")
        second.close()
        assert client.collection_exists("lifecycle")
    finally:
        client.close()


def test_sync_context_manager_releases_local_directory(memory_factory, tmp_path):
    with memory_factory(Memory):
        pass
    with closing(QdrantClient(path=str(tmp_path / "qdrant"))) as reopened:
        assert reopened.collection_exists("lifecycle")


@pytest.mark.asyncio
async def test_async_context_manager_releases_local_directory(memory_factory, tmp_path):
    async with memory_factory(AsyncMemory):
        pass
    with closing(QdrantClient(path=str(tmp_path / "qdrant"))) as reopened:
        assert reopened.collection_exists("lifecycle")
