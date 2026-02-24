import importlib
import importlib.metadata
import os
import sys
import types
from dataclasses import dataclass
from typing import Any, Dict, Optional
from unittest.mock import Mock, patch

import pytest


def _build_fake_zvec_module() -> tuple[types.ModuleType, dict[str, Any]]:
    state: dict[str, Any] = {"collections": {}, "create_calls": [], "open_calls": []}

    class DataType:
        STRING = "STRING"
        VECTOR_FP32 = "VECTOR_FP32"

    class MetricType:
        COSINE = "COSINE"

    class FlatIndexParam:
        def __init__(self, metric_type=None):
            self.metric_type = metric_type

    class FieldSchema:
        def __init__(self, name, data_type, nullable=False, index_param=None):
            self.name = name
            self.data_type = data_type
            self.nullable = nullable
            self.index_param = index_param

    class VectorSchema:
        def __init__(self, name, data_type, dimension=0, index_param=None):
            self.name = name
            self.data_type = data_type
            self.dimension = dimension
            self.index_param = index_param

    class CollectionSchema:
        def __init__(self, name, fields=None, vectors=None):
            self.name = name
            self.fields = fields or []
            self.vectors = vectors or []

    class CollectionOption:
        def __init__(self, read_only=False, enable_mmap=True):
            self.read_only = read_only
            self.enable_mmap = enable_mmap

    @dataclass
    class VectorQuery:
        field_name: str
        vector: Any = None

    class Doc:
        def __init__(self, id: str, score: Optional[float] = None, fields=None, vectors=None):
            self.id = id
            self.score = score
            self.fields = fields or {}
            self.vectors = vectors or {}

    def _parse_literal(raw: str):
        raw = raw.strip()
        if raw.startswith("'") and raw.endswith("'"):
            value = raw[1:-1]
            return value.replace("\\'", "'").replace("\\\\", "\\")
        if raw == "true":
            return True
        if raw == "false":
            return False
        if raw == "null":
            return None
        try:
            if "." in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            return raw

    def _maybe_numeric(value):
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                if "." in value:
                    return float(value)
                return int(value)
            except ValueError:
                return value
        return value

    def _matches_filter(fields: Dict[str, Any], filter_expression: Optional[str]) -> bool:
        if not filter_expression:
            return True

        for condition in filter_expression.split(" and "):
            condition = condition.strip()
            operators = [" not in ", " in ", ">=", "<=", "!=", "=", ">", "<"]

            key = None
            operator = None
            rhs = None
            for candidate in operators:
                if candidate in condition:
                    key, rhs = condition.split(candidate, 1)
                    key = key.strip()
                    operator = candidate.strip()
                    rhs = rhs.strip()
                    break

            if operator is None or key is None:
                raise ValueError(f"Unsupported filter expression in test fake: {condition}")

            lhs_value = fields.get(key)
            lhs_numeric = _maybe_numeric(lhs_value)

            if operator in {"in", "not in"}:
                if not (rhs.startswith("(") and rhs.endswith(")")):
                    return False
                values_raw = rhs[1:-1].strip()
                values = []
                if values_raw:
                    values = [_parse_literal(v.strip()) for v in values_raw.split(",")]
                if operator == "in" and lhs_value not in values:
                    return False
                if operator == "not in" and lhs_value in values:
                    return False
                continue

            rhs_value = _parse_literal(rhs)
            rhs_numeric = _maybe_numeric(rhs_value)

            if operator == "=" and lhs_value != rhs_value:
                return False
            if operator == "!=" and lhs_value == rhs_value:
                return False
            if operator == ">" and not (lhs_numeric > rhs_numeric):
                return False
            if operator == ">=" and not (lhs_numeric >= rhs_numeric):
                return False
            if operator == "<" and not (lhs_numeric < rhs_numeric):
                return False
            if operator == "<=" and not (lhs_numeric <= rhs_numeric):
                return False

        return True

    class Collection:
        def __init__(self, path: str, schema=None, option=None):
            self.path = path
            self.schema = schema
            self.option = option
            self.docs: Dict[str, Doc] = {}
            self.destroy_called = False
            self.last_query = {}

        @property
        def stats(self):
            return {"doc_count": len(self.docs)}

        def upsert(self, docs):
            docs = docs if isinstance(docs, list) else [docs]
            for doc in docs:
                self.docs[doc.id] = Doc(id=doc.id, fields=dict(doc.fields), vectors=dict(doc.vectors), score=doc.score)
            return []

        def update(self, docs):
            docs = docs if isinstance(docs, list) else [docs]
            for doc in docs:
                existing = self.docs.get(doc.id, Doc(id=doc.id))
                if doc.fields:
                    existing.fields.update(doc.fields)
                if doc.vectors:
                    existing.vectors.update(doc.vectors)
                self.docs[doc.id] = existing
            return []

        def delete(self, ids):
            ids = [ids] if isinstance(ids, str) else ids
            for doc_id in ids:
                self.docs.pop(doc_id, None)
            return []

        def fetch(self, ids):
            ids = [ids] if isinstance(ids, str) else ids
            return {doc_id: self.docs[doc_id] for doc_id in ids if doc_id in self.docs}

        def query(self, vectors=None, topk=10, filter=None, include_vector=False):  # noqa: A002, ARG002
            self.last_query = {"vectors": vectors, "topk": topk, "filter": filter}
            result = [doc for doc in self.docs.values() if _matches_filter(doc.fields, filter)]

            if vectors is not None and getattr(vectors, "vector", None) is not None:
                query_vec = vectors.vector
                for doc in result:
                    vector = doc.vectors.get(vectors.field_name, [])
                    score = 0.0
                    if vector and query_vec:
                        score = float(sum(a * b for a, b in zip(query_vec, vector)))
                    doc.score = score
                result.sort(key=lambda item: item.score if item.score is not None else 0.0, reverse=True)

            return result[:topk]

        def destroy(self):
            self.destroy_called = True
            self.docs = {}
            state["collections"].pop(self.path, None)
            if os.path.isdir(self.path):
                os.rmdir(self.path)

    def create_and_open(path, schema, option):
        os.makedirs(path, exist_ok=True)
        collection = Collection(path=path, schema=schema, option=option)
        state["collections"][path] = collection
        state["create_calls"].append(path)
        return collection

    def open_collection(path, option):
        state["open_calls"].append(path)
        if path not in state["collections"]:
            raise RuntimeError("collection path does not exist")
        collection = state["collections"][path]
        collection.option = option
        return collection

    module = types.ModuleType("zvec")
    module.Collection = Collection
    module.CollectionOption = CollectionOption
    module.CollectionSchema = CollectionSchema
    module.DataType = DataType
    module.Doc = Doc
    module.FieldSchema = FieldSchema
    module.FlatIndexParam = FlatIndexParam
    module.MetricType = MetricType
    module.VectorQuery = VectorQuery
    module.VectorSchema = VectorSchema
    module.create_and_open = create_and_open
    module.open = open_collection
    return module, state


@pytest.fixture()
def zvec_backend(monkeypatch):
    fake_module, fake_state = _build_fake_zvec_module()
    monkeypatch.setitem(sys.modules, "zvec", fake_module)
    monkeypatch.setattr(importlib.metadata, "version", lambda _: "0.0.0")
    fake_posthog = types.ModuleType("posthog")

    class _Posthog:
        def __init__(self, *args, **kwargs):  # noqa: D401, ANN002, ANN003
            pass

        def capture(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return None

    fake_posthog.Posthog = _Posthog
    monkeypatch.setitem(sys.modules, "posthog", fake_posthog)
    fake_qdrant = types.ModuleType("qdrant_client")

    class _QdrantClient:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            pass

    fake_qdrant.QdrantClient = _QdrantClient
    monkeypatch.setitem(sys.modules, "qdrant_client", fake_qdrant)

    for module_name in ("mem0.vector_stores.zvec",):
        if module_name in sys.modules:
            del sys.modules[module_name]

    zvec_store = importlib.import_module("mem0.vector_stores.zvec")
    return zvec_store, fake_state


def test_init_create_and_open_path_behavior(zvec_backend, tmp_path):
    zvec_store, state = zvec_backend

    zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))
    assert len(state["create_calls"]) == 1
    assert len(state["open_calls"]) == 0

    zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))
    assert len(state["create_calls"]) == 1
    assert len(state["open_calls"]) == 1


def test_create_col_falls_back_to_open_when_create_fails(zvec_backend, tmp_path):
    zvec_store, state = zvec_backend
    store = zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))

    os.rmdir(store.collection_path)
    state["open_calls"].clear()

    with patch.object(zvec_store, "create_and_open", side_effect=RuntimeError("boom")):
        store.create_col(vector_size=3, on_disk=True)

    assert state["open_calls"] == [store.collection_path]


def test_insert_search_get_update_delete_list_reset(zvec_backend, tmp_path):
    zvec_store, state = zvec_backend
    store = zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))

    vectors = [[1.0, 0.0, 0.0], [0.8, 0.1, 0.1]]
    payloads = [
        {"data": "loves cats", "user_id": "u1", "topic": "pets"},
        {"data": "likes tea", "user_id": "u2", "topic": "drinks"},
    ]
    ids = ["id1", "id2"]
    store.insert(vectors=vectors, payloads=payloads, ids=ids)

    search_results = store.search(query="cats", vectors=[1.0, 0.0, 0.0], limit=2, filters={"user_id": "u1"})
    assert len(search_results) == 1
    assert search_results[0].id == "id1"
    assert search_results[0].payload["topic"] == "pets"
    assert search_results[0].score is not None

    fetched = store.get("id1")
    assert fetched is not None
    assert fetched.payload["data"] == "loves cats"
    assert fetched.payload["topic"] == "pets"

    store.update("id1", payload={"data": "loves cats and coffee", "user_id": "u1", "topic": "pets"})
    updated = store.get("id1")
    assert updated is not None
    assert updated.payload["data"] == "loves cats and coffee"

    listed = store.list(limit=10)
    assert isinstance(listed, list)
    assert isinstance(listed[0], list)
    assert len(listed[0]) == 2

    store.delete("id2")
    assert store.get("id2") is None

    old_create_calls = len(state["create_calls"])
    store.reset()
    assert len(state["create_calls"]) == old_create_calls + 1
    assert store.list(limit=10) == [[]]


def test_filter_translation_eq_range_multi_condition(zvec_backend, tmp_path):
    zvec_store, _ = zvec_backend
    store = zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))

    filter_string = store._translate_filters(
        {
            "user_id": "u1",
            "created_at": {"gte": "2024-01-01", "lte": "2024-12-31"},
            "run_id": {"ne": "run-x"},
        }
    )

    assert "user_id = 'u1'" in filter_string
    assert "created_at >= '2024-01-01'" in filter_string
    assert "created_at <= '2024-12-31'" in filter_string
    assert "run_id != 'run-x'" in filter_string


def test_filter_translation_in_and_nin(zvec_backend, tmp_path):
    zvec_store, _ = zvec_backend
    store = zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))

    filter_string = store._translate_filters({"user_id": {"in": ["u1", "u2"]}, "agent_id": {"nin": ["a1"]}})

    assert "user_id in ('u1', 'u2')" in filter_string
    assert "agent_id not in ('a1')" in filter_string


def test_filter_translation_all_supported_operators(zvec_backend, tmp_path):
    zvec_store, _ = zvec_backend
    store = zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))

    filter_string = store._translate_filters(
        {
            "user_id": {"eq": "u1"},
            "agent_id": {"ne": "agent-x"},
            "created_at": {"gt": 1, "gte": 2, "lt": 9, "lte": 10},
            "run_id": {"in": ["r1", "r2"]},
            "actor_id": {"nin": ["bot"]},
        }
    )

    assert "user_id = 'u1'" in filter_string
    assert "agent_id != 'agent-x'" in filter_string
    assert "created_at > 1" in filter_string
    assert "created_at >= 2" in filter_string
    assert "created_at < 9" in filter_string
    assert "created_at <= 10" in filter_string
    assert "run_id in ('r1', 'r2')" in filter_string
    assert "actor_id not in ('bot')" in filter_string


@pytest.mark.parametrize(
    ("filters", "expected_ids"),
    [
        ({"user_id": {"eq": "u2"}}, {"id2"}),
        ({"user_id": {"ne": "u2"}}, {"id1", "id3"}),
        ({"created_at": {"gt": 1}}, {"id2", "id3"}),
        ({"created_at": {"gte": 2}}, {"id2", "id3"}),
        ({"created_at": {"lt": 3}}, {"id1", "id2"}),
        ({"created_at": {"lte": 1}}, {"id1"}),
        ({"user_id": {"in": ["u1", "u3"]}}, {"id1", "id3"}),
        ({"user_id": {"nin": ["u1", "u3"]}}, {"id2"}),
    ],
)
def test_search_with_each_supported_filter_operator(zvec_backend, tmp_path, filters, expected_ids):
    zvec_store, _ = zvec_backend
    store = zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))
    store.insert(
        vectors=[[1.0, 0.0, 0.0], [0.8, 0.1, 0.0], [0.7, 0.2, 0.1]],
        payloads=[
            {"data": "d1", "user_id": "u1", "created_at": "1"},
            {"data": "d2", "user_id": "u2", "created_at": "2"},
            {"data": "d3", "user_id": "u3", "created_at": "3"},
        ],
        ids=["id1", "id2", "id3"],
    )

    results = store.search(query="", vectors=[1.0, 0.0, 0.0], limit=10, filters=filters)
    assert {doc.id for doc in results} == expected_ids


def test_translate_filters_none_and_empty(zvec_backend, tmp_path):
    zvec_store, _ = zvec_backend
    store = zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))

    assert store._translate_filters(None) is None
    assert store._translate_filters({}) is None


def test_unsupported_filter_raises(zvec_backend, tmp_path):
    zvec_store, _ = zvec_backend
    store = zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))

    with pytest.raises(ValueError, match="Unsupported filter field"):
        store._translate_filters({"custom_key": "value"})

    with pytest.raises(ValueError, match="Unsupported filter operator"):
        store._translate_filters({"user_id": {"contains": "abc"}})

    with pytest.raises(ValueError, match="AND filters only"):
        store._translate_filters({"$or": [{"user_id": "u1"}, {"user_id": "u2"}]})

    with pytest.raises(ValueError, match="AND filters only"):
        store._translate_filters({"$not": [{"user_id": "u1"}]})

    with pytest.raises(ValueError, match="expects a non-empty list"):
        store._translate_filters({"user_id": {"in": []}})

    with pytest.raises(ValueError, match="expects a non-empty list"):
        store._translate_filters({"user_id": {"nin": "u1"}})


def test_payload_round_trip_uses_metadata_json_envelope(zvec_backend, tmp_path):
    zvec_store, state = zvec_backend
    store = zvec_store.Zvec(collection_name="memory", embedding_model_dims=3, path=str(tmp_path))

    payload = {
        "data": "prefers concise answers",
        "hash": "abc123",
        "user_id": "u1",
        "custom_number": 7,
        "custom_bool": True,
        "custom_nested": {"a": 1},
    }
    store.insert(vectors=[[0.2, 0.3, 0.4]], payloads=[payload], ids=["id1"])

    fake_collection = state["collections"][store.collection_path]
    stored_doc = fake_collection.docs["id1"]
    assert "metadata_json" in stored_doc.fields
    assert "custom_number" not in stored_doc.fields

    fetched = store.get("id1")
    assert fetched is not None
    assert fetched.payload["data"] == "prefers concise answers"
    assert fetched.payload["hash"] == "abc123"
    assert fetched.payload["custom_number"] == 7
    assert fetched.payload["custom_bool"] is True
    assert fetched.payload["custom_nested"] == {"a": 1}


def test_memory_smoke_sync_zvec(zvec_backend, tmp_path):
    from mem0.configs.base import MemoryConfig
    from mem0.memory.main import Memory
    from mem0.vector_stores.configs import VectorStoreConfig

    config = MemoryConfig(
        vector_store=VectorStoreConfig(
            provider="zvec",
            config={
                "collection_name": "mem0",
                "embedding_model_dims": 3,
                "path": str(tmp_path),
            },
        )
    )

    fake_embedder = Mock()
    fake_embedder.embed.return_value = [1.0, 0.0, 0.0]

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fake_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=Mock()),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = Memory(config)
        add_result = memory.add([{"role": "user", "content": "I like cats"}], user_id="u1", infer=False)
        assert add_result["results"]
        assert add_result["results"][0]["event"] == "ADD"

        listed_raw = memory.vector_store.list(filters={"user_id": "u1"}, limit=10)
        assert isinstance(listed_raw, list)
        assert isinstance(listed_raw[0], list)

        search_result = memory.search("cats", user_id="u1")
        assert search_result["results"]

        all_result = memory.get_all(user_id="u1")
        assert all_result["results"]

        delete_all_result = memory.delete_all(user_id="u1")
        assert delete_all_result["message"] == "Memories deleted successfully!"
        assert memory.get_all(user_id="u1")["results"] == []


@pytest.mark.asyncio
async def test_memory_smoke_async_zvec(zvec_backend, tmp_path):
    from mem0.configs.base import MemoryConfig
    from mem0.memory.main import AsyncMemory
    from mem0.vector_stores.configs import VectorStoreConfig

    config = MemoryConfig(
        vector_store=VectorStoreConfig(
            provider="zvec",
            config={
                "collection_name": "mem0",
                "embedding_model_dims": 3,
                "path": str(tmp_path),
            },
        )
    )

    fake_embedder = Mock()
    fake_embedder.embed.return_value = [1.0, 0.0, 0.0]

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=fake_embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=Mock()),
        patch("mem0.memory.main.capture_event"),
    ):
        memory = AsyncMemory(config)
        add_result = await memory.add([{"role": "user", "content": "I like tea"}], user_id="u2", infer=False)
        assert add_result["results"]
        assert add_result["results"][0]["event"] == "ADD"

        listed_raw = memory.vector_store.list(filters={"user_id": "u2"}, limit=10)
        assert isinstance(listed_raw, list)
        assert isinstance(listed_raw[0], list)

        search_result = await memory.search("tea", user_id="u2")
        assert search_result["results"]

        all_result = await memory.get_all(user_id="u2")
        assert all_result["results"]

        delete_all_result = await memory.delete_all(user_id="u2")
        assert delete_all_result["message"] == "Memories deleted successfully!"
        assert (await memory.get_all(user_id="u2"))["results"] == []
