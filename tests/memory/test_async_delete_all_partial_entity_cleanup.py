import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from qdrant_client import QdrantClient

from mem0.memory.main import AsyncMemory
from mem0.memory.storage import SQLiteManager
from mem0.vector_stores.qdrant import Qdrant


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_size", [1, 1000], ids=["saturated-page", "whole-scope"])
@pytest.mark.parametrize("failure", ["partial", "all", "none", "transient", "history", "late"])
async def test_delete_all_preserves_links_for_failed_operations(failure, batch_size):
    """A failed memory deletion must not erase its shared entity association."""
    client = QdrantClient(":memory:")
    store = Qdrant("memories", 2, client=client)
    entities = Qdrant("entities", 2, client=client)
    store._bm25_encoder = entities._bm25_encoder = False
    memory_ids = sorted([str(uuid4()), str(uuid4())])
    entity_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
    payloads = [{"data": f"memory-{i}", "user_id": "alice"} for i in range(2)]
    store.insert([[1.0, 0.0]] * 2, payloads=payloads, ids=memory_ids)
    entities.insert(
        [[1.0, 0.0]] * 3,
        payloads=[
            {"data": "shared", "user_id": "alice", "linked_memory_ids": memory_ids},
            {"data": "second", "user_id": "alice", "linked_memory_ids": [memory_ids[1]]},
            {"data": "other-tenant", "user_id": "bob", "linked_memory_ids": ["bob-memory"]},
        ],
        ids=entity_ids,
    )
    memory = AsyncMemory.__new__(AsyncMemory)
    memory.vector_store = store
    memory._entity_store = entities
    memory.db = SQLiteManager(":memory:")
    memory.embedding_model = SimpleNamespace(embed=lambda *args: [1.0, 0.0])
    original_delete = store.delete
    original_history = memory.db.add_history
    attempts = {}
    lock = threading.Lock()

    def delete(vector_id):
        # Embedded Qdrant write concurrency is a separate reported bug (#4892).
        with lock:
            attempts[vector_id] = attempts.get(vector_id, 0) + 1
            if (
                failure == "all"
                or (
                    vector_id == memory_ids[0]
                    and (failure == "partial" or (failure == "transient" and attempts[vector_id] == 1))
                )
                or (failure == "late" and vector_id == memory_ids[1])
            ):
                raise RuntimeError("injected vector deletion failure")
            return original_delete(vector_id)

    def add_history(memory_id, *args, **kwargs):
        if failure == "history" and memory_id == memory_ids[0]:
            raise RuntimeError("injected history failure after successful vector deletion")
        return original_history(memory_id, *args, **kwargs)

    try:
        with (
            patch.object(store, "delete", side_effect=delete),
            patch.object(memory.db, "add_history", side_effect=add_history),
            patch("mem0.memory.main.capture_event"),
            patch("mem0.memory.main.detect_decay_usage_from_delete_all", return_value=None),
            patch("mem0.memory.main.display_first_run_notice_async", new_callable=AsyncMock),
            patch("mem0.memory.main.DELETE_ALL_BATCH_SIZE", batch_size),
        ):
            result = await memory.delete_all(user_id="alice")

        remaining_memories = {row.id for row in store.list(filters={"user_id": "alice"}, top_k=10)[0]}
        remaining_entities = {
            row.payload["data"]: row.payload["linked_memory_ids"]
            for row in entities.list(filters={"user_id": "alice"}, top_k=10)[0]
        }
        stopped_before_second = batch_size == 1 and failure in {"partial", "all", "transient"}
        expected_memories = (
            set(memory_ids)
            if failure == "all" or stopped_before_second
            else {memory_ids[0]}
            if failure == "partial"
            else {memory_ids[1]}
            if failure == "late"
            else set()
        )
        expected_entities = (
            {"shared": memory_ids, "second": [memory_ids[1]]}
            if failure == "all" or stopped_before_second
            else {"shared": [memory_ids[0]]}
            if failure in {"partial", "history"}
            else {"shared": [memory_ids[1]], "second": [memory_ids[1]]}
            if failure == "late"
            else {}
        )
        assert remaining_memories == expected_memories
        assert remaining_entities == expected_entities
        assert entities.get(entity_ids[2]).payload["linked_memory_ids"] == ["bob-memory"]
        expected_failed = (
            {memory_ids[0]}
            if failure in {"partial", "history"} or (failure != "none" and stopped_before_second)
            else set(memory_ids)
            if failure == "all"
            else {memory_ids[1]}
            if failure == "late"
            else set()
        )
        assert result.get("failed", []) == sorted(expected_failed)
    finally:
        memory.db.close()
        client.close()
