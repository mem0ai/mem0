import gc
import importlib.util
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from mem0.configs.base import MemoryConfig
from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.configs import EmbedderConfig
from mem0.exceptions import ValidationError as Mem0ValidationError
from mem0.memory.main import AsyncMemory, Memory
from mem0.vector_stores.configs import VectorStoreConfig
from tests.zvec_embedding_fixture import FIXTURE_EMBEDDINGS_PATH, FixtureEmbedding, load_fixture_embeddings

RUN_LOCAL_E2E = os.getenv("MEM0_ZVEC_LOCAL_E2E") == "1"
LOCAL_MODEL_PATH = Path(os.getenv("MEM0_ZVEC_LOCAL_MODEL", "/Users/dgordon/models/bge-large-en-v1.5"))
HAS_ZVEC = importlib.util.find_spec("zvec") is not None
HAS_SENTENCE_TRANSFORMERS = importlib.util.find_spec("sentence_transformers") is not None

pytestmark = [
    pytest.mark.skipif(not RUN_LOCAL_E2E, reason="Set MEM0_ZVEC_LOCAL_E2E=1 to run local zvec e2e tests."),
    pytest.mark.skipif(not HAS_ZVEC, reason="zvec is not installed."),
    pytest.mark.skipif(not FIXTURE_EMBEDDINGS_PATH.exists(), reason="precomputed zvec embedding fixture is missing."),
]

if HAS_SENTENCE_TRANSFORMERS:
    from mem0.embeddings.huggingface import HuggingFaceEmbedding
else:
    HuggingFaceEmbedding = object


def _memory_config(
    tmp_path: Path,
    embedding_dims: int,
    collection_name: str = "mem0",
    embedder_model: str = "fixture://zvec",
) -> MemoryConfig:
    return MemoryConfig(
        vector_store=VectorStoreConfig(
            provider="zvec",
            config={
                "collection_name": collection_name,
                "embedding_model_dims": embedding_dims,
                "path": str(tmp_path / "zvec"),
            },
        ),
        embedder=EmbedderConfig(
            provider="huggingface",
            config={
                "model": embedder_model,
                "embedding_dims": embedding_dims,
                "model_kwargs": {"local_files_only": True},
            },
        ),
        history_db_path=str(tmp_path / "history.db"),
    )


@pytest.fixture(scope="session")
def fixture_embedder() -> FixtureEmbedding:
    return FixtureEmbedding(load_fixture_embeddings())


@pytest.fixture(scope="session")
def local_embedder():
    if not HAS_SENTENCE_TRANSFORMERS:
        pytest.skip("sentence-transformers is not installed")
    if not LOCAL_MODEL_PATH.exists():
        pytest.skip("Local BGE model path does not exist")
    config = BaseEmbedderConfig(model=str(LOCAL_MODEL_PATH), model_kwargs={"local_files_only": True})
    return HuggingFaceEmbedding(config)


@pytest.fixture
def patched_runtime_with_fixture_embeddings(monkeypatch, fixture_embedder):
    monkeypatch.setattr("mem0.memory.main.EmbedderFactory.create", lambda *args, **kwargs: fixture_embedder)
    monkeypatch.setattr("mem0.memory.main.LlmFactory.create", lambda *args, **kwargs: Mock())
    monkeypatch.setattr("mem0.memory.main.capture_event", lambda *args, **kwargs: None)


@pytest.fixture
def patched_runtime_with_local_model(monkeypatch, local_embedder):
    monkeypatch.setattr("mem0.memory.main.EmbedderFactory.create", lambda *args, **kwargs: local_embedder)
    monkeypatch.setattr("mem0.memory.main.LlmFactory.create", lambda *args, **kwargs: Mock())
    monkeypatch.setattr("mem0.memory.main.capture_event", lambda *args, **kwargs: None)


@pytest.fixture
def sync_memory(tmp_path, fixture_embedder, patched_runtime_with_fixture_embeddings):
    config = _memory_config(tmp_path, fixture_embedder.config.embedding_dims, collection_name="sync")
    return Memory(config)


@pytest.fixture
def async_memory(tmp_path, fixture_embedder, patched_runtime_with_fixture_embeddings):
    config = _memory_config(tmp_path, fixture_embedder.config.embedding_dims, collection_name="async")
    return AsyncMemory(config)


@pytest.fixture
def sync_memory_local_model(tmp_path, local_embedder, patched_runtime_with_local_model):
    config = _memory_config(
        tmp_path,
        local_embedder.config.embedding_dims,
        collection_name="sync-model",
        embedder_model=str(LOCAL_MODEL_PATH),
    )
    return Memory(config)


@pytest.fixture
def async_memory_local_model(tmp_path, local_embedder, patched_runtime_with_local_model):
    config = _memory_config(
        tmp_path,
        local_embedder.config.embedding_dims,
        collection_name="async-model",
        embedder_model=str(LOCAL_MODEL_PATH),
    )
    return AsyncMemory(config)


def test_sync_memory_full_interface_lifecycle_and_history(sync_memory):
    first_add = sync_memory.add("I like hiking", user_id="u-sync", infer=False)
    first_memory_id = first_add["results"][0]["id"]

    second_add = sync_memory.add(
        [
            {"role": "system", "content": "skip me"},
            {"role": "user", "name": "alice", "content": "I drink tea"},
            {"role": "assistant", "name": "agent-a", "content": "Noted"},
        ],
        user_id="u-sync",
        infer=False,
        metadata={"source": "local-e2e"},
    )
    assert len(second_add["results"]) == 2

    fetched = sync_memory.get(first_memory_id)
    assert fetched is not None
    assert fetched["memory"] == "I like hiking"

    searched = sync_memory.search("hiking", user_id="u-sync", limit=10)
    assert searched["results"]
    assert any(item["id"] == first_memory_id for item in searched["results"])

    actor_filtered = sync_memory.get_all(user_id="u-sync", filters={"actor_id": "alice"})
    assert actor_filtered["results"]
    assert all(item.get("actor_id") == "alice" for item in actor_filtered["results"])

    sync_memory.update(first_memory_id, "I like hiking and cycling")
    updated = sync_memory.get(first_memory_id)
    assert updated is not None
    assert updated["memory"] == "I like hiking and cycling"

    history_before_delete = sync_memory.history(first_memory_id)
    assert {entry["event"] for entry in history_before_delete} >= {"ADD", "UPDATE"}

    sync_memory.delete(first_memory_id)
    assert sync_memory.get(first_memory_id) is None

    history_after_delete = sync_memory.history(first_memory_id)
    assert "DELETE" in {entry["event"] for entry in history_after_delete}

    with pytest.raises(NotImplementedError):
        sync_memory.chat("hello")

    delete_all_result = sync_memory.delete_all(user_id="u-sync")
    assert delete_all_result["message"] == "Memories deleted successfully!"
    assert sync_memory.get_all(user_id="u-sync")["results"] == []

    sync_memory.reset()
    assert sync_memory.get_all(user_id="u-sync")["results"] == []


def test_sync_memory_unhappy_paths(sync_memory):
    with pytest.raises(Mem0ValidationError):
        sync_memory.add("missing identifiers", infer=False)

    with pytest.raises(Mem0ValidationError):
        sync_memory.add(1234, user_id="u-sync", infer=False)

    with pytest.raises(Mem0ValidationError):
        sync_memory.get_all()

    with pytest.raises(Mem0ValidationError):
        sync_memory.search("anything")

    with pytest.raises(ValueError):
        sync_memory.delete_all()

    with pytest.raises(Exception):
        sync_memory.update("missing-id", "new value")

    with pytest.raises(Exception):
        sync_memory.delete("missing-id")

    assert sync_memory.get("missing-id") is None


def test_sync_memory_filter_edges_and_threshold(sync_memory):
    sync_memory.add(
        [
            {"role": "user", "content": "Run one memory"},
            {"role": "assistant", "content": "Assistant notes run one"},
        ],
        user_id="u-sync",
        infer=False,
    )

    eq_filter = sync_memory.search(
        "memory",
        user_id="u-sync",
        filters={"role": {"eq": "user"}},
        limit=10,
    )
    assert eq_filter["results"]
    assert all(item.get("role") == "user" for item in eq_filter["results"])

    in_filter = sync_memory.search(
        "memory",
        user_id="u-sync",
        filters={"role": {"in": ["assistant"]}},
        limit=10,
    )
    assert in_filter["results"]
    assert all(item.get("role") == "assistant" for item in in_filter["results"])

    high_threshold = sync_memory.search("memory", user_id="u-sync", threshold=2.0, limit=10)
    assert high_threshold["results"] == []

    with pytest.raises(ValueError, match="AND filters only"):
        sync_memory.search(
            "memory",
            user_id="u-sync",
            filters={"OR": [{"role": "user"}, {"role": "assistant"}]},
            limit=10,
        )

    with pytest.raises(ValueError, match="AND filters only"):
        sync_memory.search(
            "memory",
            user_id="u-sync",
            filters={"NOT": [{"role": "assistant"}]},
            limit=10,
        )

    with pytest.raises(AttributeError):
        sync_memory.search(
            "memory",
            user_id="u-sync",
            filters={"run_id": {"in": ["r1"]}},
            limit=10,
        )


def test_sync_memory_persistence_across_instances(tmp_path, fixture_embedder, patched_runtime_with_fixture_embeddings):
    config = _memory_config(tmp_path, fixture_embedder.config.embedding_dims, collection_name="persist")
    memory_one = Memory(config)
    add_result = memory_one.add("persisted memory", user_id="u-persist", infer=False)
    memory_id = add_result["results"][0]["id"]
    del memory_one
    gc.collect()

    memory_two = Memory(config)
    fetched = memory_two.get(memory_id)
    assert fetched is not None
    assert fetched["memory"] == "persisted memory"
    assert memory_two.search("persisted", user_id="u-persist")["results"]


@pytest.mark.asyncio
async def test_async_memory_full_interface_lifecycle_and_history(async_memory):
    first_add = await async_memory.add("I like coffee", user_id="u-async", infer=False)
    first_memory_id = first_add["results"][0]["id"]

    second_add = await async_memory.add(
        [
            {"role": "system", "content": "skip me"},
            {"role": "user", "name": "bob", "content": "I drink espresso"},
            {"role": "assistant", "name": "agent-b", "content": "Captured"},
        ],
        user_id="u-async",
        infer=False,
        metadata={"source": "local-e2e"},
    )
    assert len(second_add["results"]) == 2

    fetched = await async_memory.get(first_memory_id)
    assert fetched is not None
    assert fetched["memory"] == "I like coffee"

    searched = await async_memory.search("coffee", user_id="u-async", limit=10)
    assert searched["results"]
    assert any(item["id"] == first_memory_id for item in searched["results"])

    actor_filtered = await async_memory.get_all(user_id="u-async", filters={"actor_id": "bob"})
    assert actor_filtered["results"]
    assert all(item.get("actor_id") == "bob" for item in actor_filtered["results"])

    await async_memory.update(first_memory_id, "I like coffee and tea")
    updated = await async_memory.get(first_memory_id)
    assert updated is not None
    assert updated["memory"] == "I like coffee and tea"

    history_before_delete = await async_memory.history(first_memory_id)
    assert {entry["event"] for entry in history_before_delete} >= {"ADD", "UPDATE"}

    await async_memory.delete(first_memory_id)
    assert await async_memory.get(first_memory_id) is None

    history_after_delete = await async_memory.history(first_memory_id)
    assert "DELETE" in {entry["event"] for entry in history_after_delete}

    with pytest.raises(NotImplementedError):
        await async_memory.chat("hello")

    delete_all_result = await async_memory.delete_all(user_id="u-async")
    assert delete_all_result["message"] == "Memories deleted successfully!"
    assert (await async_memory.get_all(user_id="u-async"))["results"] == []

    await async_memory.reset()
    assert (await async_memory.get_all(user_id="u-async"))["results"] == []


@pytest.mark.asyncio
async def test_async_memory_unhappy_paths(async_memory):
    with pytest.raises(Mem0ValidationError):
        await async_memory.add("missing identifiers", infer=False)

    with pytest.raises(Mem0ValidationError):
        await async_memory.add(1234, user_id="u-async", infer=False)

    with pytest.raises(Mem0ValidationError):
        await async_memory.get_all()

    with pytest.raises(Mem0ValidationError):
        await async_memory.search("anything")

    with pytest.raises(ValueError):
        await async_memory.delete_all()

    with pytest.raises(Exception):
        await async_memory.update("missing-id", "new value")

    with pytest.raises(Exception):
        await async_memory.delete("missing-id")

    assert await async_memory.get("missing-id") is None


@pytest.mark.asyncio
async def test_async_memory_filter_edges_and_threshold(async_memory):
    await async_memory.add(
        [
            {"role": "user", "content": "Async run one"},
            {"role": "assistant", "content": "Assistant notes async run one"},
        ],
        user_id="u-async",
        infer=False,
    )

    eq_filter = await async_memory.search(
        "run",
        user_id="u-async",
        filters={"role": {"eq": "user"}},
        limit=10,
    )
    assert eq_filter["results"]
    assert all(item.get("role") == "user" for item in eq_filter["results"])

    in_filter = await async_memory.search(
        "run",
        user_id="u-async",
        filters={"role": {"in": ["assistant"]}},
        limit=10,
    )
    assert in_filter["results"]
    assert all(item.get("role") == "assistant" for item in in_filter["results"])

    high_threshold = await async_memory.search("run", user_id="u-async", threshold=2.0, limit=10)
    assert high_threshold["results"] == []

    with pytest.raises(ValueError, match="AND filters only"):
        await async_memory.search(
            "run",
            user_id="u-async",
            filters={"OR": [{"role": "user"}, {"role": "assistant"}]},
            limit=10,
        )

    with pytest.raises(ValueError, match="AND filters only"):
        await async_memory.search(
            "run",
            user_id="u-async",
            filters={"NOT": [{"role": "assistant"}]},
            limit=10,
        )

    with pytest.raises(AttributeError):
        await async_memory.search(
            "run",
            user_id="u-async",
            filters={"run_id": {"in": ["ra1"]}},
            limit=10,
        )


@pytest.mark.asyncio
async def test_async_memory_persistence_across_instances(
    tmp_path,
    fixture_embedder,
    patched_runtime_with_fixture_embeddings,
):
    config = _memory_config(tmp_path, fixture_embedder.config.embedding_dims, collection_name="persist-async")
    memory_one = AsyncMemory(config)
    add_result = await memory_one.add("persisted async memory", user_id="u-persist-async", infer=False)
    memory_id = add_result["results"][0]["id"]
    del memory_one
    gc.collect()

    memory_two = AsyncMemory(config)
    fetched = await memory_two.get(memory_id)
    assert fetched is not None
    assert fetched["memory"] == "persisted async memory"
    searched = await memory_two.search("persisted", user_id="u-persist-async")
    assert searched["results"]


@pytest.mark.skipif(not HAS_SENTENCE_TRANSFORMERS, reason="sentence-transformers is not installed.")
@pytest.mark.skipif(not LOCAL_MODEL_PATH.exists(), reason="Local BGE model path does not exist.")
def test_sync_memory_local_model_smoke(sync_memory_local_model):
    add_result = sync_memory_local_model.add("I like hiking", user_id="u-model-sync", infer=False)
    memory_id = add_result["results"][0]["id"]
    fetched = sync_memory_local_model.get(memory_id)
    assert fetched is not None
    assert fetched["memory"] == "I like hiking"
    assert sync_memory_local_model.search("hiking", user_id="u-model-sync")["results"]


@pytest.mark.skipif(not HAS_SENTENCE_TRANSFORMERS, reason="sentence-transformers is not installed.")
@pytest.mark.skipif(not LOCAL_MODEL_PATH.exists(), reason="Local BGE model path does not exist.")
@pytest.mark.asyncio
async def test_async_memory_local_model_smoke(async_memory_local_model):
    add_result = await async_memory_local_model.add("I like coffee", user_id="u-model-async", infer=False)
    memory_id = add_result["results"][0]["id"]
    fetched = await async_memory_local_model.get(memory_id)
    assert fetched is not None
    assert fetched["memory"] == "I like coffee"
    searched = await async_memory_local_model.search("coffee", user_id="u-model-async")
    assert searched["results"]
