import logging
import os
import sys

import pytest
from dotenv import load_dotenv
from pydantic import ValidationError

from mem0.configs.vector_stores.neptune import NeptuneAnalyticsConfig
from mem0.utils.factory import VectorStoreFactory
from mem0.vector_stores.neptune_analytics import (
    NeptuneAnalyticsVector,
    _escape_cypher,
    _validate_filter,
)

load_dotenv()

# Configure logging
logging.getLogger("mem0.vector.neptune.main").setLevel(logging.INFO)
logging.getLogger("mem0.vector.neptune.base").setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

logging.basicConfig(
    format="%(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

# Test constants
EMBEDDING_MODEL_DIMS = 1024
VECTOR_1 = [-0.1] * EMBEDDING_MODEL_DIMS
VECTOR_2 = [-0.2] * EMBEDDING_MODEL_DIMS
VECTOR_3 = [-0.3] * EMBEDDING_MODEL_DIMS

SAMPLE_PAYLOADS = [
    {"test_text": "text_value", "another_field": "field_2_value"},
    {"test_text": "text_value_BBBB"},
    {"test_text": "text_value_CCCC"}
]


@pytest.mark.skipif(not os.getenv("RUN_TEST_NEPTUNE_ANALYTICS"), reason="Only run with RUN_TEST_NEPTUNE_ANALYTICS is true")
class TestNeptuneAnalyticsOperations:
    """Test basic CRUD operations."""

    @pytest.fixture
    def na_instance(self):
        """Create Neptune Analytics vector store instance for testing."""
        config = {
            "endpoint": f"neptune-graph://{os.getenv('GRAPH_ID')}",
            "collection_name": "test",
        }
        return VectorStoreFactory.create("neptune", config)


    def test_insert_and_list(self, na_instance):
        """Test vector insertion and listing."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )
        
        list_result = na_instance.list()[0]
        assert len(list_result) == 3
        assert "label" not in list_result[0].payload


    def test_get(self, na_instance):
        """Test retrieving a specific vector."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1],
            ids=["A"],
            payloads=[SAMPLE_PAYLOADS[0]]
        )
        
        vector_a = na_instance.get("A")
        assert vector_a.id == "A"
        assert vector_a.score is None
        assert vector_a.payload["test_text"] == "text_value"
        assert vector_a.payload["another_field"] == "field_2_value"
        assert "label" not in vector_a.payload


    def test_update(self, na_instance):
        """Test updating vector payload."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1],
            ids=["A"],
            payloads=[SAMPLE_PAYLOADS[0]]
        )
        
        na_instance.update(vector_id="A", payload={"updated_payload_str": "update_str"})
        vector_a = na_instance.get("A")
        
        assert vector_a.id == "A"
        assert vector_a.score is None
        assert vector_a.payload["updated_payload_str"] == "update_str"
        assert "label" not in vector_a.payload


    def test_delete(self, na_instance):
        """Test deleting a specific vector."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1],
            ids=["A"],
            payloads=[SAMPLE_PAYLOADS[0]]
        )
        
        size_before = na_instance.list()[0]
        assert len(size_before) == 1
        
        na_instance.delete("A")
        size_after = na_instance.list()[0]
        assert len(size_after) == 0


    def test_search(self, na_instance):
        """Test vector similarity search."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )
        
        result = na_instance.search(query="", vectors=VECTOR_1, top_k=1)
        assert len(result) == 1
        assert "label" not in result[0].payload


    def test_reset(self, na_instance):
        """Test resetting the collection."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )

        list_result = na_instance.list()[0]
        assert len(list_result) == 3

        na_instance.reset()
        list_result = na_instance.list()[0]
        assert len(list_result) == 0


    def test_delete_col(self, na_instance):
        """Test deleting the entire collection."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )

        list_result = na_instance.list()[0]
        assert len(list_result) == 3

        na_instance.delete_col()
        list_result = na_instance.list()[0]
        assert len(list_result) == 0


    def test_list_cols(self, na_instance):
        """Test listing collections."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )

        result = na_instance.list_cols()
        assert result == ["MEM0_VECTOR_test"]


    def test_invalid_endpoint_format(self):
        """Test that invalid endpoint format raises ValueError."""
        config = {
            "endpoint": f"xxx://{os.getenv('GRAPH_ID')}",
            "collection_name": "test",
        }

        with pytest.raises(ValueError):
            VectorStoreFactory.create("neptune", config)


class TestNeptuneFilterValidation:
    def test_filter_rejects_dict_value(self):
        with pytest.raises(ValueError):
            _validate_filter("user_id", {"$ne": ""})

    def test_filter_rejects_list_value(self):
        with pytest.raises(ValueError):
            _validate_filter("user_id", ["alice"])

    def test_filter_rejects_invalid_key(self):
        with pytest.raises(ValueError):
            _validate_filter("user_id'; DROP", "alice")

    def test_filter_accepts_scalars(self):
        _validate_filter("user_id", "alice")
        _validate_filter("count", 42)
        _validate_filter("label", "MEM0_VECTOR_test")

    def test_escape_cypher_quotes(self):
        assert _escape_cypher("alice") == "alice"
        assert _escape_cypher("it's") == "it\\'s"
        assert _escape_cypher("a\\b") == "a\\\\b"

    def test_where_clause_escapes_values(self):
        clause = NeptuneAnalyticsVector._get_where_clause(
            {"user_id": "it's a test"}
        )
        assert "it\\'s a test" in clause

    def test_where_clause_rejects_dict(self):
        with pytest.raises(ValueError):
            NeptuneAnalyticsVector._get_where_clause(
                {"user_id": {"$ne": ""}}
            )

    def test_node_filter_escapes_values(self):
        clause = NeptuneAnalyticsVector._get_node_filter_clause(
            {"label": "it's"}
        )
        assert "it\\'s" in clause

    def test_node_filter_rejects_dict(self):
        with pytest.raises(ValueError):
            NeptuneAnalyticsVector._get_node_filter_clause(
                {"user_id": {"$ne": ""}}
            )

INJECTION_PAYLOADS = [
    "memories; DROP TABLE users; --",
    "memories` OR 1=1; --",
    "memories:Label {prop: 'val'}) DELETE n; --",
    "valid_name OR 1=1",
    "1_starts_with_digit",
    "has space",
    "",
]

class TestNeptuneAnalyticsConfigCollectionNameValidation:
    def test_accepts_valid_identifier(self):
        config = NeptuneAnalyticsConfig(collection_name="valid_name")
        assert config.collection_name == "valid_name"

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_rejects_injection_payload(self, payload):
        with pytest.raises(ValidationError, match="Invalid collection_name"):
            NeptuneAnalyticsConfig(collection_name=payload)

class TestNeptuneAnalyticsVectorInitValidation:
    def test_accepts_valid_identifier(self, monkeypatch):
        from mem0.vector_stores.neptune_analytics import NeptuneAnalyticsVector
        monkeypatch.setattr("mem0.vector_stores.neptune_analytics.NeptuneAnalyticsGraph", lambda *args, **kwargs: None)
        
        vec = NeptuneAnalyticsVector(
            endpoint="neptune-graph://test",
            collection_name="valid_name"
        )
        assert vec.collection_name.endswith("valid_name")

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_rejects_injection_payload_in_init(self, payload, monkeypatch):
        from mem0.vector_stores.neptune_analytics import NeptuneAnalyticsVector
        monkeypatch.setattr("mem0.vector_stores.neptune_analytics.NeptuneAnalyticsGraph", lambda *args, **kwargs: None)

        with pytest.raises(ValueError, match="Invalid collection_name"):
            NeptuneAnalyticsVector(
                endpoint="neptune-graph://test",
                collection_name=payload
            )


class _FakeNeptuneGraph:
    """Minimal stand-in for `NeptuneAnalyticsGraph.query()` so update()'s compensation
    path can be exercised without a real Neptune Analytics endpoint."""

    def __init__(self):
        self.nodes = {}
        self.fail_next_upsert = False
        self.soft_fail_next_upsert = False
        self.get_call_count = 0

    def query(self, query_string, params=None):
        params = params or {}

        if "UNWIND $rows" in query_string:
            rows = params["rows"]
            if "CALL neptune.algo.vectors.upsert" in query_string:
                return [{"success": True} for _ in rows]
            for row in rows:
                self.nodes[row["node_id"]] = dict(row["properties"])
            return []

        if "CALL neptune.algo.vectors.upsert" in query_string:
            if self.fail_next_upsert:
                self.fail_next_upsert = False
                raise RuntimeError("simulated Neptune upsert failure")
            if self.soft_fail_next_upsert:
                self.soft_fail_next_upsert = False
                return [{"success": False}]
            return [{"success": True}]

        if "SET n = $properties" in query_string:
            self.nodes[params["vector_id"]] = dict(params["properties"])
            return []

        if "RETURN n" in query_string and "node_id" in params:
            self.get_call_count += 1
            vector_id = params["node_id"]
            if vector_id not in self.nodes:
                return []
            return [{"n": {"~id": vector_id, "~properties": dict(self.nodes[vector_id])}}]

        if "DETACH DELETE n" in query_string:
            self.nodes.pop(params.get("node_id"), None)
            return []

        return []


class TestNeptuneAnalyticsUpdateRollback:
    """update() must not leave a payload committed against a stale embedding when the
    vector upsert step fails. See the compensation logic in `NeptuneAnalyticsVector.update()`."""

    def _make_vec(self, monkeypatch):
        monkeypatch.setattr("mem0.vector_stores.neptune_analytics.NeptuneAnalyticsGraph", lambda *args, **kwargs: None)
        vec = NeptuneAnalyticsVector(endpoint="neptune-graph://test", collection_name="rollback")
        vec.graph = _FakeNeptuneGraph()
        return vec

    def test_restores_prior_payload_when_upsert_fails(self, monkeypatch):
        vec = self._make_vec(monkeypatch)
        vec.insert(vectors=[[0.1, 0.2]], ids=["A"], payloads=[{"data": "alpha", "user_id": "u1"}])

        vec.graph.fail_next_upsert = True
        with pytest.raises(RuntimeError):
            vec.update("A", vector=[0.9, 0.9], payload={"data": "beta", "user_id": "u1"})

        restored = vec.get("A")
        assert restored.payload["data"] == "alpha"
        assert restored.payload["user_id"] == "u1"

    def test_does_not_snapshot_prior_state_for_a_vector_only_update(self, monkeypatch):
        """Only a combined payload+vector update can desync -- a vector-only update has
        nothing to roll back to, so it must skip the extra get() snapshot entirely."""
        vec = self._make_vec(monkeypatch)
        vec.insert(vectors=[[0.1, 0.2]], ids=["A"], payloads=[{"data": "alpha", "user_id": "u1"}])

        vec.graph.fail_next_upsert = True
        calls_before = vec.graph.get_call_count
        with pytest.raises(RuntimeError):
            vec.update("A", vector=[0.9, 0.9])

        assert vec.graph.get_call_count == calls_before

    def test_succeeds_normally_when_upsert_does_not_fail(self, monkeypatch):
        vec = self._make_vec(monkeypatch)
        vec.insert(vectors=[[0.1, 0.2]], ids=["A"], payloads=[{"data": "alpha", "user_id": "u1"}])

        vec.update("A", vector=[0.9, 0.9], payload={"data": "beta", "user_id": "u1"})

        updated = vec.get("A")
        assert updated.payload["data"] == "beta"

    def test_rolls_back_on_soft_upsert_failure(self, monkeypatch):
        """A soft {"success": False} row desyncs the payload from the embedding just as much as a
        thrown error, so update() must treat it as a failure and roll the payload back too."""
        vec = self._make_vec(monkeypatch)
        vec.insert(vectors=[[0.1, 0.2]], ids=["A"], payloads=[{"data": "alpha", "user_id": "u1"}])

        vec.graph.soft_fail_next_upsert = True
        with pytest.raises(RuntimeError):
            vec.update("A", vector=[0.9, 0.9], payload={"data": "beta", "user_id": "u1"})

        restored = vec.get("A")
        assert restored.payload["data"] == "alpha"
        assert restored.payload["user_id"] == "u1"
