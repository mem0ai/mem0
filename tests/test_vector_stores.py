"""
Unit tests for previously-untested vector store backends:
  - S3Vectors      (mem0/vector_stores/s3_vectors.py)
  - TurbopufferDB  (mem0/vector_stores/turbopuffer.py)
  - UpstashVector  (mem0/vector_stores/upstash_vector.py)
  - ValkeyDB       (mem0/vector_stores/valkey.py)
  - GoogleMatchingEngine (mem0/vector_stores/vertex_ai_vector_search.py)

All external cloud dependencies are mocked via sys.modules stubs so no
credentials or network access are needed.
"""

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# S3Vectors
# ============================================================================


class TestS3Vectors:
    """Tests for the AWS S3 Vectors backend."""

    @pytest.fixture(autouse=True)
    def stub_boto3(self, monkeypatch):
        boto3_stub = MagicMock()
        botocore_mod = ModuleType("botocore")
        botocore_exc = ModuleType("botocore.exceptions")

        class ClientError(Exception):
            def __init__(self, error_response, operation_name=""):
                self.response = error_response
                super().__init__(str(error_response))

        botocore_exc.ClientError = ClientError
        botocore_mod.exceptions = botocore_exc

        monkeypatch.setitem(sys.modules, "boto3", boto3_stub)
        monkeypatch.setitem(sys.modules, "botocore", botocore_mod)
        monkeypatch.setitem(sys.modules, "botocore.exceptions", botocore_exc)
        monkeypatch.delitem(sys.modules, "mem0.vector_stores.s3_vectors", raising=False)

        self.ClientError = ClientError
        self.boto3_stub = boto3_stub
        yield

    def _make_store(self, mock_client=None):
        from mem0.vector_stores.s3_vectors import S3Vectors

        if mock_client is None:
            mock_client = MagicMock()
        mock_client.get_vector_bucket.return_value = {}
        mock_client.get_index.return_value = {}
        self.boto3_stub.client.return_value = mock_client

        store = S3Vectors(
            vector_bucket_name="test-bucket",
            collection_name="test-index",
            embedding_model_dims=3,
        )
        return store, mock_client

    # --- init ---

    def test_init_bucket_already_exists(self):
        store, mock_client = self._make_store()
        mock_client.get_vector_bucket.assert_called_once_with(vectorBucketName="test-bucket")
        mock_client.create_vector_bucket.assert_not_called()

    def test_init_creates_bucket_when_not_found(self):
        from mem0.vector_stores.s3_vectors import S3Vectors

        mock_client = MagicMock()
        mock_client.get_vector_bucket.side_effect = self.ClientError(
            {"Error": {"Code": "NotFoundException"}}
        )
        mock_client.get_index.return_value = {}
        self.boto3_stub.client.return_value = mock_client

        S3Vectors(vector_bucket_name="new-bucket", collection_name="test-index", embedding_model_dims=3)

        mock_client.create_vector_bucket.assert_called_once_with(vectorBucketName="new-bucket")

    def test_init_creates_index_when_not_found(self):
        from mem0.vector_stores.s3_vectors import S3Vectors

        mock_client = MagicMock()
        mock_client.get_vector_bucket.return_value = {}
        mock_client.get_index.side_effect = self.ClientError(
            {"Error": {"Code": "NotFoundException"}}
        )
        self.boto3_stub.client.return_value = mock_client

        S3Vectors(vector_bucket_name="test-bucket", collection_name="new-index", embedding_model_dims=3)

        mock_client.create_index.assert_called_once()
        kw = mock_client.create_index.call_args.kwargs
        assert kw["indexName"] == "new-index"
        assert kw["dimension"] == 3

    def test_init_reraises_unexpected_bucket_error(self):
        from mem0.vector_stores.s3_vectors import S3Vectors

        mock_client = MagicMock()
        mock_client.get_vector_bucket.side_effect = self.ClientError(
            {"Error": {"Code": "AccessDenied"}}
        )
        self.boto3_stub.client.return_value = mock_client

        with pytest.raises(self.ClientError):
            S3Vectors(vector_bucket_name="b", collection_name="idx", embedding_model_dims=3)

    # --- insert ---

    def test_insert_calls_put_vectors(self):
        store, mock_client = self._make_store()
        store.insert(
            vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            payloads=[{"data": "mem1"}, {"data": "mem2"}],
            ids=["id1", "id2"],
        )
        mock_client.put_vectors.assert_called_once()
        kw = mock_client.put_vectors.call_args.kwargs
        assert kw["vectorBucketName"] == "test-bucket"
        assert kw["indexName"] == "test-index"
        vecs = kw["vectors"]
        assert len(vecs) == 2
        assert vecs[0]["key"] == "id1"
        assert vecs[0]["data"] == {"float32": [0.1, 0.2, 0.3]}
        assert vecs[0]["metadata"] == {"data": "mem1"}

    def test_insert_without_payloads(self):
        store, mock_client = self._make_store()
        store.insert(vectors=[[0.1, 0.2, 0.3]], ids=["id1"])
        kw = mock_client.put_vectors.call_args.kwargs
        assert kw["vectors"][0]["metadata"] == {}

    # --- search ---

    def test_search_returns_parsed_results(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {
            "vectors": [
                {"key": "id1", "metadata": {"data": "mem1", "user_id": "u1"}, "distance": 0.2}
            ]
        }
        results = store.search(query="test", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert len(results) == 1
        assert results[0].id == "id1"
        assert abs(results[0].score - 0.8) < 1e-6
        assert results[0].payload["data"] == "mem1"

    def test_search_passes_filters(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {"vectors": []}
        store.search(query="t", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u1"})
        kw = mock_client.query_vectors.call_args.kwargs
        assert kw["filter"] == {"user_id": "u1"}

    def test_search_no_filters_omits_filter_param(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {"vectors": []}
        store.search(query="t", vectors=[0.1, 0.2, 0.3], top_k=5)
        kw = mock_client.query_vectors.call_args.kwargs
        assert "filter" not in kw

    def test_search_parses_json_string_metadata(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {
            "vectors": [{"key": "id1", "metadata": json.dumps({"data": "mem1"}), "distance": 0.0}]
        }
        results = store.search(query="t", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert results[0].payload["data"] == "mem1"

    def test_search_handles_none_distance(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {
            "vectors": [{"key": "id1", "metadata": {}, "distance": None}]
        }
        results = store.search(query="t", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert results[0].score is None

    # --- delete ---

    def test_delete_calls_delete_vectors(self):
        store, mock_client = self._make_store()
        store.delete("id1")
        mock_client.delete_vectors.assert_called_once_with(
            vectorBucketName="test-bucket",
            indexName="test-index",
            keys=["id1"],
        )

    # --- get ---

    def test_get_returns_output_data(self):
        store, mock_client = self._make_store()
        mock_client.get_vectors.return_value = {
            "vectors": [{"key": "id1", "metadata": {"data": "mem1"}, "distance": None}]
        }
        result = store.get("id1")
        assert result is not None
        assert result.id == "id1"
        assert result.payload["data"] == "mem1"

    def test_get_returns_none_when_empty(self):
        store, mock_client = self._make_store()
        mock_client.get_vectors.return_value = {"vectors": []}
        assert store.get("missing") is None

    # --- update ---

    def test_update_with_vector_calls_insert(self):
        store, mock_client = self._make_store()
        store.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "updated"})
        mock_client.put_vectors.assert_called_once()

    def test_update_without_vector_fetches_existing_float32(self):
        store, mock_client = self._make_store()
        # First get_vectors call: get() to check existence
        # Second get_vectors call: fetch raw float32 data
        mock_client.get_vectors.side_effect = [
            {"vectors": [{"key": "id1", "metadata": {"data": "orig"}, "distance": None}]},
            {"vectors": [{"data": {"float32": [0.1, 0.2, 0.3]}, "metadata": {"data": "orig"}}]},
        ]
        store.update("id1", vector=None, payload={"data": "updated"})
        mock_client.put_vectors.assert_called_once()

    def test_update_without_vector_skips_when_not_found(self):
        store, mock_client = self._make_store()
        mock_client.get_vectors.return_value = {"vectors": []}
        store.update("id1", vector=None, payload={"data": "updated"})
        mock_client.put_vectors.assert_not_called()

    # --- list ---

    def test_list_filters_by_payload_field(self):
        store, mock_client = self._make_store()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "vectors": [
                    {"key": "id1", "metadata": {"data": "m1", "user_id": "u1"}, "distance": None},
                    {"key": "id2", "metadata": {"data": "m2", "user_id": "u2"}, "distance": None},
                ]
            }
        ]
        mock_client.get_paginator.return_value = paginator
        results = store.list(filters={"user_id": "u1"})
        assert isinstance(results, list) and isinstance(results[0], list)
        assert len(results[0]) == 1
        assert results[0][0].payload["user_id"] == "u1"

    def test_list_no_filter_returns_all(self):
        store, mock_client = self._make_store()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "vectors": [
                    {"key": "id1", "metadata": {"data": "m1"}, "distance": None},
                    {"key": "id2", "metadata": {"data": "m2"}, "distance": None},
                ]
            }
        ]
        mock_client.get_paginator.return_value = paginator
        results = store.list()
        assert len(results[0]) == 2

    # --- col helpers ---

    def test_list_cols(self):
        store, mock_client = self._make_store()
        mock_client.list_indexes.return_value = {
            "indexes": [{"indexName": "idx1"}, {"indexName": "idx2"}]
        }
        assert store.list_cols() == ["idx1", "idx2"]

    def test_col_info(self):
        store, mock_client = self._make_store()
        mock_client.get_index.return_value = {"index": {"dimension": 3, "status": "ACTIVE"}}
        assert store.col_info() == {"dimension": 3, "status": "ACTIVE"}

    def test_reset_deletes_and_recreates_index(self):
        store, mock_client = self._make_store()
        # After init, make get_index raise NotFoundException so that
        # create_col() inside reset() actually calls create_index.
        mock_client.get_index.side_effect = self.ClientError(
            {"Error": {"Code": "NotFoundException"}}
        )
        store.reset()
        mock_client.delete_index.assert_called_once_with(
            vectorBucketName="test-bucket", indexName="test-index"
        )
        mock_client.create_index.assert_called_once()


# ============================================================================
# TurbopufferDB
# ============================================================================


class TestTurbopufferDB:
    """Tests for the Turbopuffer backend."""

    @pytest.fixture(autouse=True)
    def stub_turbopuffer(self, monkeypatch):
        tpuf_mod = ModuleType("turbopuffer")
        mock_client = MagicMock()
        mock_namespace = MagicMock()
        mock_client.namespace.return_value = mock_namespace
        MockTurbopuffer = MagicMock(return_value=mock_client)
        tpuf_mod.Turbopuffer = MockTurbopuffer

        monkeypatch.setitem(sys.modules, "turbopuffer", tpuf_mod)
        monkeypatch.delitem(sys.modules, "mem0.vector_stores.turbopuffer", raising=False)

        self.mock_client = mock_client
        self.mock_namespace = mock_namespace
        self.MockTurbopuffer = MockTurbopuffer
        yield

    def _make_store(self, **kwargs):
        from mem0.vector_stores.turbopuffer import TurbopufferDB

        return TurbopufferDB(
            collection_name="test-ns",
            embedding_model_dims=3,
            api_key="test-key",
            **kwargs,
        )

    # --- init ---

    def test_init_creates_client_and_namespace(self):
        store = self._make_store()
        self.MockTurbopuffer.assert_called_once()
        self.mock_client.namespace.assert_called_once_with("test-ns")

    def test_init_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("TURBOPUFFER_API_KEY", raising=False)
        from mem0.vector_stores.turbopuffer import TurbopufferDB

        with pytest.raises(ValueError, match="API key"):
            TurbopufferDB(collection_name="ns", embedding_model_dims=3)

    # --- insert ---

    def test_insert_sends_correct_rows(self):
        store = self._make_store()
        store.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"data": "mem1", "user_id": "u1"}],
            ids=["id1"],
        )
        self.mock_namespace.write.assert_called_once()
        kw = self.mock_namespace.write.call_args.kwargs
        rows = kw["upsert_rows"]
        assert rows[0]["id"] == "id1"
        assert rows[0]["vector"] == [0.1, 0.2, 0.3]
        assert rows[0]["data"] == "mem1"

    def test_insert_auto_generates_ids(self):
        store = self._make_store()
        store.insert(vectors=[[0.1, 0.2, 0.3]], payloads=[{"data": "m"}])
        kw = self.mock_namespace.write.call_args.kwargs
        assert kw["upsert_rows"][0]["id"] == "0"

    def test_insert_respects_batch_size(self):
        from mem0.vector_stores.turbopuffer import TurbopufferDB

        store = TurbopufferDB(
            collection_name="ns", embedding_model_dims=3, api_key="k", batch_size=2
        )
        store.insert(
            vectors=[[0.1, 0.2, 0.3]] * 5,
            payloads=[{"data": f"m{i}"} for i in range(5)],
            ids=[f"id{i}" for i in range(5)],
        )
        assert self.mock_namespace.write.call_count == 3  # ceil(5/2)

    # --- search ---

    def test_search_returns_parsed_results(self):
        store = self._make_store()
        row = MagicMock()
        row.model_dump.return_value = {"id": "id1", "data": "mem1", "$dist": 0.3, "vector": None}
        self.mock_namespace.query.return_value = MagicMock(rows=[row])

        results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert len(results) == 1
        assert results[0].id == "id1"
        assert abs(results[0].score - 0.7) < 1e-6
        assert results[0].payload["data"] == "mem1"

    def test_search_passes_eq_filter(self):
        store = self._make_store()
        self.mock_namespace.query.return_value = MagicMock(rows=[])
        store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u1"})
        kw = self.mock_namespace.query.call_args.kwargs
        assert kw["filters"] == ("user_id", "Eq", "u1")

    def test_search_no_filter_omits_filters_param(self):
        store = self._make_store()
        self.mock_namespace.query.return_value = MagicMock(rows=[])
        store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5)
        kw = self.mock_namespace.query.call_args.kwargs
        assert "filters" not in kw

    # --- delete / update ---

    def test_delete(self):
        store = self._make_store()
        store.delete("id1")
        self.mock_namespace.write.assert_called_once_with(deletes=["id1"])

    def test_update_with_vector_uses_upsert(self):
        store = self._make_store()
        store.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "updated"})
        kw = self.mock_namespace.write.call_args.kwargs
        assert "upsert_rows" in kw
        assert kw["upsert_rows"][0]["id"] == "id1"
        assert kw["upsert_rows"][0]["vector"] == [0.1, 0.2, 0.3]

    def test_update_payload_only_uses_patch(self):
        store = self._make_store()
        store.update("id1", vector=None, payload={"data": "updated"})
        kw = self.mock_namespace.write.call_args.kwargs
        assert "patch_rows" in kw
        assert kw["patch_rows"][0]["id"] == "id1"

    # --- get ---

    def test_get_found(self):
        store = self._make_store()
        row = MagicMock()
        row.model_dump.return_value = {"id": "id1", "data": "mem1", "$dist": 0.0, "vector": None}
        self.mock_namespace.query.return_value = MagicMock(rows=[row])
        result = store.get("id1")
        assert result is not None
        assert result.id == "id1"

    def test_get_not_found_returns_none(self):
        store = self._make_store()
        self.mock_namespace.query.return_value = MagicMock(rows=[])
        result = store.get("missing")
        assert result is None

    # --- list ---

    def test_list_wraps_results_in_outer_list(self):
        store = self._make_store()
        row = MagicMock()
        row.model_dump.return_value = {"id": "id1", "data": "m", "$dist": 0.1, "vector": None}
        self.mock_namespace.query.return_value = MagicMock(rows=[row])
        results = store.list(top_k=10)
        assert isinstance(results, list) and isinstance(results[0], list)
        assert len(results[0]) == 1

    def test_list_returns_empty_on_error(self):
        store = self._make_store()
        self.mock_namespace.query.side_effect = Exception("network error")
        results = store.list()
        assert results == [[]]

    # --- _convert_filters ---

    def test_convert_filters_none_returns_none(self):
        store = self._make_store()
        assert store._convert_filters(None) is None

    def test_convert_filters_empty_returns_none(self):
        store = self._make_store()
        assert store._convert_filters({}) is None

    def test_convert_filters_single_eq(self):
        store = self._make_store()
        assert store._convert_filters({"user_id": "u1"}) == ("user_id", "Eq", "u1")

    def test_convert_filters_multiple_uses_and(self):
        store = self._make_store()
        result = store._convert_filters({"user_id": "u1", "agent_id": "a1"})
        assert result[0] == "And"
        assert len(result[1]) == 2

    def test_convert_filters_gte_lte(self):
        store = self._make_store()
        result = store._convert_filters({"score": {"gte": 0.5, "lte": 0.9}})
        assert result[0] == "And"
        assert ("score", "Gte", 0.5) in result[1]
        assert ("score", "Lte", 0.9) in result[1]

    # --- col helpers ---

    def test_col_info(self):
        store = self._make_store()
        meta = MagicMock()
        meta.approx_row_count = 42
        meta.approx_logical_bytes = 1024
        meta.created_at = "2025-01-01"
        meta.updated_at = "2025-06-01"
        self.mock_namespace.metadata.return_value = meta
        info = store.col_info()
        assert info["name"] == "test-ns"
        assert info["approx_row_count"] == 42

    def test_col_info_on_error_returns_name_only(self):
        store = self._make_store()
        self.mock_namespace.metadata.side_effect = Exception("unavailable")
        info = store.col_info()
        assert info == {"name": "test-ns"}

    def test_reset_calls_delete_all(self):
        store = self._make_store()
        store.reset()
        self.mock_namespace.delete_all.assert_called_once()

    def test_create_col_is_noop(self):
        store = self._make_store()
        store.create_col(name="new", vector_size=3, distance="cosine")
        self.mock_namespace.write.assert_not_called()

    def test_count(self):
        store = self._make_store()
        meta = MagicMock()
        meta.approx_row_count = 7
        self.mock_namespace.metadata.return_value = meta
        assert store.count() == 7

    def test_count_returns_zero_on_error(self):
        store = self._make_store()
        self.mock_namespace.metadata.side_effect = Exception("err")
        assert store.count() == 0


# ============================================================================
# UpstashVector
# ============================================================================


class TestUpstashVector:
    """Tests for the Upstash Vector backend."""

    @pytest.fixture(autouse=True)
    def stub_upstash(self, monkeypatch):
        upstash_mod = ModuleType("upstash_vector")
        MockIndex = MagicMock()
        upstash_mod.Index = MockIndex
        monkeypatch.setitem(sys.modules, "upstash_vector", upstash_mod)
        monkeypatch.delitem(sys.modules, "mem0.vector_stores.upstash_vector", raising=False)
        self.MockIndex = MockIndex
        yield

    def _make_store(self, enable_embeddings=False):
        from mem0.vector_stores.upstash_vector import UpstashVector

        mock_client = MagicMock()
        store = UpstashVector(
            collection_name="test-ns",
            client=mock_client,
            enable_embeddings=enable_embeddings,
        )
        return store, mock_client

    # --- init ---

    def test_init_with_url_and_token(self):
        from mem0.vector_stores.upstash_vector import UpstashVector

        mock_idx = MagicMock()
        self.MockIndex.return_value = mock_idx
        store = UpstashVector(collection_name="ns", url="https://x.upstash.io", token="tok")
        self.MockIndex.assert_called_once_with("https://x.upstash.io", "tok")
        assert store.client == mock_idx

    def test_init_raises_without_credentials(self):
        from mem0.vector_stores.upstash_vector import UpstashVector

        with pytest.raises(ValueError, match="client or URL and token"):
            UpstashVector(collection_name="ns")

    # --- insert ---

    def test_insert_vector_mode(self):
        store, mock_client = self._make_store(enable_embeddings=False)
        store.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"data": "mem1"}],
            ids=["id1"],
        )
        mock_client.upsert.assert_called_once()
        kw = mock_client.upsert.call_args.kwargs
        assert kw["namespace"] == "test-ns"
        v = kw["vectors"][0]
        assert v["id"] == "id1"
        assert v["vector"] == [0.1, 0.2, 0.3]
        assert v["metadata"] == {"data": "mem1"}

    def test_insert_embedding_mode_uses_data_field(self):
        store, mock_client = self._make_store(enable_embeddings=True)
        store.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"data": "mem1"}],
            ids=["id1"],
        )
        kw = mock_client.upsert.call_args.kwargs
        assert kw["vectors"][0]["data"] == "mem1"
        assert "vector" not in kw["vectors"][0]

    def test_insert_embedding_mode_raises_without_data(self):
        store, _ = self._make_store(enable_embeddings=True)
        with pytest.raises(ValueError, match="data"):
            store.insert(
                vectors=[[0.1, 0.2, 0.3]],
                payloads=[{"no_data_field": "x"}],
                ids=["id1"],
            )

    # --- search ---

    def test_search_vector_mode(self):
        store, mock_client = self._make_store(enable_embeddings=False)
        res = MagicMock()
        res.id, res.score, res.metadata = "id1", 0.9, {"data": "mem1"}
        mock_client.query_many.return_value = [[res]]
        results = store.search(query="q", vectors=[[0.1, 0.2, 0.3]], top_k=5)
        assert len(results) == 1
        assert results[0].id == "id1"
        assert results[0].score == 0.9

    def test_search_embedding_mode(self):
        store, mock_client = self._make_store(enable_embeddings=True)
        res = MagicMock()
        res.id, res.score, res.metadata = "id1", 0.8, {"data": "mem1"}
        mock_client.query.return_value = [res]
        results = store.search(query="mem1", vectors=[[0.1, 0.2, 0.3]], top_k=5)
        mock_client.query.assert_called_once()
        assert results[0].score == 0.8

    def test_search_applies_filter_string(self):
        store, mock_client = self._make_store(enable_embeddings=False)
        mock_client.query_many.return_value = [[]]
        store.search(query="q", vectors=[[0.1]], top_k=5, filters={"user_id": "u1"})
        kw = mock_client.query_many.call_args.kwargs
        assert kw["queries"][0]["filter"] == 'user_id = "u1"'

    # --- keyword_search ---

    def test_keyword_search_returns_results(self):
        store, mock_client = self._make_store()
        res = MagicMock()
        res.id, res.score, res.metadata = "id1", 0.8, {"data": "mem1"}
        mock_client.query.return_value = [res]
        results = store.keyword_search(query="mem1", top_k=5)
        assert results[0].id == "id1"

    def test_keyword_search_returns_none_on_error(self):
        store, mock_client = self._make_store()
        mock_client.query.side_effect = Exception("BM25 not available")
        assert store.keyword_search("q") is None

    # --- delete / update / get ---

    def test_delete(self):
        store, mock_client = self._make_store()
        store.delete("id1")
        mock_client.delete.assert_called_once_with(ids=["id1"], namespace="test-ns")

    def test_update(self):
        store, mock_client = self._make_store()
        store.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "updated"})
        mock_client.update.assert_called_once_with(
            id="id1",
            vector=[0.1, 0.2, 0.3],
            data="updated",
            metadata={"data": "updated"},
            namespace="test-ns",
        )

    def test_get_found(self):
        store, mock_client = self._make_store()
        vec = MagicMock()
        vec.id, vec.metadata = "id1", {"data": "mem1"}
        mock_client.fetch.return_value = [vec]
        result = store.get("id1")
        assert result.id == "id1"
        assert result.payload == {"data": "mem1"}
        assert result.score is None

    def test_get_empty_response_returns_none(self):
        store, mock_client = self._make_store()
        mock_client.fetch.return_value = []
        assert store.get("missing") is None

    def test_get_null_vector_returns_none(self):
        store, mock_client = self._make_store()
        mock_client.fetch.return_value = [None]
        assert store.get("id1") is None

    # --- list ---

    def test_list_returns_empty_for_zero_vectors(self):
        store, mock_client = self._make_store()
        info = MagicMock()
        info.namespaces = {}
        mock_client.info.return_value = info
        assert store.list() == [[]]

    def test_list_namespace_empty_vector_count(self):
        store, mock_client = self._make_store()
        ns_info = MagicMock()
        ns_info.vector_count = 0
        info = MagicMock()
        info.namespaces = {"test-ns": ns_info}
        mock_client.info.return_value = info
        assert store.list() == [[]]

    # --- _stringify ---

    def test_stringify_wraps_strings_in_quotes(self):
        store, _ = self._make_store()
        assert store._stringify("hello") == '"hello"'

    def test_stringify_passes_numbers_through(self):
        store, _ = self._make_store()
        assert store._stringify(42) == 42

    # --- col helpers ---

    def test_list_cols(self):
        store, mock_client = self._make_store()
        mock_client.list_namespaces.return_value = ["ns1", "ns2"]
        assert store.list_cols() == ["ns1", "ns2"]

    def test_delete_col_resets_namespace(self):
        store, mock_client = self._make_store()
        store.delete_col()
        mock_client.reset.assert_called_once_with(namespace="test-ns")

    def test_col_info_returns_client_info(self):
        store, mock_client = self._make_store()
        sentinel = object()
        mock_client.info.return_value = sentinel
        assert store.col_info() is sentinel

    def test_create_col_is_noop(self):
        store, mock_client = self._make_store()
        store.create_col("ns", 3, "cosine")
        mock_client.upsert.assert_not_called()


# ============================================================================
# ValkeyDB
# ============================================================================


class TestValkeyDB:
    """Tests for the Valkey vector store backend."""

    @pytest.fixture(autouse=True)
    def stub_valkey(self, monkeypatch):
        valkey_mod = ModuleType("valkey")
        valkey_exc = ModuleType("valkey.exceptions")
        valkey_cluster = ModuleType("valkey.cluster")

        class ResponseError(Exception):
            pass

        valkey_exc.ResponseError = ResponseError
        valkey_mod.exceptions = valkey_exc
        valkey_mod.ResponseError = ResponseError

        mock_client = MagicMock()
        valkey_mod.from_url = MagicMock(return_value=mock_client)

        # numpy stub
        numpy_mod = ModuleType("numpy")
        arr_mock = MagicMock()
        arr_mock.tobytes.return_value = b"\x00" * 12
        numpy_mod.array = MagicMock(return_value=arr_mock)
        numpy_mod.float32 = float

        # pytz stub
        pytz_mod = ModuleType("pytz")
        tz_mock = MagicMock()
        pytz_mod.timezone = MagicMock(return_value=tz_mock)
        pytz_mod.UTC = tz_mock

        for key, mod in [
            ("valkey", valkey_mod),
            ("valkey.exceptions", valkey_exc),
            ("valkey.cluster", valkey_cluster),
            ("numpy", numpy_mod),
            ("pytz", pytz_mod),
        ]:
            monkeypatch.setitem(sys.modules, key, mod)

        monkeypatch.delitem(sys.modules, "mem0.vector_stores.valkey", raising=False)

        self.ResponseError = ResponseError
        self.mock_client = mock_client
        yield

    def _make_store(self, index_type="hnsw"):
        # configure: FT._LIST OK; ft().info() raises "not found" → index gets created
        mock_client = self.mock_client
        mock_client.execute_command = MagicMock(return_value=[])
        mock_ft = MagicMock()
        mock_ft.info.side_effect = self.ResponseError("index not found")
        mock_client.ft.return_value = mock_ft

        from mem0.vector_stores.valkey import ValkeyDB

        return ValkeyDB(
            valkey_url="valkey://localhost:6379",
            collection_name="test-idx",
            embedding_model_dims=3,
            index_type=index_type,
        )

    # --- init ---

    def test_init_creates_index_when_not_found(self):
        store = self._make_store()
        # FT._LIST + FT.CREATE must both be called
        calls = [c.args[0] for c in self.mock_client.execute_command.call_args_list]
        assert "FT._LIST" in calls
        assert "FT.CREATE" in calls

    def test_init_skips_creation_when_index_exists(self):
        mock_client = self.mock_client
        mock_client.execute_command = MagicMock(return_value=[])
        mock_ft = MagicMock()
        mock_ft.info.return_value = {"num_docs": 0}  # index exists → no ResponseError
        mock_client.ft.return_value = mock_ft

        from mem0.vector_stores.valkey import ValkeyDB

        ValkeyDB(valkey_url="valkey://localhost", collection_name="idx", embedding_model_dims=3)
        calls = [c.args[0] for c in mock_client.execute_command.call_args_list]
        assert "FT.CREATE" not in calls

    def test_init_raises_for_invalid_index_type(self):
        mock_client = self.mock_client
        mock_client.execute_command = MagicMock(return_value=[])
        mock_client.ft.return_value = MagicMock(info=MagicMock(side_effect=self.ResponseError("not found")))

        from mem0.vector_stores.valkey import ValkeyDB

        with pytest.raises(ValueError, match="Invalid index_type"):
            ValkeyDB(valkey_url="valkey://localhost", collection_name="idx",
                     embedding_model_dims=3, index_type="bad")

    def test_init_raises_when_search_module_unavailable(self):
        mock_client = self.mock_client
        mock_client.execute_command.side_effect = self.ResponseError("unknown command `FT._LIST`")

        from mem0.vector_stores.valkey import ValkeyDB

        with pytest.raises(ValueError, match="search module"):
            ValkeyDB(valkey_url="valkey://localhost", collection_name="idx", embedding_model_dims=3)

    # --- _escape_tag_value (pure function) ---

    def test_escape_tag_value_plain(self):
        from mem0.vector_stores.valkey import ValkeyDB

        assert ValkeyDB._escape_tag_value("hello") == "hello"

    def test_escape_tag_value_email(self):
        from mem0.vector_stores.valkey import ValkeyDB

        escaped = ValkeyDB._escape_tag_value("user@example.com")
        assert r"\@" in escaped
        assert r"\." in escaped

    def test_escape_tag_value_space(self):
        from mem0.vector_stores.valkey import ValkeyDB

        escaped = ValkeyDB._escape_tag_value("foo bar")
        assert r"\ " in escaped

    def test_escape_tag_value_numeric(self):
        from mem0.vector_stores.valkey import ValkeyDB

        assert ValkeyDB._escape_tag_value(42) == "42"

    # --- _build_search_query (pure method) ---

    def test_build_search_query_no_filters(self):
        store = self._make_store()
        q = store._build_search_query("[KNN 5 @embedding $vec AS score]", filters=None)
        assert q == "*=>[KNN 5 @embedding $vec AS score]"

    def test_build_search_query_with_user_id(self):
        store = self._make_store()
        q = store._build_search_query("[KNN 5 @embedding $vec AS score]", filters={"user_id": "u1"})
        assert "@user_id:{u1}" in q
        assert "=>[KNN" in q

    def test_build_search_query_none_value_ignored(self):
        store = self._make_store()
        q = store._build_search_query("[KNN 5 @embedding $vec AS score]", filters={"user_id": None})
        assert q == "*=>[KNN 5 @embedding $vec AS score]"

    def test_build_search_query_multiple_filters(self):
        store = self._make_store()
        q = store._build_search_query(
            "[KNN 5 @embedding $vec AS score]",
            filters={"user_id": "u1", "agent_id": "a1"},
        )
        assert "@user_id:{u1}" in q
        assert "@agent_id:{a1}" in q

    # --- _build_index_schema (pure method) ---

    def test_build_index_schema_hnsw_contains_ef_construction(self):
        store = self._make_store(index_type="hnsw")
        cmd = store._build_index_schema("idx", 3, "COSINE", "mem0:idx")
        assert "HNSW" in cmd
        assert "EF_CONSTRUCTION" in cmd
        assert "EF_RUNTIME" in cmd

    def test_build_index_schema_flat_omits_ef_params(self):
        store = self._make_store(index_type="flat")
        cmd = store._build_index_schema("idx", 3, "COSINE", "mem0:idx")
        assert "FLAT" in cmd
        assert "EF_CONSTRUCTION" not in cmd

    def test_build_index_schema_flat_invalid_raises(self):
        store = self._make_store()
        # Temporarily set an invalid index_type to exercise the else branch
        store.index_type = "unknown"
        with pytest.raises(ValueError, match="Unsupported index_type"):
            store._build_index_schema("idx", 3, "COSINE", "mem0:idx")

    # --- simple client-call methods ---

    def test_delete(self):
        store = self._make_store()
        store.delete("id1")
        self.mock_client.delete.assert_called_with("mem0:test-idx:id1")

    def test_list_cols(self):
        store = self._make_store()
        self.mock_client.execute_command.return_value = ["idx1", "idx2"]
        cols = store.list_cols()
        assert "idx1" in cols or "idx2" in cols

    def test_delete_col_calls_ft_dropindex(self):
        store = self._make_store()
        self.mock_client.execute_command.reset_mock()
        self.mock_client.execute_command.return_value = "OK"
        store.delete_col()
        drop_calls = [
            c for c in self.mock_client.execute_command.call_args_list
            if c.args and c.args[0] == "FT.DROPINDEX"
        ]
        assert len(drop_calls) == 1

    def test_col_info(self):
        store = self._make_store()
        mock_ft = MagicMock()
        mock_ft.info.return_value = {"num_docs": 42}
        self.mock_client.ft.return_value = mock_ft
        assert store.col_info() == {"num_docs": 42}


# ============================================================================
# GoogleMatchingEngine (Vertex AI Vector Search)
# ============================================================================


class TestGoogleMatchingEngine:
    """Tests for the Google Vertex AI Matching Engine backend."""

    @pytest.fixture(autouse=True)
    def stub_google(self, monkeypatch):
        # --- exception classes ---
        class GoogleAPIError(Exception):
            pass

        class NotFound(GoogleAPIError):
            pass

        class PermissionDenied(GoogleAPIError):
            pass

        class InvalidArgument(GoogleAPIError):
            pass

        # --- build module stubs ---
        google_mod = ModuleType("google")
        google_cloud_mod = ModuleType("google.cloud")
        aiplatform_mod = ModuleType("google.cloud.aiplatform")
        aiplatform_v1_mod = ModuleType("google.cloud.aiplatform_v1")
        google_api_core_mod = ModuleType("google.api_core")
        google_api_core_exc_mod = ModuleType("google.api_core.exceptions")
        google_oauth2_mod = ModuleType("google.oauth2")
        service_account_mod = ModuleType("google.oauth2.service_account")

        google_api_core_exc_mod.GoogleAPIError = GoogleAPIError
        google_api_core_exc_mod.NotFound = NotFound
        google_api_core_exc_mod.PermissionDenied = PermissionDenied
        google_api_core_exc_mod.InvalidArgument = InvalidArgument
        google_api_core_mod.exceptions = google_api_core_exc_mod

        # aiplatform_v1 types
        aiplatform_v1_types_mod = ModuleType("google.cloud.aiplatform_v1.types")
        aiplatform_v1_types_index_mod = ModuleType("google.cloud.aiplatform_v1.types.index")
        mock_datapoint_cls = MagicMock()
        aiplatform_v1_types_index_mod.IndexDatapoint = mock_datapoint_cls
        aiplatform_v1_types_mod.index = aiplatform_v1_types_index_mod
        aiplatform_v1_mod.types = aiplatform_v1_types_mod
        aiplatform_v1_mod.MatchServiceClient = MagicMock()
        aiplatform_v1_mod.IndexDatapoint = mock_datapoint_cls
        aiplatform_v1_mod.FindNeighborsRequest = MagicMock()

        # matching_engine Namespace
        me_mod = ModuleType("google.cloud.aiplatform.matching_engine")
        me_ep_mod = ModuleType(
            "google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint"
        )

        class Namespace:
            def __init__(self, name, allow_list, deny_list):
                self.name = name
                self.allow_list = allow_list
                self.deny_list = deny_list

        me_ep_mod.Namespace = Namespace
        me_mod.matching_engine_index_endpoint = me_ep_mod

        # langchain
        langchain_core_mod = ModuleType("langchain_core")
        langchain_docs_mod = ModuleType("langchain_core.documents")

        class Document:
            def __init__(self, page_content="", metadata=None):
                self.page_content = page_content
                self.metadata = metadata or {}

        langchain_docs_mod.Document = Document
        langchain_core_mod.documents = langchain_docs_mod

        # mock index / endpoint returned by aiplatform
        mock_index = MagicMock()
        mock_endpoint = MagicMock()
        aiplatform_mod.init = MagicMock()
        aiplatform_mod.MatchingEngineIndex = MagicMock(return_value=mock_index)
        aiplatform_mod.MatchingEngineIndexEndpoint = MagicMock(return_value=mock_endpoint)

        # Wire parent attributes explicitly — Python only sets these during a
        # fresh import, not when stubs are pre-placed in sys.modules.
        google_mod.api_core = google_api_core_mod
        google_mod.cloud = google_cloud_mod
        google_api_core_mod.exceptions = google_api_core_exc_mod
        google_cloud_mod.aiplatform = aiplatform_mod
        google_cloud_mod.aiplatform_v1 = aiplatform_v1_mod
        aiplatform_v1_mod.types = aiplatform_v1_types_mod
        aiplatform_v1_types_mod.index = aiplatform_v1_types_index_mod
        google_oauth2_mod.service_account = service_account_mod
        langchain_core_mod.documents = langchain_docs_mod

        for key, mod in [
            ("google", google_mod),
            ("google.cloud", google_cloud_mod),
            ("google.cloud.aiplatform", aiplatform_mod),
            ("google.cloud.aiplatform_v1", aiplatform_v1_mod),
            ("google.cloud.aiplatform_v1.types", aiplatform_v1_types_mod),
            ("google.cloud.aiplatform_v1.types.index", aiplatform_v1_types_index_mod),
            ("google.cloud.aiplatform.matching_engine", me_mod),
            (
                "google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint",
                me_ep_mod,
            ),
            ("google.api_core", google_api_core_mod),
            ("google.api_core.exceptions", google_api_core_exc_mod),
            ("google.oauth2", google_oauth2_mod),
            ("google.oauth2.service_account", service_account_mod),
            ("langchain_core", langchain_core_mod),
            ("langchain_core.documents", langchain_docs_mod),
        ]:
            monkeypatch.setitem(sys.modules, key, mod)

        monkeypatch.delitem(sys.modules, "mem0.vector_stores.vertex_ai_vector_search", raising=False)
        monkeypatch.delitem(
            sys.modules, "mem0.configs.vector_stores.vertex_ai_vector_search", raising=False
        )

        self.mock_index = mock_index
        self.mock_endpoint = mock_endpoint
        self.GoogleAPIError = GoogleAPIError
        self.NotFound = NotFound
        self.PermissionDenied = PermissionDenied
        self.InvalidArgument = InvalidArgument
        yield

    def _make_store(self):
        # Stub the pydantic config so we don't need the real one installed
        config_mod = ModuleType("mem0.configs.vector_stores.vertex_ai_vector_search")

        class GoogleMatchingEngineConfig:
            def __init__(self, **kwargs):
                self.project_id = kwargs.get("project_id", "proj")
                self.project_number = kwargs.get("project_number", "123")
                self.region = kwargs.get("region", "us-central1")
                self.endpoint_id = kwargs.get("endpoint_id", "ep-123")
                self.index_id = kwargs.get("index_id", "idx-123")
                self.deployment_index_id = kwargs.get(
                    "deployment_index_id", kwargs.get("collection_name", "dep-idx")
                )
                self.collection_name = kwargs.get("collection_name", "dep-idx")
                self.vector_search_api_endpoint = kwargs.get(
                    "vector_search_api_endpoint", "api.endpoint"
                )

            def model_dump(self):
                return {}

        config_mod.GoogleMatchingEngineConfig = GoogleMatchingEngineConfig
        sys.modules["mem0.configs.vector_stores.vertex_ai_vector_search"] = config_mod
        sys.modules.pop("mem0.vector_stores.vertex_ai_vector_search", None)

        from mem0.vector_stores.vertex_ai_vector_search import GoogleMatchingEngine

        return GoogleMatchingEngine(
            project_id="proj",
            project_number="123",
            region="us-central1",
            endpoint_id="ep-123",
            index_id="idx-123",
            collection_name="dep-idx",
            vector_search_api_endpoint="api.endpoint",
        )

    # --- init ---

    def test_init_sets_attributes(self):
        store = self._make_store()
        assert store.project_id == "proj"
        assert store.collection_name == "dep-idx"
        assert store.index_id == "idx-123"

    def test_init_calls_aiplatform_init(self):
        import google.cloud.aiplatform as aip

        self._make_store()
        aip.init.assert_called_once()

    # --- insert ---

    def test_insert_calls_upsert_datapoints(self):
        store = self._make_store()
        store.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"data": "mem1", "user_id": "u1"}],
            ids=["id1"],
        )
        self.mock_index.upsert_datapoints.assert_called_once()

    def test_insert_empty_raises(self):
        store = self._make_store()
        with pytest.raises(ValueError, match="No vectors"):
            store.insert(vectors=[], payloads=[], ids=[])

    def test_insert_mismatched_payloads_raises(self):
        store = self._make_store()
        with pytest.raises(ValueError, match="payloads"):
            store.insert(
                vectors=[[0.1], [0.2]],
                payloads=[{"data": "m1"}],
                ids=["id1", "id2"],
            )

    def test_insert_mismatched_ids_raises(self):
        store = self._make_store()
        with pytest.raises(ValueError, match="ids"):
            store.insert(
                vectors=[[0.1], [0.2]],
                payloads=[{"data": "m1"}, {"data": "m2"}],
                ids=["id1"],
            )

    # --- delete ---

    def test_delete_single_id_returns_true(self):
        store = self._make_store()
        assert store.delete("id1") is True
        self.mock_index.remove_datapoints.assert_called_once_with(datapoint_ids=["id1"])

    def test_delete_list_of_ids(self):
        store = self._make_store()
        assert store.delete(ids=["id1", "id2"]) is True
        self.mock_index.remove_datapoints.assert_called_once_with(datapoint_ids=["id1", "id2"])

    def test_delete_no_id_provided_returns_false(self):
        # The ValueError is raised inside the outer try/except Exception block
        # so the method catches it and returns False instead of propagating.
        store = self._make_store()
        assert store.delete() is False

    def test_delete_already_gone_returns_true(self):
        store = self._make_store()
        self.mock_index.remove_datapoints.side_effect = self.NotFound()
        assert store.delete("id1") is True

    def test_delete_permission_denied_returns_false(self):
        store = self._make_store()
        self.mock_index.remove_datapoints.side_effect = self.PermissionDenied()
        assert store.delete("id1") is False

    def test_delete_invalid_argument_returns_false(self):
        store = self._make_store()
        self.mock_index.remove_datapoints.side_effect = self.InvalidArgument()
        assert store.delete("id1") is False

    # --- update ---

    def test_update_calls_upsert_when_found(self):
        store = self._make_store()
        # get() returns a found result
        store.get = MagicMock(return_value=MagicMock(id="id1"))
        result = store.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "up"})
        assert result is True
        self.mock_index.upsert_datapoints.assert_called_once()

    def test_update_returns_false_when_not_found(self):
        store = self._make_store()
        store.get = MagicMock(return_value=None)
        assert store.update("missing", vector=[0.1], payload={"data": "x"}) is False

    def test_update_raises_without_vector_or_payload(self):
        store = self._make_store()
        with pytest.raises(ValueError, match="Either vector or payload"):
            store.update("id1", vector=None, payload=None)

    # --- keyword_search ---

    def test_keyword_search_returns_none(self):
        store = self._make_store()
        assert store.keyword_search("query") is None

    # --- col helpers ---

    def test_col_info_returns_config_fields(self):
        store = self._make_store()
        info = store.col_info()
        assert info["project_id"] == "proj"
        assert info["index_id"] == "idx-123"
        assert info["endpoint_id"] == "ep-123"

    def test_list_cols_returns_deployment_id(self):
        store = self._make_store()
        assert store.list_cols() == ["dep-idx"]

    def test_delete_col_is_noop(self):
        store = self._make_store()
        store.delete_col()
        self.mock_index.remove_datapoints.assert_not_called()

    def test_reset_is_noop(self):
        store = self._make_store()
        store.reset()
        self.mock_index.remove_datapoints.assert_not_called()

    def test_create_col_is_noop(self):
        store = self._make_store()
        store.create_col(name="x", vector_size=3, distance="cosine")
        self.mock_index.upsert_datapoints.assert_not_called()

    # --- search / _parse_output ---

    def test_search_returns_empty_when_no_neighbors(self):
        store = self._make_store()
        self.mock_endpoint.find_neighbors.return_value = []
        results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert results == []

    def test_search_parses_neighbors(self):
        store = self._make_store()
        neighbor = MagicMock()
        neighbor.id = "id1"
        neighbor.distance = 0.3
        restrict = MagicMock()
        restrict.name = "user_id"
        restrict.allow_tokens = ["u1"]
        neighbor.restricts = [restrict]
        self.mock_endpoint.find_neighbors.return_value = [[neighbor]]
        results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert len(results) == 1
        assert results[0].id == "id1"
        assert abs(results[0].score - 0.7) < 1e-6
        assert results[0].payload.get("user_id") == "u1"
