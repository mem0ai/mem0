"""
Unit tests for mem0.vector_stores.aerospike.AerospikeDB

All Aerospike AVS client calls are mocked — no running Aerospike instance is
required.  Spin up a real AVS (e.g. via Docker) and run end-to-end tests when
you have the service available.

The sys.modules stub at the top must come before any mem0 imports so that the
lazy import inside AerospikeDB.__init__ resolves to the mock without needing
the real aerospike-vector-search package installed.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out aerospike_vector_search BEFORE importing mem0 modules.
# The lazy import inside AerospikeDB.__init__ will pick this up.
# ---------------------------------------------------------------------------
_avs_stub = MagicMock()
_avs_stub.types.VectorDistanceMetric.COSINE = "COSINE"
_avs_stub.types.VectorDistanceMetric.SQUARED_EUCLIDEAN = "SQUARED_EUCLIDEAN"
_avs_stub.types.VectorDistanceMetric.DOT_PRODUCT = "DOT_PRODUCT"
_avs_stub.types.HostPort = MagicMock(return_value=MagicMock())
_avs_stub.types.TLSConfig = MagicMock(return_value=MagicMock())
_avs_stub.types.Credentials = MagicMock(return_value=MagicMock())
sys.modules.setdefault("aerospike_vector_search", _avs_stub)
sys.modules.setdefault("aerospike_vector_search.types", _avs_stub.types)

# Now it is safe to import AerospikeDB.
from mem0.configs.vector_stores.aerospike import AerospikeConfig  # noqa: E402
from mem0.vector_stores.aerospike import AerospikeDB, OutputData, _PAYLOAD_BIN  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_neighbour(key: str, payload: dict, distance: float = 0.1):
    """Build a minimal mock AVS search / neighbour result."""
    rec = MagicMock()
    rec.key.key = key
    rec.bins = {_PAYLOAD_BIN: json.dumps(payload)}
    rec.distance = distance
    return rec


def _make_get_result(key: str, payload: dict):
    """Build a minimal mock AVS get result (no distance attribute)."""
    rec = MagicMock(spec=["key", "bins"])
    rec.key.key = key
    rec.bins = {_PAYLOAD_BIN: json.dumps(payload)}
    return rec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store():
    """Return an AerospikeDB instance whose AVS client is a fresh MagicMock."""
    db = AerospikeDB(
        host="localhost",
        port=5000,
        namespace="mem0",
        set_name="memories",
        index_name="mem0_index",
        embedding_model_dims=4,
        distance_metric="COSINE",
    )
    # Replace the real (mocked) client with a clean mock so __init__ call
    # counts don't bleed into individual tests.
    db.client = MagicMock()
    return db


# ---------------------------------------------------------------------------
# AerospikeConfig
# ---------------------------------------------------------------------------

class TestAerospikeConfig:
    def test_defaults(self):
        cfg = AerospikeConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 5000
        assert cfg.namespace == "mem0"
        assert cfg.distance_metric == "COSINE"
        assert cfg.embedding_model_dims == 1536

    def test_custom_values(self):
        cfg = AerospikeConfig(
            host="avs.example.com",
            port=4000,
            namespace="prod",
            embedding_model_dims=768,
            distance_metric="DOT_PRODUCT",
        )
        assert cfg.host == "avs.example.com"
        assert cfg.embedding_model_dims == 768

    def test_extra_fields_rejected(self):
        with pytest.raises(ValueError, match="Extra fields not allowed"):
            AerospikeConfig(unknown_field="oops")


# ---------------------------------------------------------------------------
# create_col
# ---------------------------------------------------------------------------

class TestCreateCol:
    def test_creates_index(self, store):
        store.create_col(name="new_index", vector_size=4, distance="COSINE")
        store.client.index_create.assert_called_once()
        kw = store.client.index_create.call_args.kwargs
        assert kw["name"] == "new_index"
        assert kw["dimensions"] == 4

    def test_already_exists_is_silent(self, store):
        store.client.index_create.side_effect = Exception("Index already exists")
        store.create_col(name="mem0_index", vector_size=4, distance="COSINE")  # must not raise


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------

class TestInsert:
    def test_upsert_called_for_each_vector(self, store):
        vectors = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]
        payloads = [{"data": "hello", "user_id": "u1"}, {"data": "world", "user_id": "u2"}]
        ids = ["id1", "id2"]

        store.insert(vectors=vectors, payloads=payloads, ids=ids)

        assert store.client.upsert.call_count == 2

    def test_upsert_stores_vector_and_payload_bin(self, store):
        store.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], payloads=[{"data": "test", "user_id": "u1"}], ids=["id1"])

        kw = store.client.upsert.call_args.kwargs
        assert kw["key"] == "id1"
        bins = kw["record_data"]
        assert bins["embedding"] == [0.1, 0.2, 0.3, 0.4]
        assert json.loads(bins[_PAYLOAD_BIN]) == {"data": "test", "user_id": "u1"}


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_returns_output_data(self, store):
        store.client.vector_search.return_value = [
            _make_neighbour("id1", {"data": "hello", "user_id": "u1"}, distance=0.1),
            _make_neighbour("id2", {"data": "world", "user_id": "u2"}, distance=0.3),
        ]

        results = store.search(query="test", vectors=[0.1, 0.2, 0.3, 0.4], top_k=2)

        assert len(results) == 2
        assert results[0].id == "id1"
        assert results[0].payload["data"] == "hello"
        assert results[0].score == pytest.approx(0.9)  # cosine: 1 - 0.1

    def test_vector_search_called_with_correct_args(self, store):
        store.client.vector_search.return_value = []
        query_vec = [0.1, 0.2, 0.3, 0.4]

        store.search(query="q", vectors=query_vec, top_k=5)

        store.client.vector_search.assert_called_once_with(
            namespace="mem0",
            index_name="mem0_index",
            query=query_vec,
            limit=5,
        )

    def test_client_side_filter_applied(self, store):
        store.client.vector_search.return_value = [
            _make_neighbour("id1", {"data": "match", "user_id": "alice"}, distance=0.1),
            _make_neighbour("id2", {"data": "no-match", "user_id": "bob"}, distance=0.2),
        ]

        results = store.search(query="q", vectors=[0.1, 0.2, 0.3, 0.4], filters={"user_id": "alice"})

        assert len(results) == 1
        assert results[0].id == "id1"

    def test_no_filter_returns_all(self, store):
        store.client.vector_search.return_value = [
            _make_neighbour("id1", {"user_id": "alice"}, distance=0.1),
            _make_neighbour("id2", {"user_id": "bob"}, distance=0.2),
        ]

        results = store.search(query="q", vectors=[0.1, 0.2, 0.3, 0.4], filters=None)

        assert len(results) == 2


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_calls_client(self, store):
        store.delete("id1")
        store.client.delete.assert_called_once_with(namespace="mem0", set_name="memories", key="id1")


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_vector_and_payload(self, store):
        store.update("id1", vector=[0.9, 0.8, 0.7, 0.6], payload={"data": "new"})
        kw = store.client.upsert.call_args.kwargs
        assert kw["key"] == "id1"
        bins = kw["record_data"]
        assert bins["embedding"] == [0.9, 0.8, 0.7, 0.6]
        assert json.loads(bins[_PAYLOAD_BIN]) == {"data": "new"}

    def test_update_payload_only(self, store):
        store.update("id1", vector=None, payload={"data": "only_payload"})
        bins = store.client.upsert.call_args.kwargs["record_data"]
        assert "embedding" not in bins
        assert json.loads(bins[_PAYLOAD_BIN]) == {"data": "only_payload"}

    def test_update_vector_only(self, store):
        store.update("id1", vector=[1.0, 0.0, 0.0, 0.0], payload=None)
        bins = store.client.upsert.call_args.kwargs["record_data"]
        assert bins["embedding"] == [1.0, 0.0, 0.0, 0.0]
        assert _PAYLOAD_BIN not in bins

    def test_update_nothing_does_not_call_upsert(self, store):
        store.update("id1", vector=None, payload=None)
        store.client.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing_record(self, store):
        store.client.get.return_value = _make_get_result("id1", {"data": "hello", "user_id": "u1"})

        result = store.get("id1")

        assert isinstance(result, OutputData)
        assert result.id == "id1"
        assert result.payload["data"] == "hello"

    def test_get_missing_record_returns_none(self, store):
        store.client.get.return_value = None
        assert store.get("nonexistent") is None

    def test_get_not_found_exception_returns_none(self, store):
        store.client.get.side_effect = Exception("Key not found")
        assert store.get("nonexistent") is None


# ---------------------------------------------------------------------------
# list_cols / delete_col / col_info
# ---------------------------------------------------------------------------

class TestManagement:
    def test_list_cols_filters_by_namespace(self, store):
        idx1, idx2 = MagicMock(), MagicMock()
        idx1.id.name = "mem0_index"
        idx1.id.namespace = "mem0"
        idx2.id.name = "other_index"
        idx2.id.namespace = "other_ns"
        store.client.index_list.return_value = [idx1, idx2]

        assert store.list_cols() == ["mem0_index"]

    def test_delete_col_calls_index_drop(self, store):
        store.delete_col()
        store.client.index_drop.assert_called_once_with(namespace="mem0", name="mem0_index")

    def test_col_info_returns_index_info(self, store):
        store.client.index_get.return_value = {"name": "mem0_index", "dimensions": 4}
        assert store.col_info()["name"] == "mem0_index"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestList:
    def test_list_returns_nested_list(self, store):
        store.client.vector_search.return_value = [
            _make_neighbour("id1", {"data": "a", "user_id": "u1"}, distance=0.0),
            _make_neighbour("id2", {"data": "b", "user_id": "u2"}, distance=0.0),
        ]

        results = store.list(top_k=10)

        assert isinstance(results, list)
        assert isinstance(results[0], list)
        assert len(results[0]) == 2

    def test_list_applies_filter(self, store):
        store.client.vector_search.return_value = [
            _make_neighbour("id1", {"user_id": "alice"}, distance=0.0),
            _make_neighbour("id2", {"user_id": "bob"}, distance=0.0),
        ]

        results = store.list(filters={"user_id": "alice"}, top_k=10)

        assert len(results[0]) == 1
        assert results[0][0].id == "id1"


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_drops_and_recreates_index(self, store):
        store.reset()
        store.client.index_drop.assert_called_once_with(namespace="mem0", name="mem0_index")
        store.client.index_create.assert_called_once()


# ---------------------------------------------------------------------------
# score conversion
# ---------------------------------------------------------------------------

class TestScoreConversion:
    def test_cosine_score(self, store):
        assert store._score_from_distance(0.0) == pytest.approx(1.0)
        assert store._score_from_distance(1.0) == pytest.approx(0.0)
        assert store._score_from_distance(0.4) == pytest.approx(0.6)

    def test_squared_euclidean_score(self, store):
        store.distance_metric = "SQUARED_EUCLIDEAN"
        assert store._score_from_distance(0.0) == pytest.approx(1.0)
        assert store._score_from_distance(3.0) == pytest.approx(0.25)
