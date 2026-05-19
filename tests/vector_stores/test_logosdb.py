"""Unit tests for mem0's LogosDB vector store adapter.

These tests mock the underlying logosdb C extension so they run in any
environment without the native binary installed.
"""

import os
import sys
import tempfile
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Minimal fake logosdb C-extension objects
# ---------------------------------------------------------------------------

DIM = 4


def make_vec(*values: float) -> List[float]:
    return list(values)


class _FakeHit:
    def __init__(self, id: int, score: float, text: str = "", timestamp: str = "") -> None:
        self.id = id
        self.score = score
        self.text = text
        self.timestamp = timestamp


class _FakeDB:
    """In-memory substitute for logosdb.DB."""

    def __init__(self, **kwargs: Any) -> None:
        self._store: Dict[int, Dict[str, Any]] = {}
        self._next_id = 0

    def put(self, vec: Any, text: str = "", timestamp: str = "") -> int:
        row_id = self._next_id
        self._next_id += 1
        self._store[row_id] = {"vec": vec, "text": text, "timestamp": timestamp}
        return row_id

    def search(self, query: Any, top_k: int = 5) -> List[_FakeHit]:
        hits = []
        for row_id, data in list(self._store.items())[:top_k]:
            hits.append(
                _FakeHit(id=row_id, score=0.99, text=data["text"], timestamp=data["timestamp"])
            )
        return hits

    def delete(self, row_id: int) -> None:
        self._store.pop(row_id, None)

    def update(self, row_id: int, vec: Any, text: str = "", timestamp: str = "") -> int:
        self.delete(row_id)
        return self.put(vec, text=text, timestamp=timestamp)

    def count(self) -> int:
        return len(self._store)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Inject fake logosdb into sys.modules before the adapter module loads.
# ---------------------------------------------------------------------------

_fake_logosdb = MagicMock()
_fake_logosdb.DB = _FakeDB
_fake_logosdb.DIST_COSINE = 0

# Ensure the real logosdb (if present) does not interfere.
sys.modules.setdefault("logosdb", _fake_logosdb)
sys.modules.setdefault("logosdb._core", _fake_logosdb)

# Now import the adapter — logosdb.DB is already _FakeDB in sys.modules.
import importlib  # noqa: E402
import mem0.vector_stores.logosdb as _logosdb_mod  # noqa: E402

# Patch the module-level names that the adapter uses.
_logosdb_mod.DB = _FakeDB
_logosdb_mod.DIST_COSINE = 0

from mem0.vector_stores.logosdb import LogosDB, OutputData  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path):
    yield LogosDB(
        collection_name="test",
        path=str(tmp_path / "logosdb"),
        embedding_model_dims=DIM,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateCol:
    def test_creates_collection_directory(self, store, tmp_path):
        store.create_col("alpha", vector_size=DIM)
        assert os.path.isdir(os.path.join(str(tmp_path / "logosdb"), "alpha"))

    def test_idempotent(self, store):
        store.create_col("alpha", vector_size=DIM)
        store.create_col("alpha", vector_size=DIM)
        assert "alpha" in store._dbs


class TestInsert:
    def test_insert_single(self, store):
        store.insert("col", vectors=[make_vec(0.1, 0.2, 0.3, 0.4)], ids=["uuid-1"])
        assert "uuid-1" in store._id_maps["col"].values()

    def test_insert_generates_ids_when_none(self, store):
        store.insert("col", vectors=[make_vec(0.1, 0.2, 0.3, 0.4)])
        assert len(store._id_maps["col"]) == 1

    def test_insert_multiple(self, store):
        vecs = [make_vec(float(i), 0.0, 0.0, 0.0) for i in range(5)]
        store.insert("col", vectors=vecs)
        assert len(store._id_maps["col"]) == 5

    def test_payload_text_stored(self, store):
        store.insert(
            "col",
            vectors=[make_vec(0.1, 0.2, 0.3, 0.4)],
            payloads=[{"data": "hello world"}],
            ids=["id-1"],
        )
        db = store._dbs["col"]
        row = list(db._store.values())[0]
        assert row["text"] == "hello world"


class TestSearch:
    def test_returns_output_data(self, store):
        store.insert("col", vectors=[make_vec(1.0, 0.0, 0.0, 0.0)], ids=["id-1"])
        results = store.search("col", query=make_vec(1.0, 0.0, 0.0, 0.0), limit=5)
        assert len(results) == 1
        assert isinstance(results[0], OutputData)
        assert results[0].id == "id-1"

    def test_empty_collection_returns_empty(self, store):
        results = store.search("col", query=make_vec(0.0, 0.0, 0.0, 0.0))
        assert results == []

    def test_limit_respected(self, store):
        vecs = [make_vec(float(i), 0.0, 0.0, 0.0) for i in range(10)]
        store.insert("col", vectors=vecs)
        results = store.search("col", query=make_vec(0.0, 0.0, 0.0, 0.0), limit=3)
        assert len(results) <= 3

    def test_payload_in_results(self, store):
        store.insert(
            "col",
            vectors=[make_vec(1.0, 0.0, 0.0, 0.0)],
            payloads=[{"data": "context text"}],
            ids=["id-1"],
        )
        results = store.search("col", query=make_vec(1.0, 0.0, 0.0, 0.0))
        assert results[0].payload.get("data") == "context text"


class TestDelete:
    def test_delete_existing(self, store):
        store.insert("col", vectors=[make_vec(1.0, 0.0, 0.0, 0.0)], ids=["id-1"])
        store.delete("col", "id-1")
        assert "id-1" not in store._id_maps["col"].values()

    def test_delete_nonexistent_is_noop(self, store):
        store.create_col("col", vector_size=DIM)
        store.delete("col", "ghost-id")


class TestUpdate:
    def test_update_replaces_vector(self, store):
        store.insert("col", vectors=[make_vec(0.1, 0.0, 0.0, 0.0)], ids=["id-1"])
        store.update("col", "id-1", vector=make_vec(0.9, 0.0, 0.0, 0.0), payload={"data": "new"})
        assert "id-1" in store._id_maps["col"].values()

    def test_update_nonexistent_is_noop(self, store):
        store.create_col("col", vector_size=DIM)
        store.update("col", "ghost", vector=make_vec(0.0, 0.0, 0.0, 0.0))


class TestGet:
    def test_get_existing(self, store):
        store.insert("col", vectors=[make_vec(1.0, 0.0, 0.0, 0.0)], ids=["id-1"])
        result = store.get("col", "id-1")
        assert result is not None
        assert result.id == "id-1"

    def test_get_nonexistent_returns_none(self, store):
        store.create_col("col", vector_size=DIM)
        assert store.get("col", "missing") is None


class TestListCols:
    def test_lists_created_collections(self, store):
        store.create_col("alpha", vector_size=DIM)
        store.create_col("beta", vector_size=DIM)
        cols = store.list_cols()
        assert "alpha" in cols
        assert "beta" in cols

    def test_empty_root_returns_empty(self, tmp_path):
        s = LogosDB(path=str(tmp_path / "empty"), embedding_model_dims=DIM)
        assert s.list_cols() == []


class TestDeleteCol:
    def test_removes_from_registry(self, store):
        store.create_col("col", vector_size=DIM)
        store.delete_col("col")
        assert "col" not in store._dbs

    def test_delete_nonexistent_is_noop(self, store):
        store.delete_col("ghost")


class TestColInfo:
    def test_returns_stats(self, store):
        store.insert("col", vectors=[make_vec(1.0, 0.0, 0.0, 0.0)], ids=["id-1"])
        info = store.col_info("col")
        assert info["name"] == "col"
        assert info["count"] == 1
        assert info["dim"] == DIM

    def test_count_reflects_deletes(self, store):
        store.insert("col", vectors=[make_vec(1.0, 0.0, 0.0, 0.0)], ids=["id-1"])
        store.delete("col", "id-1")
        info = store.col_info("col")
        assert info["count"] == 0


class TestReset:
    def test_closes_all_dbs(self, store):
        store.create_col("a", vector_size=DIM)
        store.create_col("b", vector_size=DIM)
        store.reset()
        assert store._dbs == {}
        assert store._id_maps == {}


class TestList:
    def test_returns_nested_list(self, store):
        store.insert("col", vectors=[make_vec(1.0, 0.0, 0.0, 0.0)], ids=["id-1"])
        result = store.list("col")
        assert isinstance(result, list)
        assert isinstance(result[0], list)

    def test_empty_collection_returns_nested_empty(self, store):
        result = store.list("col")
        assert result == [[]]


class TestConfig:
    def test_logosdb_config_defaults(self):
        from mem0.configs.vector_stores.logosdb import LogosDBConfig

        cfg = LogosDBConfig()
        assert cfg.collection_name == "mem0"
        assert cfg.embedding_model_dims == 1536
        assert cfg.distance_metric == "cosine"

    def test_logosdb_config_custom(self):
        from mem0.configs.vector_stores.logosdb import LogosDBConfig

        cfg = LogosDBConfig(
            collection_name="myapp",
            path="/data/myapp",
            embedding_model_dims=1024,
            distance_metric="l2",
        )
        assert cfg.collection_name == "myapp"
        assert cfg.embedding_model_dims == 1024

    def test_logosdb_config_rejects_extra_fields(self):
        from mem0.configs.vector_stores.logosdb import LogosDBConfig

        with pytest.raises(ValueError, match="Extra fields not allowed"):
            LogosDBConfig(unknown_field="bad")
