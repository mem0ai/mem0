import importlib.util
import gc
import sys
import types
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tests.zvec_embedding_fixture import FixtureEmbedding, load_fixture_embeddings

HAS_ZVEC = importlib.util.find_spec("zvec") is not None
pytestmark = pytest.mark.skipif(not HAS_ZVEC, reason="zvec is not installed in this environment")

if HAS_ZVEC:
    from mem0.configs.base import MemoryConfig
    from mem0.configs.enums import MemoryType
    from mem0.configs.vector_stores.zvec import ZvecConfig
    from mem0.memory.main import AsyncMemory, Memory
    from mem0.memory.setup import get_or_create_user_id
    from mem0.vector_stores.configs import VectorStoreConfig
    from mem0.vector_stores.zvec import Zvec
else:
    MemoryConfig = object
    MemoryType = object
    ZvecConfig = object
    AsyncMemory = object
    Memory = object
    get_or_create_user_id = object
    VectorStoreConfig = object
    Zvec = object


def _store_config(path: Path, collection_name: str = "memory") -> VectorStoreConfig:
    return VectorStoreConfig(
        provider="zvec",
        config={
            "collection_name": collection_name,
            "embedding_model_dims": 3,
            "path": str(path),
        },
    )


def _memory_config(tmp_path: Path, collection_name: str = "mem0") -> MemoryConfig:
    return MemoryConfig(
        vector_store=_store_config(tmp_path / "store", collection_name=collection_name),
        history_db_path=str(tmp_path / "history.db"),
    )


@pytest.fixture(scope="session")
def fixture_embedder() -> FixtureEmbedding:
    payload = load_fixture_embeddings()
    three_dim_payload = {
        "embedding_dims": 3,
        "texts": {text: vector[:3] for text, vector in payload["texts"].items()},
    }
    return FixtureEmbedding(three_dim_payload)


def test_vector_store_config_instantiates_real_zvec_config(tmp_path):
    config = _store_config(tmp_path / "zvec")
    assert isinstance(config.config, ZvecConfig)
    assert config.config.path == str(tmp_path / "zvec")


def test_adapter_bootstraps_and_reopens_existing_collection(tmp_path):
    path = tmp_path / "zvec"
    store = Zvec(collection_name="memory", embedding_model_dims=3, path=str(path))
    store.insert(vectors=[[1.0, 0.0, 0.0]], payloads=[{"data": "persisted", "user_id": "u1"}], ids=["id1"])
    assert store.get("id1") is not None

    store = None
    gc.collect()

    reopened = Zvec(collection_name="memory", embedding_model_dims=3, path=str(path))
    fetched = reopened.get("id1")
    assert fetched is not None
    assert fetched.payload["data"] == "persisted"


def test_real_zvec_crud_list_shape_and_reset(tmp_path):
    store = Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path / "zvec"))
    store.insert(
        vectors=[[1.0, 0.0, 0.0], [0.8, 0.2, 0.0], [0.0, 1.0, 0.0]],
        payloads=[
            {"data": "cats", "user_id": "u1", "run_id": "r1", "created_at": "1"},
            {"data": "tea", "user_id": "u2", "run_id": "r2", "created_at": "2"},
            {"data": "dogs", "user_id": "u3", "run_id": "r3", "created_at": "3"},
        ],
        ids=["id1", "id2", "id3"],
    )

    search_results = store.search(query="cats", vectors=[1.0, 0.0, 0.0], limit=5, filters={"user_id": "u1"})
    assert len(search_results) == 1
    assert search_results[0].id == "id1"

    fetched = store.get("id2")
    assert fetched is not None
    assert fetched.payload["data"] == "tea"

    store.update("id2", payload={"data": "tea updated", "user_id": "u2", "run_id": "r2", "created_at": "2"})
    updated = store.get("id2")
    assert updated is not None
    assert updated.payload["data"] == "tea updated"

    listed = store.list(filters={"user_id": {"in": ["u1", "u2"]}}, limit=10)
    assert isinstance(listed, list)
    assert listed
    assert isinstance(listed[0], list)
    assert {item.id for item in listed[0]} == {"id1", "id2"}

    store.delete("id3")
    assert store.get("id3") is None

    info = store.col_info()
    assert hasattr(info, "doc_count")
    assert info.doc_count == 2

    store.reset()
    assert store.list(limit=10) == [[]]


def test_real_zvec_search_filter_correctness(tmp_path):
    store = Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path / "zvec"))
    store.insert(
        vectors=[[1.0, 0.0, 0.0], [0.8, 0.2, 0.0], [0.0, 1.0, 0.0]],
        payloads=[
            {"data": "cats", "user_id": "u1", "run_id": "r1", "created_at": "1"},
            {"data": "tea", "user_id": "u2", "run_id": "r2", "created_at": "2"},
            {"data": "dogs", "user_id": "u3", "run_id": "r3", "created_at": "3"},
        ],
        ids=["id1", "id2", "id3"],
    )

    eq_results = store.search(query="", vectors=[1.0, 0.0, 0.0], limit=10, filters={"user_id": "u2"})
    assert {doc.id for doc in eq_results} == {"id2"}

    range_results = store.search(
        query="",
        vectors=[1.0, 0.0, 0.0],
        limit=10,
        filters={"created_at": {"gte": "2", "lte": "3"}},
    )
    assert {doc.id for doc in range_results} == {"id2", "id3"}

    in_results = store.search(
        query="",
        vectors=[1.0, 0.0, 0.0],
        limit=10,
        filters={"run_id": {"in": ["r1", "r3"]}},
    )
    assert {doc.id for doc in in_results} == {"id1", "id3"}

    nin_results = store.search(
        query="",
        vectors=[1.0, 0.0, 0.0],
        limit=10,
        filters={"run_id": {"nin": ["r1", "r3"]}},
    )
    assert {doc.id for doc in nin_results} == {"id2"}


def test_memory_sync_flow_with_real_zvec(tmp_path, fixture_embedder):
    config = _memory_config(tmp_path)

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fixture_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=Mock()),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = Memory(config)
        add_result = memory.add([{"role": "user", "content": "I like cats"}], user_id="u1", infer=False)
        memory_id = add_result["results"][0]["id"]

        assert memory.get(memory_id)["memory"] == "I like cats"
        assert memory.search("cats", user_id="u1")["results"]
        assert memory.get_all(user_id="u1")["results"]

        memory.update(memory_id, "I like cats and tea")
        assert memory.get(memory_id)["memory"] == "I like cats and tea"

        memory.delete(memory_id)
        assert memory.get(memory_id) is None

        memory.add([{"role": "user", "content": "I like tea"}], user_id="u1", infer=False)
        delete_all_result = memory.delete_all(user_id="u1")
        assert delete_all_result["message"] == "Memories deleted successfully!"
        assert memory.get_all(user_id="u1")["results"] == []

        memory.reset()
        assert memory.get_all(user_id="u1")["results"] == []


@pytest.mark.asyncio
async def test_memory_async_flow_with_real_zvec(tmp_path, fixture_embedder):
    config = _memory_config(tmp_path)

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fixture_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=Mock()),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = AsyncMemory(config)
        add_result = await memory.add([{"role": "user", "content": "I like tea"}], user_id="u2", infer=False)
        memory_id = add_result["results"][0]["id"]

        assert (await memory.get(memory_id))["memory"] == "I like tea"
        assert (await memory.search("tea", user_id="u2"))["results"]
        assert (await memory.get_all(user_id="u2"))["results"]

        await memory.update(memory_id, "I like tea and coffee")
        assert (await memory.get(memory_id))["memory"] == "I like tea and coffee"

        await memory.delete(memory_id)
        assert await memory.get(memory_id) is None

        await memory.add([{"role": "user", "content": "I like coffee"}], user_id="u2", infer=False)
        delete_all_result = await memory.delete_all(user_id="u2")
        assert delete_all_result["message"] == "Memories deleted successfully!"
        assert (await memory.get_all(user_id="u2"))["results"] == []

        await memory.reset()
        assert (await memory.get_all(user_id="u2"))["results"] == []


def test_real_zvec_auxiliary_methods_defaults_and_delete_col(tmp_path):
    store = Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path / "zvec"))

    assert "memory" in store.list_cols()
    info = store.col_info()
    assert hasattr(info, "doc_count")
    assert info.doc_count == 0

    store.insert(vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    assert store.get("0") is not None
    assert store.get("1") is not None
    assert store.get("missing-id") is None

    nested_vector_search = store.search(query="", vectors=[[1.0, 0.0, 0.0]], limit=1)
    assert nested_vector_search
    assert nested_vector_search[0].id == "0"

    before_payload = store.get("0").payload
    store.update("0")
    after_payload = store.get("0").payload
    assert after_payload == before_payload

    store.delete_col()
    assert store.col_info() is None
    store.delete_col()
    assert "memory" not in store.list_cols()


def test_real_zvec_rejects_unsupported_filter_shapes(tmp_path):
    store = Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path / "zvec"))

    with pytest.raises(ValueError, match="Unsupported logical filter operator"):
        store.search(query="", vectors=[1.0, 0.0, 0.0], limit=5, filters={"$and": [{"user_id": "u1"}]})

    with pytest.raises(ValueError, match="Unsupported filter operator"):
        store.search(query="", vectors=[1.0, 0.0, 0.0], limit=5, filters={"user_id": {"contains": "u"}})

    with pytest.raises(ValueError, match="Unsupported filter field"):
        store.search(query="", vectors=[1.0, 0.0, 0.0], limit=5, filters={"custom_field": "x"})


def test_get_or_create_user_id_with_real_zvec(tmp_path):
    store = Zvec(collection_name="identity", embedding_model_dims=3, path=str(tmp_path / "zvec"))
    user_id = get_or_create_user_id(store)
    assert isinstance(user_id, str)
    assert user_id

    existing = store.get(user_id)
    assert existing is not None
    assert existing.payload.get("user_id") == user_id

    repeated = get_or_create_user_id(store)
    assert repeated == user_id


def test_memory_sync_from_config_and_procedural_memory_with_real_zvec(tmp_path, fixture_embedder):
    config_dict = {
        "vector_store": {
            "provider": "zvec",
            "config": {
                "collection_name": "sync-proc",
                "embedding_model_dims": 3,
                "path": str(tmp_path / "store"),
            },
        },
        "history_db_path": str(tmp_path / "history.db"),
    }
    llm = Mock()
    llm.generate_response.return_value = "Follow concise recovery runbook."

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fixture_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=llm),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = Memory.from_config(config_dict)
        result = memory.add(
            [{"role": "user", "content": "Document the production checklist"}],
            user_id="u-proc",
            agent_id="a-proc",
            memory_type=MemoryType.PROCEDURAL.value,
        )

    memory_id = result["results"][0]["id"]
    fetched = memory.get(memory_id)
    assert fetched["memory"] == "Follow concise recovery runbook."
    assert fetched["metadata"]["memory_type"] == MemoryType.PROCEDURAL.value


@pytest.mark.asyncio
async def test_memory_async_from_config_and_procedural_memory_with_real_zvec(tmp_path, fixture_embedder):
    config_dict = {
        "vector_store": {
            "provider": "zvec",
            "config": {
                "collection_name": "async-proc",
                "embedding_model_dims": 3,
                "path": str(tmp_path / "store"),
            },
        },
        "history_db_path": str(tmp_path / "history.db"),
    }
    llm = Mock()
    llm.generate_response.return_value = "Async procedural guideline."
    fake_langchain_core = types.ModuleType("langchain_core")
    fake_langchain_messages = types.ModuleType("langchain_core.messages")
    fake_langchain_utils = types.ModuleType("langchain_core.messages.utils")
    fake_langchain_utils.convert_to_messages = lambda messages: messages

    with (
        patch.dict(
            sys.modules,
            {
                "langchain_core": fake_langchain_core,
                "langchain_core.messages": fake_langchain_messages,
                "langchain_core.messages.utils": fake_langchain_utils,
            },
        ),
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fixture_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=llm),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = await AsyncMemory.from_config(config_dict)
        result = await memory.add(
            [{"role": "user", "content": "Generate async runbook"}],
            user_id="u-proc",
            agent_id="a-proc",
            memory_type=MemoryType.PROCEDURAL.value,
        )

    memory_id = result["results"][0]["id"]
    fetched = await memory.get(memory_id)
    assert fetched["memory"] == "Async procedural guideline."
    assert fetched["metadata"]["memory_type"] == MemoryType.PROCEDURAL.value


def test_memory_sync_infer_true_update_event_with_real_zvec(tmp_path, fixture_embedder):
    config = _memory_config(tmp_path, collection_name="infer-update")
    llm = Mock()

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fixture_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=llm),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = Memory(config)
        seed_id = memory.add("I like apples", user_id="u-sync", infer=False)["results"][0]["id"]
        llm.generate_response.side_effect = [
            '{"facts": ["I like apples"]}',
            '{"memory": [{"id": "0", "text": "I like apples and bananas", "event": "UPDATE", "old_memory": "I like apples"}]}',
        ]
        result = memory.add("Please refine this preference", user_id="u-sync", infer=True)

    assert result["results"][0]["event"] == "UPDATE"
    assert result["results"][0]["id"] == seed_id
    assert memory.get(seed_id)["memory"] == "I like apples and bananas"


def test_memory_sync_infer_true_delete_event_with_real_zvec(tmp_path, fixture_embedder):
    config = _memory_config(tmp_path, collection_name="infer-delete")
    llm = Mock()

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fixture_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=llm),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = Memory(config)
        seed_id = memory.add("I dislike traffic", user_id="u-sync", infer=False)["results"][0]["id"]
        llm.generate_response.side_effect = [
            '{"facts": ["I dislike traffic"]}',
            '{"memory": [{"id": "0", "text": "I dislike traffic", "event": "DELETE"}]}',
        ]
        result = memory.add("Remove this memory", user_id="u-sync", infer=True)

    assert result["results"][0]["event"] == "DELETE"
    assert result["results"][0]["id"] == seed_id
    assert memory.get(seed_id) is None


def test_memory_sync_infer_true_add_event_with_real_zvec(tmp_path, fixture_embedder):
    config = _memory_config(tmp_path, collection_name="infer-add")
    llm = Mock()

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fixture_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=llm),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = Memory(config)
        llm.generate_response.side_effect = [
            '{"facts": ["I enjoy tea"]}',
            '{"memory": [{"text": "I enjoy tea", "event": "ADD"}]}',
        ]
        result = memory.add("Save this preference", user_id="u-sync", infer=True)

    assert result["results"][0]["event"] == "ADD"
    created_id = result["results"][0]["id"]
    assert memory.get(created_id)["memory"] == "I enjoy tea"


def test_memory_sync_infer_true_none_event_updates_session_ids_with_real_zvec(tmp_path, fixture_embedder):
    config = _memory_config(tmp_path, collection_name="infer-none")
    llm = Mock()

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fixture_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=llm),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = Memory(config)
        seed_id = memory.add("Same fact", user_id="u-sync", infer=False)["results"][0]["id"]
        llm.generate_response.side_effect = [
            '{"facts": ["Same fact"]}',
            '{"memory": [{"id": "0", "text": "Same fact", "event": "NONE"}]}',
        ]
        result = memory.add(
            "No semantic change",
            user_id="u-sync",
            infer=True,
            metadata={"agent_id": "agent-9", "run_id": "run-9"},
        )

    assert result["results"] == []
    fetched = memory.get(seed_id)
    assert fetched["agent_id"] == "agent-9"
    assert fetched["run_id"] == "run-9"


@pytest.mark.asyncio
async def test_memory_async_infer_true_events_with_real_zvec(tmp_path, fixture_embedder):
    config = _memory_config(tmp_path, collection_name="infer-async")
    llm = Mock()

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fixture_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=llm),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = AsyncMemory(config)

        llm.generate_response.side_effect = [
            '{"facts": ["async add"]}',
            '{"memory": [{"text": "async add", "event": "ADD"}]}',
        ]
        add_result = await memory.add("store async", user_id="u-async", infer=True)
        add_id = add_result["results"][0]["id"]
        assert (await memory.get(add_id))["memory"] == "async add"

        llm.generate_response.side_effect = [
            '{"facts": ["async add"]}',
            '{"memory": [{"id": "0", "text": "async updated", "event": "UPDATE", "old_memory": "async add"}]}',
        ]
        update_result = await memory.add("update async", user_id="u-async", infer=True)
        assert update_result["results"][0]["event"] == "UPDATE"
        assert (await memory.get(add_id))["memory"] == "async updated"

        llm.generate_response.side_effect = [
            '{"facts": ["async updated"]}',
            '{"memory": [{"id": "0", "text": "async updated", "event": "NONE"}]}',
        ]
        none_result = await memory.add(
            "noop async",
            user_id="u-async",
            infer=True,
            metadata={"agent_id": "agent-async", "run_id": "run-async"},
        )
        assert none_result["results"] == []
        unchanged = await memory.get(add_id)
        assert unchanged["agent_id"] == "agent-async"
        assert unchanged["run_id"] == "run-async"

        llm.generate_response.side_effect = [
            '{"facts": ["async updated"]}',
            '{"memory": [{"id": "0", "text": "async updated", "event": "DELETE"}]}',
        ]
        delete_result = await memory.add("delete async", user_id="u-async", infer=True)
        assert delete_result["results"][0]["event"] == "DELETE"
        assert await memory.get(add_id) is None
