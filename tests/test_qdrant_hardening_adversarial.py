import asyncio
import threading
import time
import warnings
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from qdrant_client import QdrantClient, models
from qdrant_client.grpc import PointId
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PayloadIndexInfo, PayloadSchemaType, SparseVectorParams, VectorParams

from mem0.configs.base import MemoryConfig
from mem0.configs.vector_stores.qdrant import QdrantConfig
from mem0.memory import main as memory_main
from mem0.memory.main import AsyncMemory, Memory, _safe_deepcopy_config
from mem0.vector_stores import qdrant as qdrant_module
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.vector_stores.qdrant import Qdrant
from mem0.vector_stores.utils import normalize_list_result
from server import server_state


def test_existing_remote_client_does_not_gain_local_fallback_path():
    client = MagicMock(spec=QdrantClient)

    config = VectorStoreConfig(provider="qdrant", config={"client": client})

    assert config.config.client is client
    assert config.config.path is None


def test_vector_store_config_does_not_mutate_caller_when_injecting_sdk_default():
    caller_config = {}

    config = VectorStoreConfig(provider="qdrant", config=caller_config)

    assert caller_config == {}
    assert config.config.path == "/tmp/qdrant"


def test_existing_local_client_is_detected_without_repeating_path(monkeypatch):
    client = QdrantClient(":memory:")
    monkeypatch.setattr(qdrant_module.Qdrant, "create_col", lambda *args, **kwargs: None)
    try:
        store = Qdrant(collection_name="memories", embedding_model_dims=4, client=client)
        assert store.is_local is True
    finally:
        client.close()


def test_qdrant_grpc_point_id_is_a_supported_scroll_offset():
    rows = [SimpleNamespace(id="one")]

    assert normalize_list_result((rows, PointId(num=42))) == rows


def test_real_payload_schema_model_is_recognized_as_keyword():
    store = Qdrant.__new__(Qdrant)
    store.client = MagicMock()
    store.collection_name = "memories"
    store.is_local = False
    info = SimpleNamespace(
        payload_schema={
            field: PayloadIndexInfo(data_type=PayloadSchemaType.KEYWORD, points=1)
            for field in ("user_id", "agent_id", "run_id", "actor_id")
        }
    )

    store._create_filter_indexes(info)

    store.client.create_payload_index.assert_not_called()


def test_false_collection_create_result_revalidates_the_winner():
    store = Qdrant.__new__(Qdrant)
    store.client = MagicMock()
    store.collection_name = "memories"
    store.is_local = True
    store.client.collection_exists.return_value = False
    store.client.create_collection.return_value = False
    info = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=VectorParams(size=4, distance=Distance.COSINE),
                sparse_vectors={"bm25": SparseVectorParams(modifier=models.Modifier.IDF)},
            )
        ),
        payload_schema={},
    )
    store.client.get_collection.return_value = info

    store.create_col(vector_size=4, on_disk=False)

    store.client.get_collection.assert_called_once_with("memories")
    assert store._has_bm25_slot is True


def test_real_qdrant_conflict_revalidates_without_recreating():
    store = Qdrant.__new__(Qdrant)
    store.client = MagicMock()
    store.collection_name = "memories"
    store.is_local = True
    store.client.collection_exists.return_value = False
    store.client.create_collection.side_effect = UnexpectedResponse(
        status_code=409,
        reason_phrase="Conflict",
        content=b"already exists",
        headers={},
    )
    info = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=VectorParams(size=4, distance=Distance.COSINE),
                sparse_vectors={},
            )
        ),
        payload_schema={},
    )
    store.client.get_collection.return_value = info

    store.create_col(vector_size=4, on_disk=False)

    store.client.get_collection.assert_called_once_with("memories")
    store.client.delete_collection.assert_not_called()


def test_collection_probe_does_not_list_every_qdrant_collection():
    store = Qdrant.__new__(Qdrant)
    store.client = MagicMock()
    store.collection_name = "memories"
    store.is_local = True
    store.client.collection_exists.return_value = True
    store.client.get_collections.side_effect = AssertionError("full collection scan is unnecessary")
    info = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=VectorParams(size=4, distance=Distance.COSINE),
                sparse_vectors={},
            )
        ),
        payload_schema={},
    )
    store.client.get_collection.return_value = info

    store.create_col(vector_size=4, on_disk=False)

    store.client.collection_exists.assert_called_once_with("memories")
    store.client.get_collections.assert_not_called()


def test_collection_probe_falls_back_for_older_qdrant_server():
    store = Qdrant.__new__(Qdrant)
    store.client = MagicMock()
    store.collection_name = "memories"
    store.is_local = True
    store.client.collection_exists.side_effect = UnexpectedResponse(
        status_code=404,
        reason_phrase="Not Found",
        content=b"endpoint unavailable",
        headers={},
    )
    store.client.get_collections.return_value = SimpleNamespace(collections=[SimpleNamespace(name="memories")])
    info = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=VectorParams(size=4, distance=Distance.COSINE),
                sparse_vectors={},
            )
        ),
        payload_schema={},
    )
    store.client.get_collection.return_value = info

    store.create_col(vector_size=4, on_disk=False)

    store.client.get_collections.assert_called_once()
    store.client.create_collection.assert_not_called()


@pytest.mark.parametrize("collection_name", ["", "   ", "bad\nname", "bad\x7fname"])
def test_invalid_collection_names_fail_before_client_calls(collection_name, monkeypatch):
    with pytest.raises(ValueError, match="collection_name"):
        QdrantConfig(url="https://qdrant.internal", collection_name=collection_name)

    client = MagicMock(spec=QdrantClient)
    with pytest.raises(ValueError, match="collection_name"):
        Qdrant(collection_name=collection_name, embedding_model_dims=4, client=client)
    client.collection_exists.assert_not_called()


def test_validated_server_config_does_not_mutate_caller_dictionary():
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {"host": "qdrant.internal", "port": "6333"},
        }
    }

    normalized = server_state._validated_config(config)

    assert config["vector_store"]["config"]["port"] == "6333"
    assert normalized["vector_store"]["config"]["port"] == 6333


def test_valid_qdrant_config_serialization_does_not_warn_with_api_key():
    secret = "S3CR3T-valid-config-sentinel"
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {"url": "https://qdrant.internal", "api_key": secret},
        }
    }

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        normalized = server_state._validated_config(config)

    assert normalized["vector_store"]["config"]["api_key"] == secret
    assert not captured


def test_memory_config_model_dump_serializes_provider_config_without_warning():
    config = MemoryConfig(
        vector_store={
            "provider": "qdrant",
            "config": {"url": "https://qdrant.internal", "api_key": "S3CR3T-sdk-sentinel"},
        }
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        dumped = config.model_dump(mode="python")

    assert dumped["vector_store"]["config"]["url"] == "https://qdrant.internal"
    assert not captured


def test_config_clone_failure_logs_only_exception_type(caplog):
    secret = "https://user:S3CR3T-clone@qdrant.internal"

    class ExplodingConfig:
        def __deepcopy__(self, memo):
            raise RuntimeError(secret)

    with caplog.at_level("DEBUG"):
        _safe_deepcopy_config(ExplodingConfig())

    assert "RuntimeError" in caplog.text
    assert secret not in caplog.text


def test_entity_list_failure_does_not_log_provider_exception_text(caplog):
    secret = "https://user:S3CR3T-list@qdrant.internal"
    memory = Memory.__new__(Memory)
    memory._entity_store = MagicMock()
    memory._entity_store.list.side_effect = RuntimeError(secret)

    with caplog.at_level("DEBUG"):
        assert memory._existing_entities_by_text({"user_id": "alice"}) == {}

    assert "RuntimeError" in caplog.text
    assert secret not in caplog.text


def test_real_qdrant_delete_all_drains_more_than_one_page_and_preserves_other_tenant(tmp_path, monkeypatch):
    store = Qdrant(
        collection_name="memories",
        embedding_model_dims=1,
        path=str(tmp_path / "qdrant"),
    )
    try:
        alice_count = memory_main.DELETE_ALL_PAGE_SIZE + 5
        ids = list(range(alice_count + 1))
        store.insert(
            vectors=[[0.1] for _ in ids],
            ids=ids,
            payloads=[
                {"data": "", "user_id": "alice", "created_at": "2026-01-01T00:00:00+00:00"} for _ in range(alice_count)
            ]
            + [{"data": "", "user_id": "bob", "created_at": "2026-01-01T00:00:00+00:00"}],
        )

        memory = Memory.__new__(Memory)
        memory.vector_store = store
        memory.config = MemoryConfig(
            vector_store={
                "provider": "qdrant",
                "config": {"path": str(tmp_path / "qdrant"), "embedding_model_dims": 1},
            }
        )
        memory.db = MagicMock()
        memory.embedding_model = MagicMock()
        memory._entity_store = MagicMock()
        memory._entity_store.list.return_value = ([], None)
        monkeypatch.setattr(memory_main, "capture_event", MagicMock())
        monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
        monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())

        result = memory.delete_all(user_id="alice")

        assert result == {"message": "Memories deleted successfully!"}
        assert normalize_list_result(store.list(filters={"user_id": "alice"}, top_k=10)) == []
        bob = normalize_list_result(store.list(filters={"user_id": "bob"}, top_k=10))
        assert len(bob) == 1
        assert memory.db.add_history.call_count == alice_count
        assert memory._entity_store.list.call_count <= 2
    finally:
        store.client.close()


def test_sync_entity_cleanup_drains_pages_and_retries_partial_failures(monkeypatch):
    remaining = {f"entity-{index}": SimpleNamespace(id=f"entity-{index}") for index in range(5)}
    failed_once = set()

    class EntityStore:
        def list(self, **kwargs):
            return (list(remaining.values())[:2], None)

        def delete(self, vector_id):
            if vector_id == "entity-0" and vector_id not in failed_once:
                failed_once.add(vector_id)
                raise RuntimeError("transient")
            remaining.pop(vector_id)

    memory = Memory.__new__(Memory)
    memory._entity_store = EntityStore()
    monkeypatch.setattr(memory_main, "ENTITY_CLEANUP_PAGE_SIZE", 2)

    memory._bulk_clear_entity_store({"user_id": "alice"})

    assert not remaining
    assert failed_once == {"entity-0"}


def test_real_qdrant_bulk_entity_cleanup_is_tenant_scoped(tmp_path, monkeypatch):
    store = Qdrant(
        collection_name="mem0_entities",
        embedding_model_dims=1,
        path=str(tmp_path / "qdrant-entities"),
    )
    try:
        store.insert(
            vectors=[[0.1] for _ in range(6)],
            ids=list(range(6)),
            payloads=[{"data": "", "user_id": "alice"} for _ in range(5)] + [{"data": "", "user_id": "bob"}],
        )
        memory = Memory.__new__(Memory)
        memory._entity_store = store
        monkeypatch.setattr(memory_main, "ENTITY_CLEANUP_PAGE_SIZE", 2)

        memory._bulk_clear_entity_store({"user_id": "alice"})

        assert normalize_list_result(store.list(filters={"user_id": "alice"}, top_k=10)) == []
        bob = normalize_list_result(store.list(filters={"user_id": "bob"}, top_k=10))
        assert len(bob) == 1
    finally:
        store.client.close()


def test_sync_delete_all_surfaces_incomplete_bulk_entity_cleanup(monkeypatch):
    memory = Memory.__new__(Memory)
    memory.vector_store = MagicMock()
    memory.vector_store.list.return_value = ([], None)
    memory._bulk_clear_entity_store = MagicMock(side_effect=RuntimeError("entity cleanup incomplete"))
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())

    with pytest.raises(RuntimeError, match="entity cleanup incomplete"):
        memory.delete_all(user_id="alice")


@pytest.mark.asyncio
async def test_async_entity_cleanup_uses_bounded_parallelism(monkeypatch):
    record_count = 50
    remaining = {f"entity-{index}": SimpleNamespace(id=f"entity-{index}") for index in range(record_count)}
    guard = threading.Lock()
    active = 0
    maximum_active = 0

    class EntityStore:
        def list(self, **kwargs):
            return (list(remaining.values()), None)

        def delete(self, vector_id):
            nonlocal active, maximum_active
            with guard:
                active += 1
                maximum_active = max(maximum_active, active)
            try:
                time.sleep(0.005)
                remaining.pop(vector_id)
            finally:
                with guard:
                    active -= 1

    memory = AsyncMemory.__new__(AsyncMemory)
    memory._entity_store = EntityStore()
    monkeypatch.setattr(memory_main, "DELETE_ALL_ASYNC_CONCURRENCY", 7)

    await memory._bulk_clear_entity_store({"user_id": "alice"})

    assert not remaining
    assert 1 < maximum_active <= 7


@pytest.mark.asyncio
async def test_multiple_runtime_leases_delay_close_until_last_request(monkeypatch):
    instance = MagicMock()
    monkeypatch.setattr(server_state, "_memory_instance", instance)
    monkeypatch.setattr(server_state, "_active_leases", {})
    monkeypatch.setattr(server_state, "_retired_instances", {})
    closed = MagicMock()
    monkeypatch.setattr(server_state, "_close_memory_instance", closed)

    first = server_state.memory_instance_lease()
    second = server_state.memory_instance_lease()
    first.__enter__()
    second.__enter__()
    server_state._retire_memory_instance(instance)
    first.__exit__(None, None, None)
    closed.assert_not_called()

    await asyncio.sleep(0)
    second.__exit__(None, None, None)

    closed.assert_called_once_with(instance)
